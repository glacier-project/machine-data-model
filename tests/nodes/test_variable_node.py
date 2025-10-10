import random
from enum import Enum
from typing import Any

import pytest
from unitsnet_py.units.length import LengthUnits

from machine_data_model.nodes.measurement_unit.measure_builder import NoneMeasureUnits
from machine_data_model.nodes.subscription.variable_subscription import (
    DataChangeSubscription,
    VariableSubscription,
)
from machine_data_model.nodes.variable_node import (
    BooleanVariableNode,
    NumericalVariableNode,
    ObjectVariableNode,
    StringVariableNode,
    VariableNode,
)
from tests import (
    NUM_TESTS,
    gen_random_string,
    get_random_numerical_node,
    get_random_simple_node,
    get_random_string_node,
)


@pytest.mark.parametrize(
    "var_name, var_description",
    [(gen_random_string(10), gen_random_string(20)) for _ in range(NUM_TESTS)],
)
class TestVariableNode:
    def test_string_variable_node_creation(
        self,
        var_name: str,
        var_description: str,
    ) -> None:
        var_value = gen_random_string()
        str_var = StringVariableNode(
            name=var_name, description=var_description, value=var_value
        )

        assert str_var.name == var_name
        assert str_var.description == var_description
        assert str_var.value == var_value

    def test_string_variable_node_write(
        self, var_name: str, var_description: str
    ) -> None:
        str_var = StringVariableNode(
            name=var_name, description=var_description, value=gen_random_string()
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
        "unit",
        [
            LengthUnits.Meter,
            NoneMeasureUnits.NONE,
            "LengthUnits.Meter",
            "NoneMeasureUnits.NONE",
        ],
    )
    def test_numeric_variable_node_creation(
        self, var_name: str, var_description: str, unit: Enum | str
    ) -> None:
        var_value = random.uniform(0, 1000)
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
        "unit",
        [
            LengthUnits.Meter,
            NoneMeasureUnits.NONE,
            "LengthUnits.Meter",
            "NoneMeasureUnits.NONE",
        ],
    )
    def test_numeric_variable_node_write(
        self, var_name: str, var_description: str, unit: Enum | str
    ) -> None:
        var_value = random.uniform(0, 1000)
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
        properties = {
            node.name: node
            for node in [
                get_random_simple_node(),
                get_random_simple_node(),
                get_random_simple_node(),
            ]
        }
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
        str_prop = get_random_string_node()
        obj_var = ObjectVariableNode(
            name=var_name,
            description=var_description,
            properties={str_prop.name: str_prop},
        )

        num_var = get_random_numerical_node()
        obj_var.add_property(num_var)
        obj_var.remove_property(str_prop.name)

        assert obj_var.name == var_name
        assert obj_var.description == var_description
        assert not obj_var.has_property(str_prop.name)
        assert obj_var.has_property(num_var.name)
        assert obj_var.get_property(num_var.name) == num_var

    def test_object_variable_node_getattr(
        self, var_name: str, var_description: str
    ) -> None:
        properties = {
            node.name: node
            for node in [
                get_random_simple_node(),
                get_random_simple_node(),
                get_random_simple_node(),
            ]
        }
        obj_var = ObjectVariableNode(
            name=var_name, description=var_description, properties=properties
        )

        num_var = get_random_numerical_node(var_name="example")
        obj_var.add_property(num_var)

        assert obj_var.example.value == num_var.value

    def test_variable_node_subscription(
        self, var_name: str, var_description: str
    ) -> None:
        updates = []

        def on_data_change(
            subscription: VariableSubscription, variable: VariableNode, value: Any
        ) -> None:
            updates.append((subscription.subscriber_id, value))

        obj_var = ObjectVariableNode(name=var_name, description=var_description)
        num_var = get_random_numerical_node()
        obj_var.add_property(num_var)
        subscription_1 = DataChangeSubscription("subscriber_1", "corr_1")
        subscription_2 = DataChangeSubscription("subscriber_2", "corr_2")
        obj_var.subscribe(subscription_1)
        obj_var.set_subscription_callback(on_data_change)
        num_var.subscribe(subscription_2)
        num_var.set_subscription_callback(on_data_change)

        num_var.write(10)

        assert len(updates) == 2
        assert updates[0] == ("subscriber_2", num_var.read())
        assert updates[1] == ("subscriber_1", obj_var.read())

    def test_delete_variable_node_subscription(
        self, var_name: str, var_description: str
    ) -> None:
        num_var = get_random_numerical_node(
            var_name=var_name, var_description=var_description
        )
        num_subscriptions = 5

        subscriptions = [
            num_var.subscribe(VariableSubscription(f"subscriber_{i}", f"corr_{i}"))
            for i in range(num_subscriptions)
        ]
        duplicate_subscription = num_var.subscribe(
            VariableSubscription("subscriber_1", "corr_1")
        )

        assert len(num_var.get_subscriptions()) == num_subscriptions
        assert all(subscriptions)
        assert not duplicate_subscription

        unsubscriptions = [
            num_var.unsubscribe(VariableSubscription(f"subscriber_{i}", f"corr_{i}"))
            for i in range(num_subscriptions)
        ]

        assert len(num_var.get_subscriptions()) == 0
        assert all(unsubscriptions)
