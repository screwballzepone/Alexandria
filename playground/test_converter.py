"""
Tests for hypothetical temperature conversion functions.

These tests cover:
    - celsius_to_fahrenheit(c)
    - fahrenheit_to_celsius(f)

Edge cases: 0°C, 100°C, -40°C (unique point where °C == °F), absolute zero.
"""

import math

import pytest

# ---------------------------------------------------------------------------
# The functions under test are imported from wherever they'll live.
# For now we define stub versions so the tests compile and FAIL as written.
# Replace the import below with the real module once it exists:
#
#     from temperature import celsius_to_fahrenheit, fahrenheit_to_celsius
# ---------------------------------------------------------------------------

# ---- STUB DEFINITIONS — remove when the real module exists ----------------
# These deliberately raise NotImplementedError so every test fails.


def celsius_to_fahrenheit(c: float) -> float:
    """Convert Celsius to Fahrenheit.  Formula: (c * 9/5) + 32."""
    raise NotImplementedError("celsius_to_fahrenheit not implemented")


def fahrenheit_to_celsius(f: float) -> float:
    """Convert Fahrenheit to Celsius.  Formula: (f - 32) * 5/9."""
    raise NotImplementedError("fahrenheit_to_celsius not implemented")


# ---- ACCURACY HELPER ------------------------------------------------------


def _approx(actual: float, expected: float, tolerance: float = 1e-9) -> bool:
    """Assert two floats are close within an absolute tolerance."""
    return abs(actual - expected) < tolerance


# ====================================================================
# TEMPERATURE CONVERSION TESTS
# ====================================================================


class TestCelsiusToFahrenheit:
    """celsius_to_fahrenheit(c) -> float"""

    def test_water_freezing_point(self):
        """0°C should convert to 32°F (standard freezing point of water)."""
        result = celsius_to_fahrenheit(0.0)
        assert _approx(result, 32.0), f"Expected 32.0, got {result}"

    def test_water_boiling_point(self):
        """100°C should convert to 212°F (standard boiling point of water)."""
        result = celsius_to_fahrenheit(100.0)
        assert _approx(result, 212.0), f"Expected 212.0, got {result}"

    def test_negative_forty(self):
        """-40°C should convert to -40°F (unique crossover point)."""
        result = celsius_to_fahrenheit(-40.0)
        assert _approx(result, -40.0), f"Expected -40.0, got {result}"

    def test_absolute_zero(self):
        """-273.15°C should convert to -459.67°F (absolute zero)."""
        result = celsius_to_fahrenheit(-273.15)
        assert _approx(result, -459.67, tolerance=1e-2), (
            f"Expected -459.67, got {result}"
        )

    def test_room_temperature(self):
        """21°C should convert to 69.8°F (typical room temp)."""
        result = celsius_to_fahrenheit(21.0)
        assert _approx(result, 69.8), f"Expected 69.8, got {result}"

    def test_human_body_temperature(self):
        """37°C should convert to 98.6°F (average human body temp)."""
        result = celsius_to_fahrenheit(37.0)
        assert _approx(result, 98.6), f"Expected 98.6, got {result}"

    def test_positive_integer_input(self):
        """Accepts int and returns float."""
        result = celsius_to_fahrenheit(10)
        assert isinstance(result, float), "Should return a float"
        assert _approx(result, 50.0), f"Expected 50.0, got {result}"

    def test_negative_celsius(self):
        """-10°C should convert to 14°F."""
        result = celsius_to_fahrenheit(-10.0)
        assert _approx(result, 14.0), f"Expected 14.0, got {result}"


class TestFahrenheitToCelsius:
    """fahrenheit_to_celsius(f) -> float"""

    def test_water_freezing_point(self):
        """32°F should convert to 0°C."""
        result = fahrenheit_to_celsius(32.0)
        assert _approx(result, 0.0), f"Expected 0.0, got {result}"

    def test_water_boiling_point(self):
        """212°F should convert to 100°C."""
        result = fahrenheit_to_celsius(212.0)
        assert _approx(result, 100.0), f"Expected 100.0, got {result}"

    def test_negative_forty(self):
        """-40°F should convert to -40°C (unique crossover point)."""
        result = fahrenheit_to_celsius(-40.0)
        assert _approx(result, -40.0), f"Expected -40.0, got {result}"

    def test_absolute_zero(self):
        """-459.67°F should convert to -273.15°C (absolute zero)."""
        result = fahrenheit_to_celsius(-459.67)
        assert _approx(result, -273.15, tolerance=1e-2), (
            f"Expected -273.15, got {result}"
        )

    def test_room_temperature(self):
        """69.8°F should convert to 21°C."""
        result = fahrenheit_to_celsius(69.8)
        assert _approx(result, 21.0), f"Expected 21.0, got {result}"

    def test_human_body_temperature(self):
        """98.6°F should convert to 37°C."""
        result = fahrenheit_to_celsius(98.6)
        assert _approx(result, 37.0), f"Expected 37.0, got {result}"

    def test_positive_integer_input(self):
        """Accepts int and returns float."""
        result = fahrenheit_to_celsius(32)
        assert isinstance(result, float), "Should return a float"
        assert _approx(result, 0.0), f"Expected 0.0, got {result}"


