#!/usr/bin/env python3
"""Update TV-Spielfilm channel logos when the upstream list changes."""

import argparse
import base64
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

import requests


CHANNELS_URL = "https://rhea-export.tvspielfilm.de/channels/epg"


def fetch_channels():
    response = requests.get(CHANNELS_URL, timeout=30)
    response.raise_for_status()
    return response.json()["data"]["data_list"]


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    return parser.parse_args()


def main():
    output_dir = parse_args().output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    marker = output_dir / "tvsp.md5"
    destination = output_dir / "tvs-logos"
    channels = fetch_channels()
    digest = hashlib.md5(
        json.dumps(channels, sort_keys=True).encode("utf-8")
    ).hexdigest()
    previous = marker.read_text(encoding="ascii").strip() if marker.exists() else ""
    if previous == digest and destination.is_dir():
        print("TV-Spielfilm logos unchanged")
        return

    with tempfile.TemporaryDirectory(prefix="tvs-logos-", dir=output_dir) as temp:
        generated = Path(temp) / "tvs-logos"
        generated.mkdir()
        for channel in channels:
            logo = channel["logo"].replace("data:image/png;base64,", "")
            (generated / (str(channel["id"]) + ".png")).write_bytes(
                base64.b64decode(logo)
            )

        backup = output_dir / ".tvs-logos.backup"
        if backup.exists():
            shutil.rmtree(backup)
        try:
            if destination.exists():
                os.replace(destination, backup)
            os.replace(generated, destination)
        except Exception:
            if backup.exists() and not destination.exists():
                os.replace(backup, destination)
            raise
        finally:
            if backup.exists():
                shutil.rmtree(backup)

    marker_tmp = marker.with_suffix(".md5.tmp")
    marker_tmp.write_text(digest, encoding="ascii")
    os.replace(marker_tmp, marker)
    print("New tvs-logos")


if __name__ == "__main__":
    main()
