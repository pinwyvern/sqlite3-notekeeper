#!/usr/bin/env python3
import argparse, re, sqlite3
from datetime import date
from pathlib import Path

DB_DEFAULT = "notes.db"
FILENAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})_(.+)\.txt$", re.I)
WORD_RE = re.compile(r"\b[\w'-]+\b", re.UNICODE)


def connect(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL UNIQUE,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            day INTEGER NOT NULL,
            hash TEXT NOT NULL,
            word_count INTEGER NOT NULL,
            content TEXT NOT NULL,
            mtime_ns INTEGER NOT NULL,
            file_size INTEGER NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_notes_date
            ON notes(year, month, day);
        CREATE INDEX IF NOT EXISTS idx_notes_hash
            ON notes(hash);
    """)
    conn.commit()
    return conn


def index_notes(conn, directory, recursive=False):
    directory = Path(directory).resolve()
    if not directory.is_dir():
        raise SystemExit(f"Not a directory: {directory}")

    files = directory.rglob("*.txt") if recursive else directory.glob("*.txt")
    added = updated = unchanged = skipped = 0

    for path in sorted(files):
        match = FILENAME_RE.match(path.name)
        if not match:
            skipped += 1
            continue

        year, month, day = map(int, match.groups()[:3])
        note_hash = match.group(4)
        try:
            date(year, month, day)
            stat = path.stat()
        except (ValueError, OSError) as exc:
            print(f"Skipping {path.name}: {exc}")
            skipped += 1
            continue

        filename = path.relative_to(directory).as_posix()
        existing = conn.execute(
            "SELECT id, mtime_ns, file_size FROM notes WHERE filename=?",
            (filename,),
        ).fetchone()

        if (existing and existing["mtime_ns"] == stat.st_mtime_ns
                and existing["file_size"] == stat.st_size):
            unchanged += 1
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError as exc:
            print(f"Could not read {path}: {exc}")
            skipped += 1
            continue

        word_count = len(WORD_RE.findall(content))
        conn.execute("""
            INSERT INTO notes (
                filename, year, month, day, hash, word_count,
                content, mtime_ns, file_size
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(filename) DO UPDATE SET
                year=excluded.year, month=excluded.month,
                day=excluded.day, hash=excluded.hash,
                word_count=excluded.word_count,
                content=excluded.content,
                mtime_ns=excluded.mtime_ns,
                file_size=excluded.file_size
        """, (
            filename, year, month, day, note_hash, word_count,
            content, stat.st_mtime_ns, stat.st_size,
        ))

        if existing:
            updated += 1
        else:
            added += 1

    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    print(f"Added: {added}  Updated: {updated}")
    print(f"Unchanged: {unchanged}  Skipped: {skipped}")
    print(f"Database: {total} total notes")


def show_note(conn, note_id):
    note = conn.execute(
        "SELECT * FROM notes WHERE id=?", (note_id,)
    ).fetchone()
    if not note:
        print(f"No note found with ID {note_id}.")
        return

    for key, label in (
        ("id", "ID"), ("year", "YEAR"), ("month", "MONTH"),
        ("day", "DAY"), ("hash", "HASH"),
        ("word_count", "WORD COUNT"), ("filename", "FILENAME"),
    ):
        print(f"{label + ':':12}{note[key]}")
    print("-" * 60, "\nCONTENT:")
    print(note["content"])


def search_notes(conn, term, year=None, limit=50):
    sql = """
        SELECT id, year, month, day, hash, word_count, filename,
               snippet(content, 1, 2, 3, '...', 24) AS preview
        FROM notes WHERE instr(lower(content), lower(?)) > 0
    """
    params = [term]
    if year is not None:
        sql += " AND year=?"
        params.append(year)
    sql += " ORDER BY year, month, day, id LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    print(f"Found {len(rows)} matching note(s):")
    for row in rows:
        print(
            f"\nID {row['id']} | "
            f"{row['year']:04}-{row['month']:02}-{row['day']:02} | "
            f"{row['hash']} | {row['word_count']} words"
        )
        print(f"  {row['filename']}\n  {row['preview'] or ''}")


def list_notes(conn, year=None, limit=50):
    sql = """
        SELECT id, year, month, day, hash, word_count, filename
        FROM notes
    """
    params = []
    if year is not None:
        sql += " WHERE year=?"
        params.append(year)
    sql += " ORDER BY year, month, day, id LIMIT ?"
    params.append(limit)

    for row in conn.execute(sql, params):
        print(
            f"{row['id']:>6}  {row['year']:04}-"
            f"{row['month']:02}-{row['day']:02}  "
            f"{row['hash']:<20} {row['word_count']:>5} words  "
            f"{row['filename']}"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Index and search a directory of text notes."
    )
    parser.add_argument("--db", default=DB_DEFAULT,
                        help=f"Database file (default: {DB_DEFAULT})")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("index", help="Index or update notes")
    p.add_argument("directory")
    p.add_argument("--recursive", action="store_true",
                   help="Also scan subdirectories")

    p = sub.add_parser("show", help="Display a note by ID")
    p.add_argument("id", type=int)

    p = sub.add_parser("search", help="Search note contents")
    p.add_argument("term")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int, default=50)

    p = sub.add_parser("list", help="List indexed notes")
    p.add_argument("--year", type=int)
    p.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    conn = connect(args.db)
    try:
        if args.command == "index":
            index_notes(conn, args.directory, args.recursive)
        elif args.command == "show":
            show_note(conn, args.id)
        elif args.command == "search":
            search_notes(conn, args.term, args.year, args.limit)
        elif args.command == "list":
            list_notes(conn, args.year, args.limit)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