# ====================================================================
# ROUND-TRIP SYMMETRY TESTS
# ====================================================================


class TestRoundTrip:
    """Conversions should be self-inverse (within floating point precision)."""

    @pytest.mark.parametrize(
        "celsius",
        [
            -273.15,
            -40.0,
            -20.0,
            0.0,
            21.0,
            37.0,
            100.0,
            5000.0,
            -1000.0,
            1.0 / 3.0,
            math.pi,
            float("inf"),
        ],
    )
    def test_celsius_round_trip(self, celsius):
        """round-trip: celsius -> fahrenheit -> celsius recovers original."""
        if math.isinf(celsius):
            f = celsius_to_fahrenheit(celsius)
            c = fahrenheit_to_celsius(f)
            assert c == celsius, f"Infinite round-trip failed: {c} != {celsius}"
        else:
            f = celsius_to_fahrenheit(celsius)
            c = fahrenheit_to_celsius(f)
            assert _approx(c, celsius, tolerance=1e-9), (
                f"Round-trip failed: {celsius}°C -> {f}°F -> {c}°C"
            )

    @pytest.mark.parametrize(
        "fahrenheit",
        [
            -459.67,
            -40.0,
            0.0,
            32.0,
            69.8,
            98.6,
            212.0,
            9000.0,
            -1000.0,
            1.0 / 3.0,
            math.e,
            float("-inf"),
        ],
    )
    def test_fahrenheit_round_trip(self, fahrenheit):
        """round-trip: fahrenheit -> celsius -> fahrenheit recovers original."""
        if math.isinf(fahrenheit):
            c = fahrenheit_to_celsius(fahrenheit)
            f = celsius_to_fahrenheit(c)
            assert f == fahrenheit, f"Infinite round-trip failed: {f} != {fahrenheit}"
        else:
            c = fahrenheit_to_celsius(fahrenheit)
            f = celsius_to_fahrenheit(c)
            assert _approx(f, fahrenheit, tolerance=1e-9), (
                f"Round-trip failed: {fahrenheit}°F -> {c}°C -> {f}°F"
            )


# ====================================================================
# ERROR / INVALID INPUT TESTS
# ====================================================================


class TestErrorHandling:
    """The conversion functions must handle invalid inputs gracefully."""

    def test_none_input_raises_type_error(self):
        """Passing None should raise TypeError (cannot multiply NoneType)."""
        with pytest.raises(TypeError):
            celsius_to_fahrenheit(None)
        with pytest.raises(TypeError):
            fahrenheit_to_celsius(None)

    def test_string_input_raises_type_error(self):
        """Passing a string should raise TypeError (cannot multiply str)."""
        with pytest.raises(TypeError):
            celsius_to_fahrenheit("100")
        with pytest.raises(TypeError):
            fahrenheit_to_celsius("212")

    def test_list_input_raises_type_error(self):
        """Passing a list should raise TypeError."""
        with pytest.raises(TypeError):
            celsius_to_fahrenheit([0])
        with pytest.raises(TypeError):
            fahrenheit_to_celsius([32])

    def test_infinity_conversion(self):
        """Infinity should convert to infinity (no crash)."""
        inf_p = float("inf")
        inf_n = float("-inf")

        assert _approx(celsius_to_fahrenheit(inf_p), inf_p), "Inf + failed"
        assert _approx(celsius_to_fahrenheit(inf_n), inf_n), "-Inf failed"
        assert _approx(fahrenheit_to_celsius(inf_p), inf_p), "Inf reverse failed"
        assert _approx(fahrenheit_to_celsius(inf_n), inf_n), "-Inf reverse failed"

    def test_nan_input(self):
        """NaN input should produce NaN output (no crash)."""
        nan = float("nan")
        c_result = celsius_to_fahrenheit(nan)
        f_result = fahrenheit_to_celsius(nan)
        assert math.isnan(c_result), f"Expected NaN, got {c_result}"
        assert math.isnan(f_result), f"Expected NaN, got {f_result}"

    def test_bool_input(self):
        """Bool input should be treated as int (True=1, False=0) or raise TypeError."""
        # This depends on implementation: bool is a subclass of int in Python.
        # Either behavior is acceptable — just ensure no crash.
        try:
            result = celsius_to_fahrenheit(True)
            assert _approx(result, 33.8), (
                f"If bool accepted, True (1°C) -> 33.8°F, got {result}"
            )
        except TypeError:
            pass  # Also acceptable — strictly typed

        try:
            result = fahrenheit_to_celsius(False)
            assert _approx(result, -17.77777777777778, tolerance=1e-6), (
                f"If bool accepted, False (0°F) -> -17.78°C, got {result}"
            )
        except TypeError:
            pass  # Also acceptable
