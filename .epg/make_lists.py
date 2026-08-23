#!/usr/bin/env python3
"""Create the MAC and Xtream JSON lists published with the EPG release."""

import argparse
import csv
import gzip
import html
import json
import os
import re
import time
import uuid
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import boto3
import requests
from bs4 import BeautifulSoup
from dateutil.parser import parse

from maclist import alllist as mac_seed


R2_ACCESS_KEY = "4b36152b6b64b8a9f4d7010b84f535fc"
R2_SECRET_KEY = "7ad1ed517b6baa6af2fa00d50a1a18b0ce416bb0b6fb14f4c122a2960f1ab9bc"
R2_ENDPOINT_URL = "https://145ef3f7a9832804bef0e31548db8a83.r2.cloudflarestorage.com"
STBEMU_PUBLIC_URL = "https://pub-38f23eb5f3304328b9774fadfa233a38.r2.dev/stbemu.csv.gz"
BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)
HEADERS = {
    "accept": "*/*",
    "user-agent": BROWSER_UA,
    "Accept-Encoding": "gzip, deflate",
}
BLOGGER_LIST_INDEX_URL = (
    "https://ikracccam.blogspot.com/p/stalker-and-iptv-link.html"
)
BLOGGER_DRIVE_LINK_PATTERN = re.compile(
    r'<div\b[^>]*class=["\'][^"\']*titre-content-'
    r'(?P<kind>iptv|stalker)[^"\']*["\'][^>]*>.*?'
    r'(?P<url>https://drive\.google\.com/uc\?[^\s<"\']+).*?</div>',
    re.IGNORECASE | re.DOTALL,
)


