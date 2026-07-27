"""Tests for NIA normalization/validation and the salary-exclusion rule.

Run:  pytest        (or)  python -m pytest
"""
from app.nia import normalize_nia, is_valid_nia
from app.columns import display_fields, header_key, is_salary


def test_normalize_strips_hyphens_and_spaces_and_uppercases():
    assert normalize_nia("GHA-001849879-4") == "GHA0018498794"
    assert normalize_nia("gha 001849879 4") == "GHA0018498794"
    assert normalize_nia("  GHA0018498794  ") == "GHA0018498794"
    assert normalize_nia("GHA0018498794") == "GHA0018498794"


def test_normalize_forms_are_equal():
    assert normalize_nia("GHA-001849879-4") == normalize_nia("GHA0018498794")


def test_normalize_empty():
    assert normalize_nia("") == ""
    assert normalize_nia(None) == ""


def test_validation():
    assert is_valid_nia("GHA0018498794") is True
    assert is_valid_nia("GHA-001849879-4".replace("-", "")) is True
    assert is_valid_nia("GHA001849879") is False   # too few digits
    assert is_valid_nia("ABC0018498794") is False   # wrong prefix
    assert is_valid_nia("") is False


def test_header_key_normalizes():
    assert header_key(" First  Name ") == "FIRST NAME"
    assert header_key("monthly salary") == "MONTHLY SALARY"


def test_salary_is_excluded_from_display():
    record = {
        "FIRST NAME": "Ama",
        "LAST NAME": "Mensah",
        "MONTHLY SALARY": "5000",
        "GENDER": "F",
    }
    fields = dict(display_fields(record))
    assert "MONTHLY SALARY" not in fields
    assert fields["FIRST NAME"] == "Ama"
    assert is_salary("MONTHLY SALARY") is True
