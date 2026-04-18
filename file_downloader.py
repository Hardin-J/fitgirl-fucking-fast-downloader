"""
file_downloader.py — Streams a file from a URL to disk with Rich progress bar support.
Supports resuming interrupted downloads via HTTP Range requests.
"""

import os
import sys
from pathlib import Path
from typing import Optional

import requests
from rich.progress import Progress, TaskID


CHUNK_SIZE = 1024 * 256  # 256 KB chunks

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


class DownloadResult:
    def __init__(self, filename: str, success: bool, skipped: bool = False, error: str = ""):
        self.filename = filename
        self.success = success
        self.skipped = skipped
        self.error = error

    def __repr__(self):
        status = "✓ skipped" if self.skipped else ("✓ ok" if self.success else f"✗ {self.error}")
        return f"DownloadResult({self.filename!r}, {status})"


def download_file(
    url: str,
    dest_dir: Path,
    filename: str,
    progress: Optional[Progress] = None,
    task_id: Optional[TaskID] = None,
    timeout: int = 60,
) -> DownloadResult:
    """
    Download a file from `url` to `dest_dir/filename`.
    Supports HTTP Range-based resume if the file already partially exists.
    Updates the Rich progress bar if provided.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_path = dest_dir / filename

    # --- Resume support ---
    existing_size = dest_path.stat().st_size if dest_path.exists() else 0

    req_headers = dict(HEADERS)
    if existing_size > 0:
        req_headers["Range"] = f"bytes={existing_size}-"

    try:
        resp = requests.get(url, headers=req_headers, stream=True, timeout=timeout)

        # 416 = Range Not Satisfiable → file already complete
        if resp.status_code == 416:
            if progress and task_id is not None:
                progress.update(task_id, description=f"[green]✓ Already done[/green] {filename}")
            return DownloadResult(filename=filename, success=True, skipped=True)

        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0)) + existing_size
        is_resume = resp.status_code == 206  # Partial content

        if progress and task_id is not None:
            progress.update(task_id, total=total_size, completed=existing_size)

        mode = "ab" if is_resume else "wb"
        with open(dest_path, mode) as f:
            for chunk in resp.iter_content(chunk_size=CHUNK_SIZE):
                if chunk:
                    f.write(chunk)
                    if progress and task_id is not None:
                        progress.advance(task_id, len(chunk))

        # Validate: if server told us content-length, verify
        if total_size > 0:
            actual_size = dest_path.stat().st_size
            if actual_size < total_size:
                return DownloadResult(
                    filename=filename,
                    success=False,
                    error=f"Incomplete: got {actual_size}/{total_size} bytes",
                )

        return DownloadResult(filename=filename, success=True)

    except requests.RequestException as e:
        return DownloadResult(filename=filename, success=False, error=str(e))
    except OSError as e:
        return DownloadResult(filename=filename, success=False, error=f"IO error: {e}")


if __name__ == "__main__":
    # Quick standalone test
    if len(sys.argv) < 4:
        print("Usage: python file_downloader.py <url> <dest_dir> <filename>")
        sys.exit(1)

    from rich.progress import (
        BarColumn,
        DownloadColumn,
        Progress,
        TextColumn,
        TimeRemainingColumn,
        TransferSpeedColumn,
    )

    url, dest, name = sys.argv[1], sys.argv[2], sys.argv[3]
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
    ) as prog:
        tid = prog.add_task(name, total=None)
        result = download_file(url, Path(dest), name, progress=prog, task_id=tid)
    print(result)
