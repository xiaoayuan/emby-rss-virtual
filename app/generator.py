import os
import shutil
from pathlib import Path
from typing import List
from .models import MediaFile, Rule


def rebuild_rule_dir(virtual_root: str, rule: Rule, files: List[MediaFile]) -> dict:
    target = Path(virtual_root) / rule.target_subdir
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)

    linked = 0
    errors = 0
    for mf in files:
        try:
            # 使用“剧名/文件名”结构，Emby 更稳定
            series_dir = target / mf.path.parent.name
            series_dir.mkdir(parents=True, exist_ok=True)
            dst = series_dir / mf.path.name
            os.symlink(mf.path, dst)
            linked += 1
        except Exception:
            errors += 1

    return {
        "rule": rule.name,
        "target": str(target),
        "linked": linked,
        "errors": errors,
    }
