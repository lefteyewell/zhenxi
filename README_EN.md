# Zhenxi (PhotoManager)

**Zhenxi** — local photo management software for photographers: fast retrieval (faces / text /
EXIF / folders / arbitrary combinations), thumbnails and full-size viewing,
batch export at common resolutions — **the app never deletes or modifies your original
files**.

## Latest release v0.7.8 (2026-11-27)

> 📥 Download: [Releases page](https://github.com/lefteyewell/zhenxi/releases) ｜
> 📋 All version changes: [CHANGELOG.md](CHANGELOG.md)

**New**

- **Automatic GPS place names** - photos with GPS now show a city-level place name automatically (no country/province); manual labels always take priority. Place rows in category browsing can also be labeled/renamed directly
- **"Labeled places" side panel** - the map page's right panel now lists labeled places (with photo/folder counts) and updates with the current view of the globe
- **Chinese names for places in China** - about 5,000 Chinese place names added from the offline gazetteer (incl. Hong Kong, Macao and Taiwan, China)

**Fixed**

- **Some place entries showed no photos** - archived photos were still counted in place/map totals; counts now match the photo list
- **Selected marker drifted after rotating the globe** - selection is now tracked by coordinates
- **Clicking the empty preview area opened the previously viewed photo** - now disabled
- **Scrollbar covered the merge button in the "similar persons" dialog** - fixed

**Improved**

- **Precise return from place/map photo views** - category scrolling position and map viewpoint/zoom/selection are preserved
- **Higher map zoom limit** - dense GPS points are easier to tell apart; the gazetteer now follows China's official naming (Xizang; South Tibet under Xizang, China; "Hong Kong, China / Macao, China")
- **English UI completion** - 15 missing translations added, 88 obsolete entries removed

<details>
<summary>Previous release v0.7.7 (2026-11-20) summary</summary>

**Changed**

- **"Find likely duplicates" now requires exactly 1 person checked** - the people-page button is disabled (with a hint) when nothing or multiple people are checked ("click Select and check 1 person first" / "only 1 person can be checked for duplicate search"); background scanning, closing the dialog without interrupting, and automatic queueing are unchanged
- **Library-wide scan entry removed** - the "Scan all" button inside the dialog and the scan-when-nothing-checked entry are gone; duplicate search is per-person only. "Show all" merely clears the person filter and never starts a scan
- **Help and hint texts updated** - help now states when the button is available; the empty-list hint guides users to check 1 person first

</details>

<details>
<summary>Previous release v0.7.6 (2026-11-19) summary</summary>

**Fixed**

- **Inconsistent top hints in the "similar persons" dialog depending on entry point** - waiting states mixed three phrasings ("Scanning…", "compared 0 / 1 faces", "Loading…"); scan waits now uniformly show "Scanning… · elapsed mm:ss" (with counts and ETA once known), and only candidate loading shows "Loading…"
- **Entering from the menu kept the previous "focus: Person X" filter** - the menu/library entry is meant to browse all candidates but could show a filtered subset; it now resets to show everything
- **The people-page search button tooltip did not match reality** - the old text said "compares this one person only" while the scan actually compares the whole library (named included); rewritten

**Improved**

- **Completion reminder for background scans** - scans already ran in the background and closing the dialog didn't interrupt them, but the completion toast only appeared while the dialog was open; now a toast reports "found N groups; tap to view" when the dialog is closed, and tapping reopens the dialog. "No groups found" and failure are reported too
- **Dialog text and tooltips now describe background/queue behavior** - scans run in the background, closing the dialog doesn't interrupt, and repeated searches queue automatically

</details>

<details>
<summary>Previous release v0.7.5 (2026-11-19) summary</summary>

**Fixed**

- **"Result count shown, but the list stayed empty" when searching similar persons** - when searching for several persons in a row, or while a library-wide scan was still running, the new scan request was silently dropped while the dialog still opened, showing the *previous* scan's progress and result count; the list was filtered by the current person whose scan never ran, so it appeared empty intermittently. Requests during a busy period are now queued, and the selected person is rescanned automatically once the current scan finishes
- **No feedback when the selected person had no usable faces or the scan failed** - the dialog now says so explicitly and clears the anchor filter to show all candidates; a failed library-wide scan reports "scan failed, please retry"
- **A candidate-load failure was misreported as "no candidates"** - it now explicitly says loading failed

**Improved**

- **Elapsed / estimated time in the scan progress** - the progress line now shows "elapsed mm:ss · about mm:ss remaining", estimated from the actual rate and refreshed every second
- **Persistent queue hint inside the dialog** - while queued it shows "queued: the scan for 'Person X' will start automatically when the current scan finishes" (previously only a one-off toast)

</details>

<details>
<summary>Previous release v0.7.4 (2026-11-18) summary</summary>

**Fixed**

- **The "similar persons" dialog stayed blank on Kylin** - after a library-wide scan, searching for one person's duplicates showed no results; the root cause was unreliable cross-thread signal payloads on Kylin's Qt build. All such data now crosses threads as JSON text (the 0.7.3 hardening only mitigated this)
- **The dialog's "focus: Person N" label pointed at the wrong person** - all person labels inside the dialog now use the same re-ordered numbering as the people page
- **Stale duplicate-person candidates resurfaced after renaming / merging / deleting persons** - recycled internal IDs made dead candidates point at another person; all three paths now clean up the candidate table
- **The ✕ on "Selected persons" rows did not respond** - the row's hover area swallowed the button press; ✕ now equals unchecking the row

**Improved**

- **The "User guide" dialog is now an outline** - chapter list on the left, content on the right; titles unified with menu entries; the first-run dialog is titled "First-run guide"; the license dialog gained a Chinese reference tab (unofficial translation)
- **Advanced search field hints** - short explanations beside the camera→rating inputs (person name or number, GPS accepts place names, >/&gt;= comparisons supported)

</details>

<details>
<summary>Previous release v0.7.3 (2026-11-18) summary</summary>

**New**

- **"Selected persons" panel on the people page during multi-select** - when entering selection mode the info panel is replaced by a list of checked persons (avatar / name / photo count) that updates instantly; an ✕ on each row unchecks directly, reducing mis-selection risk. Leaving selection mode or the people page restores the info panel

**Fixed**

- **Face count in the photo info panel drifted** - hiding a face updated neither the summary counter nor the advanced-search "face count" filter; both now follow the visible-face count in real time, and existing libraries are resynced automatically (once per database, no action needed)
- **The "N more" expander was missing with exactly 4 faces** - the collapse threshold did not match the single-row display, silently hiding one face without offering the expander
- **Searching by person number failed** - `person:` used internal IDs while the UI shows re-ordered numbers (renaming any person shifts them); search now matches the displayed numbers exactly
- **The "similar persons" dialog errored on open and could stall at "summarizing…"** - a misplaced decorator made the status lookup "not a function", aborting dialog initialization; candidate list refresh is now fault-tolerant per row

</details>

<details>
<summary>Previous release v0.7.2 (2026-11-18) summary</summary>

**New**

- **JPEG XL (.jxl) works out of the box** - the libjxl reference decoder `djxl` (BSD-3) now ships with the package, so manually installing pillow-jxl-plugin is no longer needed (an installed plugin still takes priority); import, thumbnails, previews, faces, text recognition and semantic vectors all work
- **Apple Live Photos (.livp) import** - .livp is a zip wrapping "HEIC still + MOV video"; it is unpacked into two ordinary records that each go through the existing pipelines, with no special-cased paths
- **FITS astronomy format import** - a built-in zero-dependency mini parser (8/16/32-bit integers and 32/64-bit floats) with percentile-stretch display
- **Multi-layer photo decoding fallback** - OpenCV → Pillow → (djxl for .jxl) → ImageMagick-if-installed, so niche-format photos no longer fail outright when OpenCV cannot decode them

**Improved**

- **Help "Exceptions" section updated**: .jxl now "supported out of the box"; FITS removed from the ImageMagick-dependency list; video playback decoding is built into the program (Qt's FFmpeg backend decodes H.264/HEVC natively — no system codec extension needed)

</details>

<details>
<summary>Previous release v0.7.1 (2026-11-15) summary</summary>

**Fixed**

- **Camera RAW files disguised as .tiff were not recognized** - some conversion tools store Nikon NEF / Canon CR2 sensor data verbatim in a .tiff container: the extension looks like an ordinary image while the content is camera RAW. They were decoded as ordinary images: some failed to import outright, others only yielded their tiny embedded thumbnail (120×160–852×640), leaving an extra-small preview, wrong dimensions, no faces and failed OCR. Files are now sniffed **by content**: a .tif/.tiff that LibRaw recognizes as camera RAW (real size clearly larger, or ordinary decoding fails outright) goes through the RAW decoding path. All 21 sample files now decode to their true 1306×978–7360×4912 images, with thumbnails, previews, dimensions, faces and OCR restored
- **Preview orientation was wrong on such files** - on some container RAW files (Nikon D3X sample) the outer TIFF orientation tag conflicts with the embedded pixel orientation, and re-rotating by the tag laid the image on its side with undetectable faces. Orientation now follows the actual decoded data; already-upright images are no longer rotated again
- **The photo viewer still showed blank or tiny previews for .tif/.tiff** - .tif/.tiff sit in the "Qt-decodable" list, so the viewer handed the original file straight to the Qt image engine, bypassing the sniffing path entirely; the integrity deep-decode check skipped them the same way. Both places now sniff for container RAW first: the viewer shows an on-demand decoded preview (cached after first use) and the deep check covers container files

**Improved**

- **Ordinary TIFF photos are completely unaffected** - sniffing applies only to .tif / .tiff extensions and requires the LibRaw size to be ≥2× the ordinary decode (or the ordinary decode to fail) before treating the file as camera RAW; sniff results are cached per file (path + mtime + size), so repeated analysis passes add no overhead
- **Viewer button "1:1 Original" renamed to "High-res" with an honest tooltip** - the view for RAW/HEIC files is a decoded preview up to 1920 px on the long edge (a long-standing design); the tooltip now says so plainly
- **Help dialog gained an "Exceptions & special notes" section** - preview resolution for RAW/HEIC, JPEG XL unsupported by default, and ImageMagick dependency for niche formats, collected in one place

> ⚠️ **After upgrading, run "Scan & import" once**: the first launch resets existing .tif / .tiff photos in the library to pending re-analysis (once per database); one scan then rebuilds their thumbnails, previews and dimensions and re-runs face / text / semantic / perceptual-hash analysis. Ordinary photos and videos are unaffected. Backing up the database first is recommended.

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
