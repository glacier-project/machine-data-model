#!/bin/bash
poetry run black $1
poetry run isort $1 --profile black
poetry run flake8 $1 --format='%(path)s::%(row)d,%(col)d::%(code)s::%(text)s'
poetry run lizard $1 -w
