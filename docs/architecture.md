# Architecture

Morti Score is organized as a layered FastAPI application. The code separates
HTTP routing, business logic, data access, persistence models and response
schemas so that each layer has a focused responsibility.

## Request flow

```text
Client -> FastAPI router -> service -> repository -> database
```

Routers parse HTTP input and call services. Services contain business logic and
orchestration. Repositories isolate SQLAlchemy queries. Pydantic schemas define
request and response contracts.

## Prediction flow

```text
Prediction endpoint
  -> PredictionService
  -> PredictionContextLoader
  -> team/match repositories
  -> model calculator
  -> Redis cache
  -> response schema
```

`PredictionService` validates the matchup, checks the prediction cache, loads
teams and finished matches, delegates expected-goal calculation to the selected
model, builds the score matrix and returns a `PredictionRead` schema.

The prediction package is split into focused modules:

- `service.py` for orchestration;
- `cache.py` for Redis-backed prediction cache operations;
- `context.py` for loading teams and historical matches;
- `models/` for basic Poisson, improved Poisson and Elo calculators;
- `score_matrix.py` for Poisson scoreline probabilities;
- `errors.py`, `constants.py` and `types.py` for shared support code.

## Dashboard flow

```text
Dashboard route -> services -> Jinja2 template
```

The dashboard route collects teams, matches and standings through service
objects, then renders a Jinja2 template. It is intended as a quick visual demo
of the same data exposed by the API.

## Infrastructure

The application is designed to run as:

```text
FastAPI app + PostgreSQL + Redis via Docker Compose
```

PostgreSQL stores application data. Redis caches prediction responses. Alembic
manages database migrations. For local development and tests, the project can
also use SQLite and an in-memory Redis fallback when configured.