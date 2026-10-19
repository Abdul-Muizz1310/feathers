"""Schema shapes the generated-output tests render (see docs/specs/07).

Each shape stresses a different corner of the templates; together with the bundled
``demos/users.yaml`` they cover every field kind, both pagination styles, no list at
all, a custom handler, an ``auth: none`` route, an integer key, and two models declared
out of alphabetical order (import sorting).
"""

from __future__ import annotations

OFFSET = """\
service:
  name: offset_svc
  description: An offset-paginated list and a hard delete
models:
  - name: Item
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: label, type: str, max_length: 50 }
endpoints:
  - { method: GET, path: "/items", handler: items.list, auth: viewer, paginate: offset }
  - { method: POST, path: "/items", handler: items.create, auth: editor }
  - { method: GET, path: "/items/{id}", handler: items.get, auth: viewer }
  - { method: DELETE, path: "/items/{id}", handler: items.delete, auth: admin }
"""

KITCHEN = """\
service:
  name: kitchen_sink
  description: Every field kind, a custom handler and a public route
models:
  - name: Widget
    audit: true
    fields:
      - { name: id, type: int, primary: true }
      - { name: title, type: str, max_length: 80, unique: true }
      - { name: body, type: text, nullable: true }
      - { name: price, type: float, default: 1.5 }
      - { name: active, type: bool, default: true }
      - { name: meta, type: json, nullable: true }
      - { name: seen_at, type: datetime, nullable: true }
      - { name: kind, type: enum, values: [small, large], default: small }
  - name: Gadget
    soft_delete: true
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: label, type: str }
endpoints:
  - { method: GET, path: "/widgets", handler: widgets.list, auth: none, paginate: offset }
  - { method: POST, path: "/widgets", handler: widgets.create, auth: editor }
  - { method: GET, path: "/widgets/{id}", handler: widgets.get, auth: none }
  - { method: PUT, path: "/widgets/{id}", handler: widgets.update, auth: editor }
  - { method: DELETE, path: "/widgets/{id}", handler: widgets.delete, auth: admin }
  - { method: POST, path: "/widgets/{id}/publish", handler: widgets.publish, auth: admin }
  - { method: GET, path: "/gadgets", handler: gadgets.list, auth: viewer, paginate: cursor }
  - { method: POST, path: "/gadgets", handler: gadgets.create, auth: any }
  - { method: GET, path: "/gadgets/{id}", handler: gadgets.get }
  - { method: PATCH, path: "/gadgets/{id}", handler: gadgets.update, auth: editor }
  - { method: DELETE, path: "/gadgets/{id}", handler: gadgets.delete, auth: admin }
"""

BARE = """\
service:
  name: bare_svc
models:
  - name: Note
    fields:
      - { name: id, type: uuid, primary: true }
      - { name: text, type: text }
endpoints:
  - { method: GET, path: "/notes/{id}", handler: notes.get, auth: any }
observability:
  metrics: none
  logging: stdlib
"""

#: name -> (schema YAML, generated package / directory name)
SHAPES: dict[str, tuple[str, str]] = {
    "offset": (OFFSET, "offset_svc"),
    "kitchen": (KITCHEN, "kitchen_sink"),
    "bare": (BARE, "bare_svc"),
}
