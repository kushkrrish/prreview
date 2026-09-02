"""Dummy module for testing the PR review agent's ingestion pipeline."""


def add_numbers(a: int, b: int) -> int:
    """Returns the sum of two integers with input validation."""
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both inputs must be integers.")
    return a + b


def divide_numbers(a: int, b: int) -> float:
    """Returns a divided by b. Raises ValueError on division by zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


def get_user_greeting(name: str | None = None) -> str:
    """Returns a personalized greeting string handling None values."""
    if not name or not name.strip():
        return "Hello, stranger!"
    return f"Hello, {name.strip()}!"


class Counter:
    """A simple counter that tracks a running total with bounds."""

    def __init__(self, start: int = 0, max_limit: int = 100) -> None:
        self.value = start
        self.max_limit = max_limit

    def increment(self, amount: int = 1) -> None:
        """Increments value, capping at max_limit."""
        self.value = min(self.value + amount, self.max_limit)

    def decrement(self, amount: int = 1) -> None:
        """Decrements the counter by amount."""
        self.value -= amount

    def reset(self) -> None:
        self.value = 0


def find_max(numbers: list[int]) -> int:
    """Returns the maximum value in a list of integers. Returns None if empty."""
    if not numbers:
        raise ValueError("List cannot be empty.")
    return max(numbers)