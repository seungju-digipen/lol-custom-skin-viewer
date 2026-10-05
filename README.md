# LoL Custom Skin Viewer

[English](README.md) | [한국어](README.ko.md)

A local Windows viewer for League of Legends custom skin models and animations. It reads mod assets and combines them with animations extracted from your installed game.

## Features

- Import ZIP/FANTOME archives or extracted mod folders.
- Upload a collection folder once and select mods from a saved library.
- Convert selected mods on demand and cache results.
- Rotate, zoom, choose animations, pause playback, and adjust playback speed and background color.
- Decode TEX/DDS textures and read per-material texture assignments from BIN files.
- Prefer mod textures over original assets and apply initial submesh visibility.
- Inspect the model's bind pose without animation.

## Requirements and setup

Windows x64, Python 3.11 or newer, an installed copy of League of Legends, and an internet connection for initial setup are required.

1. Run `./setup.ps1` from PowerShell. This installs Python dependencies and downloads conversion tools and a local .NET 8 runtime into `tools/`.
2. Edit `config.json` and set `champions_dir` to your game's `Game/DATA/FINAL/Champions` directory. Alternatively, set the `LOL_CHAMPIONS_DIR` environment variable.
3. Run `start.cmd`.
4. Open http://127.0.0.1:8766/ in your browser.

Mods are processed locally. The browser's 3D viewer library loads from Google's CDN and requires internet access. The server binds only to 127.0.0.1 and does not modify your original game files.

## Usage

For a single mod, select a ZIP/FANTOME and click **모드 열기** (Open mod).

For a collection, choose **모드 모음 폴더** (Mod collection folder), upload the parent folder, then use **저장된 폴더 → 모드 목록 → 선택한 모드 보기** (Saved folder → Mod list → View selected mod).

Libraries and conversion caches are stored in `.data/`. Individual files are limited to 300 MB; the browser's collection upload limit is 5 GB. The current UI is in Korean.

## Hosting

This version is designed for local use. GitHub stores the source code; GitHub Pages serves static files and cannot run this Python backend. A remote deployment would also need access to game assets, compatible conversion tools, persistent storage, and authentication. It cannot automatically read a visitor's installed game directory.

For a hosted version, either build a browser-only viewer for already-converted GLB files or use a separate backend service for conversion. The existing server is not ready to be exposed to the public internet.

## Known limitations

- Only the first model is displayed; selecting multiple models/forms is not implemented.
- Game shaders, skill effects, audio, and animation-dependent prop visibility are not reproduced.
- Custom skeletons may not be compatible with the original animations.
- Some TEX/DDS/BIN formats may fail to convert or require filename-based texture matching.
- Extract RAR/7Z archives before importing them.
- This is a personal local prototype, not a production hosting server.

## Source and external tools

- `server.py`: uploads, libraries, original asset extraction, texture mapping, and GLB conversion API.
- `index.html`: browser UI.
- `setup.ps1`: local dependency setup.
- [lol2gltf](https://github.com/Crauzer/lol2gltf)
- [wadtools](https://github.com/LeagueToolkit/wadtools)
- [ltk-tex-utils](https://github.com/LeagueToolkit/ltk-tex-utils)
- [ritobin](https://github.com/moonshadow565/ritobin)
- [model-viewer](https://github.com/google/model-viewer)

External binaries are not included in this repository and remain subject to their own licenses. No original game assets, custom mods, models, images, or personal file paths are included. This project is not affiliated with Riot Games.
