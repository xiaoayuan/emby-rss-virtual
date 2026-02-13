import os
from datetime import datetime
from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates

from .config import load_config
from .library import scan_media_files, match_titles_to_files
from .generator import rebuild_rule_dir
from .scheduler import start_scheduler, apply_schedule, scheduler
from .rss import fetch_source_titles
from .emby import refresh_emby
from .db import (
    init_db,
    list_sources,
    create_source,
    toggle_source,
    delete_source,
    list_rules,
    create_rule,
    toggle_rule,
    delete_rule,
    get_setting,
    set_setting,
    append_run_log,
    list_run_logs,
)

app = FastAPI(title="Emby RSS Virtual Libraries")
templates = Jinja2Templates(directory="app/templates")

MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/media")
VIRTUAL_ROOT = os.getenv("VIRTUAL_ROOT", "/virtual")

state = {
    "last_run": None,
    "last_result": [],
    "last_emby_refresh": None,
    "last_source_test": None,
    "last_rule_preview": None,
}


PRESET_SOURCES = {
    # TMDB provider IDs (常用): Netflix=8, Disney+=337, AppleTV+=350, Max/HBO=1899(示例，按地区可能不同)
    "netflix": {
        "name": "Netflix 榜单(TMDB)",
        "kind": "tmdb",
        "rss_url": "media=tv&region=US&provider=8&limit=30",
        "platform": "Netflix",
    },
    "hbo": {
        "name": "HBO/Max 榜单(TMDB)",
        "kind": "tmdb",
        "rss_url": "media=tv&region=US&provider=1899&limit=30",
        "platform": "HBO/Max",
    },
    "disney": {
        "name": "Disney+ 榜单(TMDB)",
        "kind": "tmdb",
        "rss_url": "media=tv&region=US&provider=337&limit=30",
        "platform": "Disney+",
    },
    "appletv": {
        "name": "AppleTV+ 榜单(TMDB)",
        "kind": "tmdb",
        "rss_url": "media=tv&region=US&provider=350&limit=30",
        "platform": "AppleTV+",
    },
    "trakt_shows": {
        "name": "Trakt 热门剧集",
        "kind": "trakt",
        "rss_url": "kind=shows&mode=trending&limit=30",
        "platform": "Trakt",
    },
    "tmdb_movie": {
        "name": "TMDB 热门电影",
        "kind": "tmdb",
        "rss_url": "media=movie&region=US&limit=30",
        "platform": "TMDB",
    },
    "jw_hk_netflix_popular": {
        "name": "JustWatch HK Netflix 热门",
        "kind": "justwatch",
        "rss_url": "country=HK&content=show&provider=nfx&mode=popular&limit=30",
        "platform": "JustWatch",
    },
    "jw_hk_netflix_latest": {
        "name": "JustWatch HK Netflix 最新",
        "kind": "justwatch",
        "rss_url": "country=HK&content=show&provider=nfx&mode=latest&limit=30",
        "platform": "JustWatch",
    },
}


def _split_csv(s: str):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def _parse_ids(csv_text: str):
    out = []
    for x in _split_csv(csv_text):
        try:
            out.append(int(x))
        except ValueError:
            pass
    return out


def seed_from_yaml_if_empty():
    if list_sources() or list_rules():
        return
    cfg = load_config()
    source_id_map = []
    for r in cfg.rules:
        for i, url in enumerate(r.rss_urls, start=1):
            create_source(name=f"{r.name}-RSS{i}", kind="rss", rss_url=url, platform="")
        all_src = list_sources()
        ids = [s["id"] for s in all_src if s["name"].startswith(f"{r.name}-RSS")]
        source_id_map.append((r, ids))

    for r, ids in source_id_map:
        create_rule(
            name=r.name,
            target_subdir=r.target_subdir,
            source_ids=",".join(str(i) for i in ids),
            include_keywords=",".join(r.include_keywords),
            exclude_keywords=",".join(r.exclude_keywords),
            max_items=r.max_items,
        )


