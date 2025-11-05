import inspect
from enum import Enum
from typing import Type, Dict

import unitsnet_py
from unitsnet_py.abstract_unit import AbstractMeasure


class NoneMeasureUnits(Enum):
    """
    Enum for representing units for `NoneMeasure`.

    :cvar NONE: The only available unit, representing no unit.
    """

    NONE = 0


class NoneMeasure(AbstractMeasure):
    """
    Represents a value with no unit.

    This class is used for values that do not have a unit of measurement.

    Attributes:
        _value (float): The value.
    """

    def __init__(
        self, value: float, from_unit: NoneMeasureUnits = NoneMeasureUnits.NONE
    ):
        """
        Initializes a `NoneMeasure` instance.

        Args:
            value (float): The value of the `NoneMeasure`.
            from_unit (NoneMeasureUnits): The unit of the value, which must be `NoneMeasureUnits.NONE`.
        """

        assert from_unit == NoneMeasureUnits.NONE
        self._value: float = value

    @property
    def base_value(self) -> float:
        """
        Returns the base value.

        Returns:
            float: The value with no unit.
        """

        return self._value

    def to_string(
        self,
        unit: NoneMeasureUnits = NoneMeasureUnits.NONE,
        fractional_digits: int | None = None,
    ) -> str:
        """
        Formats the `NoneMeasure` to a string.

        Args:
            unit (NoneMeasureUnits): The unit to format, which must be `NoneMeasureUnits.NONE`.
            fractional_digits (int | None): The number of fractional digits to keep.

        Returns:
            str: A string representation of the `NoneMeasure`.
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
        Gets the abbreviation of the `NoneMeasure` unit.

        This method returns an empty string since `NoneMeasure` has no unit.

        Args:
            unit_abbreviation (NoneMeasureUnits): The unit abbreviation, which must be `NoneMeasureUnits.NONE`.

        Returns:
            str: An empty string.

        Raises:
            ValueError: If the unit is not `NoneMeasureUnits.NONE`.
        """

        if unit_abbreviation == NoneMeasureUnits.NONE:
            return ""
        else:
            raise ValueError("Invalid unit for NoneMeasure measure")


class MeasureBuilder:
    """
    A utility class for building measure objects from a value and a unit.

    This class creates an appropriate measure object, such as `NoneMeasure` or
    units from the `unitsnet_py` package, based on the provided unit.

    Attributes:
        _measure_ctor (Dict[Type[Enum], Type[AbstractMeasure]]): A dictionary mapping unit enums to their measure constructors.
    """

    def __init__(self) -> None:
        """
        Initializes a new `MeasureBuilder` instance.
        """

        self._measure_ctor: Dict[Type[Enum], Type[AbstractMeasure]] = {}

        # Explore the unitsnet_py package to store the measure object from the unit.
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

        # Add the NoneMeasure unit.
        self._measure_ctor[NoneMeasureUnits] = NoneMeasure

    def get_measure_unit(self, unit: str | Enum) -> Enum:
        """
        Retrieves the unit enum based on a string or enum.

        If a string is passed, it should be in the format "Module.Unit".

        Args:
            unit (str | Enum): The unit as a string or an `Enum`.

        Returns:
            Enum: The unit enum corresponding to the provided unit.

        Raises:
            ValueError: If the unit type is invalid.
        """

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
        """
        Creates a measure object from a value and a unit.

        Args:
            value (float): The value of the measure.
            unit (str | Enum): The unit of the measure.

        Returns:
            AbstractMeasure: An instance of the corresponding measure class.

        Raises:
            ValueError: If the unit is invalid.
        """

        unit = self.get_measure_unit(unit)
        measure = self._measure_ctor[unit.__class__]
        return measure(value=value, from_unit=unit)


_measure_builder: "MeasureBuilder" = MeasureBuilder()


def get_measure_builder() -> "MeasureBuilder":
    """
    Gets the MeasureBuilder instance.

    Returns:
        MeasureBuilder: The MeasureBuilder instance.
    """
    return _measure_builder
