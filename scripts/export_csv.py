#!/usr/bin/env python3
"""Export local demo requests as a spreadsheet-safe, Google Sheets-ready CSV."""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path
from typing import Any

# Also support `python scripts/export_csv.py` from the repository root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from store import Store  # noqa: E402

COLUMNS = {
    "appointments": [
        "id",
        "call_id",
        "patient_name",
        "phone",
        "service_id",
        "starts_at",
        "ends_at",
        "notes",
        "status",
        "created_at",
    ],
    "messages": ["id", "call_id", "name", "phone", "message", "created_at"],
}


def safe_csv_cell(value: Any) -> Any:
    """Neutralize formula prefixes, including ones hidden behind whitespace."""
    if isinstance(value, str) and (
        value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n"))
    ):
        return "'" + value
    return value


def export_csv(store: Store, output: str | Path, table: str = "appointments") -> int:
    if table not in COLUMNS:
        raise ValueError("table must be appointments or messages")
    rows = store.list_appointments() if table == "appointments" else store.list_messages()
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS[table])
        writer.writeheader()
        writer.writerows({key: safe_csv_cell(row[key]) for key in COLUMNS[table]} for row in rows)
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/clinic.sqlite3", help="Existing SQLite database path")
    parser.add_argument("--output", default="exports/appointments.csv")
    parser.add_argument("--table", choices=COLUMNS, default="appointments")
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error(f"database does not exist: {args.db}; run a demo call first")
    with Store(args.db) as store:
        count = export_csv(store, args.output, args.table)
    print(
        f"Exported {count} {args.table} to {args.output}. Timestamps are UTC; import through Google Sheets File > Import."
    )


if __name__ == "__main__":
    main()
