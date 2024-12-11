import random
from enum import Enum
from typing import Tuple, Union

import pytest
from unitsnet_py import AccelerationUnits, LengthUnits
from unitsnet_py.abstract_unit import AbstractMeasure
from unitsnet_py.units.length import Length

from machine_data_model.nodes.measurement_unit.measure_builder import (
    MeasureBuilder,
    NoneMeasure,
    NoneMeasureUnits,
)

NUM_VALUES = 3


class TestMeasureBuilder:

    @pytest.mark.parametrize(
        "value", [random.uniform(0, 1000) for i in range(NUM_VALUES)]
    )
    @pytest.mark.parametrize(
        "measure_info",
        [(Length, LengthUnits.Meter), (NoneMeasure, NoneMeasureUnits.NONE)],
    )
    def test_creation_from_enum(
        self, value: float, measure_info: Tuple[AbstractMeasure, Enum]
    ):
        # Arrange
        measure_builder = MeasureBuilder()
        measure_domain, measure_unit = measure_info

        # Act
        measure_value = measure_builder.create_measure(value, measure_unit)

        # Assert
        assert measure_value.base_value == value
        assert str(measure_value).endswith(
            measure_domain.get_unit_abbreviation(measure_unit)
        )

    @pytest.mark.parametrize(
        "value", [random.uniform(0, 1000) for i in range(NUM_VALUES)]
    )
    @pytest.mark.parametrize(
        "measure_info",
        [(Length, "LengthUnits.Meter"), (NoneMeasure, "NoneMeasureUnits.NONE")],
    )
    def test_creation_from_str(
        self, value: float, measure_info: Tuple[AbstractMeasure, str]
    ):
        # Arrange
        measure_builder = MeasureBuilder()
        measure_domain, measure_unit = measure_info

        # Act
        measure_value = measure_builder.create_measure(value, measure_unit)

        # Assert
        assert measure_value.base_value == value
        assert str(measure_value).endswith(
            measure_domain.get_unit_abbreviation(measure_unit)
        )
