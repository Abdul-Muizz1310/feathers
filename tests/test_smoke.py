"""Smoke test — the package imports and exposes its installed version."""

from importlib.metadata import version

import feathers


def test_package_importable() -> None:
    # __version__ is derived from the installed distribution metadata, so it
    # tracks pyproject's version automatically and cannot drift from it.
    assert feathers.__version__
    assert feathers.__version__ == version("feathers-cli")
