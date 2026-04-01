# Documentation Guidelines

This file describes what documentation exists in this project and when it must be updated.

---

## Rule: always keep documentation in sync with code changes

Whenever you make a code change, check whether any of the documents below are affected and
update them in the same commit or pull request.  Outdated documentation is treated the same
as a bug.

---

## Documents and what triggers an update

| Document | Update when … |
|---|---|
| [`docs/database.md`](database.md) | A new table, column, index, constraint, or data-type change is added or removed via an Alembic migration or ORM model change |
| [`docs/architecture.md`](architecture.md) | A new service, container, component, or major design decision is introduced or removed |
| [`docs/api.md`](api.md) | A new endpoint is added, an existing endpoint changes its path / method / request / response shape, or an endpoint is removed |
| [`docs/deployment.md`](deployment.md) | A new required environment variable is introduced, a service port changes, or the deployment procedure changes |
| [`docs/idp-configuration.md`](idp-configuration.md) | Auth / SSO settings change (SAML metadata, OIDC redirect URIs, etc.) |
| [`README.md`](../README.md) | Project-level setup steps, prerequisites, or quick-start instructions change |

---

## What to include in each type of update

### Database changes (`docs/database.md`)

* Add a new section for every new table.
* Add a row to the **Table overview** table.
* For each column: document the SQL type, nullability, default value, and purpose.
* Document every primary key, foreign key, unique constraint, and index.
* Update the **Entity-relationship overview** diagram if relationships change.

### API changes (`docs/api.md`)

* Document the HTTP method, path, request body (with field types), and response shape.
* Note any new authentication or authorisation requirements.

### Architecture changes (`docs/architecture.md`)

* Update the ASCII diagram if a new container or major component is added.
* Add a row to the Tech-Stack Decisions table if a new library or tool is adopted.
* Update the Data Model section if high-level data model relationships change.
* Update the Component Responsibilities tables if a new module is added.

---

## Alembic migrations

Every Alembic migration file in `backend/alembic/versions/` must be accompanied by a
corresponding update to `docs/database.md`.  The migration file and the documentation
update should be in the same pull request.

---

## Session notes

Completed-session notes live in `docs/sessions/`.  Create a new file
`docs/sessions/session-NN-<short-name>.md` for every major development session.  Each
session note should record:

* What was built or changed.
* New environment variables introduced.
* New database tables or columns added (with a reference to `docs/database.md`).
* New API endpoints added.
* Test coverage added.
