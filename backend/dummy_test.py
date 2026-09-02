"""Dummy module for testing the PR review agent's ingestion pipeline."""


def add_numbers(a: int, b: int) -> int:
    """Returns the sum of two integers."""
    return a + b


def divide_numbers(a: int, b: int) -> float:
    """Returns a divided by b. Does not handle division by zero."""
    return a / b


def get_user_greeting(name: str) -> str:
    """Returns a greeting string for the given user name."""
    if name == "":
        return "Hello, stranger!"
    return f"Hello, {name}!"


class Counter:
    """A simple counter that tracks a running total."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def increment(self, amount: int = 1) -> None:
        self.value += amount

    def reset(self) -> None:
        self.value = 0


def find_max(numbers: list[int]) -> int:
    """Returns the maximum value in a list of integers."""
    max_val = numbers[0]
    for n in numbers:
        if n > max_val:
            max_val = n
    return max_val