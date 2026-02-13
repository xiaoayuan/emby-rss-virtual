from dataclasses import dataclass, field
from pathlib import Path
from typing import List


@dataclass
class Rule:
    name: str
    enabled: bool
    target_subdir: str
    rss_urls: List[str]
    include_keywords: List[str] = field(default_factory=list)
    exclude_keywords: List[str] = field(default_factory=list)
    max_items: int = 100


@dataclass
class Settings:
    max_scan_files: int = 200000
    video_exts: List[str] = field(default_factory=lambda: [".mkv", ".mp4", ".avi", ".ts", ".m2ts"])


@dataclass
class AppConfig:
    settings: Settings
    rules: List[Rule]


@dataclass
class MediaFile:
    path: Path
    stem: str
