"""Build the sample operations handoff and printable reports."""

from datetime import date
from html import escape

_SIGNAL_LABELS = {
    "sales_spike": "Lonjakan penjualan",
    "stock_gap": "Selisih stok",
    "sensor_exception": "Pembacaan sensor melewati ambang contoh",
}

_QUALITY_LABELS = {
    "duplicate": "Catatan duplikat",
    "missing_sensor": "Pembacaan sensor kosong",
}

_SAMPLE_NOTICE = "Laporan memakai data sintetis dan contoh penugasan. Draf eskalasi tetap di aplikasi."


def workflow(dataset: dict) -> dict:
    """Show a supervisor request, program follow-up, and a draft escalation."""
    sensor = next((row for row in dataset["signals"] if row["kind"] == "sensor_exception"), None)
    if sensor:
        reference = f"S{sensor['id']}"
        sensor_evidence = (
            f"{reference}, {sensor['site']}, {sensor['day']}. "
            f"Pembacaan {sensor['actual']}, ambang contoh {sensor['reference']}."
        )
        escalation = {
            "subject": f"Draf eskalasi untuk penanggung jawab dan HSE • {reference}",
            "message": (
                f"{sensor_evidence} Petugas lokasi perlu memeriksa catatan sumber dan "
                "mengonfirmasi kondisi di lokasi. Tim HSE meninjau tindak lanjut sesuai "
                "prosedur yang berlaku. Dampak lingkungan belum terkonfirmasi."
            ),
            "owner": "Petugas lokasi dan tim HSE",
            "status": "Draf • menunggu tinjauan • belum dikirim",
        }
    else:
        sensor_evidence = "Belum ada sinyal sensor dalam data yang ditinjau."
        escalation = {
            "subject": "Draf eskalasi untuk penanggung jawab dan HSE",
            "message": sensor_evidence,
            "owner": "Petugas lokasi dan tim HSE",
            "status": "Belum ada kasus untuk ditinjau",
        }

    missing = next((row for row in dataset["quality"] if row["issue"] == "missing_sensor"), None)
    missing_evidence = (
        f"{missing['site']}, {missing['day']}. Pembacaan sensor kosong."
        if missing else "Belum ada catatan sensor kosong dalam data yang ditinjau."
    )
    cutoff = date.fromisoformat(dataset["end"])

    return {
        "requests": [
            {
                "title": "Arahan atasan • ringkasan operasi mingguan",
                "owner": "Penanggung jawab operasi",
                "status": "Ruang lingkup ditetapkan",
                "acceptance": (
                    "Tampilkan penjualan, selisih stok, dan sinyal sensor per lokasi. "
                    "Sertakan periode, tautan bukti, dan pemilik tindak lanjut."
                ),
            },
            {
                "title": "Pemeriksaan • angka dan sumber",
                "owner": "Analis operasi",
                "status": "Ringkasan dari kueri tersedia",
                "acceptance": "Cocokkan angka dengan dasbor dan buka catatan sumber untuk setiap sinyal.",
            },
            {
                "title": "Serah terima • laporan dan keputusan",
                "owner": "Penanggung jawab operasi",
                "status": "Menunggu tinjauan",
                "acceptance": "Tinjau laporan, lalu tentukan pemilik dan tenggat untuk temuan terbuka.",
            },
        ],
        "risks": [
            {
                "title": "Pembacaan tinggi memerlukan verifikasi dampak lingkungan",
                "owner": "Petugas lokasi",
                "evidence": sensor_evidence,
                "status": "Menunggu verifikasi" if sensor else "Belum ada sinyal",
            },
            {
                "title": "Kesenjangan pemantauan karena pembacaan kosong",
                "owner": "Penanggung jawab pencatatan sensor",
                "evidence": missing_evidence,
                "status": "Tindak lanjut terbuka" if missing else "Belum ada catatan kosong",
            },
        ],
        "programs": [
            {
                "title": "K3L • tinjau catatan pemantauan sensor",
                "owner": "Koordinator K3L",
                "due": "2026-11-18",
                "status": (
                    "Lewat tenggat • bukti tinjauan belum tersedia"
                    if cutoff > date(2026, 11, 18) else "Bukti tinjauan belum tersedia"
                ),
            },
            {
                "title": "K3L • periksa tindak lanjut sinyal lingkungan",
                "owner": "Tim HSE",
                "due": "2026-11-24",
                "status": (
                    "Lewat tenggat • menunggu konfirmasi"
                    if cutoff > date(2026, 11, 24) else "Terjadwal • menunggu konfirmasi"
                ),
            },
        ],
        "escalation": escalation,
    }


def _table(caption: str, headings: tuple[str, ...], rows: list[tuple]) -> str:
    columns = "".join(f'<th scope="col">{escape(heading)}</th>' for heading in headings)
    data = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(value))}</td>" for value in row)
        data.append(f"<tr>{cells}</tr>")
    if not data:
        data.append(f'<tr><td colspan="{len(headings)}">Tidak ada catatan untuk pilihan ini.</td></tr>')
    body = "".join(data)
    return f"""<div class="table-wrap"><table><caption>{escape(caption)}</caption>
<thead><tr>{columns}</tr></thead><tbody>{body}</tbody></table></div>"""


