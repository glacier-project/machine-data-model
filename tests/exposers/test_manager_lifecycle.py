"""Tests for the ExposerManager lifecycle: construction, start, stop."""

import pytest

from machine_data_model.data_model import DataModel
from machine_data_model.exposers.exposer_manager import ExposerManager


def _make_data_model() -> DataModel:
    return DataModel(name="test")


@pytest.mark.exposer
def test_constructor_stores_data_model_and_defaults() -> None:
    """The manager exposes the data_model property and applies defaults."""
    data_model = _make_data_model()
    manager = ExposerManager(data_model)
    assert manager.data_model is data_model
    assert manager.host == "0.0.0.0"
    assert manager.port == 8080
