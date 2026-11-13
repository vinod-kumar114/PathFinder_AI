"""Small shared helpers for the regression tests (synthetic data only)."""

import json
from pathlib import Path

import pandas as pd
from openpyxl import Workbook

from src.database import get_connection


def write_sheet(path, rows, sheet="Scholarships", title_rows=0):
    """Write rows (list of dicts) to an xlsx; optional title rows above the header."""
    path = Path(path)
    df = pd.DataFrame(rows)
    with pd.ExcelWriter(str(path), engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet, startrow=title_rows)
    return path


def write_workbook(path, sheets):
    """sheets: {sheet name: list of header+data row lists}"""
    wb = Workbook()
    wb.remove(wb.active)
    for name, grid in sheets.items():
        ws = wb.create_sheet(name)
        for r in grid:
            ws.append(r)
    wb.save(str(path))
    return Path(path)


def all_rows(sql="SELECT * FROM scholarships ORDER BY id"):
    conn = get_connection()
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    finally:
        conn.close()


def count_rows():
    return len(all_rows())


def insert_row(**fields):
    """Insert a scholarship row directly (after init_db)."""
    conn = get_connection()
    try:
        cols = ", ".join(fields)
        marks = ", ".join("?" for _ in fields)
        conn.execute(f"INSERT INTO scholarships ({cols}) VALUES ({marks})", list(fields.values()))
        conn.commit()
    finally:
        conn.close()


def raw(row):
    return json.loads(row["raw_data"])
