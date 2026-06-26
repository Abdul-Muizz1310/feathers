"""Tests for feathers.bench — the generation-speed benchmark."""

from __future__ import annotations

import pytest

from feathers import bench
from feathers.bench import (
    DEFAULT_ITERATIONS,
    BenchResult,
    format_report,
    run_benchmark,
)


def test_default_iterations_is_positive() -> None:
    assert DEFAULT_ITERATIONS >= 1


def test_run_benchmark_times_requested_iterations() -> None:
    result = run_benchmark(3)
    assert isinstance(result, BenchResult)
    assert result.iterations == 3
    assert result.median_ms > 0
    assert result.p95_ms >= result.median_ms
    assert result.gen_per_sec > 0


def test_run_benchmark_single_iteration() -> None:
    """One sample exercises the single-element percentile branch."""
    result = run_benchmark(1)
    assert result.iterations == 1
    # With one sample, median and p95 are the same observation.
    assert result.p95_ms == pytest.approx(result.median_ms)


def test_run_benchmark_rejects_non_positive_iterations() -> None:
    with pytest.raises(ValueError, match="iterations must be >= 1"):
        run_benchmark(0)


def test_run_benchmark_accepts_preparsed_schema() -> None:
    """Passing a parsed schema skips re-reading the demo YAML each call."""
    from feathers.schema import load_schema

    parsed = load_schema(bench.DEMO_SCHEMA)
    result = run_benchmark(2, schema=parsed)
    assert result.iterations == 2


def test_gen_per_sec_handles_zero_median(monkeypatch: pytest.MonkeyPatch) -> None:
    """A degenerate zero-time median yields an infinite throughput, not a crash."""
    ticks = iter([0.0, 0.0])
    monkeypatch.setattr(bench, "perf_counter", lambda: next(ticks))
    result = run_benchmark(1)
    assert result.median_ms == 0.0
    assert result.gen_per_sec == float("inf")


def test_format_report_contains_all_metrics() -> None:
    result = BenchResult(iterations=7, median_ms=12.5, p95_ms=20.0, gen_per_sec=80.0)
    report = format_report(result)
    assert "services generated: 7" in report
    assert "median: 12.50 ms" in report
    assert "p95: 20.00 ms" in report
    assert "throughput: 80.0 gen/s" in report
    assert bench.DEMO_SCHEMA.name in report
