"""Dummy module for testing the PR review agent's ingestion pipeline."""


def add_numbers(a: int, b: int) -> int:
    """Returns the sum of two integers."""
    return a + b


def divide_numbers(a: int, b: int) -> float:
    """Returns a divided by b. Raises ValueError on division by zero."""
    if b == 0:
        raise ValueError("Cannot divide by zero.")
    return a / b


def get_user_greeting(name: str) -> str:
    """Returns a personalized greeting string."""
    if not name or not name.strip():
        return "Hello, stranger!"
    return f"Hello, {name.strip()}!"


class Counter:
    """A simple counter that tracks a running total."""

    def __init__(self, start: int = 0) -> None:
        self.value = start

    def increment(self, amount: int = 1) -> None:
        self.value += amount

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