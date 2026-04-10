"""Unit tests for feathers.generator.context — plural(), snake(), ModelView.py_fields."""

from __future__ import annotations

from feathers.generator.context import ModelView, build_context, plural, snake
from feathers.schema import load_schema

# ---------------------------------------------------------------------------
# plural() — coverage for lines 43 + 45
# ---------------------------------------------------------------------------


def test_plural_regular_word() -> None:
    assert plural("user") == "users"


def test_plural_word_ending_in_y() -> None:
    """Cover context.py:43 — 'y' → 'ies'."""
    assert plural("entry") == "entries"
    assert plural("category") == "categories"


def test_plural_word_ending_in_s() -> None:
    """Cover context.py:45 — already ends in 's' → unchanged."""
    assert plural("status") == "status"
    assert plural("address") == "address"


def test_plural_single_char() -> None:
    assert plural("x") == "xs"


# ---------------------------------------------------------------------------
# snake() — already 100% but exercised for completeness
# ---------------------------------------------------------------------------


def test_snake_camel() -> None:
    assert snake("UserProfile") == "user_profile"
    assert snake("HTMLParser") == "html_parser"


# ---------------------------------------------------------------------------
# ModelView.py_fields — coverage for lines 60-76
# ---------------------------------------------------------------------------


def test_model_view_py_fields(minimal_yaml_text: str) -> None:
    """Cover context.py:60-76 — py_fields property."""
    schema = load_schema(minimal_yaml_text)
    ctx = build_context(schema)
    model_view: ModelView = ctx["models"][0]
    fields = model_view.py_fields
    assert isinstance(fields, list)
    assert len(fields) == 2
    # Check field structure
    f_id = fields[0]
    assert f_id["name"] == "id"
    assert f_id["py_type"] == "UUID"
    assert f_id["sa_type"] == "UUID"
    assert f_id["primary"] is True

    f_label = fields[1]
    assert f_label["name"] == "label"
    assert f_label["py_type"] == "str"
    assert f_label["nullable"] is False
    assert f_label["max_length"] == 50
