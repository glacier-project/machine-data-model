#!/bin/bash
poetry run ruff check --fix $1
poetry run ruff format $1
poetry run lizard $1 -w
