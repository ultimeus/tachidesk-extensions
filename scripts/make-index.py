#!/usr/bin/env python3
"""Generate a classic Tachiyomi/Mihon/Suwayomi `index.min.json` for a personal
extension repo, from built APKs + an Inspector `output.json`.

Layout expected (relative to CWD):
    repo/apk/*.apk        built, signed extension APKs
    output.json          produced by keiyoushi extensions-inspector:
                         { "<pkg>": [ {"id","name","lang","baseUrl"}, ... ], ... }

Produces:
    repo/index.min.json  flat array, the file Tachidesk points at
    repo/icon/<pkg>.png  per-extension icon (app resolves <base>/icon/<pkg>.png)
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

ANDROID_HOME = os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"]
BUILD_TOOLS = sorted((Path(ANDROID_HOME) / "build-tools").iterdir())[-1]
AAPT = BUILD_TOOLS / "aapt"

REPO = Path("repo")
APK_DIR = REPO / "apk"
ICON_DIR = REPO / "icon"
ICON_DIR.mkdir(parents=True, exist_ok=True)

PKG_RE = re.compile(r"package: name='([^']+)'")
VCODE_RE = re.compile(r"versionCode='([^']+)'")
VNAME_RE = re.compile(r"versionName='([^']+)'")
CW_RE = re.compile(r"'tachiyomix.contentWarning' value='([^']+)'")
LABEL_RE = re.compile(r"^application-label:'([^']+)'", re.MULTILINE)
ICON320_RE = re.compile(r"^application-icon-320:'([^']+)'", re.MULTILINE)

with open("output.json", encoding="utf-8") as f:
    inspector = json.load(f)

extensions = []
for apk in sorted(APK_DIR.glob("*.apk")):
    badging = subprocess.check_output(
        [str(AAPT), "dump", "--include-meta-data", "badging", str(apk)]
    ).decode("utf-8", "replace")

    pkg_line = next(l for l in badging.splitlines() if l.startswith("package: "))
    pkg = PKG_RE.search(pkg_line).group(1)
    code = int(VCODE_RE.search(pkg_line).group(1))
    version = VNAME_RE.search(pkg_line).group(1)

    label = LABEL_RE.search(badging)
    name = label.group(1) if label else pkg

    cw = CW_RE.search(badging)
    nsfw = 0 if (cw and cw.group(1) == "0") else (0 if not cw else 1)

    icon = ICON320_RE.search(badging)
    if icon:
        with ZipFile(apk) as z, z.open(icon.group(1)) as src, \
                (ICON_DIR / f"{pkg}.png").open("wb") as dst:
            dst.write(src.read())

    srcs = inspector.get(pkg, [])
    sources = [
        {"name": s["name"], "lang": s["lang"], "id": str(s["id"]), "baseUrl": s["baseUrl"]}
        for s in srcs
    ]
    langs = {s["lang"] for s in sources}
    lang = langs.pop() if len(langs) == 1 else "all"

    extensions.append({
        "name": name,
        "pkg": pkg,
        "apk": apk.name,
        "lang": lang,
        "code": code,
        "version": version,
        "nsfw": nsfw,
        "sources": sources,
    })

extensions.sort(key=lambda e: e["name"].lower())

if not extensions:
    print("ERROR: no APKs found under repo/apk", file=sys.stderr)
    sys.exit(1)

with (REPO / "index.min.json").open("w", encoding="utf-8") as f:
    json.dump(extensions, f, ensure_ascii=False, separators=(",", ":"))

print(f"wrote repo/index.min.json with {len(extensions)} extension(s):")
for e in extensions:
    print(f"  - {e['pkg']} v{e['version']} (code {e['code']}, {len(e['sources'])} source(s))")
