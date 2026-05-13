"""Simple Python calculator with basic arithmetic operations and error handling."""

from __future__ import annotations


def add(a: float, b: float) -> float:
    """Return the sum of two numbers.

    Args:
        a: First operand.
        b: Second operand.

    Returns:
        The sum a + b.
    """
    return a + b


def subtract(a: float, b: float) -> float:
    """Return the difference of two numbers.

    Args:
        a: First operand.
        b: Second operand.

    Returns:
        The difference a - b.
    """
    return a - b


def multiply(a: float, b: float) -> float:
    """Return the product of two numbers.

    Args:
        a: First operand.
        b: Second operand.

    Returns:
        The product a * b.
    """
    return a * b


def divide(a: float, b: float) -> float:
    """Return the quotient of two numbers.

    Args:
        a: First operand (numerator).
        b: Second operand (denominator).

    Returns:
        The quotient a / b.

    Raises:
        ZeroDivisionError: If b is zero.
    """
    if b == 0:
        raise ZeroDivisionError("division by zero is not allowed")
    return a / b
