"""Generate labeled demonstration records and query reproducible EDA views."""

from contextlib import closing
from datetime import date, timedelta
from pathlib import Path
import random
import sqlite3

SITES = ("Barat", "Tengah", "Timur")
SIGNAL_LABELS = {
    "sales_spike": "lonjakan penjualan",
    "stock_gap": "selisih stok",
    "sensor_exception": "pembacaan sensor di atas acuan",
}
FIRST = date(2026, 8, 31)
LAST = FIRST + timedelta(days=83)
SIGNAL_TRUTH = {
    ("Barat", FIRST + timedelta(days=65), "sales_spike"),
    ("Tengah", FIRST + timedelta(days=67), "stock_gap"),
    ("Timur", FIRST + timedelta(days=70), "sensor_exception"),
}


def generate(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random(291)
    rows = []
    for index, site in enumerate(SITES):
        for offset in range((LAST - FIRST).days + 1):
            day = FIRST + timedelta(days=offset)
            sales = 130 + index * 26 + offset // 4 + rng.randint(-8, 8)
            if day.weekday() >= 5:
                sales -= 36
            stock = 350 + index * 53 + rng.randint(-30, 30)
            counted = stock + rng.randint(-5, 5)
            sensor = round(42 + index * 0.8 + rng.uniform(-2, 2), 1)
            if (site, day, "sales_spike") in SIGNAL_TRUTH:
                sales += 155
            if (site, day, "stock_gap") in SIGNAL_TRUTH:
                counted -= 47
            if (site, day, "sensor_exception") in SIGNAL_TRUTH:
                sensor = 53.6
            if site == "Timur" and offset == 73:
                sensor = None
            rows.append((day.isoformat(), site, sales, stock, counted, sensor))
    rows.append(rows[48])
    with closing(sqlite3.connect(":memory:")) as source:
        source.executescript(Path(__file__).with_name("analysis.sql").read_text())
        source.executemany(
            "INSERT INTO raw_daily (day, site, sales, book_stock, counted_stock, sensor) VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )
        source.commit()
        with closing(sqlite3.connect(path)) as destination:
            source.backup(destination)


def connect(path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def snapshot(path: Path, site: str, start: date, end: date) -> dict:
    parameters = (start.isoformat(), end.isoformat(), site, site)
    window = "day BETWEEN ? AND ? AND (? = 'Semua' OR site = ?)"
    with closing(connect(path)) as connection:
        totals = connection.execute(
            f"""SELECT COUNT(*) AS days, COALESCE(SUM(sales), 0) AS sales,
                       ROUND(AVG(sensor), 1) AS avg_sensor,
                       COALESCE(SUM(ABS(counted_stock - book_stock)), 0) AS stock_gap
                FROM daily WHERE {window}""", parameters
        ).fetchone()
        distribution = connection.execute(
            f"""SELECT MIN(sales) AS sales_min, ROUND(AVG(sales), 1) AS sales_mean,
                       MAX(sales) AS sales_max,
                       MIN(ABS(counted_stock - book_stock)) AS stock_min,
                       ROUND(AVG(ABS(counted_stock - book_stock)), 1) AS stock_mean,
                       MAX(ABS(counted_stock - book_stock)) AS stock_max,
                       MIN(sensor) AS sensor_min, ROUND(AVG(sensor), 1) AS sensor_mean,
                       MAX(sensor) AS sensor_max
                FROM daily WHERE {window}""", parameters
        ).fetchone()
        weekly = connection.execute(
            f"""SELECT strftime('%Y-W%W', day) AS week, SUM(sales) AS sales,
                       SUM(ABS(counted_stock - book_stock)) AS stock_gap,
                       ROUND(AVG(sensor), 1) AS avg_sensor
                FROM daily WHERE {window} GROUP BY week ORDER BY week""", parameters
        )
        rows = connection.execute(
            f"SELECT id, day, site, kind, actual, reference FROM signals WHERE {window} ORDER BY day, site, kind",
            parameters,
        )
        quality = connection.execute(
            f"SELECT day, site, issue FROM quality WHERE {window} ORDER BY day, site, issue",
            parameters,
        )
        return {
            "site": site, "start": start.isoformat(), "end": end.isoformat(),
            "totals": dict(totals), "weekly": [dict(row) for row in weekly],
            "signals": [dict(row) for row in rows], "quality": [dict(row) for row in quality],
            "distribution": dict(distribution),
        }


def source_record(path: Path, row_id: int) -> dict | None:
    with closing(connect(path)) as connection:
        row = connection.execute("SELECT * FROM raw_daily WHERE id = ?", (row_id,)).fetchone()
        return dict(row) if row else None


def evidence(dataset: dict) -> dict[str, str]:
    totals = dataset["totals"]
    scope = f"{dataset['site']}, {dataset['start']} hingga {dataset['end']}"
    result = {
        "R0": (
            f"{scope}: {totals['days']} catatan lokasi-hari; total penjualan "
            f"{totals['sales']} unit; jumlah selisih stok absolut {totals['stock_gap']} unit."
        )
    }
    for row in dataset["signals"]:
        result[f"S{row['id']}"] = (
            f"{row['day']} {row['site']}: {SIGNAL_LABELS[row['kind']]}, nilai {row['actual']}, "
            f"acuan {row['reference']}."
        )
    return result
