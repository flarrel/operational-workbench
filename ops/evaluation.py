"""Paired, fixed-case evaluation for four Indonesian operational drafting tasks."""

from dataclasses import dataclass
import re
from time import perf_counter

from .prompts import VERSION, DraftError, generate


@dataclass(frozen=True)
class Case:
    id: str
    task: str
    brief: str
    facts: dict[str, str]
    required_ids: tuple[str, ...] = ()
    required_values: tuple[str, ...] = ()


# Cases are fixed before comparing outputs. The missing-data cases each contain a distractor.
CASES = (
    Case("S1", "summary", "Ringkas perubahan penjualan dan sisa stok Barat.",
         {"A": "Penjualan Barat naik menjadi 212 unit.", "B": "Stok akhir Barat 314 unit."},
         ("A", "B"), ("212", "314")),
    Case("S2", "summary", "Ringkas status pemeriksaan dan penjualan.",
         {"A": "Ada 27 catatan yang perlu diperiksa.", "B": "Total penjualan 184 unit."},
         ("A", "B"), ("27", "184")),
    Case("S3", "summary", "Ringkas selisih karton dan catatan pengiriman.",
         {"A": "Stok fisik kurang 38 karton.", "B": "70 karton disiapkan untuk pengiriman."},
         ("A", "B"), ("38", "70")),
    Case("S4", "summary", "Ringkas laba bersih periode ini.",
         {"A": "Penjualan mencapai 278 unit."}),
    Case("C1", "content", "Minta operator mengonfirmasi satu pembacaan sensor.",
         {"A": "Pembacaan contoh sebesar 56 derajat di Timur."}, ("A",), ("56",)),
    Case("C2", "content", "Buat pesan ke tim persediaan untuk memeriksa selisih.",
         {"A": "Kurang 31 unit antara catatan dan hitung fisik."}, ("A",), ("31",)),
    Case("C3", "content", "Tulis draf ke tim penjualan untuk meninjau penurunan.",
         {"A": "Penjualan masih 115 unit, di bawah acuan mingguan."}, ("A",), ("115",)),
    Case("C4", "content", "Tulis pesan berisi nama penanggung jawab penjualan.",
         {"A": "Penjualan Tengah 143 unit."}),
    Case("I1", "ideas", "Berikan ide berbeda untuk menyelidiki pembacaan tinggi.",
         {"A": "Sensor Timur di atas batas demo."}, ("A",)),
    Case("I2", "ideas", "Beri ide untuk memeriksa ketidaksesuaian stok.",
         {"A": "Hitung fisik Barat di bawah catatan buku."}, ("A",)),
    Case("I3", "ideas", "Beri ide penyelidikan lonjakan penjualan.",
         {"A": "Penjualan Tengah melewati pola hari serupa."}, ("A",)),
    Case("I4", "ideas", "Beri ide yang bergantung pada nama pemasok stok tersebut.",
         {"A": "Stok fisik tercatat 117 unit."}),
    Case("A1", "analysis", "Bandingkan volume dengan acuan dan usulkan verifikasi.",
         {"A": "Penjualan 228 unit; acuan 136 unit."}, ("A",), ("228", "136")),
    Case("A2", "analysis", "Bandingkan pembacaan dan batas lalu beri tindak lanjut.",
         {"A": "Pembacaan 54 derajat; batas simulasi 49 derajat."}, ("A",), ("54", "49")),
    Case("A3", "analysis", "Bandingkan stok fisik dan catatan yang tersedia.",
         {"A": "Stok fisik 297 unit.", "B": "Stok buku 331 unit."}, ("A", "B"), ("297", "331")),
    Case("A4", "analysis", "Hitung margin kotor dengan biaya pokok dan pendapatan.",
         {"A": "Penjualan 196 unit."}),
)
FORMATS = {
    "summary": r"(?ms)^\s*- [^\n]+\n\s*- [^\n]+",
    "content": r"(?ims)^Subjek:\s*\S.*?^Pesan:\s*\S",
    "ideas": r"(?ims)^Ide 1:\s*\S.*?^Ide 2:\s*\S",
    "analysis": r"(?ims)^Temuan:\s*\S.*?^Tindak lanjut:\s*\S",
}
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?")
REFERENCE = re.compile(r"\[([A-Z][A-Z0-9]*)\]")


def score(case: Case, draft: str) -> dict[str, bool]:
    if not case.required_ids:
        return {
            "recognizes_missing_data": bool(re.search(
                r"\b(tidak tersedia|tidak ada|belum tersedia|tidak ditemukan|tidak (dapat|bisa) (mengetahui|menghitung|memberikan))\b",
                draft, re.IGNORECASE,
            )),
            "stays_on_requested_information": len(draft.split()) <= 22 and not NUMBER.search(draft),
        }
    citations = set(REFERENCE.findall(draft))
    without_labels = re.sub(r"(?im)^Ide [12]:", "", REFERENCE.sub("", draft))
    expected = {number for fact in case.facts.values() for number in NUMBER.findall(fact)}
    observed = set(NUMBER.findall(without_labels))
    checks = {
        "format": bool(re.search(FORMATS[case.task], draft)),
        "required_sources": set(case.required_ids) <= citations <= case.facts.keys(),
        "required_figures": set(case.required_values) <= observed,
        "no_extra_figures": observed <= expected,
        "brief": len(draft.split()) <= 100,
    }
    if case.task == "ideas":
        ideas = re.findall(r"(?im)^Ide [12]:\s*([^\n]+)", draft)
        checks["distinct_ideas"] = len(ideas) == 2 and ideas[0].strip().casefold() != ideas[1].strip().casefold()
    if case.task == "content":
        checks["asks_for_action"] = bool(re.search(
            r"\b(mohon|tolong|harap|konfirmasi|periksa|verifikasi|tinjau)\b", draft, re.IGNORECASE,
        ))
    return checks


def run() -> dict:
    summary = {variant: {"passed": 0, "total": len(CASES)} for variant in ("baseline", "refined")}
    cases = []
    for case in CASES:
        row = {"id": case.id, "task": case.task, "brief": case.brief, "facts": case.facts}
        for variant, counts in summary.items():
            start = perf_counter()
            try:
                draft = generate(case.task, case.brief, case.facts, variant)
                checks = score(case, draft)
                result = {"draft": draft, "checks": checks, "passed": all(checks.values())}
            except DraftError as error:
                result = {"error": str(error), "checks": {}, "passed": False}
            counts["passed"] += result["passed"]
            row[variant] = {**result, "seconds": round(perf_counter() - start, 2)}
        cases.append(row)
    return {
        "model": "Qwen3-4B Q4_K_M", "prompt_version": VERSION,
        "settings": {"temperature": 0, "seed": 291, "max_tokens": 384, "enable_thinking": False},
        "summary": summary, "cases": cases,
    }
