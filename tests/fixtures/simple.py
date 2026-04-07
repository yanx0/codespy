# Simple fixture — low complexity
# This is a comment line

def greet(name: str) -> str:
    """Return a greeting."""
    return f"Hello, {name}!"


def add(a: int, b: int) -> int:
    return a + b


class Calculator:
    """Simple calculator class."""

    def multiply(self, a: int, b: int) -> int:
        return a * b

    def divide(self, a: float, b: float) -> float:
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b
