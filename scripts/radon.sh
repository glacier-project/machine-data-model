#!/bin/bash
if [ ! -d "radon/" ]; then
  mkdir radon/
fi

# Code metrics (quality, maintainability, complexity).
uv run radon cc "$(find "$1" -type f -name "*.py")" --total-average -s -o SCORE --min C -j | python3 -m json.tool > radon/radon_cc_result.json
uv run radon mi "$(find "$1" -type f -name "*.py")" --min B -j | python3 -m json.tool > radon/radon_mi_result.json
uv run radon hal "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > radon/radon_hal_result.json
uv run radon raw "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > radon/radon_raw_result.json
