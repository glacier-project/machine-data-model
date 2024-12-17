import inspect
from enum import Enum

import unitsnet_py
from unitsnet_py.abstract_unit import AbstractMeasure


class NoneMeasureUnits(Enum):
    NONE = 0


class NoneMeasure(AbstractMeasure):
    """
    NoneMeasure represents a value with no unit.

    Args:
        value (float): The value.
        from_unit (NoneMeasureUnits): The unit of the value, always
            NoneMeasureUnits.NONE.
    """

    def __init__(
        self, value: float, from_unit: NoneMeasureUnits = NoneMeasureUnits.NONE
    ):
        assert from_unit == NoneMeasureUnits.NONE
        self._value = value

    @property
    def base_value(self) -> float:
        return self._value

    def to_string(
        self,
        unit: NoneMeasureUnits = NoneMeasureUnits.NONE,
        fractional_digits: int | None = None,
    ) -> str:
        """
        Format the NoneMeasure to a string.

        Args:
            unit (str): The unit to format the NoneMeasure. The only one available is
                'NONE'.
            fractional_digits (int, optional): The number of fractional digits to keep.

        Returns:
            str: The string format of the NoneMeasure.
        """
        assert unit == NoneMeasureUnits.NONE
        if fractional_digits is not None:
            return (
                f"{super()._truncate_fraction_digits(self._value, fractional_digits)}"
            )
        return f"{self._value}"

    def get_unit_abbreviation(
        self, unit_abbreviation: NoneMeasureUnits = NoneMeasureUnits.NONE
    ) -> str:
        """
        Get NoneMeasure unit abbreviation.
        Note! the only available unit is 'NONE', so the method will always return an
        empty string.
        """
        if unit_abbreviation == NoneMeasureUnits.NONE:
            return ""
        else:
            raise ValueError("Invalid unit for NoneMeasure measure")


class MeasureBuilder:
    """
    A MeasureBuilder class is a utility builder class used to create a measure object
    from a value and a unit.
    """

    def __init__(self) -> None:
        """
        Initialize a new MeasureBuilder instance.
        """
        # explore the unitsnet_py package to store the measure object from the unit
        self._measure_ctor = {}
        units = inspect.getmembers(
            unitsnet_py,
            lambda member: inspect.isclass(member)
            and member.__name__.endswith("Units"),
        )
        for unit in units:
            unit_name = unit[0]
            measure_name = unit_name.replace("Units", "")
            measure = getattr(unitsnet_py, measure_name)
            assert inspect.isclass(measure)
            self._measure_ctor[unit[1]] = measure

        # add the NoneMeasure unit
        self._measure_ctor[NoneMeasureUnits] = NoneMeasure

    def get_measure_unit(self, unit: str | Enum) -> Enum:
        if isinstance(unit, Enum):
            assert unit.__class__ in self._measure_ctor
            return unit
        elif isinstance(unit, str):
            assert "." in unit
            unit_class, unit_name = unit.split(".")
        else:
            raise ValueError("Invalid unit type")

        if unit_class == "NoneMeasureUnits":
            unit_cl = NoneMeasureUnits
        else:
            unit_cl = getattr(unitsnet_py, unit_class)
        return unit_cl[unit_name]

    def create_measure(self, value: float, unit: str | Enum) -> AbstractMeasure:
        unit = self.get_measure_unit(unit)
        measure = self._measure_ctor[unit.__class__]
        return measure(value=value, from_unit=unit)


_measure_builder: "MeasureBuilder" = MeasureBuilder()


def get_measure_builder() -> "MeasureBuilder":
    """
    Get the MeasureBuilder instance.
    :return: The MeasureBuilder instance.
    """
    return _measure_builder
