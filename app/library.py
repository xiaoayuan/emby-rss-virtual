import os
import re
from pathlib import Path
from typing import List
from .models import MediaFile


def norm(s: str) -> str:
    s = s.lower()
    s = re.sub(r"[\[\](){}._-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def scan_media_files(media_root: str, exts: List[str], max_scan: int) -> List[MediaFile]:
    root = Path(media_root)
    if not root.exists():
        return []

    exts = {e.lower() for e in exts}
    out = []
    count = 0
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in exts:
            out.append(MediaFile(path=p, stem=norm(p.stem)))
            count += 1
            if count >= max_scan:
                break
    return out


def match_titles_to_files(titles: List[str], files: List[MediaFile], include_keywords: List[str], exclude_keywords: List[str], limit: int) -> List[MediaFile]:
    include_keywords = [k.lower() for k in include_keywords]
    exclude_keywords = [k.lower() for k in exclude_keywords]

    matched = []
    used = set()

    for t in titles:
        t_norm = norm(t)
        t_low = t.lower()

        if include_keywords and not any(k in t_low for k in include_keywords):
            continue
        if exclude_keywords and any(k in t_low for k in exclude_keywords):
            continue

        for mf in files:
            if mf.path in used:
                continue
            if t_norm and (t_norm in mf.stem or mf.stem in t_norm):
                matched.append(mf)
                used.add(mf.path)
                break

        if len(matched) >= limit:
            break

    return matched
