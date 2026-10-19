# feathers benchmarks

## Generation speed (`feathers bench`)

`feathers bench` measures how fast feathers scaffolds a complete service. It
reuses the exact pipeline behind `feathers new` — `load_schema` followed by
`render_service` — so the number reflects real generation work rather than a
synthetic micro-benchmark.

### What it measures

- The bundled demo schema (`src/feathers/demos/users.yaml`: 1 model, 5
  endpoints, 41 rendered files as of 0.2.0) is scaffolded into a throwaway temporary
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

0.2.0, captured on 2026-10-20 with `feathers bench -n 200` on a shared Linux host
(Linux 7.0, x86_64, 16 cores, Python 3.12.14) under a load average of ~9 from other
work — treat it as an upper bound:

| Metric | Value |
|---|---|
| Service scaffolded from schema (median) | 153.48 ms |
| Service scaffolded from schema (p95) | 287.87 ms |
| Throughput | 6.5 gen/s |
| Iterations | 200 |

On the same host and load, the pre-0.2 generator's 36-file tree measured a 168.72 ms median (50
iterations), so the five added templates did not measurably slow generation.

Earlier, 0.1.x on a different machine, captured on 2026-06-27:

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

## Generated-service request throughput (not yet measured)

The generated service is now DB-backed — each model emits a SQLAlchemy ORM
table, an async repository, a service layer, and CRUD routes, and the service
boots and persists on SQLite (Postgres via `DATABASE_URL`). A request-per-second
load test of a generated `GET /users/{id}` endpoint is therefore achievable, but
it is **not yet measured** — no RPS figure is claimed here. The next step is a
Locust-driven mode of `feathers bench`; the measured throughput and latency will
be recorded here once it runs.
