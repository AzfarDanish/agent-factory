"""Tests for coloring page domain rules."""

import pytest
from src.core.coloring_domain import (
    validate_request, validate_age_group, validate_style, validate_prompt,
    validate_quantity, get_complexity_limit, get_line_width_range,
    ColoringPageError, AgeGroup, Style,
)


class TestValidateRequest:
    def test_valid_request(self):
        result = validate_request("a dragon", "child", "cartoon")
        assert result["prompt"] == "a dragon"
        assert result["age_group"] == "child"
        assert result["style"] == "cartoon"
        assert result["quantity"] == 1

    def test_valid_request_with_quantity(self):
        result = validate_request("a dragon", "adult", "mandala", quantity=5)
        assert result["quantity"] == 5

    def test_invalid_age_group(self):
        with pytest.raises(ColoringPageError, match="Invalid age_group"):
            validate_request("a dragon", "senior", "simple")

    def test_invalid_style(self):
        with pytest.raises(ColoringPageError, match="not allowed"):
            validate_request("a dragon", "child", "mandala")

    def test_style_not_allowed_for_age(self):
        with pytest.raises(ColoringPageError, match="not allowed"):
            validate_request("a dragon", "toddler", "mandala")

    def test_short_prompt(self):
        with pytest.raises(ColoringPageError, match="at least 3 characters"):
            validate_request("ab", "child", "simple")

    def test_long_prompt(self):
        with pytest.raises(ColoringPageError, match="500 characters"):
            validate_request("x" * 501, "child", "simple")

    def test_invalid_quantity(self):
        with pytest.raises(ColoringPageError, match="Quantity"):
            validate_request("dragon", "child", "simple", quantity=0)


class TestAgeGroup:
    def test_valid(self):
        assert validate_age_group("toddler") == AgeGroup.TODDLER
        assert validate_age_group("CHILD") == AgeGroup.CHILD

    def test_invalid(self):
        with pytest.raises(ColoringPageError):
            validate_age_group("alien")


class TestStyle:
    def test_valid(self):
        assert validate_style("simple", AgeGroup.TODDLER) == Style.SIMPLE

    def test_not_allowed(self):
        with pytest.raises(ColoringPageError):
            validate_style("mandala", AgeGroup.TODDLER)

    def test_all_styles_for_adult(self):
        for s in Style:
            result = validate_style(s.value, AgeGroup.ADULT)
            assert result == s


class TestComplexityLimits:
    def test_toddler_limit(self):
        assert get_complexity_limit(AgeGroup.TODDLER) == 5

    def test_child_limit(self):
        assert get_complexity_limit(AgeGroup.CHILD) == 10

    def test_adult_limit(self):
        assert get_complexity_limit(AgeGroup.ADULT) == 999

    def test_child_line_width(self):
        lo, hi = get_line_width_range(AgeGroup.CHILD)
        assert lo >= 3
        assert hi <= 5
