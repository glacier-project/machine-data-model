#!/bin/bash
black daedalus
isort daedalus --profile black
flake8 --format='%(path)s::%(row)d,%(col)d::%(code)s::%(text)s' daedalus
lizard daedalus -w