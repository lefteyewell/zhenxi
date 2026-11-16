# Zhenxi (PhotoManager)

**Zhenxi** — local photo management software for photographers: fast retrieval (faces / text /
EXIF / folders / arbitrary combinations), thumbnails and full-size viewing,
batch export at common resolutions — **the app never deletes or modifies your original
files**.

## Latest release v0.7.1 (2026-11-15)

> 📥 Download: [Releases page](https://github.com/lefteyewell/zhenxi/releases) ｜
> 📋 All version changes: [CHANGELOG.md](CHANGELOG.md)

**Fixed**

- **Camera RAW files disguised as .tiff were not recognized** - some conversion tools store Nikon NEF / Canon CR2 sensor data verbatim in a .tiff container: the extension looks like an ordinary image while the content is camera RAW. They were decoded as ordinary images: some failed to import outright, others only yielded their tiny embedded thumbnail (120×160–852×640), leaving an extra-small preview, wrong dimensions, no faces and failed OCR. Files are now sniffed **by content**: a .tif/.tiff that LibRaw recognizes as camera RAW (real size clearly larger, or ordinary decoding fails outright) goes through the RAW decoding path. All 21 sample files now decode to their true 1306×978–7360×4912 images, with thumbnails, previews, dimensions, faces and OCR restored
- **Preview orientation was wrong on such files** - on some container RAW files (Nikon D3X sample) the outer TIFF orientation tag conflicts with the embedded pixel orientation, and re-rotating by the tag laid the image on its side with undetectable faces. Orientation now follows the actual decoded data; already-upright images are no longer rotated again
- **The photo viewer still showed blank or tiny previews for .tif/.tiff** - .tif/.tiff sit in the "Qt-decodable" list, so the viewer handed the original file straight to the Qt image engine, bypassing the sniffing path entirely; the integrity deep-decode check skipped them the same way. Both places now sniff for container RAW first: the viewer shows an on-demand decoded preview (cached after first use) and the deep check covers container files

**Improved**

- **Ordinary TIFF photos are completely unaffected** - sniffing applies only to .tif / .tiff extensions and requires the LibRaw size to be ≥2× the ordinary decode (or the ordinary decode to fail) before treating the file as camera RAW; sniff results are cached per file (path + mtime + size), so repeated analysis passes add no overhead
- **Viewer button "1:1 Original" renamed to "High-res" with an honest tooltip** - the view for RAW/HEIC files is a decoded preview up to 1920 px on the long edge (a long-standing design); the tooltip now says so plainly
- **Help dialog gained an "Exceptions & special notes" section** - preview resolution for RAW/HEIC, JPEG XL unsupported by default, and ImageMagick dependency for niche formats, collected in one place

> ⚠️ **After upgrading, run "Scan & import" once**: the first launch resets existing .tif / .tiff photos in the library to pending re-analysis (once per database); one scan then rebuilds their thumbnails, previews and dimensions and re-runs face / text / semantic / perceptual-hash analysis. Ordinary photos and videos are unaffected. Backing up the database first is recommended. See [CHANGELOG.md](CHANGELOG.md).

<details>
<summary>Previous release v0.6.31 (2026-11-13) summary</summary>

**Fixed**

- **Face boxes on camera RAW photos were all misplaced** - v0.6.30 made RAW face detection work for the first time, but boxes were recorded on the small detection image (a ~1000 px embedded preview) while the UI scaled them against the full sensor dimensions now stored in the library (6000×4000 class) - several times off, with width/height swapped again for portrait shots. Both the boxes in the preview dialog and the face thumbnails in the info panel landed in the wrong place. Boxes now carry their own detection-image dimensions and every UI path normalizes against them; the long-standing slight offset on portrait JPEGs is fixed too
- **Only the display was wrong** - detection, SFace features and people clustering all use the same detection image and remain valid; no change to the recognition algorithms

**Improved**

- **Tool Center now explains which photos each button analyzes**: Face detection / Text recognition / Perceptual hash / Semantic vectors are incremental, while Event clustering / Face clustering / Detect stacks are full rebuilds; the Help dialog links to it and all English strings are added
- **Old and new metadata packages stay compatible** - after face boxes gained their own dimensions, `.meta.db` files exported by older versions still match face ownership correctly; user-assigned person names are backed up before stale results are invalidated

> ⚠️ That release asks you to re-run "Face detection" once, with a database backup first.

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
