#!/bin/bash
poetry run ruff check --fix "$@"
poetry run ruff format "$@"
#poetry run lizard "$@" -w
