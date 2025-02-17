import inspect
from enum import Enum

import unitsnet_py
from unitsnet_py.abstract_unit import AbstractMeasure


class NoneMeasureUnits(Enum):
    """
    Enum for representing units for `NoneMeasure`.

    :ivar NONE: The only available unit, representing no unit.
    """

    NONE = 0


class NoneMeasure(AbstractMeasure):
    """
    Represents a value with no unit.

    This class is used to represent a value that does not have any unit
    associated with it. The unit of measurement is always `NONE`.

    :param value: The value.
    :param from_unit: The unit of the value, which is always `NONE`.
    """

    def __init__(
        self, value: float, from_unit: NoneMeasureUnits = NoneMeasureUnits.NONE
    ):
        """
        Initializes a `NoneMeasure` instance with a value and a unit.

        :param value: The value of the `NoneMeasure`.
        :param from_unit: The unit of the value. This is always `NONE`, and an assertion ensures it cannot be anything else.
        """
        assert from_unit == NoneMeasureUnits.NONE
        self._value = value

    @property
    def base_value(self) -> float:
        """
        Returns the base value.

        :return: The value with no unit.
        """

        return self._value

    def to_string(
        self,
        unit: NoneMeasureUnits = NoneMeasureUnits.NONE,
        fractional_digits: int | None = None,
    ) -> str:
        """
        Format the `NoneMeasure` to a string.

        This method returns the string representation of the value. The unit is
        always `NONE`, and an optional number of fractional digits can be
        specified.

        :param unit: The unit to format the `NoneMeasure`. The only valid value is `NONE`.
        :param fractional_digits: The number of fractional digits to keep. Optional.
        :return: A string representation of the `NoneMeasure`.
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
        Get the abbreviation of the `NoneMeasure` unit.

        This method returns an empty string since the only valid unit is `NONE`.

        :param unit_abbreviation: The unit abbreviation. Must be `NONE`.
        :raises ValueError: If the unit is not `NONE`.
        :return: An empty string as `NoneMeasure` has no abbreviation.
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
