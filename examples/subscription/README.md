# Subscription Examples

This folder contains examples demonstrating the subscription mechanism in `VariableNode` from the machine data model.

## Prerequisites

- Ensure you are in the project root directory (`/path/to/glacier-machine-data-model`).
- The `machine_data_model` package should be importable (run from the root or install the package).

## Examples

### 1. Basic Subscription (`basic_subscription.py`)

Demonstrates subscribing to a `NumericalVariableNode`, setting a callback, and receiving notifications on value updates.

Run: `python examples/subscription/basic_subscription.py`

### 2. Data Change Notifications (`data_change_notification.py`)

Demonstrates `DataChangeSubscription`, which notifies when the value changes by more than a specified deadband.

Run: `python examples/subscription/data_change_notification.py`

### 3. Range Notifications (`range_notification.py`)

Demonstrates `RangeSubscription`, which notifies on transitions into or out of a specified range.

Run: `python examples/subscription/range_notification.py`

### 3. Unsubscribing (`unsubscribe_example.py`)

Illustrates subscribing multiple listeners and unsubscribing them (by object or by IDs), stopping notifications.

Run: `python examples/subscription/unsubscribe_example.py`

### 4. Hierarchical Notifications (`hierarchical_notifications.py`)

Demonstrates notifications propagating from child properties to parent `ObjectVariableNode` instances.

Run: `python examples/subscription/hierarchical_notifications.py`

### 5. Multiple Subscribers (`multiple_subscribers.py`)

Shows multiple subscriptions to the same node and how notifications are sent to all active subscribers.

Run: `python examples/subscription/multiple_subscribers.py`

## Notes

- Each example is self-contained and prints output to the console.
- Modify the scripts to experiment with different values or subscription types.
- For more details, refer to the `VariableNode` and `VariableSubscription` classes in `machine_data_model/nodes/`.
