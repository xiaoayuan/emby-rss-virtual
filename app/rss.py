from typing import List, Dict, Any
from urllib.parse import parse_qs
import os
import requests
import feedparser


def _dedupe(titles: List[str]) -> List[str]:
    seen = set()
    out = []
    for t in titles:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out


def _to_int(v: str, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_params(s: str) -> Dict[str, str]:
    raw = parse_qs((s or "").lstrip("?"), keep_blank_values=False)
    return {k: v[0] for k, v in raw.items() if v}


def fetch_rss_titles(urls: List[str]) -> List[str]:
    titles: List[str] = []
    for u in urls:
        try:
            d = feedparser.parse(u)
            for e in d.entries:
                t = (e.get("title") or "").strip()
                if t:
                    titles.append(t)
        except Exception:
            continue
    return _dedupe(titles)


def fetch_tmdb_titles(param_text: str) -> List[str]:
    api_key = os.getenv("TMDB_API_KEY", "").strip()
    if not api_key:
        return []

    p = _parse_params(param_text)
    media = p.get("media", "tv")  # tv/movie
    region = p.get("region", "US")
    provider = p.get("provider", "")
    limit = _to_int(p.get("limit", "30"), 30)

    url = f"https://api.themoviedb.org/3/discover/{media}"
    q = {
        "api_key": api_key,
        "sort_by": "popularity.desc",
        "watch_region": region,
        "include_adult": "false",
        "page": 1,
    }
    if provider:
        q["with_watch_providers"] = provider

    try:
        r = requests.get(url, params=q, timeout=20)
        if not r.ok:
            return []
        data = r.json()
        out = []
        for x in data.get("results", [])[:limit]:
            t = (x.get("title") or x.get("name") or "").strip()
            if t:
                out.append(t)
        return _dedupe(out)
    except Exception:
        return []


def fetch_trakt_titles(param_text: str) -> List[str]:
    client_id = os.getenv("TRAKT_CLIENT_ID", "").strip()
    if not client_id:
        return []

    p = _parse_params(param_text)
    kind = p.get("kind", "shows")  # shows/movies
    mode = p.get("mode", "trending")  # trending/popular
    limit = _to_int(p.get("limit", "30"), 30)

    if kind not in {"shows", "movies"}:
        kind = "shows"
    if mode not in {"trending", "popular"}:
        mode = "trending"

    url = f"https://api.trakt.tv/{kind}/{mode}"
    headers = {
        "Content-Type": "application/json",
        "trakt-api-version": "2",
        "trakt-api-key": client_id,
    }

    try:
        r = requests.get(url, headers=headers, params={"limit": limit}, timeout=20)
        if not r.ok:
            return []
        arr = r.json()
        out = []
        for item in arr:
            obj = item.get("show") if kind == "shows" else item.get("movie")
            t = (obj or {}).get("title", "").strip()
            if t:
                out.append(t)
        return _dedupe(out)
    except Exception:
        return []


def fetch_justwatch_titles(param_text: str) -> List[str]:
    # JustWatch 无稳定公开官方 API；这里用其公开接口做 best-effort。
    p = _parse_params(param_text)
    country = p.get("country", "HK")
    content = p.get("content", "show")  # show/movie
    provider = p.get("provider", "nfx")  # nfx/dnp/atp/hbm...
    mode = p.get("mode", "popular")  # popular/latest
    limit = _to_int(p.get("limit", "30"), 30)

    sort_by = "popularity"
    if mode == "latest":
        sort_by = "release_date"

    body = {
        "page_size": min(max(limit, 1), 100),
        "page": 1,
        "query": "",
        "content_types": [content],
        "providers": [provider],
        "sort_by": sort_by,
        "sort_asc": False,
    }
    url = f"https://apis.justwatch.com/content/titles/{country}/popular"

    try:
        r = requests.post(url, json=body, timeout=20)
        if not r.ok:
            return []
        data = r.json()
        out = []
        for x in data.get("items", [])[:limit]:
            t = (x.get("title") or x.get("original_title") or "").strip()
            if t:
                out.append(t)
        return _dedupe(out)
    except Exception:
        return []


def fetch_source_titles(source: Dict[str, Any]) -> List[str]:
    if not int(source.get("enabled", 1)):
        return []

    kind = (source.get("kind") or "rss").lower()
    cfg = (source.get("rss_url") or "").strip()

    if kind == "rss":
        return fetch_rss_titles([cfg]) if cfg else []
    if kind == "tmdb":
        return fetch_tmdb_titles(cfg)
    if kind == "trakt":
        return fetch_trakt_titles(cfg)
    if kind == "justwatch":
        return fetch_justwatch_titles(cfg)

    return []