def run_once():
    cfg = load_config()

    # Web 设置优先
    max_scan = int(get_setting("max_scan_files", str(cfg.settings.max_scan_files)) or cfg.settings.max_scan_files)
    video_exts = _split_csv(get_setting("video_exts", ",".join(cfg.settings.video_exts))) or cfg.settings.video_exts
    prefer_local = get_setting("prefer_local_over_strm", "1") == "1"

    # 将密钥注入运行环境（供来源适配器使用）
    os.environ["TMDB_API_KEY"] = get_setting("tmdb_api_key", os.getenv("TMDB_API_KEY", ""))
    os.environ["TRAKT_CLIENT_ID"] = get_setting("trakt_client_id", os.getenv("TRAKT_CLIENT_ID", ""))

    files = scan_media_files(MEDIA_ROOT, video_exts, max_scan)
    if prefer_local:
        # 本地实体优先于 .strm
        files.sort(key=lambda f: 1 if f.path.suffix.lower() == ".strm" else 0)

    src_map = {s["id"]: s for s in list_sources()}
    result = []

    for rule in list_rules():
        if not int(rule.get("enabled", 1)):
            continue

        titles = []
        for sid in _parse_ids(rule.get("source_ids", "")):
            src = src_map.get(sid)
            if src:
                titles.extend(fetch_source_titles(src))

        matched = match_titles_to_files(
            titles=titles,
            files=files,
            include_keywords=_split_csv(rule.get("include_keywords", "")),
            exclude_keywords=_split_csv(rule.get("exclude_keywords", "")),
            limit=int(rule.get("max_items", 100)),
        )

        class _R:
            name = rule["name"]
            target_subdir = rule["target_subdir"]

        result.append(rebuild_rule_dir(VIRTUAL_ROOT, _R, matched))

    state["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    state["last_result"] = result
    append_run_log(f"run: {len(result)} rules")

    emby_url = get_setting("emby_url", "")
    emby_key = get_setting("emby_api_key", "")
    auto_refresh = get_setting("emby_auto_refresh", "0") == "1"
    if auto_refresh and emby_url and emby_key:
        resp = refresh_emby(emby_url, emby_key)
        state["last_emby_refresh"] = resp
        append_run_log(f"emby refresh: {resp}")

    return result


@app.on_event("startup")
def startup_event():
    os.makedirs(VIRTUAL_ROOT, exist_ok=True)
    init_db()
    seed_from_yaml_if_empty()

    if not get_setting("cron_expr", ""):
        set_setting("cron_expr", os.getenv("CRON_EXPR", "30 3 * * *"))

    cron_expr = get_setting("cron_expr", os.getenv("CRON_EXPR", "30 3 * * *"))
    start_scheduler(run_once, cron_expr)


@app.get("/")
def dashboard(request: Request):
    sources = list_sources()
    rules = list_rules()
    enabled_sources = sum(1 for s in sources if int(s["enabled"]) == 1)
    enabled_rules = sum(1 for r in rules if int(r["enabled"]) == 1)

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "media_root": MEDIA_ROOT,
            "virtual_root": VIRTUAL_ROOT,
            "sources": sources,
            "rules": rules,
            "enabled_sources": enabled_sources,
            "enabled_rules": enabled_rules,
            "last_run": state["last_run"],
            "last_result": state["last_result"],
            "run_logs": list_run_logs(15),
            "emby_url": get_setting("emby_url", ""),
            "emby_auto_refresh": get_setting("emby_auto_refresh", "0"),
            "last_emby_refresh": state["last_emby_refresh"],
            "presets": PRESET_SOURCES,
            "cron_expr": get_setting("cron_expr", os.getenv("CRON_EXPR", "30 3 * * *")),
            "tmdb_api_key": get_setting("tmdb_api_key", ""),
            "trakt_client_id": get_setting("trakt_client_id", ""),
            "max_scan_files": get_setting("max_scan_files", "200000"),
            "video_exts": get_setting("video_exts", ".mkv,.mp4,.avi,.ts,.m2ts,.strm"),
            "prefer_local_over_strm": get_setting("prefer_local_over_strm", "1"),
            "last_source_test": state["last_source_test"],
            "last_rule_preview": state["last_rule_preview"],
        },
    )


