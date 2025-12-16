echo "Storing the current python path"
PYTHON_PATH="$(poetry run which python3)"

poetry run tox run "$@"

echo "Restoring the initial python path"
poetry env use "$PYTHON_PATH"
