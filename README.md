# Game File Downloader

A Python CLI tool for automatically downloading all `.rar` game files from a FitGirl Repacks paste page (via `fuckingfast.co`).

## Features

- 🕷️ **Auto-scrape** — reads all `fuckingfast.co` links from the paste page
- 🤖 **Headless Chromium** — uses Playwright to resolve real CDN download URLs
- 📥 **Streaming downloads** — efficient chunked downloads with live progress bars
- ♻️ **Resume support** — skips files that are already fully downloaded
- 📊 **Rich terminal UI** — per-file speed, ETA, and a final summary table
- 🧪 **Dry-run mode** — preview all links without downloading

---

## Requirements

- Python 3.9+
- ~150 MB disk space for Playwright's Chromium browser

---

## Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install Playwright's headless Chromium browser
playwright install chromium
```

---

## Usage

```bash
python downloader.py --url "<paste_page_url>" --output "<download_directory>"
```

### Arguments

| Argument | Required | Default | Description |
|----------|----------|---------|-------------|
| `--url` | ✅ | — | URL of the paste page (e.g. `paste.fitgirl-repacks.site/...`) |
| `--output` | ✅ | — | Directory to save downloaded `.rar` files |
| `--delay` | ❌ | `2.0` | Seconds to wait between URL resolves (reduces IP block risk) |
| `--dry-run` | ❌ | off | Print all found links without downloading |
| `--no-resume` | ❌ | off | Re-download files even if they already exist |

---

## Examples

```bash
# Standard download
python downloader.py \
  --url "https://paste.fitgirl-repacks.site/?d0f6e0541d9a75f6#..." \
  --output ~/Downloads/WWE_2K23

# Preview links only (no downloads)
python downloader.py \
  --url "https://paste.fitgirl-repacks.site/?d0f6e0541d9a75f6#..." \
  --output ~/Downloads/WWE_2K23 \
  --dry-run

# Slower, safer (5s delay between each resolve)
python downloader.py \
  --url "https://paste.fitgirl-repacks.site/?d0f6e0541d9a75f6#..." \
  --output ~/Downloads/WWE_2K23 \
  --delay 5
```

---

## How It Works

```
Paste Page URL
     │
     ▼
[scraper.py]  ──── Fetches paste page HTML, extracts all fuckingfast.co links
     │
     ▼
[fuckingfast.py] ── Launches headless Chromium, clicks the download button,
                    intercepts the real CDN download URL via network monitoring
     │
     ▼
[file_downloader.py] ── Streams each .rar file to disk with HTTP Range resume
     │
     ▼
[downloader.py] ──── Coordinates everything, shows Rich terminal progress UI
```

---

## Project Structure

```
Game downloader/
├── downloader.py       # Main CLI entry point
├── scraper.py          # Paste page link extractor
├── fuckingfast.py      # Playwright URL resolver
├── file_downloader.py  # HTTP streaming downloader
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

---

## Troubleshooting

**"No links found"** — The paste page may have changed its HTML structure. Run `python scraper.py <url>` to debug.

**"URL resolve failed"** — fuckingfast.co may have changed its button selectors. Increase `--delay` to avoid rate limits.

**Download stops mid-way** — Re-run the same command. Resume mode will skip completed files and continue from where it left off.
