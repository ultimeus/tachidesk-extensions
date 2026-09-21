#!/usr/bin/env python3

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

from bs4 import BeautifulSoup


CATALOG_URL = "https://www.scan-manga.com/scanlation/liste_series.html"


def fetch_rendered_html(flaresolverr_url: str) -> str:
    payload = json.dumps(
        {
            "cmd": "request.get",
            "url": CATALOG_URL,
            "maxTimeout": 120_000,
            "waitInSeconds": 10,
        },
    ).encode()
    request = urllib.request.Request(
        f"{flaresolverr_url.rstrip('/')}/v1",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=150) as response:
        result = json.load(response)

    if result.get("status") != "ok":
        raise RuntimeError(f"FlareSolverr failed: {result.get('message', 'unknown error')}")

    html = result.get("solution", {}).get("response", "")
    if not html:
        raise RuntimeError("FlareSolverr returned an empty page")
    return html


def parse_catalog(html: str) -> list[dict[str, str]]:
    soup = BeautifulSoup(html, "html.parser")
    mangas: dict[str, dict[str, str]] = {}
    for link in soup.select("#contenu_lettre_id a.texte_manga[href]"):
        title = link.get_text(" ", strip=True)
        url = link.get("href", "").strip()
        if title and url.startswith("/") and url.endswith(".html"):
            mangas[url] = {"title": title, "url": url}
    return sorted(mangas.values(), key=lambda manga: manga["title"].casefold())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--html-file", type=Path)
    args = parser.parse_args()

    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
    else:
        html = fetch_rendered_html(os.environ.get("FLARESOLVERR_URL", "http://127.0.0.1:8191"))

    catalog = parse_catalog(html)
    if not args.html_file and len(catalog) < 1_000:
        raise RuntimeError(f"Catalog looks incomplete: only {len(catalog)} entries")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(catalog, ensure_ascii=False, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(catalog)} Scan-Manga entries to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
