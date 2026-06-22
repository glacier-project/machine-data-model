# Intentionally empty.
#
# This package must stay importable without the optional connector extras so
# that the no-extras CI job can collect (and deselect via ``-m "not
# connector"``) the dependency-free tests in this directory, such as
# ``test_abstract_async_connector`` and ``test_registry``.
#
# OPC UA test helpers live in the ``opcua`` subpackage (the only consumer is
# ``opcua/conftest.py``); do not re-introduce ``asyncua``/``aiomqtt`` imports
# here. The top-level ``tests/conftest.py`` skips the dependency-specific
# subdirectories when their extra is missing.
