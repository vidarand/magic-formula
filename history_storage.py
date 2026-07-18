#!/usr/bin/env python3
"""Shared helpers for loading/saving historical stock data."""

import gzip
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

HISTORY_DATA = Path("data/stock_history.json")
HISTORY_MANIFEST = Path("data/stock_history.manifest.json")
HISTORY_SHARDS_DIR = Path("data/stock_history_shards")

MAX_SINGLE_FILE_SIZE_BYTES = 15 * 1024 * 1024
TARGET_SHARD_SIZE_BYTES = 4 * 1024 * 1024


def _json_bytes(data: Dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


EMPTY_JSON_OBJECT_BYTES = len(_json_bytes({}))


def load_history_data() -> Dict:
    """Load historical stock data from either single-file or sharded format."""
    if HISTORY_MANIFEST.exists():
        with open(HISTORY_MANIFEST, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        history: Dict = {}
        for shard in manifest.get("shards", []):
            shard_file = HISTORY_SHARDS_DIR / shard["file"]
            with gzip.open(shard_file, "rt", encoding="utf-8") as f:
                shard_data = json.load(f)
            history.update(shard_data)
        return history

    if HISTORY_DATA.exists():
        with open(HISTORY_DATA, "r", encoding="utf-8") as f:
            content = f.read()
            if not content.strip():
                return {}
            return json.loads(content)

    return {}


def save_history_data(history: Dict):
    """Save historical data in a single JSON file or split/compressed shards when large."""
    HISTORY_DATA.parent.mkdir(exist_ok=True)
    serialized = _json_bytes(history)

    if len(serialized) <= MAX_SINGLE_FILE_SIZE_BYTES:
        with open(HISTORY_DATA, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        if HISTORY_MANIFEST.exists():
            HISTORY_MANIFEST.unlink()
        if HISTORY_SHARDS_DIR.exists():
            shutil.rmtree(HISTORY_SHARDS_DIR)
        return

    if HISTORY_SHARDS_DIR.exists():
        shutil.rmtree(HISTORY_SHARDS_DIR)
    HISTORY_SHARDS_DIR.mkdir(parents=True, exist_ok=True)

    shards = []
    current_shard: Dict = {}
    current_size = EMPTY_JSON_OBJECT_BYTES

    for ticker in sorted(history.keys()):
        ticker_data = history[ticker]
        ticker_size = len(_json_bytes({ticker: ticker_data})) - EMPTY_JSON_OBJECT_BYTES
        separator_size = 1 if current_shard else 0
        candidate_size = current_size + separator_size + ticker_size

        if current_shard and candidate_size > TARGET_SHARD_SIZE_BYTES:
            shards.append(current_shard)
            current_shard = {}
            current_size = EMPTY_JSON_OBJECT_BYTES
            separator_size = 0

        current_shard[ticker] = ticker_data
        current_size = current_size + separator_size + ticker_size

    if current_shard:
        shards.append(current_shard)

    manifest_shards = []
    for i, shard in enumerate(shards, start=1):
        filename = f"stock_history.part{i:04d}.json.gz"
        shard_path = HISTORY_SHARDS_DIR / filename

        with gzip.open(shard_path, "wt", encoding="utf-8") as f:
            json.dump(shard, f, ensure_ascii=False, separators=(",", ":"))

        manifest_shards.append(
            {
                "file": filename,
                "ticker_count": len(shard),
            }
        )

    created_at = datetime.now(tz=timezone.utc).isoformat()

    with open(HISTORY_MANIFEST, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": 1,
                "format": "sharded-gzip",
                "created_at": created_at,
                "shard_count": len(manifest_shards),
                "total_tickers": len(history),
                "shards": manifest_shards,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    with open(HISTORY_DATA, "w", encoding="utf-8") as f:
        json.dump(
            {
                "_storage": "sharded-gzip",
                "manifest": str(HISTORY_MANIFEST),
                "shards_dir": str(HISTORY_SHARDS_DIR),
                "shard_count": len(manifest_shards),
                "total_tickers": len(history),
                "created_at": created_at,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )
