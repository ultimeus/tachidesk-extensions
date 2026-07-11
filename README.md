# tachidesk-extensions

Personal Tachiyomi/Mihon/Suwayomi (Tachidesk) extension repo hosting **patched
extensions** while fixes are pending upstream at
[keiyoushi/extensions-source](https://github.com/keiyoushi/extensions-source).

## Add to Tachidesk / Suwayomi

Add this URL as an extension repo (keep the official keiyoushi repo too):

```
https://raw.githubusercontent.com/ultimeus/tachidesk-extensions/repo/index.min.json
```

Because patched builds bump `versionCode`, they take precedence over the official
build until the fix is merged upstream. These builds are signed with a personal
key (different signature than keiyoushi), so **uninstall the official copy of a
patched extension once** before installing from here.

## How it works

- Patched sources live in the fork `ultimeus/extensions-source` (branch `deploy`).
- `modules.txt` lists which Gradle targets to build.
- `.github/workflows/build.yml` builds them release-signed, runs
  [extensions-inspector](https://github.com/keiyoushi/extensions-inspector) to
  resolve source IDs, and `scripts/make-index.py` emits the classic
  `index.min.json` (+ `apk/`, `icon/`) onto the `repo` branch.

## Adding another fix

1. Apply the fix on `ultimeus/extensions-source` (`deploy` branch) + open a clean
   PR branch upstream.
2. Add its `:src:<lang>:<name>:assembleRelease` line to `modules.txt`.
3. Push to `main` (or run the workflow) → the `repo` branch updates.
