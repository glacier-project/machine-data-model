import random

import pytest
from unitsnet_py import LengthUnits
from unitsnet_py.units.length import Length

from machine_data_model.nodes.measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasure,
    NoneMeasureUnits,
)
from tests import NUM_TESTS


class TestMeasureBuilder:

    @pytest.mark.parametrize(
        "value", [random.uniform(0, 1000) for i in range(NUM_TESTS)]
    )
    @pytest.mark.parametrize(
        "domain, unit",
        [(Length, LengthUnits.Meter), (NoneMeasure, NoneMeasureUnits.NONE)],
    )
    def test_creation_from_enum(self, value, domain, unit):
        # Arrange
        measure_builder = MeasureBuilder()

        # Act
        measure_value = measure_builder.create_measure(value, unit)

        # Assert
        assert measure_value.base_value == value
        assert str(measure_value).endswith(domain.get_unit_abbreviation(unit))

    @pytest.mark.parametrize(
        "value", [random.uniform(0, 1000) for i in range(NUM_TESTS)]
    )
    @pytest.mark.parametrize(
        "domain, unit",
        [(Length, "LengthUnits.Meter"), (NoneMeasure, "NoneMeasureUnits.NONE")],
    )
    def test_creation_from_str(self, value, domain, unit):
        # Arrange
        measure_builder = MeasureBuilder()

        # Act
        measure_value = measure_builder.create_measure(value, unit)

        # Assert
        assert measure_value.base_value == value
        assert str(measure_value).endswith(domain.get_unit_abbreviation(unit))