def _findings(dataset: dict) -> str:
    totals = dataset["totals"]
    stats = _table(
        "Total periode",
        ("Catatan lokasi-hari", "Penjualan (unit)", "Total selisih stok absolut (unit)"),
        [(totals["days"], totals["sales"], totals["stock_gap"])],
    )
    signals = _table(
        "Sinyal untuk ditinjau",
        ("Sumber", "Lokasi", "Tanggal", "Temuan", "Nilai", "Acuan"),
        [
            (
                f"S{row['id']}", row["site"], row["day"], _SIGNAL_LABELS[row["kind"]],
                row["actual"], row["reference"],
            )
            for row in dataset["signals"]
        ],
    )
    quality = _table(
        "Kualitas data",
        ("Lokasi", "Tanggal", "Catatan"),
        [
            (row["site"], row["day"], _QUALITY_LABELS[row["issue"]])
            for row in dataset["quality"]
        ],
    )
    return stats + signals + quality


def _evaluation(report: dict | None) -> str:
    summary = (report or {}).get("summary", {})
    comparisons = []
    for key, label in (("baseline", "Prompt awal"), ("refined", "Prompt revisi")):
        row = summary.get(key)
        if isinstance(row, dict) and "passed" in row and "total" in row:
            comparisons.append((label, row["passed"], row["total"]))
    if len(comparisons) != 2:
        return "<p>Hasil evaluasi prompt belum tersedia.</p>"
    return _table("Pemeriksaan prompt", ("Versi", "Kasus lulus", "Jumlah kasus"), comparisons)


def _next_actions(dataset: dict) -> str:
    profile = workflow(dataset)
    return _table(
        "Tindak lanjut",
        ("Penanggung jawab", "Tindak lanjut", "Status"),
        [
            (row["owner"], row["acceptance"], row["status"])
            for row in profile["requests"][1:]
        ] + [
            (row["owner"], row["title"], row["status"])
            for row in profile["risks"]
        ],
    )


_LIMITATIONS = """
<p>Ambang diuji pada contoh yang ditanamkan dalam data sintetis. Verifikasi setiap sinyal
dan draf terhadap catatan sumber sebelum mengambil keputusan operasional.</p>
"""


def render_report(dataset: dict, evaluation: dict | None, *, briefing: bool) -> str:
    """Render status notes or the guided briefing from the same dashboard facts."""
    scope = escape(f"{dataset['site']} · {dataset['start']} hingga {dataset['end']}")
    if briefing:
        title = "Paparan Operasi"
        sections = f"""
<section><h2>Persiapan tinjauan mingguan</h2>
<ol>
<li>Buka dasbor, pilih lokasi dan periode, lalu periksa perubahan pada tren mingguan.</li>
<li>Buka sinyal dan cocokkan angka dengan catatan sumber.</li>
<li>Gunakan prompt ringkasan, bandingkan draf dengan sumber, lalu revisi sebelum serah terima.</li>
<li>Tinjau tenggat program K3L dan draf eskalasi sebelum menetapkan tindak lanjut.</li>
</ol></section>
<section><h2>Temuan operasional</h2>{_findings(dataset)}</section>
<section><h2>Hasil evaluasi dan batasan</h2>{_evaluation(evaluation)}{_LIMITATIONS}</section>
<section><h2>Keputusan dan pemilik</h2>{_next_actions(dataset)}</section>
"""
    else:
        title = "Laporan Status Operasi"
        sections = f"""
<section><h2>Status dan ruang lingkup</h2>
<p>Tinjau ringkasan dan temuan dari dasbor sebelum serah terima.</p>
{_findings(dataset)}</section>
<section><h2>Evaluasi dan risiko</h2>{_evaluation(evaluation)}{_LIMITATIONS}</section>
<section><h2>Tindakan berikutnya</h2>{_next_actions(dataset)}</section>
"""
    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    body {{ font: 1rem/1.55 system-ui, sans-serif; color: #132a30; background: #f5f7f7; padding: 1rem; }}
    main {{ max-width: 70rem; margin: auto; padding: clamp(1rem, 3vw, 2rem); background: white; }}
    a {{ color: #135961; }}
    h1, h2 {{ line-height: 1.2; }}
    section {{ margin-block: 1.75rem; }}
    .scope {{ color: #35505a; }}
    .notice {{ background: #eaf2f2; padding: .75rem; border-inline-start: .25rem solid #297377; }}
    .table-wrap {{ overflow-x: auto; margin-block: 1rem; }}
    table {{ border-collapse: collapse; min-width: 100%; }}
    caption {{ text-align: start; font-weight: 700; margin-block: .25rem; }}
    th, td {{ text-align: start; padding: .45rem; border-block-end: 1px solid #d5dddd; }}
    @media print {{
      body, main {{ background: white; padding: 0; }}
      nav {{ display: none; }}
      h2 {{ break-after: avoid; }}
      tr {{ break-inside: avoid; }}
    }}
  </style>
</head>
<body>
<main>
<nav aria-label="Asisten Operasional"><a href="/">Kembali ke dasbor</a></nav>
<header><h1>{title}</h1><p class="scope">{scope}</p><p class="notice">{_SAMPLE_NOTICE}</p></header>
{sections}
</main>
</body>
</html>"""
