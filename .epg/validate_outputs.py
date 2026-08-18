#!/usr/bin/env python3
"""Validate all files before the workflow replaces release assets."""

import argparse
import gzip
import json
import xml.etree.ElementTree as ET
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def read_json(path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def validate_outputs(output_dir):
    output_dir = output_dir.resolve()
    guide = output_dir / "guide.xml"
    compressed = output_dir / "guide.xml.gz"
    maclist = output_dir / "maclist.json"
    xtreamlist = output_dir / "xtreamlist.json"
    for path in (guide, compressed, maclist, xtreamlist):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError("Missing or empty output: %s" % path)

    guide_bytes = guide.read_bytes()
    ET.fromstring(guide_bytes)
    with gzip.open(compressed, "rb") as handle:
        if handle.read() != guide_bytes:
            raise RuntimeError("guide.xml.gz does not contain guide.xml")

    mac_data = read_json(maclist)
    if not isinstance(mac_data, dict) or not mac_data:
        raise RuntimeError("maclist.json is not a non-empty object")
    xtream_data = read_json(xtreamlist)
    if not isinstance(xtream_data, dict):
        raise RuntimeError("xtreamlist.json is not an object")
    if not isinstance(xtream_data.get("regions"), list):
        raise RuntimeError("xtreamlist.json has no regions list")
    if not isinstance(xtream_data.get("urls"), list) or not xtream_data["urls"]:
        raise RuntimeError("xtreamlist.json has no URL entries")
    print("All release outputs are valid")


def main():
    validate_outputs(parse_args().output_dir)


if __name__ == "__main__":
    main()
