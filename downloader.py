#!/usr/bin/env python3
"""
downloader.py — Game File Downloader
=====================================
Automatically downloads all .rar files linked from a FitGirl Repacks paste page.

Usage:
    python downloader.py --url <paste_url> --output <directory> [options]

Options:
    --url       URL of the paste page containing download links  [required]
    --output    Directory to save downloaded files               [required]
    --workers   Number of Playwright resolve workers (default: 1)
    --delay     Seconds to wait between each resolve (default: 2)
    --dry-run   Print links without downloading
    --resume    Skip files that already exist (default: True)
"""

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import List, Optional

from rich import print as rprint
from rich.console import Console
from rich.panel import Panel
from rich.progress import (
    BarColumn,
    DownloadColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)
from rich.table import Table
from rich.text import Text

from fuckingfast import resolve_download_url
from file_downloader import download_file, DownloadResult
from scraper import scrape_links_async, DownloadLink

console = Console()


# ── Banner ─────────────────────────────────────────────────────────────────────

BANNER = r"""
  ____                        ____                      _                 _
 / ___| __ _ _ __ ___   ___  |  _ \  _____      ___ __ | | ___   __ _  __| | ___ _ __
| |  _ / _` | '_ ` _ \ / _ \ | | | |/ _ \ \ /\ / / '_ \| |/ _ \ / _` |/ _` |/ _ \ '__|
| |_| | (_| | | | | | |  __/ | |_| | (_) \ V  V /| | | | | (_) | (_| | (_| |  __/ |
 \____|\__,_|_| |_| |_|\___| |____/ \___/ \_/\_/ |_| |_|_|\___/ \__,_|\__,_|\___|_|
"""


def print_banner():
    console.print(Panel(
        Text(BANNER, style="bold cyan", justify="center"),
        subtitle="[dim]FitGirl Repacks · fuckingfast.co · Auto Downloader[/dim]",
        border_style="cyan",
    ))


# ── Summary table ──────────────────────────────────────────────────────────────

