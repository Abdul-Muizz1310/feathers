"""feathers — scaffold production FastAPI services from YAML."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("feathers-cli")
except PackageNotFoundError:  # pragma: no cover - only when running un-installed
    __version__ = "0.0.0"
