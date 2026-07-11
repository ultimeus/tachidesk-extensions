#!/usr/bin/env python3
"""Generate a full keiyoushi/Suwayomi-compatible extension repo from built APKs
plus an Inspector `output.json`.

Emits under repo/:
    repo.json        metadata Suwayomi reads first (points at index.pb, declares key)
    index.pb         gzipped protobuf Index (what modern Suwayomi/Mihon consume)
    index.json       same Index as JSON (new format)
    index.min.json   legacy flat format (older clients)
    icon/<pkg>.png   per-extension icons
"""
import gzip
import json
import os
import re
import struct
import subprocess
from pathlib import Path
from zipfile import ZipFile

from google.protobuf import json_format

import index_pb2

# ---- repo identity -------------------------------------------------------
REPO_NAME = "Ultimeus"
BADGE_LABEL = "ULT"
WEBSITE = "https://github.com/ultimeus/tachidesk-extensions"
# SHA-256 of the signing certificate for C:\b\repo-signing\signingkey.jks (alias key0)
SIGNING_KEY_FP = "83c29df5755459f0a5a3e9b5a33f1c4c893967b4f5b900b6e2c545e518ac9503"
RAW_BASE = "https://raw.githubusercontent.com/ultimeus/tachidesk-extensions/repo"
APK_BASE_URL = f"{RAW_BASE}/apk"
ICON_BASE_URL = f"{RAW_BASE}/icon"
INDEX_PB_URL = f"{RAW_BASE}/index.pb"

ANDROID_HOME = os.environ.get("ANDROID_HOME") or os.environ["ANDROID_SDK_ROOT"]
AAPT = sorted((Path(ANDROID_HOME) / "build-tools").iterdir())[-1] / "aapt"

REPO = Path("repo")
APK_DIR = REPO / "apk"
ICON_DIR = REPO / "icon"
ICON_DIR.mkdir(parents=True, exist_ok=True)

PKG_RE = re.compile(r"package: name='([^']+)'")
VCODE_RE = re.compile(r"versionCode='([^']+)'")
VNAME_RE = re.compile(r"versionName='([^']+)'")
CW_RE = re.compile(r"'tachiyomix.contentWarning' value='([^']+)'")
LIB_RE = re.compile(r"'tachiyomix.extensionLib' value='([^']+)'")
NAME_RE = re.compile(r"'tachiyomix.name' value='([^']+)'")
LABEL_RE = re.compile(r"^application-label:'([^']+)'", re.MULTILINE)
ICON_RE = re.compile(r"^application-icon-320:'([^']+)'", re.MULTILINE)


def hex_to_float(h):
    return round(struct.unpack(">f", struct.pack(">I", int(h, 16)))[0], 1)


with open("output.json", encoding="utf-8") as f:
    inspector = json.load(f)

proto_exts = []   # index_pb2.Extension
legacy = []       # classic index.min.json objects

for apk in sorted(APK_DIR.glob("*.apk")):
    badging = subprocess.check_output(
        [str(AAPT), "dump", "--include-meta-data", "badging", str(apk)]
    ).decode("utf-8", "replace")

    pline = next(l for l in badging.splitlines() if l.startswith("package: "))
    pkg = PKG_RE.search(pline).group(1)
    code = int(VCODE_RE.search(pline).group(1))
    version = VNAME_RE.search(pline).group(1)

    nm = NAME_RE.search(badging) or LABEL_RE.search(badging)
    name = nm.group(1) if nm else pkg

    cw_m = CW_RE.search(badging)
    cw_meta = int(cw_m.group(1)) if cw_m else 0          # 0 safe / 1 mixed / 2 nsfw

    lib_m = LIB_RE.search(badging)
    ext_lib = str(hex_to_float(lib_m.group(1).strip())) if lib_m else "1.5"

    icon_m = ICON_RE.search(badging)
    if icon_m:
        with ZipFile(apk) as z, z.open(icon_m.group(1)) as s, \
                (ICON_DIR / f"{pkg}.png").open("wb") as o:
            o.write(s.read())

    srcs = inspector.get(pkg, [])
    proto_exts.append(index_pb2.Extension(
        name=name,
        packageName=pkg,
        resources=index_pb2.Resources(
            apkUrl=f"{APK_BASE_URL}/{apk.name}",
            iconUrl=f"{ICON_BASE_URL}/{pkg}.png",
        ),
        extensionLib=ext_lib,
        versionCode=code,
        versionName=version,
        contentWarning=cw_meta + 1,   # -> proto enum SAFE=1 / MIXED=2 / NSFW=3
        sources=[
            index_pb2.Source(
                id=int(s["id"]), name=s["name"],
                language=s["lang"], homeUrl=s["baseUrl"],
            ) for s in srcs
        ],
    ))

    langs = {s["lang"] for s in srcs}
    legacy.append({
        "name": name, "pkg": pkg, "apk": apk.name,
        "lang": langs.pop() if len(langs) == 1 else "all",
        "code": code, "version": version,
        "nsfw": 0 if cw_meta == 0 else 1,
        "sources": [
            {"name": s["name"], "lang": s["lang"], "id": str(s["id"]), "baseUrl": s["baseUrl"]}
            for s in srcs
        ],
    })

proto_exts.sort(key=lambda e: e.packageName)
legacy.sort(key=lambda e: e["name"].lower())

index = index_pb2.Index(
    name=REPO_NAME,
    badgeLabel=BADGE_LABEL,
    signingKey=SIGNING_KEY_FP,
    contact=index_pb2.Contact(website=WEBSITE),
    extensionList=index_pb2.ExtensionList(extensions=proto_exts),
)

(REPO / "index.json").write_text(
    json_format.MessageToJson(index, preserving_proto_field_name=True),
    encoding="utf-8",
)
(REPO / "index.pb").write_bytes(gzip.compress(index.SerializeToString()))
(REPO / "index.min.json").write_text(
    json.dumps(legacy, ensure_ascii=False, separators=(",", ":")),
    encoding="utf-8",
)
(REPO / "repo.json").write_text(
    json.dumps({
        "index_v2": INDEX_PB_URL,
        "meta": {
            "name": REPO_NAME,
            "website": WEBSITE,
            "signingKeyFingerprint": SIGNING_KEY_FP,
        },
    }, ensure_ascii=False),
    encoding="utf-8",
)

print(f"generated repo with {len(proto_exts)} extension(s):")
for e in proto_exts:
    print(f"  - {e.packageName} v{e.versionName} (code {e.versionCode}, {len(e.sources)} source(s))")