@app.post("/run")
def run_now():
    run_once()
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources")
def add_source(
    name: str = Form(...),
    kind: str = Form("rss"),
    rss_url: str = Form(""),
    platform: str = Form(""),
):
    create_source(name=name, kind=kind, rss_url=rss_url, platform=platform)
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources/preset")
def add_source_preset(code: str = Form(...)):
    p = PRESET_SOURCES.get(code)
    if p:
        create_source(name=p["name"], kind=p.get("kind", "rss"), rss_url=p["rss_url"], platform=p["platform"])
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources/{source_id}/toggle")
def source_toggle(source_id: int):
    toggle_source(source_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources/{source_id}/delete")
def source_delete(source_id: int):
    delete_source(source_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/rules")
def add_rule(
    name: str = Form(...),
    target_subdir: str = Form(...),
    source_ids: str = Form(...),
    include_keywords: str = Form(""),
    exclude_keywords: str = Form(""),
    max_items: int = Form(100),
):
    create_rule(name, target_subdir, source_ids, include_keywords, exclude_keywords, max_items)
    return RedirectResponse(url="/", status_code=303)


@app.post("/rules/{rule_id}/toggle")
def rule_toggle(rule_id: int):
    toggle_rule(rule_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/rules/{rule_id}/delete")
def rule_delete(rule_id: int):
    delete_rule(rule_id)
    return RedirectResponse(url="/", status_code=303)


@app.post("/emby/settings")
def save_emby_settings(
    emby_url: str = Form(""),
    emby_api_key: str = Form(""),
    emby_auto_refresh: str = Form("0"),
):
    set_setting("emby_url", emby_url.strip())
    set_setting("emby_api_key", emby_api_key.strip())
    set_setting("emby_auto_refresh", "1" if emby_auto_refresh == "1" else "0")
    return RedirectResponse(url="/", status_code=303)


@app.post("/emby/refresh")
def emby_refresh_now():
    resp = refresh_emby(get_setting("emby_url", ""), get_setting("emby_api_key", ""))
    state["last_emby_refresh"] = resp
    append_run_log(f"emby manual refresh: {resp}")
    return RedirectResponse(url="/", status_code=303)


@app.post("/system/settings")
def save_system_settings(
    cron_expr: str = Form("30 3 * * *"),
    tmdb_api_key: str = Form(""),
    trakt_client_id: str = Form(""),
    max_scan_files: str = Form("200000"),
    video_exts: str = Form(".mkv,.mp4,.avi,.ts,.m2ts,.strm"),
    prefer_local_over_strm: str = Form("1"),
):
    set_setting("cron_expr", cron_expr.strip() or "30 3 * * *")
    set_setting("tmdb_api_key", tmdb_api_key.strip())
    set_setting("trakt_client_id", trakt_client_id.strip())
    set_setting("max_scan_files", max_scan_files.strip() or "200000")
    set_setting("video_exts", video_exts.strip() or ".mkv,.mp4,.avi,.ts,.m2ts,.strm")
    set_setting("prefer_local_over_strm", "1" if prefer_local_over_strm == "1" else "0")

    # 立即更新调度
    apply_schedule(run_once, get_setting("cron_expr", "30 3 * * *"))
    if not scheduler.running:
        scheduler.start()

    append_run_log("system settings updated")
    return RedirectResponse(url="/", status_code=303)


@app.post("/sources/{source_id}/test")
def source_test(source_id: int):
    os.environ["TMDB_API_KEY"] = get_setting("tmdb_api_key", os.getenv("TMDB_API_KEY", ""))
    os.environ["TRAKT_CLIENT_ID"] = get_setting("trakt_client_id", os.getenv("TRAKT_CLIENT_ID", ""))

    src = next((s for s in list_sources() if s["id"] == source_id), None)
    if not src:
        state["last_source_test"] = {"error": "source not found"}
        return RedirectResponse(url="/", status_code=303)

    titles = fetch_source_titles(src)
    state["last_source_test"] = {
        "source": src["name"],
        "count": len(titles),
        "sample": titles[:20],
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    append_run_log(f"source test: {src['name']} => {len(titles)}")
    return RedirectResponse(url="/", status_code=303)


@app.post("/rules/{rule_id}/preview")
def rule_preview(rule_id: int):
    cfg = load_config()
    max_scan = int(get_setting("max_scan_files", str(cfg.settings.max_scan_files)) or cfg.settings.max_scan_files)
    video_exts = _split_csv(get_setting("video_exts", ",".join(cfg.settings.video_exts))) or cfg.settings.video_exts
    prefer_local = get_setting("prefer_local_over_strm", "1") == "1"

    os.environ["TMDB_API_KEY"] = get_setting("tmdb_api_key", os.getenv("TMDB_API_KEY", ""))
    os.environ["TRAKT_CLIENT_ID"] = get_setting("trakt_client_id", os.getenv("TRAKT_CLIENT_ID", ""))

    files = scan_media_files(MEDIA_ROOT, video_exts, max_scan)
    if prefer_local:
        files.sort(key=lambda f: 1 if f.path.suffix.lower() == ".strm" else 0)

    src_map = {s["id"]: s for s in list_sources()}
    rule = next((r for r in list_rules() if r["id"] == rule_id), None)
    if not rule:
        state["last_rule_preview"] = {"error": "rule not found"}
        return RedirectResponse(url="/", status_code=303)

    titles = []
    for sid in _parse_ids(rule.get("source_ids", "")):
        src = src_map.get(sid)
        if src:
            titles.extend(fetch_source_titles(src))

    matched = match_titles_to_files(
        titles=titles,
        files=files,
        include_keywords=_split_csv(rule.get("include_keywords", "")),
        exclude_keywords=_split_csv(rule.get("exclude_keywords", "")),
        limit=min(int(rule.get("max_items", 100)), 30),
    )

    state["last_rule_preview"] = {
        "rule": rule["name"],
        "count": len(matched),
        "sample": [str(x.path) for x in matched[:20]],
        "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    append_run_log(f"rule preview: {rule['name']} => {len(matched)}")
    return RedirectResponse(url="/", status_code=303)


@app.get("/health")
def health():
    return {"ok": True, "last_run": state["last_run"]}
