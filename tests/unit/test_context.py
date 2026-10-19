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
    """Words ending in s/sh/ch/x/z get 'es' suffix."""
    assert plural("status") == "statuses"
    assert plural("address") == "addresses"
    assert plural("crash") == "crashes"
    assert plural("match") == "matches"


def test_plural_single_char() -> None:
    assert plural("x") == "xes"


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


# ---------------------------------------------------------------------------
# 0.2.0 — service id, public endpoints, per-model pagination flags
# ---------------------------------------------------------------------------

_PAGINATION_YAML = """\
service:
  name: feathers_demo
models:
  - name: User
    fields:
      - { name: id, type: uuid, primary: true }
  - name: Order
    fields:
      - { name: id, type: int, primary: true }
  - name: Tag
    fields:
      - { name: id, type: int, primary: true }
endpoints:
  - { method: GET, path: "/users", handler: users.list, paginate: cursor }
  - { method: GET, path: "/orders", handler: orders.list, paginate: none }
  - { method: GET, path: "/orders/{id}", handler: orders.get, auth: none }
  - { method: POST, path: "/orders/{id}/ship", handler: orders.ship, auth: none }
  - { method: GET, path: "/tags/{id}", handler: tags.get, auth: admin }
"""


def test_service_id_is_the_kebab_form_of_the_name() -> None:
    ctx = build_context(load_schema(_PAGINATION_YAML))
    assert ctx["service"]["id"] == "feathers-demo"


def test_service_id_of_a_camel_case_name() -> None:
    ctx = build_context(load_schema(_PAGINATION_YAML.replace("feathers_demo", "HelloUsers")))
    assert ctx["service"]["id"] == "hello-users"
    assert ctx["service"]["snake"] == "hello_users"


def test_pagination_flags_follow_the_list_endpoints() -> None:
    ctx = build_context(load_schema(_PAGINATION_YAML))
    models = {m.name: m for m in ctx["models"]}
    assert (models["User"].cursor_list, models["User"].offset_list) == (True, False)
    # `paginate: none` on a list is offset pagination with the default window.
    assert (models["Order"].cursor_list, models["Order"].offset_list) == (False, True)
    assert (models["Tag"].cursor_list, models["Tag"].offset_list) == (False, False)


def test_public_endpoints_are_exactly_the_auth_none_routes() -> None:
    ctx = build_context(load_schema(_PAGINATION_YAML))
    assert ctx["public_endpoints"] == [
        ("GET", r"^/orders/[^/]+$"),
        ("POST", r"^/orders/[^/]+/ship$"),
    ]


def test_endpoint_url_template_substitutes_the_path_parameter() -> None:
    ctx = build_context(load_schema(_PAGINATION_YAML))
    by_handler = {e.handler: e for e in ctx["endpoints"]}
    assert by_handler["orders.get"].route_path == "/{id}"
    assert by_handler["orders.get"].url_template == "/orders/{item_id}"
    assert by_handler["orders.list"].route_path == ""
    assert by_handler["orders.list"].url_template == "/orders"
