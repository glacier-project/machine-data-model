#!/bin/bash
poetry export --without-hashes --format=requirements.txt -o requirements.txt
poetry export --without-hashes --with=dev --format=requirements.txt -o requirements-dev.txt
