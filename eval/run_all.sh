#!/bin/sh
# Runs every configuration reported in report/REPORT.md, one after another (the GPU is shared).
cd "$(dirname "$0")/.."
PY=${PY:-.venv/bin/python}
$PY -m eval.run_eval --tag A_qwen3-1.7b_multi            --runs 3
$PY -m eval.run_eval --tag B_qwen3-1.7b_single           --runs 3 --mode single
$PY -m eval.run_eval --tag C_qwen3-1.7b_multi_nothink    --runs 1 --think none
# 8B models need ~6 GB and swap on a 16 GB laptop: only with HEAVY=1 ./eval/run_all.sh
if [ "${HEAVY:-0}" = "1" ]; then
$PY -m eval.run_eval --tag D_qwen3-8b_multi              --runs 1 --model ollama_chat/qwen3:8b
$PY -m eval.run_eval --tag E_llama3.1-8b_multi           --runs 1 --model ollama_chat/llama3.1:8b
$PY -m eval.run_eval --tag F_qwen3-8b_multi-transfer     --runs 1 --model ollama_chat/qwen3:8b --mode multi-transfer
fi
$PY -m eval.summarize
