"""Measure feathers service-generation speed.

This module benchmarks the *generation* pipeline that backs ``feathers new``:
it scaffolds a service from a bundled demo schema into a throwaway directory a
number of times, timing each render with :func:`time.perf_counter`.

The benchmark is deliberately local and reproducible: it needs no database and
no network. It reuses the exact same entry points as ``feathers new``
(:func:`feathers.schema.load_schema` and
:func:`feathers.generator.render_service`) so the measured number reflects real
generation work, not a duplicated code path.
"""

from __future__ import annotations

import statistics
import tempfile
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter

from feathers.generator import render_service
from feathers.schema import ServiceSchema, load_schema

DEFAULT_ITERATIONS: int = 50
"""Default number of generations to time when none is supplied."""

DEMO_SCHEMA: Path = Path(__file__).resolve().parent / "demos" / "users.yaml"
"""The bundled schema scaffolded during a benchmark run."""


@dataclass(frozen=True)
class BenchResult:
    """Outcome of a generation benchmark.

    Attributes:
        iterations: Number of services generated and timed.
        median_ms: Median wall-clock time per generation, in milliseconds.
        p95_ms: 95th-percentile time per generation, in milliseconds.
        gen_per_sec: Generations per second, derived from the median time.
    """

    iterations: int
    median_ms: float
    p95_ms: float
    gen_per_sec: float


def _percentile(samples: list[float], fraction: float) -> float:
    """Return the ``fraction`` percentile of ``samples`` (linear, nearest-rank).

    Args:
        samples: Non-empty list of timing samples.
        fraction: Target percentile in the closed interval ``[0, 1]``.

    Returns:
        The sample at the nearest-rank position for ``fraction``.
    """
    ordered = sorted(samples)
    if len(ordered) == 1:
        return ordered[0]
    rank = max(0, min(len(ordered) - 1, round(fraction * (len(ordered) - 1))))
    return ordered[rank]


def run_benchmark(
    iterations: int = DEFAULT_ITERATIONS,
    *,
    schema: ServiceSchema | None = None,
) -> BenchResult:
    """Scaffold a service ``iterations`` times and report timing statistics.

    Each iteration renders the full service tree into a fresh temporary
    directory that is deleted before the next iteration, so disk usage stays
    flat and no run contaminates another.

    Args:
        iterations: How many generations to time. Must be at least 1.
        schema: Pre-parsed schema to scaffold. Defaults to the bundled demo
            schema, parsed once so YAML loading does not skew the timings.

    Returns:
        A :class:`BenchResult` summarising the timed generations.

    Raises:
        ValueError: If ``iterations`` is less than 1.
    """
    if iterations < 1:
        raise ValueError(f"iterations must be >= 1, got {iterations}")

    parsed = schema if schema is not None else load_schema(DEMO_SCHEMA)

    samples_ms: list[float] = []
    for _ in range(iterations):
        with tempfile.TemporaryDirectory(prefix="feathers-bench-") as tmp:
            start = perf_counter()
            render_service(parsed, out_dir=Path(tmp), force=True)
            samples_ms.append((perf_counter() - start) * 1000.0)

    median_ms = statistics.median(samples_ms)
    return BenchResult(
        iterations=iterations,
        median_ms=median_ms,
        p95_ms=_percentile(samples_ms, 0.95),
        gen_per_sec=1000.0 / median_ms if median_ms > 0 else float("inf"),
    )


def format_report(result: BenchResult) -> str:
    """Render a benchmark result as a human-readable multi-line report.

    Args:
        result: The benchmark outcome to format.

    Returns:
        A newline-joined report listing the schema, iteration count, median and
        p95 latency in milliseconds, and generations per second.
    """
    return "\n".join(
        (
            f"schema: {DEMO_SCHEMA.name}",
            f"services generated: {result.iterations}",
            f"median: {result.median_ms:.2f} ms",
            f"p95: {result.p95_ms:.2f} ms",
            f"throughput: {result.gen_per_sec:.1f} gen/s",
        )
    )
