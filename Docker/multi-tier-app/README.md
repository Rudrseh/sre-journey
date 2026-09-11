# Multi-Container Notes App (Docker Compose Demo)

A small but "real" 4-service stack, built to demonstrate Docker Compose fundamentals
in an SRE interview: service orchestration, healthchecks, persistence, networking,
and config management.

## Architecture

```
        [ client ]
            |
            v
     +-------------+
     |   nginx     |  <-- reverse proxy, only open port (8080)
     +-------------+
            |
            v
     +-------------+        +--------------+
     |   web       | -----> |   cache      |  (Redis - visit counter)
     | (Flask app) |        +--------------+
     |             |
     |             | -----> +--------------+
     +-------------+        |   db         |  (Postgres - notes storage)
                             +--------------+
```

- **nginx** — reverse proxy, the only service exposing a port to the host
- **web** — Flask app (served by gunicorn), talks to both backing services
- **db** — Postgres, stores notes persistently in a named volume
- **cache** — Redis, tracks an ephemeral visit counter
- **app-net** — a custom bridge network so containers resolve each other by
  service name (`db`, `cache`, `web`) instead of IP

## How to run

```bash
cp .env.example .env
# edit .env with real values if you want

docker compose up --build
```

Visit **http://localhost:8080** — you'll see a visit counter (Redis) and a
notes form that persists to Postgres.

Check health directly:
```bash
curl http://localhost:8080/health
```

## Key design decisions (what to say in the interview)

**1. Healthchecks + `condition: service_healthy`, not just `depends_on`**
Plain `depends_on` only waits for a container to *start* — not for Postgres to
actually be ready to accept connections. I used `pg_isready` / `redis-cli ping`
/ an HTTP health check so each service only starts after its dependency is
truly ready. This is one of the most common causes of "works on my machine,
crashes in prod" bugs.

**2. App-level retry logic as a second safety net**
Even with healthchecks, I added retry-with-backoff in `get_db_connection()` —
because network blips or slow startups can still happen, and defense in depth
is a habit worth having before you get to Kubernetes readiness/liveness probes.

**3. Named volume for Postgres, none for Redis**
`db-data` volume ensures notes survive `docker compose down` / container
recreation. Redis is deliberately left ephemeral here — the visit counter is
meant to reset, which is a good talking point about being intentional with
what needs to persist.

**4. Secrets via `.env`, never hardcoded**
`POSTGRES_PASSWORD` and friends are injected via `env_file`, and `.env` is
gitignored. Only `.env.example` (no real secrets) is committed.

**5. Only nginx exposes a port**
`web`, `db`, and `cache` have no `ports:` mapping to the host — they're only
reachable inside `app-net`. This mirrors a real production pattern: only the
edge service is internet-facing.

**6. Non-root user + explicit HEALTHCHECK in the Dockerfile**
The Flask image runs as `appuser`, not root, and defines its own
`HEALTHCHECK` so `docker ps` and Compose can both see container health
without relying on the app never crashing silently.

## Things to break on purpose (for the "debug this" part of the interview)

- Stop the `db` container mid-run (`docker compose stop db`) and show the
  `/health` endpoint reporting `db: false` while the app stays up.
- Set a wrong `POSTGRES_PASSWORD` in `.env` and walk through diagnosing it via
  `docker compose logs web` and `docker compose logs db`.
- Run `docker stats` while hammering the visit counter to talk about resource
  limits (`mem_limit`, `cpus`) you could add per service.

## Useful commands to have ready

```bash
docker compose ps                 # service status + health
docker compose logs -f web        # tail app logs
docker exec -it <container> sh    # shell into a running container
docker compose down -v            # tear down INCLUDING volumes (wipes data)
```