def print_summary(results: List[DownloadResult]):
    table = Table(title="Download Summary", border_style="blue", show_lines=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("File", style="cyan", no_wrap=False)
    table.add_column("Status", justify="center")

    ok = skipped = failed = 0
    for i, r in enumerate(results, 1):
        if r.skipped:
            status = "[yellow]⏭  Skipped[/yellow]"
            skipped += 1
        elif r.success:
            status = "[green]✓  Done[/green]"
            ok += 1
        else:
            status = f"[red]✗  {r.error[:60]}[/red]"
            failed += 1
        table.add_row(str(i), r.filename, status)

    console.print(table)
    console.print(
        f"\n[bold green]✓ {ok} downloaded[/bold green]  "
        f"[yellow]⏭ {skipped} skipped[/yellow]  "
        f"[red]✗ {failed} failed[/red]"
    )


# ── Core logic ─────────────────────────────────────────────────────────────────

async def run(
    paste_url: str,
    output_dir: Path,
    delay: float,
    dry_run: bool,
    resume: bool,
):
    print_banner()

    # ── Step 1: Scrape paste page ──────────────────────────────────────────────
    console.rule("[bold blue]Step 1 · Scraping paste page[/bold blue]")
    console.print(f"  URL: [link={paste_url}]{paste_url}[/link]")

    with console.status("[cyan]Fetching download links…[/cyan]"):
        try:
            links: List[DownloadLink] = await scrape_links_async(paste_url)
        except Exception as e:
            console.print(f"[red]Error scraping paste page:[/red] {e}")
            sys.exit(1)

    if not links:
        console.print("[red]No fuckingfast.co links found on the paste page. Exiting.[/red]")
        sys.exit(1)

    console.print(f"  [green]Found {len(links)} download link(s)[/green]")

    if dry_run:
        console.rule("[bold yellow]Dry Run — Links found[/bold yellow]")
        for i, lnk in enumerate(links, 1):
            console.print(f"  [dim]{i:>4}.[/dim] [cyan]{lnk.filename}[/cyan]")
            console.print(f"        [dim]{lnk.url}[/dim]")
        console.print(f"\n[bold]Total: {len(links)} file(s). (dry-run, nothing downloaded)[/bold]")
        return

    # ── Step 2: Resolve real download URLs ────────────────────────────────────
    console.rule("[bold blue]Step 2 · Resolving real download URLs[/bold blue]")
    console.print("  [dim]Using headless Chromium via Playwright…[/dim]")
    output_dir.mkdir(parents=True, exist_ok=True)

    resolved: List[tuple[DownloadLink, Optional[str]]] = []
    results: List[DownloadResult] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold]{task.description}"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        console=console,
        transient=False,
    ) as resolve_progress:
        resolve_task = resolve_progress.add_task("Resolving URLs", total=len(links))

        for lnk in links:
            dest_path = output_dir / lnk.filename

            # Skip if resume mode and file already done
            if resume and dest_path.exists() and dest_path.stat().st_size > 0:
                resolve_progress.advance(resolve_task)
                resolved.append((lnk, None))  # None = will be skipped
                results.append(DownloadResult(filename=lnk.filename, success=True, skipped=True))
                console.print(f"  [yellow]⏭  Skipping (exists):[/yellow] {lnk.filename}")
                continue

            resolve_progress.update(resolve_task, description=f"Resolving · {lnk.filename[:50]}")
            real_url = await resolve_download_url(lnk.url)
            resolved.append((lnk, real_url))

            if real_url:
                console.print(f"  [green]✓[/green] {lnk.filename}")
            else:
                console.print(f"  [red]✗ Could not resolve:[/red] {lnk.filename}")
                results.append(DownloadResult(filename=lnk.filename, success=False, error="URL resolve failed"))

            resolve_progress.advance(resolve_task)

            if delay > 0:
                await asyncio.sleep(delay)

    # ── Step 3: Download files ────────────────────────────────────────────────
    to_download = [(lnk, url) for lnk, url in resolved if url is not None]

    if not to_download:
        console.print("[yellow]Nothing to download (all resolved to None or skipped).[/yellow]")
    else:
        console.rule(f"[bold blue]Step 3 · Downloading {len(to_download)} file(s)[/bold blue]")
        console.print(f"  Output: [cyan]{output_dir}[/cyan]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=30),
            DownloadColumn(),
            TransferSpeedColumn(),
            TimeRemainingColumn(),
            console=console,
        ) as dl_progress:
            overall_task = dl_progress.add_task(
                f"[bold]Overall (0/{len(to_download)})",
                total=len(to_download),
            )

            for i, (lnk, real_url) in enumerate(to_download):
                file_task: TaskID = dl_progress.add_task(
                    lnk.filename[:45],
                    total=None,
                    start=True,
                )
                result = download_file(
                    url=real_url,
                    dest_dir=output_dir,
                    filename=lnk.filename,
                    progress=dl_progress,
                    task_id=file_task,
                )
                results.append(result)
                dl_progress.remove_task(file_task)
                dl_progress.update(
                    overall_task,
                    advance=1,
                    description=f"[bold]Overall ({i+1}/{len(to_download)})",
                )

    # ── Summary ────────────────────────────────────────────────────────────────
    console.rule("[bold blue]Summary[/bold blue]")
    print_summary(results)


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        prog="downloader",
        description="Auto-download game files from a FitGirl paste page.",
    )
    parser.add_argument("--url", required=True, help="Paste page URL containing download links")
    parser.add_argument("--output", required=True, help="Output directory for downloaded files")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between URL resolves (default: 2)")
    parser.add_argument("--dry-run", action="store_true", help="Show links without downloading")
    parser.add_argument("--no-resume", action="store_true", help="Re-download existing files")

    args = parser.parse_args()

    output_dir = Path(args.output).expanduser().resolve()
    resume = not args.no_resume

    asyncio.run(run(
        paste_url=args.url,
        output_dir=output_dir,
        delay=args.delay,
        dry_run=args.dry_run,
        resume=resume,
    ))


if __name__ == "__main__":
    main()
