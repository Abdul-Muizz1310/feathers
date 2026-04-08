"""Smoke test — the package imports and exposes a version."""

import feathers


def test_package_importable() -> None:
    assert feathers.__version__ == "0.1.0"
