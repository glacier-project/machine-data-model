"""Tests for the AbstractExposer base class."""

import pytest

from machine_data_model.exposers.abstract_exposer import AbstractExposer


@pytest.mark.exposer
def test_abstract_exposer_cannot_be_instantiated() -> None:
    """Instantiating the ABC directly is a TypeError."""
    with pytest.raises(TypeError):
        AbstractExposer()  # type: ignore[abstract]


@pytest.mark.exposer
def test_subclass_with_register_can_be_instantiated() -> None:
    """A concrete subclass that implements register() works."""

    class _Stub(AbstractExposer):
        def register(self, app, manager) -> None:  # type: ignore[no-untyped-def]
            pass

    _Stub()  # must not raise
