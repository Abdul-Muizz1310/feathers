# Demo script

> Placeholder. Filled in at Phase 1 S6 once the end-to-end generate-and-run path is green.

Planned 10-second demo:

1. `feathers new --schema demos/users.yaml --name hello-users --out /tmp`
2. `cd /tmp/hello-users && make run`
3. Open `http://localhost:8000/docs` — Swagger UI loads
4. `curl http://localhost:8000/health` — `{"status":"ok"}`
5. `feathers add endpoint --schema demos/users-extended.yaml` — new route appears,
   existing hand-written code untouched
