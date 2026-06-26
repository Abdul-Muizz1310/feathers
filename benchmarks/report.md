# feathers benchmarks

## Generation speed (`feathers bench`)

`feathers bench` measures how fast feathers scaffolds a complete service. It
reuses the exact pipeline behind `feathers new` — `load_schema` followed by
`render_service` — so the number reflects real generation work rather than a
synthetic micro-benchmark.

### What it measures

- The bundled demo schema (`src/feathers/demos/users.yaml`: 1 model, 5
  endpoints, ~24 rendered files) is scaffolded into a throwaway temporary
  directory `--iterations` times (default 50).
- Each generation is timed with `time.perf_counter`. The temp directory is
  deleted before the next iteration, so disk usage stays flat and runs do not
  contaminate one another.
- The schema is parsed once up front, so YAML loading does not skew the
  per-generation timings.

It reports services generated, median and p95 milliseconds per generation, and
generations per second (derived from the median).

It needs no database and no network: it is fully local and reproducible, and a
default run completes in a few seconds.

### How to run

```bash
feathers bench               # 50 iterations (default)
feathers bench -n 200        # more iterations for a tighter estimate
uv run feathers bench        # from a checkout, without installing
```

### Measured result

Captured on this machine on 2026-06-27:

| Metric | Value |
|---|---|
| Service scaffolded from schema (median) | 37.29 ms |
| Service scaffolded from schema (p95) | 39.64 ms |
| Throughput | 26.8 gen/s |
| Iterations | 50 |

Host: Windows 11 (AMD64, AMD Ryzen-class CPU) - Python 3.12.12.

Numbers are machine-dependent: CPU, disk, and filesystem all affect them. Run
`feathers bench` on your own hardware for a figure that matches your
environment.

## Generated-service request throughput (v0.2 target)

A load test of a generated `GET /users/{id}` endpoint (target: >= 10,000
req/s) is a **v0.2 target and is not yet measured**. It requires the
DB-backed generated service planned for v0.2; today's generated models are
stubs with no database wiring, so a meaningful request-per-second load test is
not yet achievable. When that lands, `feathers bench` will grow a Locust-driven
mode and the measured request throughput will be recorded here.
