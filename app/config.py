import os
import yaml
from .models import AppConfig, Rule, Settings


def load_config() -> AppConfig:
    cfg_path = os.getenv("APP_CONFIG", "/config/rules.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    settings_raw = raw.get("settings", {})
    settings = Settings(
        max_scan_files=settings_raw.get("max_scan_files", 200000),
        video_exts=settings_raw.get("video_exts", [".mkv", ".mp4", ".avi", ".ts", ".m2ts"]),
    )

    rules = []
    for r in raw.get("rules", []):
        rules.append(
            Rule(
                name=r.get("name", "unnamed"),
                enabled=bool(r.get("enabled", True)),
                target_subdir=r.get("target_subdir", "rss-default"),
                rss_urls=r.get("rss_urls", []),
                include_keywords=r.get("include_keywords", []),
                exclude_keywords=r.get("exclude_keywords", []),
                max_items=int(r.get("max_items", 100)),
            )
        )

    return AppConfig(settings=settings, rules=rules)
