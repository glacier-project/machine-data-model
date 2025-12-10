"""
Tests for the timestamp module.

This module contains unit tests for the centralized timestamp provider,
verifying default behavior, custom providers, and reset functionality.
"""

import time

from machine_data_model.utils.timestamp import (
    get_timestamp_ns,
    get_timestamp_provider,
    reset_timestamp_provider,
    set_timestamp_provider,
)


class TestTimestampProvider:
    """
    Tests for the timestamp provider functionality.
    """

    def teardown_method(self) -> None:
        """
        Reset the timestamp provider after each test.
        """
        reset_timestamp_provider()

    def test_get_timestamp_ns_returns_integer(self) -> None:
        """
        Verify that get_timestamp_ns returns an integer.
        """
        timestamp = get_timestamp_ns()
        assert isinstance(timestamp, int)

    def test_get_timestamp_ns_returns_nanoseconds(self) -> None:
        """
        Verify that get_timestamp_ns returns a value in nanoseconds.

        The returned value should be close to time.time_ns().
        """
        before = time.time_ns()
        timestamp = get_timestamp_ns()
        after = time.time_ns()

        assert before <= timestamp <= after

    def test_get_timestamp_ns_increases_over_time(self) -> None:
        """
        Verify that successive calls to get_timestamp_ns return increasing
        values.
        """
        timestamp1 = get_timestamp_ns()
        # Small delay to ensure time passes
        time.sleep(0.001)
        timestamp2 = get_timestamp_ns()

        assert timestamp2 > timestamp1

    def test_set_timestamp_provider_with_fixed_value(self) -> None:
        """
        Verify that set_timestamp_provider allows setting a fixed timestamp.
        """
        fixed_timestamp = 1672531200000000000  # 2023-01-01 00:00:00 UTC in ns
        set_timestamp_provider(lambda: fixed_timestamp)

        assert get_timestamp_ns() == fixed_timestamp
        assert get_timestamp_ns() == fixed_timestamp

    def test_set_timestamp_provider_with_custom_function(self) -> None:
        """
        Verify that set_timestamp_provider works with a custom function.
        """
        counter = [0]

        def incrementing_provider() -> int:
            counter[0] += 1000000000
            return counter[0]

        set_timestamp_provider(incrementing_provider)

        assert get_timestamp_ns() == 1000000000
        assert get_timestamp_ns() == 2000000000
        assert get_timestamp_ns() == 3000000000

    def test_get_timestamp_provider_returns_current_provider(self) -> None:
        """
        Verify that get_timestamp_provider returns the current provider.
        """
        # Get default provider
        default_provider = get_timestamp_provider()
        assert callable(default_provider)

        # Set custom provider and verify it's returned
        def custom_provider() -> int:
            return 42

        set_timestamp_provider(custom_provider)

        assert get_timestamp_provider() is custom_provider

    def test_reset_timestamp_provider_restores_default(self) -> None:
        """
        Verify that reset_timestamp_provider restores the default behavior.
        """
        # Set a custom provider
        fixed_timestamp = 1672531200000000000
        set_timestamp_provider(lambda: fixed_timestamp)
        assert get_timestamp_ns() == fixed_timestamp

        # Reset to default
        reset_timestamp_provider()

        # Should now return real time (close to time.time_ns())
        before = time.time_ns()
        timestamp = get_timestamp_ns()
        after = time.time_ns()

        assert before <= timestamp <= after
        assert timestamp != fixed_timestamp

    def test_timestamp_provider_isolation_between_tests(self) -> None:
        """
        Verify that teardown properly resets the provider.

        This test sets a custom provider and relies on teardown to reset it.
        The next test should see the default provider.
        """
        set_timestamp_provider(lambda: 999999999999999999)
        assert get_timestamp_ns() == 999999999999999999

    def test_provider_returning_zero(self) -> None:
        """
        Verify that a provider returning zero works correctly.
        """
        set_timestamp_provider(lambda: 0)
        assert get_timestamp_ns() == 0

    def test_provider_returning_large_value(self) -> None:
        """
        Verify that a provider returning a large value works correctly.
        """
        large_timestamp = 9999999999999999999
        set_timestamp_provider(lambda: large_timestamp)
        assert get_timestamp_ns() == large_timestamp

    def test_multiple_set_operations(self) -> None:
        """
        Verify that multiple set operations work correctly.
        """
        set_timestamp_provider(lambda: 100)
        assert get_timestamp_ns() == 100

        set_timestamp_provider(lambda: 200)
        assert get_timestamp_ns() == 200

        set_timestamp_provider(lambda: 300)
        assert get_timestamp_ns() == 300

    def test_default_provider_after_fresh_import(self) -> None:
        """
        Verify that after reset, the provider behaves like time.time_ns().
        """
        reset_timestamp_provider()

        # The default provider should return values very close to time.time_ns()
        tolerance_ns = 1_000_000  # 1ms tolerance
        expected = time.time_ns()
        actual = get_timestamp_ns()

        assert abs(actual - expected) < tolerance_ns
