# 06 — Generated platform auth: contract v2

## Goal

Every service `feathers new` emits authenticates its callers exactly as the portfolio's
platform token contract v2 says (`docs/specs/platform-contract-v2.md` in the workspace
meta-repo, decision DR-0033). The generated `core/platform_token.py` is one copy of that
contract (DR-0006: each backend owns its copy), so this spec restates the parts a
generated service implements and lists the cases its own test suite must prove.

Scope: **bastion's key only.** Contract v2 also lets a backend trust its own DR-0030
frontend key; a generated service has no frontend, so it trusts exactly one issuer
(`iss == "bastion"`). The `frontend` role still ranks (as `viewer`) so the role table
matches the contract.

## Inputs

| Input | Source |
|---|---|
| Service id | Derived at generation time from the schema: `snake(service.name)` with `_` → `-` (`feathers_demo` → `feathers-demo`). Emitted as the constant `SERVICE_ID`; never configuration. |
| Bastion public key | `BASTION_SIGNING_KEY_PUBLIC` (base64 SPKI DER, Ed25519), else fetched from `BASTION_PUBLIC_KEY_URL` (JSON field `publicKey`, same encoding) and cached for an hour. |
| Token | `X-Platform-Token`, else `Authorization: Bearer <token>`. A blank header counts as absent. |
| `DEMO_MODE` | `bool`, **default `false`**. Only effect: a request with **no** token proceeds as anonymous (WARNING logged). |
| `RATE_LIMIT_PER_MINUTE` | `int >= 1`, default 120. Fixed one-minute window per key, in process. |
| `auth:` per endpoint | `none` → public route; `any` → any authenticated caller; `viewer`/`editor`/`admin` → minimum role. |

## Verification (pure core: `verify_token(token, key, *, now) -> Caller | Rejection`)

A token is accepted iff, in order:

1. it is a compact JWS whose header `alg == "EdDSA"` (`none`, `HS256`, … ⇒ check `alg`);
2. its signature verifies against the bastion key (⇒ `signature`; unparseable ⇒ `malformed`);
3. its claims parse strictly: `iss`, `aud`, `sub` (non-empty) are strings, `role` is one of
   `viewer|editor|admin|frontend`, `exp` and `iat` are integers (a list `aud`, a float or
   boolean time, a missing claim ⇒ that claim's name);
4. `iss == "bastion"` (⇒ `iss`);
5. `aud == SERVICE_ID` (⇒ `aud`);
6. `exp + 10 > now` (⇒ `exp`); `iat - 10 <= now` (⇒ `iat`);
7. `iat < exp` and `exp - iat <= 300` (⇒ `lifetime`).

The result is `Caller(iss, sub, role)` or `Rejection(check)`. `Rejection.check` names the
failed check for the WARNING log; the token itself is never logged.

## Enforcement (imperative shell: middleware + `require_role`)

Route classes, decided from the request path and method:

- **platform** (never authenticated, never rate limited): `/health`, `/version`, `/metrics`,
  `/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc` — exact paths only.
- **public endpoint**: a schema endpoint declared `auth: none` (method + path template).
  No token needed; rate limited by client address.
- **protected**: everything else, including hand-written routes (fail closed by default).

For a protected route:

| Situation | Response |
|---|---|
| no bastion key resolvable (unset, malformed, fetch failed) | `503 {"detail": "platform_auth_unconfigured"}` |
| token present, verification fails | `401 {"detail": "invalid_platform_token"}` — also under `DEMO_MODE=true` |
| token absent, `DEMO_MODE=false` | `401 {"detail": "missing_platform_token"}` |
| token absent, `DEMO_MODE=true` | proceeds as anonymous; WARNING logged |
| over the rate limit | `429 {"detail": "rate_limited"}` |
| route's role above the caller's | `403 {"detail": "insufficient_role"}` (anonymous demo callers pass) |

Rank: `viewer = frontend = 1 < editor = 2 < admin = 3`; `auth: any` needs rank ≥ 1.
Rate-limit key: `"{iss}:{sub}"` when authenticated, else the leftmost `X-Forwarded-For`
address, else the socket peer.

There is **no test-mode bypass**: the generated tests sign real tokens with a key pair
created per test session and point `BASTION_SIGNING_KEY_PUBLIC` at its public half.

CORS (only when `CORS_ORIGINS` is set): allowed request headers are exactly
`authorization`, `content-type`, `x-platform-token`, `x-request-id`; no credentials. The
CORS middleware is the outermost layer so a preflight never meets the token check.

## Test cases (emitted into every generated service's `tests/test_platform_token.py`)

Numbers refer to the contract's conformance list; "n/a" ones need a frontend key.

Pass:
- C1 a valid bastion token with `aud == SERVICE_ID` reaches a protected route (200).
- C6a expired 5 s ago ⇒ 200 (leeway). C7a `iat` 5 s in the future ⇒ 200.
- C10b no token with `DEMO_MODE=true` ⇒ 200 and a WARNING record.
- C13 every platform route answers without a token (no key configured at all).
- `Authorization: Bearer` is accepted; `X-Platform-Token` wins when both are sent.
- `auth: none` endpoint answers without a token and without a key.
- Role table: admin ≥ editor ≥ viewer; `frontend` satisfies `viewer` and `any`.
- Key fetched from `BASTION_PUBLIC_KEY_URL` once and reused from the cache.
- C14 the rate-limit key is `iss:sub`; a second caller is not throttled by the first.

Fail:
- C2 `aud` = another service id ⇒ 401 invalid. C3 `aud` missing ⇒ 401; `aud` a list that
  contains our id ⇒ 401.
- C4 (bastion-only form) `iss == "bastion"` signed by a different key ⇒ 401; signed by
  bastion's key with `iss == "magpie-frontend"` ⇒ 401.
- C6b expired 15 s ago ⇒ 401. C7b `iat` 15 s in the future ⇒ 401.
- `exp - iat == 301` ⇒ 401; `exp <= iat` ⇒ 401.
- C8 `alg: none` and `HS256` (keyed with the public key bytes) ⇒ 401.
- C9 tampered payload ⇒ 401. Unknown `role` ⇒ 401. Empty `sub` ⇒ 401. Float `exp` ⇒ 401.
- C10a no token, `DEMO_MODE=false` ⇒ 401 `missing_platform_token`.
- C11 invalid token with `DEMO_MODE=true` ⇒ 401 `invalid_platform_token`.
- C12 no key configured ⇒ 503 on a protected route, 200 on `/health`.
- Malformed `BASTION_SIGNING_KEY_PUBLIC` (not base64, not Ed25519) ⇒ 503.
- Key URL unreachable or answering without `publicKey` ⇒ 503.
- Insufficient role ⇒ 403. Over the limit ⇒ 429.
- `DEMO_MODE` defaults to `false` in `Settings`.
- A WARNING naming the failed check is logged and the token text never appears in logs.
- CORS preflight from an allowed origin asking for `x-platform-token` succeeds.
- C5 n/a (no frontend key in a generated service).

Generator-side (feathers' own unit tests):
- `SERVICE_ID` is the kebab form of the schema name (`feathers_demo` → `feathers-demo`).
- `auth: none` endpoints appear in the public-endpoint table; others do not.
- Schema names that cannot be a package name and a service id (`hello-users`,
  `1users`, `hello users`) and endpoint paths that are not plain segments or `{param}`s
  are rejected before any file is written.

## Acceptance

- The generated suite passes in `tests/e2e` (generated project, its own `pytest`).
- The e2e boot test and the Postgres integration tier drive CRUD with minted tokens.
- `feathers_demo`, regenerated, passes the same suite in its own CI.
