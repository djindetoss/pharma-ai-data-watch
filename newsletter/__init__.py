"""IncreaseNET AI Community – Newsletter.

Builds a short, curated bi-weekly newsletter from the items the daily
pipeline already collects (portal/js/articles.json). See newsletter/README.md.
"""
from pathlib import Path

import yaml

PKG_DIR = Path(__file__).resolve().parent
REPO_ROOT = PKG_DIR.parent
DRAFTS_DIR = PKG_DIR / "drafts"
EDITIONS_DIR = PKG_DIR / "editions"
EDITIONS_INDEX = PKG_DIR / "editions.json"


def load_config(path: Path | None = None) -> dict:
    with open(path or PKG_DIR / "config.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)
