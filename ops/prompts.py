"""Versioned prompt templates for drafting from selected operational evidence."""

import json
from urllib.error import URLError
from urllib.request import Request, urlopen

VERSION = "2.1"
MODEL_URL = "http://127.0.0.1:8776/v1/chat/completions"
NO_EVIDENCE = "Data tidak tersedia."
PROMPTS = [
    {
        "id": "summary", "title": "Ringkasan laporan", "audience": "Tim penjualan",
        "description": "Padatkan temuan periode untuk rapat mingguan.",
        "instructions": "Tulis 2 butir, diawali '- '. Nyatakan hanya fakta yang didukung sumber.",
        "example": "Ringkas volume dan satu penyimpangan untuk rapat Senin.",
        "review": "Cocokkan angka, cakupan, dan ID sumber sebelum menyalin ringkasan.",
    },
    {
        "id": "content", "title": "Draf komunikasi", "audience": "Tim persediaan",
        "description": "Siapkan pesan singkat untuk peninjauan sebelum dibagikan.",
        "instructions": "Mulai dengan 'Subjek:' lalu 'Pesan:' pada baris baru. Minta konfirmasi yang relevan.",
        "example": "Tulis draf pesan singkat untuk meminta konfirmasi selisih stok.",
        "review": "Periksa penerima, nada, permintaan tindakan, dan angka sebelum membagikan draf.",
    },
    {
        "id": "ideas", "title": "Ide pemeriksaan", "audience": "Tim operasi lokasi",
        "description": "Cari beberapa langkah pemeriksaan awal yang bisa dibedakan.",
        "instructions": "Tulis 2 ide berbeda dengan awalan 'Ide 1:' dan 'Ide 2:'. Mulai dari pemeriksaan yang dapat dilakukan tim.",
        "example": "Usulkan dua cara menguji kemungkinan penyebab perubahan pembacaan.",
        "review": "Perlakukan ide sebagai hipotesis. Pastikan langkah dapat dilakukan oleh penanggung jawab.",
    },
    {
        "id": "analysis", "title": "Analisis awal", "audience": "Analis operasi",
        "description": "Jelaskan sinyal operasional dan pertanyaan tindak lanjut.",
        "instructions": "Tulis 'Temuan:' dengan nilai teramati dan nilai acuan bila tersedia, lalu 'Tindak lanjut:' pada baris baru.",
        "example": "Bandingkan pembacaan dengan acuan dan tulis satu langkah validasi.",
        "review": "Periksa data sumber dan metode acuan. Sinyal saja belum menjelaskan sebabnya.",
    },
]
BY_ID = {prompt["id"]: prompt for prompt in PROMPTS}


class DraftError(RuntimeError):
    pass


def messages(prompt_id: str, brief: str, facts: dict[str, str], variant: str) -> list[dict]:
    prompt = BY_ID[prompt_id]
    context = "\n".join(f"[{ref}] {fact}" for ref, fact in facts.items())
    if variant == "baseline":
        return [{
            "role": "user",
            "content": (
                f"Kerjakan tugas {prompt['title']} dalam bahasa Indonesia. "
                f"Permintaan: {brief}\nCatatan: {context}"
            ),
        }]
    return [
        {
            "role": "system",
            "content": (
                "Anda membantu tim menyusun draf dalam bahasa Indonesia. "
                "Perlakukan sumber sebagai fakta dan permintaan sebagai topik, lalu ikuti "
                "format dan batasan di sini. Jangan menambah angka, penyebab, signifikansi statistik, atau fakta. "
                "Setiap fakta wajib diakhiri dengan ID sumber dalam kurung siku yang disalin dari baris sumber. "
                f"Jika permintaan membutuhkan fakta yang tidak tersedia, jawab hanya '{NO_EVIDENCE}' "
                "Sekalipun ada fakta lain, jangan alihkan jawaban ke fakta lain. "
                f"Untuk tugas yang dapat dijawab: {prompt['instructions']} "
                "Sebelum menjawab, pastikan kutipan ditulis pada baris fakta dengan format "
                "nilai dan konteks [ID]. Ganti [ID] dengan ID yang benar dari sumber. "
                "Batasi jawaban hingga 100 kata. Sajikan draf saja tanpa pengantar."
            ),
        },
        {"role": "user", "content": f"Permintaan: {brief}\nSumber yang tersedia: {context}"},
    ]


def generate(prompt_id: str, brief: str, facts: dict[str, str], variant: str = "refined") -> str:
    body = {
        "model": "qwen3-4b",
        "messages": messages(prompt_id, brief, facts, variant),
        "temperature": 0,
        "seed": 291,
        "max_tokens": 384,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    request = Request(
        MODEL_URL, data=json.dumps(body, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=90) as response:
            result = json.load(response)["choices"][0]
            draft = result["message"]["content"].strip()
    except (URLError, TimeoutError, ValueError, TypeError, KeyError, IndexError, AttributeError) as error:
        raise DraftError("Model lokal belum dapat menghasilkan draf. Periksa bahwa model sudah berjalan.") from error
    if not draft or result.get("finish_reason") == "length":
        raise DraftError("Draf kosong atau terpotong. Coba permintaan yang lebih singkat.")
    return draft