def get_blogger_drive_links(page_url=BLOGGER_LIST_INDEX_URL):
    """Return the IPTV and Stalker Google Drive links from one Blogger page."""
    response = requests.get(page_url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    links = {}
    for match in BLOGGER_DRIVE_LINK_PATTERN.finditer(response.text):
        kind = match.group("kind").lower()
        url = html.unescape(match.group("url"))
        if kind in links and links[kind] != url:
            raise RuntimeError("Multiple %s Google Drive links found" % kind)
        links[kind] = url

    missing = {"iptv", "stalker"} - set(links)
    if missing:
        raise RuntimeError(
            "Could not obtain Blogger Google Drive link(s): %s"
            % ", ".join(sorted(missing))
        )
    return links


def get_blogger_hidden_link(page_url):
    """Return the hidden download link, including the Blogger feed fallback."""
    errors = []
    for suffix in ("", "?m=1"):
        try:
            response = requests.get(page_url + suffix, headers=HEADERS, timeout=20)
            response.raise_for_status()
            node = BeautifulSoup(response.content, "html.parser").select_one(
                "div.titre-content.hidden-link p"
            )
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
            errors.append(
                "%s: link missing (%d bytes)" %
                (response.url, len(response.content))
            )
        except requests.RequestException as exc:
            errors.append("%s: %s" % (page_url + suffix, exc))

    feed_url = (
        "https://ikracccam.blogspot.com/feeds/pages/default"
        "?alt=json&max-results=100"
    )
    try:
        response = requests.get(feed_url, headers=HEADERS, timeout=20)
        response.raise_for_status()
        for entry in response.json().get("feed", {}).get("entry", []):
            alternate_urls = [
                item.get("href", "").split("?", 1)[0]
                for item in entry.get("link", [])
                if item.get("rel") == "alternate"
            ]
            if page_url.split("?", 1)[0] not in alternate_urls:
                continue
            node = BeautifulSoup(
                entry.get("content", {}).get("$t", ""), "html.parser"
            ).select_one("div.titre-content.hidden-link p")
            if node and node.get_text(strip=True):
                return node.get_text(strip=True)
        errors.append("%s: matching page/link missing" % feed_url)
    except (requests.RequestException, ValueError) as exc:
        errors.append("Blogger feed: %s" % exc)

    raise RuntimeError(
        "Could not obtain Blogger download link: " + "; ".join(errors)
    )


def get_boto(bucket_name, object_key):
    """Read the legacy private R2 CSV source."""
    rows = []
    client = boto3.client(
        "s3",
        aws_access_key_id=R2_ACCESS_KEY,
        aws_secret_access_key=R2_SECRET_KEY,
        endpoint_url=R2_ENDPOINT_URL,
    )
    response = client.get_object(Bucket=bucket_name, Key=object_key)
    with gzip.GzipFile(fileobj=response["Body"]) as archive:
        for line in archive:
            rows.append(
                line.decode("utf-8")
                .replace('"', "")
                .replace("\\", "")
                .strip()
                .split(",")
            )
    return rows


def get_boto2(url):
    rows = []
    response = requests.get(
        url, headers={"User-Agent": "Mozilla/5.0"}, timeout=30
    )
    response.raise_for_status()
    content = gzip.decompress(response.content).decode(
        "utf-8", errors="replace"
    ).splitlines()
    for line in content:
        rows.append(
            line.replace('"', "").replace("\\", "").strip().split(",")
        )
    return rows


def add_stbemu_mac(mac_list, url, mac):
    url = url.strip().rstrip("/")
    if not url.endswith("/c"):
        url += "/c"
    url = url.replace(":80/c", "/c")
    mac = mac.strip()
    mac_list.setdefault(url, [])
    if mac not in mac_list[url]:
        mac_list[url].append(mac)


def add_stbemu_rows(mac_list, rows, weekstamp):
    for row in rows:
        if len(row) < 3:
            continue
        try:
            if weekstamp > datetime.timestamp(parse(" ".join(row[2:]))):
                continue
        except (TypeError, ValueError, OverflowError):
            pass
        add_stbemu_mac(mac_list, row[0], row[1])


def get_public_stbemu_rows():
    response = requests.get(
        STBEMU_PUBLIC_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()
    content = gzip.decompress(response.content).decode(
        "utf-8", errors="replace"
    ).splitlines()
    return list(csv.reader(content))


def add_blogger_stalker_list(mac_list, weekstamp, link=None):
    if link is None:
        link = get_blogger_hidden_link(
            "https://ikracccam.blogspot.com/p/link-stalcker-google-drive.html"
        )
    response = requests.get(link, headers=HEADERS, timeout=30)
    response.raise_for_status()
    pattern = re.compile(
        r"URL:\s*(?P<url>\S+)\s*.*?"
        r"MAC:\s*(?P<mac>(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2})\s*.*?"
        r"Expire:\s*(?P<expire>[A-Za-z]+\s+\d{1,2},\s+\d{4},\s+"
        r"\d{1,2}:\d{2}\s*(?:am|pm)|unknown|unlimited)",
        re.IGNORECASE | re.DOTALL,
    )
    for match in pattern.finditer(response.text):
        try:
            if weekstamp > datetime.timestamp(parse(match.group("expire"))):
                continue
        except (TypeError, ValueError, OverflowError):
            pass
        add_stbemu_mac(mac_list, match.group("url"), match.group("mac"))


def add_optional_stalker_page(mac_list, now, weekstamp):
    try:
        url = (
            "https://stbstalker.alaaeldinee.com/{year_month}/"
            "smart-stb-emu-pro-{date}.html?m=1"
        ).format(
            year_month=now.strftime("%Y/%m"),
            date=now.strftime("%d-%m-%Y"),
        )
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        for line in response.text.splitlines():
            if "PORTAL :" not in line:
                continue
            entries = re.findall(
                "PORTAL : .*", line.replace("PORTAL", "\nPORTAL")
            )
            for entry in entries:
                if "datePublished" in entry:
                    continue
                values = re.findall("(?<= : ).*?(?=</p>)", entry)
                if not values or len(values) != 5:
                    continue
                portal, mac, expired = values[0], values[3], values[4]
                try:
                    if weekstamp > datetime.timestamp(parse(expired)):
                        continue
                except (TypeError, ValueError, OverflowError):
                    pass
                add_stbemu_mac(mac_list, portal, mac)
    except Exception as exc:
        print("optional stalker page error: %s" % exc)


def collect_xtream_list(weekstamp, link=None):
    entries = []
    if link is None:
        link = get_blogger_hidden_link(
            "https://ikracccam.blogspot.com/p/link-stalker-ikra.html"
        )
    response = requests.get(link, headers=HEADERS, timeout=30)
    response.raise_for_status()
    pattern = re.compile(
        r"^(https?://[^/\s?#]+)/+get\.php\?"
        r"(username=[^&]+&password=[^&]+)(?:&type=m3u)?$"
    )
    for url in response.text.strip().splitlines():
        match = pattern.match(url)
        if match:
            entries.append({
                "url": match.group(1).rstrip("/"),
                "userpass": match.group(2),
                "region": None,
            })

    regions = []
    rows = get_boto2(
        "https://pub-38f23eb5f3304328b9774fadfa233a38.r2.dev/"
        "xtreamity-db.csv.gz"
    )
    for row in rows:
        if len(row) < 6:
            continue
        try:
            if weekstamp > datetime.timestamp(parse(row[3] + row[4])):
                continue
        except (TypeError, ValueError, OverflowError):
            pass
        if row[5] not in regions:
            regions.append(row[5])
        entries.append({
            "url": row[0].rstrip("/"),
            "userpass": "username=%s&password=%s" % (row[1], row[2]),
            "region": row[5],
        })

    url_regions = {}
    for entry in entries:
        if entry.get("region"):
            url_regions.setdefault(entry["url"], entry["region"])
    for entry in entries:
        if entry.get("region") is None and entry["url"] in url_regions:
            entry["region"] = url_regions[entry["url"]]

    grouped = defaultdict(lambda: {
        "url": None,
        "region": None,
        "userpasses": set(),
    })
    for entry in entries:
        key = (entry["url"], entry["region"])
        grouped[key]["url"] = entry["url"]
        grouped[key]["region"] = entry["region"]
        grouped[key]["userpasses"].add(entry["userpass"])

    result = []
    credential_pattern = re.compile(r"username=([^&]+)&password=(.+)")
    for value in grouped.values():
        converted = []
        for userpass in sorted(value["userpasses"]):
            match = credential_pattern.search(userpass)
            if match:
                converted.append({
                    "user": match.group(1),
                    "pass": match.group(2),
                })
        result.append({
            "url": value["url"],
            "region": value["region"],
            "userpasses": converted,
        })
    result.sort(key=lambda item: len(item["userpasses"]), reverse=True)
    return {"regions": sorted(regions), "urls": result}


def write_json_atomic(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=4)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    now = datetime.now()
    weekstamp = datetime.timestamp(now + timedelta(days=7))
    blogger_links = get_blogger_drive_links()

    mac_list = {url: list(macs) for url, macs in mac_seed.items()}
    add_blogger_stalker_list(mac_list, weekstamp, blogger_links["stalker"])
    try:
        add_stbemu_rows(mac_list, get_public_stbemu_rows(), weekstamp)
    except Exception as exc:
        print("stbemu public list error: %s" % exc)
    add_optional_stalker_page(mac_list, now, weekstamp)
    sorted_mac_list = dict(sorted(
        sorted(mac_list.items()),
        key=lambda item: len(item[1]),
        reverse=True,
    ))

    xtream_list = collect_xtream_list(weekstamp, blogger_links["iptv"])
    write_json_atomic(output_dir / "xtreamlist.json", xtream_list)
    print("New xtream list created")
    write_json_atomic(output_dir / "maclist.json", sorted_mac_list)
    print("New maclist created")


if __name__ == "__main__":
    main()
