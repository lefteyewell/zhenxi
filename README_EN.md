# Zhenxi (PhotoManager)

**Zhenxi** — local photo management software for photographers: fast retrieval (faces / text /
EXIF / folders / arbitrary combinations), thumbnails and full-size viewing,
batch export at common resolutions — **the app never deletes your original
files**.

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
