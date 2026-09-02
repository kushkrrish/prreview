"""Dummy smoke tests for the repo's sample helper code."""

import pytest

from backend.dummy_test import Counter, add_numbers, divide_numbers, find_max, get_user_greeting


def test_add_numbers_returns_sum() -> None:
    assert add_numbers(2, 3) == 5


def test_add_numbers_rejects_non_ints() -> None:
    with pytest.raises(TypeError, match="Both inputs must be integers"):
        add_numbers(2, "3")


def test_divide_numbers_returns_value() -> None:
    assert divide_numbers(10, 2) == 5.0


def test_divide_numbers_rejects_zero() -> None:
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide_numbers(10, 0)


def test_get_user_greeting_handles_blank_and_none() -> None:
    assert get_user_greeting() == "Hello, stranger!"
    assert get_user_greeting("   ") == "Hello, stranger!"
    assert get_user_greeting("  alice  ") == "Hello, alice!"


def test_counter_increment_and_reset() -> None:
    counter = Counter(start=2, max_limit=5)
    counter.increment(3)
    assert counter.value == 5

    counter.increment(10)
    assert counter.value == 5

    counter.decrement(2)
    assert counter.value == 3

    counter.reset()
    assert counter.value == 0


def test_find_max_returns_largest_number() -> None:
    assert find_max([1, 4, 9, 2]) == 9


def test_find_max_rejects_empty_list() -> None:
    with pytest.raises(ValueError, match="List cannot be empty"):
        find_max([])