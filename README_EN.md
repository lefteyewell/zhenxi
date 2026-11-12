# Zhenxi (PhotoManager)

**Zhenxi** — local photo management software for photographers: fast retrieval (faces / text /
EXIF / folders / arbitrary combinations), thumbnails and full-size viewing,
batch export at common resolutions — **the app never deletes or modifies your original
files**.

## Latest release v0.6.29 (2026-11-12)

> 📥 Download: [Releases page](https://github.com/lefteyewell/zhenxi/releases) ｜
> 📋 All version changes: [CHANGELOG.md](CHANGELOG.md)

**Fixed**

- **The tray bubble message never appeared** - the call passed the display duration into the icon parameter slot, raising a silent TypeError; fixed, the "minimized to tray" message now shows properly
- **Deleting a person now needs just one checkbox** - previously required 2 or more; deleting a person only removes face ownership, photos are untouched (confirmation step kept)
- **Filter → All inside a person's photo list no longer jumps back to all photos** - it stays within the person and reloads that person's full photo list

**Improved**

- **The About dialog now mentions GPLv3 only once** - the copyright line is simplified and the warranty line just points to Help → Open-source license
- **Cleaner people-page top bar** - the "Clear selection" button is gone (Select itself toggles the mode); buttons are left-aligned with an always-visible horizontal scrollbar when the window is too narrow
- **26 missing English UI strings added** - full scan of 1544 translation literals with zero misses (duplicate-persons dialog, settings descriptions, count fragments, etc.)

<details>
<summary>Previous release v0.6.28 (2026-11-12) summary</summary>

**Fixed**

- **Tapping "Stack view" on a person's photo list then leaving it always jumped back to "All photos"** - exiting stacks now returns to the view you came from (e.g. the person list), keeping the original behavior only for the all-photos entry
- **Face clustering similarity threshold actually defaulted to 0.50** - 0.6.9 intended to raise it to 0.60 but the settings reader kept the old default, so users who never touched the slider clustered at 0.50 (too loose, prone to merging different people); now unified at 0.60 - users with a manually saved value are unaffected
- **The About dialog's license pointer pointed at itself** - now points to Help → Open-source license (GPLv3) and the duplicate LICENSE sentence was removed
- **Duplicate-persons dialog merged in the wrong direction** (hidden bug since 0.6.20) - now keeps the side with more photos
- **Merged/ignored rows stayed in the duplicate dialog** - rows now disappear immediately with the count synced; refresh requests are queued instead of dropped
- **The dialog showed the previous scan's results** - the old list is cleared when a scan starts, with a live "Compared N / M faces" counter

**Improved**

- **Empty stack view now shows guidance** - hints to run "Detect photo stacks" in the Tools Center
- **Face-detection completion message now uses a "re-scan pending photos" wording** - avoids being misread as a full-library rescan
- **Threshold description highlights "Face clustering"** - bolded with a note that it is not "Face recognition"; the suggested value is now 0.6
- **People-page action buttons merged into one top-bar row** - fixed row with disabled states and a context-aware duplicate scan button
- **Photo thumbnails show only the file name** - the date/time prefix was removed; shooting time is still in the info panel
- **Merging prefers user-renamed names** - if exactly one side was renamed, it absorbs the other and keeps its name regardless of photo counts

</details>

**English UI**: click the `中 / EN` button at the right end of the top toolbar.
The interface language is remembered across restarts. Missing translations
fall back to Chinese; adding a new language = dropping one JSON file into
`photo_manager/ui/qml/i18n/` (see `docs/DEPENDENCIES.md` for tooling notes).

## License

- **Copyright (C) 2026 蒙汗药 (Menghanyao)**
- Community edition: released under the [GNU GPLv3](LICENSE) — free for
  personal use, study, and open-source derivatives; derivative works must be
  licensed GPLv3 as well. An unofficial Chinese explainer is available at
  [docs/LICENSE-GPLv3-zh.md](docs/LICENSE-GPLv3-zh.md) (the English original
  in `LICENSE` prevails).
- Closed-source integration / OEM bundling requires a commercial license —
  see [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md) (contact:
  lefteyewell@qq.com).
- By contributing you agree to [CLA.md](CLA.md) (copyright assignment; it is
  what makes dual licensing possible).
- Third-party dependency licenses: [THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md)

## Official release

- **Official repository**: [github.com/lefteyewell/zhenxi](https://github.com/lefteyewell/zhenxi)
  (source, release downloads, issue tracker) — this is the authoritative
  source-availability channel per GPLv3 §6.

## Upgrading

There is no in-app auto-update; upgrading means swapping in a new version
directory manually. Your data lives in `data\` inside the program folder —
move it along. See [CHANGELOG.md](CHANGELOG.md) for what's new in each version.

**Method 1 (recommended): extract the new version to a new folder, migrate data**

1. Extract the new package into a **new folder** (don't overwrite the old one,
   so you can always roll back);
2. Copy the whole `data\` folder from the old directory into the new one at
   `PhotoManager\data\` (library, thumbnails and backups are inherited; your
   original photos live outside the app and are untouched; UI settings are
   stored in system config and carry over automatically);
3. Launch the new `PhotoManager`, verify everything is fine, then delete or
   archive the old folder.

**Method 2: extract over the old folder** — fully exit the app first
(including the tray icon), then extract the new package over the old folder.
`data\` is not part of the package and won't be overwritten; if extraction
complains about files in use, the app hasn't exited completely.

**Notes**:

- The program folder must be **writable** (avoid protected locations like
  Program Files; `D:\PhotoManager` is recommended);
- Run "Tools → Backup" in the old version before upgrading; for releases with
  database schema changes, the new version migrates automatically on first
  launch — a pre-upgrade backup keeps you safe either way;
- Moving the program folder together with `data\` to another PC or drive is
  fine (thumbnail paths are relative); if your original photos moved too,
  affected photos show as missing — update the scan roots and re-import.

## Requirements

- Windows 10/11 x86_64, or Kylin V10 desktop aarch64 (Phytium / Kunpeng)
- Fully offline: all dependencies and AI models ship inside the package

## Tech stack

| Component | Choice |
|---|---|
| Language / UI | Python + PySide6 (Qt Quick / QML) |
| Database | SQLite (WAL + FTS5) |
| RAW decoding | rawpy (LibRaw) |
| OCR | RapidOCR (PP-OCRv4 ONNX, offline) |
| Faces | YuNet detection + SFace recognition (ONNX) |
| Semantic search | Chinese-CLIP ViT-B/16 (ONNX, offline) |

## Documentation

- 中文说明与操作指南：软件内「帮助 → 使用说明」（HelpDialog），离线内置
- Dependencies & platform differences: [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md)
- i18n architecture: `photo_manager/ui/qml/i18n/I18n.qml` (data-driven
  language packs; new languages need no code changes)

## Feature highlights

- Ingest / EXIF / thumbnails / search / export engine
- OCR / face recognition / auto grouping / smart albums
- Two-machine metadata sync / duplicate detection / advanced search / backup
- Rating & pick/reject flags, color labels, bulk tagging, albums, events,
  people (face clusters), places, devices, timeline, statistics, map, trash
- Bulk time shift, metadata CSV export, slideshow, video playback
- Semantic search (`clip:` syntax), scene auto-tagging, duplicate finder
- Integrity check + deep decode check for damaged files
- Scheduled tasks (in-app timer or OS scheduler), tray mode, launch at startup

## Development

```
python -m photo_manager.main          # GUI
python tests/smoke_ui.py              # QML smoke (offscreen)
python -m unittest discover -s tests -p "test_*.py"
```

See [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md) for packaging notes
(Windows PyInstaller / Kylin aarch64 Docker, glibc constraints).

### Building from source

Full three-platform build instructions: **[docs/BUILDING.md](docs/BUILDING.md)**
(mirrors CI `.github/workflows/release.yml` step by step — following it yields
packages identical to the official Release).

```powershell
# Windows (simplest)
pip install -r requirements.txt
python tools\fetch_models.py     # downloads CLIP x2 + geo.sqlite (~750MB, sha256-verified)
python tools\build_win.ps1       # PyInstaller + smoke self-test -> dist\PhotoManager\
```

Kylin V10 aarch64 needs no ARM hardware — any Docker-capable x86_64 machine
cross-builds via `tools/arm/kylin.Dockerfile` (glibc 2.31 base). The legacy
`tools/arm/build_kylin.sh` misses critical runtime-library closure steps and
must not be used for shipping.
