import random
from enum import Enum

import pytest
from unitsnet_py.units.length import LengthUnits

from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
)
from tests import NUM_TESTS, gen_random_string


@pytest.mark.parametrize(
    "var_name, var_description",
    [(gen_random_string(10), gen_random_string(20)) for _ in range(3)],
)
class TestVariableNode:
    properties = {
        "a": NumericalVariableNode(
            name="a", description="b", value=1, measure_unit=LengthUnits.Meter
        ),
        "b": StringVariableNode(name="b", description="b", value="c"),
        "c": BooleanVariableNode(name="c", description="b", value=True),
    }

    @pytest.mark.parametrize("var_value", [gen_random_string(10) for _ in range(3)])
    def test_string_variable_node_creation(
        self, var_name: str, var_description: str, var_value: str
    ) -> None:
        str_var = StringVariableNode(
            name=var_name, description=var_description, value=var_value
        )

        assert str_var.name == var_name
        assert str_var.description == var_description
        assert str_var.value == var_value

    @pytest.mark.parametrize("var_value", [gen_random_string(10) for _ in range(3)])
    def test_string_variable_node_write(
        self, var_name: str, var_description: str, var_value: str
    ) -> None:
        str_var = StringVariableNode(
            name=var_name, description=var_description, value=var_value
        )

        new_value = gen_random_string(10)
        str_var.value = new_value

        assert str_var.name == var_name
        assert str_var.description == var_description
        assert str_var.value == new_value

    def test_boolean_variable_node_creation(
        self, var_name: str, var_description: str
    ) -> None:
        bool_var = BooleanVariableNode(
            name=var_name, description=var_description, value=True
        )

        assert bool_var.name == var_name
        assert bool_var.description == var_description
        assert bool_var.value

    def test_boolean_variable_node_write(
        self, var_name: str, var_description: str
    ) -> None:
        bool_var = BooleanVariableNode(
            name=var_name, description=var_description, value=True
        )

        bool_var.value = False

        assert bool_var.name == var_name
        assert bool_var.description == var_description
        assert not bool_var.value

    @pytest.mark.parametrize(
        "var_value", [random.uniform(0, 1000) for i in range(NUM_TESTS)]
    )
    @pytest.mark.parametrize(
        "unit",
        [
            LengthUnits.Meter,
            NoneMeasureUnits.NONE,
            "LengthUnits.Meter",
            "NoneMeasureUnits.NONE",
        ],
    )
    def test_numeric_variable_node_creation(
        self, var_name: str, var_description: str, var_value: float, unit: Enum | str
    ) -> None:
        numeric_var = NumericalVariableNode(
            name=var_name,
            description=var_description,
            value=var_value,
            measure_unit=unit,
        )

        assert numeric_var.name == var_name
        assert numeric_var.description == var_description
        assert numeric_var.value == var_value

    @pytest.mark.parametrize(
        "var_value", [random.uniform(0, 1000) for i in range(NUM_TESTS)]
    )
    @pytest.mark.parametrize(
        "unit",
        [
            LengthUnits.Meter,
            NoneMeasureUnits.NONE,
            "LengthUnits.Meter",
            "NoneMeasureUnits.NONE",
        ],
    )
    def test_numeric_variable_node_write(
        self, var_name: str, var_description: str, var_value: float, unit: Enum | str
    ) -> None:
        numeric_var = NumericalVariableNode(
            name=var_name, description=var_description, value=-1, measure_unit=unit
        )

        numeric_var.value = var_value

        assert numeric_var.name == var_name
        assert numeric_var.description == var_description
        assert numeric_var.value == var_value

    def test_object_variable_node_creation(
        self, var_name: str, var_description: str
    ) -> None:
        properties = self.properties
        obj_var = ObjectVariableNode(
            name=var_name, description=var_description, properties=properties
        )

        assert obj_var.name == var_name
        assert obj_var.description == var_description
        for key in properties:
            assert obj_var.has_property(key)
            assert obj_var.get_property(key) == properties[key]
        prop_val = {}
        for key in properties:
            prop_val[key] = properties[key].value
        assert obj_var.value == prop_val

    def test_object_variable_node_update(
        self, var_name: str, var_description: str
    ) -> None:
        str_prop = StringVariableNode(name="b", description="b", value="c")
        obj_var = ObjectVariableNode(
            name=var_name, description=var_description, properties={"b": str_prop}
        )

        num_var = NumericalVariableNode(
            name="a", description="b", value=-1, measure_unit=LengthUnits.Meter
        )
        obj_var.add_property(num_var)
        obj_var.remove_property("b")

        assert obj_var.name == var_name
        assert obj_var.description == var_description
        assert not obj_var.has_property("b")
        assert obj_var.has_property("a")
        assert obj_var.get_property("a") == num_var

    def test_object_variable_node_subscribe(
        self, var_name: str, var_description: str
    ) -> None:
        str_prop = StringVariableNode(name="b", description="b", value="c")
        obj_var = ObjectVariableNode(
            name=var_name, description=var_description, properties={"b": str_prop}
        )

        num_var = NumericalVariableNode(
            name="a", description="b", value=-1, measure_unit=LengthUnits.Meter
        )
        obj_var.add_property(num_var)

        subscriber = "test"
        obj_var.subscribe(subscriber)
        num_var.write(10)

        assert obj_var.name == var_name
        assert obj_var.description == var_description
        assert obj_var.has_property("a")
        assert obj_var.value["a"] == 10
