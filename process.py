#!/usr/bin/env python3

import argparse
import hashlib
import os
import tempfile
from datetime import date
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = BASE_DIR / "inbox"
OUTPUT_DIR = BASE_DIR / "archive"


def archive_notes(input_dir: Path, output_dir: Path) -> None:
    if not input_dir.is_dir():
        raise SystemExit(f"Input directory does not exist: {input_dir}")
    if input_dir.resolve() == output_dir.resolve():
        raise SystemExit("Input and output directories must be different.")

    output_dir.mkdir(parents=True, exist_ok=True)
    archived = skipped = 0

    for source in sorted(input_dir.iterdir()):
        if not source.is_file() or source.is_symlink():
            continue

        content = source.read_bytes()
        digest = hashlib.sha256(content).hexdigest()
        filename = f"{date.today().isoformat()}_{digest}.txt"
        destination = output_dir / filename

        fd, temp_name = tempfile.mkstemp(dir=output_dir)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "wb") as temp:
                temp.write(content)
                temp.flush()
                os.fsync(temp.fileno())

            try:
                os.link(temp_path, destination)
            except FileExistsError:
                if destination.read_bytes() != content:
                    raise RuntimeError(
                        f"Hash collision or conflicting file: {destination}"
                    )
                skipped += 1
        finally:
            temp_path.unlink(missing_ok=True)

        source.unlink()
        archived += 1
        print(f"Archived: {source.name} -> {destination.name}")

    print(f"\nDone. Archived: {archived}, duplicates skipped: {skipped}")


def main() -> None:
    archive_notes(INPUT_DIR, OUTPUT_DIR)


if __name__ == "__main__":
    main()