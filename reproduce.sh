#!/usr/bin/env bash
# Reproduce or verify the frozen solver-800 Snake Hermes benchmark.
set -euo pipefail
cd "$(dirname "$0")"

mode="${1:---verify}"
case "$mode" in
  --verify)
    PYTHONPATH=. python3 -m pytest -q
    python3 analysis/verify_solver800_artifacts.py
    ;;
  --rerun-benchmarks)
    output_dir="${2:-results/reproduced_solver800}"
    mkdir -p "$output_dir"
    python3 experiments/run_paired_capability_benchmark.py \
      --output "$output_dir/paired_capability_benchmark_solver800.json" \
      --duration 10 --fault-time 4 --seeds 7 26 --environments flat --workers 0
    python3 analysis/statistics_paired_capability.py \
      --input "$output_dir/paired_capability_benchmark_solver800.json" \
      --output "$output_dir/paired_capability_statistics_solver800.json" \
      --permutations 5000 --bootstrap 5000
    python3 experiments/run_paired_capability_benchmark.py \
      --output "$output_dir/paired_capability_robustness_solver800.json" \
      --duration 10 --fault-time 4 --seeds 7 26 \
      --environments low_friction variable_friction incline --workers 0
    python3 analysis/statistics_robustness_capability.py \
      --input "$output_dir/paired_capability_robustness_solver800.json" \
      --output "$output_dir/paired_capability_robustness_solver800_statistics.json" \
      --permutations 5000 --bootstrap 5000
    printf 'Fresh raw/statistical artifacts saved under %s\n' "$output_dir"
    ;;
  *)
    printf 'Usage: bash reproduce.sh [--verify | --rerun-benchmarks [output_dir]]\n' >&2
    exit 2
    ;;
esac
