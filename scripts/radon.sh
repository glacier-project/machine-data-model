#!/bin/bash
if [ ! -d "randon/" ]; then
  mkdir randon/
fi

# Add randon to asses code metrics (quality, maintainability, complexity)
poetry run radon cc "$(find "$1" -type f -name "*.py")" --total-average -s -o SCORE --min C -j | python3 -m json.tool > randon/radon_cc_result.json
poetry run radon mi "$(find "$1" -type f -name "*.py")" --min B -j | python3 -m json.tool > randon/radon_mi_result.json
poetry run radon hal "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > randon/radon_hal_result.json
poetry run radon raw "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > randon/radon_raw_result.json