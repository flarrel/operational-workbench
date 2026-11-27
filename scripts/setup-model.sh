#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
runtime=${1:-"$repo/../internal/runtime"}
mkdir -p "$runtime"
cd "$runtime"

check() {
    printf '%s  %s\n' "$1" "$2" | shasum -a 256 -c
}

archive_sha=78d16911c82fa7a6b7586856034ca4c99497b3fb2e80f42be7b8a2dcafa80512
model_sha=7485fe6f11af29433bc51cab58009521f205840f5b4ae3a32fa7f92e8534fdf5

if [ ! -f llama.zip ]; then
    curl -fLSs --retry 2 --max-filesize 30000000 -o llama.zip.part \
        https://github.com/ggml-org/llama.cpp/releases/download/b6760/llama-b6760-bin-macos-arm64.zip
    check "$archive_sha" llama.zip.part
    mv llama.zip.part llama.zip
fi
check "$archive_sha" llama.zip
unzip -oq llama.zip -d llama

if [ ! -f model.gguf ]; then
    curl -fLSs --retry 2 --max-filesize 2700000000 -o model.part \
        https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/a9a60d0/Qwen3-4B-Q4_K_M.gguf
    check "$model_sha" model.part
    mv model.part model.gguf
else
    check "$model_sha" model.gguf
fi
