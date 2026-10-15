#!/usr/bin/env python3
"""Build/check the runnable HTML copies and the distributable ZIP."""
from __future__ import annotations

import argparse
import base64
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent
READABLE = ROOT / "APP_SOURCE_readable.html"
ASSET = ROOT / "assets" / "aerial_bg.jpg"
PACKAGE_HTML = ROOT / "index.html"
APP_SOURCE = PARENT / "app" / "index_src.html"
APP_HTML = PARENT / "app" / "index.html"
ARCHIVE = PARENT / "crowd-risk-monitor.zip"
SOURCE_TOKEN = 'FALLBACK.src = "__BG_B64__";'
READABLE_TOKEN = 'FALLBACK.src = ""; // The packaged index.html embeds the illustrative background image.'
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", ".cache"}


def fail(message: str) -> "NoReturn":
    print(f"ERROR: {message}", file=sys.stderr)
    raise SystemExit(1)


def assert_workspace_source_matches_readable() -> str:
    readable = READABLE.read_text(encoding="utf-8")
    if APP_SOURCE.exists():
        source = APP_SOURCE.read_text(encoding="utf-8")
        if source.count(SOURCE_TOKEN) != 1:
            fail(f"expected exactly one background placeholder in {APP_SOURCE}")
        normalized = source.replace(SOURCE_TOKEN, READABLE_TOKEN, 1)
        if normalized != readable:
            fail("APP_SOURCE_readable.html is not in sync with app/index_src.html; copy the latest source before building")
    if readable.count(READABLE_TOKEN) != 1:
        fail("expected exactly one readable background placeholder")
    return readable


def build_html(readable: str) -> str:
    if not ASSET.is_file():
        fail(f"missing illustrative background image: {ASSET}")
    encoded = base64.b64encode(ASSET.read_bytes()).decode("ascii")
    runnable = readable.replace(
        READABLE_TOKEN,
        f'FALLBACK.src = "data:image/jpeg;base64,{encoded}";',
        1,
    )
    if "__BG_B64__" in runnable or READABLE_TOKEN in runnable:
        fail("unreplaced background placeholder in generated HTML")
    check_javascript(runnable)
    return runnable


def check_javascript(html: str) -> None:
    start = html.rfind("<script>")
    end = html.rfind("</script>")
    if start < 0 or end <= start:
        fail("could not find the inline app script")
    script = html[start + len("<script>"):end]
    result = subprocess.run(
        ["node", "--check"], input=script, text=True, capture_output=True, check=False
    )
    if result.returncode:
        fail("JavaScript syntax check failed:\n" + result.stderr)


def package_files() -> list[Path]:
    files: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_DIRS for part in relative.parts):
            continue
        files.append(path)
    return sorted(files, key=lambda item: item.relative_to(ROOT).as_posix())


def archive_matches(files: list[Path]) -> bool:
    if not ARCHIVE.is_file():
        return False
    expected = {path.relative_to(ROOT).as_posix(): path.read_bytes() for path in files}
    try:
        with zipfile.ZipFile(ARCHIVE, "r") as archive:
            actual_names = set(archive.namelist())
            if actual_names != set(expected):
                return False
            return all(archive.read(name) == content for name, content in expected.items())
    except (OSError, zipfile.BadZipFile, KeyError):
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="check generated copies and ZIP without changing files")
    parser.add_argument("--also-app", action="store_true", help="also rebuild ../app/index.html from the synchronized source")
    args = parser.parse_args()

    readable = assert_workspace_source_matches_readable()
    runnable = build_html(readable)

    if args.check:
        if not PACKAGE_HTML.is_file() or PACKAGE_HTML.read_text(encoding="utf-8") != runnable:
            fail("crowd-risk-monitor/index.html is stale; rebuild the artifacts")
        if args.also_app:
            if not APP_SOURCE.exists() or not APP_HTML.is_file() or APP_HTML.read_text(encoding="utf-8") != runnable:
                fail("app/index.html is missing or stale; rebuild the artifacts")
        files = package_files()
        if not archive_matches(files):
            fail("crowd-risk-monitor.zip is missing, stale, or has different contents")
        print("HTML copies, inline JavaScript, and ZIP contents are in sync.")
        return

    PACKAGE_HTML.write_text(runnable, encoding="utf-8")
    if args.also_app:
        if not APP_SOURCE.exists():
            fail(f"--also-app requested, but {APP_SOURCE} is not present")
        APP_HTML.write_text(runnable, encoding="utf-8")

    files = package_files()
    with zipfile.ZipFile(ARCHIVE, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())

    check_javascript(PACKAGE_HTML.read_text(encoding="utf-8"))
    print(f"Built {PACKAGE_HTML}")
    if args.also_app:
        print(f"Built {APP_HTML}")
    print(f"Built {ARCHIVE} with {len(files)} files")


if __name__ == "__main__":
    main()
