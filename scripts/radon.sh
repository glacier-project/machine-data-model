#!/bin/bash
if [ ! -d "randon/" ]; then
  mkdir randon/
fi

# Add randon to asses code metrics (quality, maintainability, complexity)
radon cc "$(find "$1" -type f -name "*.py")" --total-average -s -o SCORE --min C -j | python3 -m json.tool > randon/radon_cc_result.json
radon mi "$(find "$1" -type f -name "*.py")" --min B -j | python3 -m json.tool > randon/radon_mi_result.json
radon hal "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > randon/radon_hal_result.json
radon raw "$(find "$1" -type f -name "*.py")" -j | python3 -m json.tool > randon/radon_raw_result.json