# Ashkan Industrial IoT Platform v13 — Smart Factory / MES Integration Edition

Stage 13 extends the reliability and manufacturing platform with a lightweight MES execution layer: product/SKU master data, production orders and targets, actual vs planned cycle time, good/reject tracking, Andon machine states, quality inspections, shift handover and lot/order genealogy. The MES APIs are role-aware and reuse the existing asset registry instead of creating a disconnected demo domain.

## Stage 13 highlights
- Product/SKU master and production-order execution
- Target, good quantity, reject quantity and cycle-time tracking
- Andon board with RUNNING/IDLE/CHANGEOVER/STARVED/BLOCKED/DOWN/MAINTENANCE states
- Quality inspection workflow (PASS/FAIL/HOLD)
- Shift handover records for operational continuity
- Production genealogy / lot traceability view
- Executive schedule-attainment and first-pass-quality KPIs
- Dedicated Smart Factory MES workspace in the responsive UI

---

# Ashkan Industrial IoT Platform v12 — Enterprise Manufacturing Command Platform

Stage 12 extends the distributed IIoT/reliability platform into manufacturing operations: multi-site hierarchy, production shifts, executive OEE, downtime-loss classification, CMMS/MRO spare-parts visibility, escalation policies, and RCA review workflows. It keeps InfluxDB for time-series telemetry, PostgreSQL for transactional state, Redis for distributed coordination, and the existing explainable reliability/event pipeline.

## Stage 12 additions
- Executive Manufacturing Command Center with OEE / Availability / Performance / Quality
- Downtime recording and loss buckets: planned, unplanned, quality, material, changeover
- Production shift model and multi-site Plant → Line → Asset context
- CMMS/MRO spare-parts inventory with reorder-point visibility
- Escalation policies for warning/high/critical operational events
- RCA approval/rejection workflow endpoint tied to incidents
- Role-aware manufacturing APIs and audit trail for downtime events


**Stage 11** closes the loop from condition detection to operational response: configurable runtime rules, domain-event correlation, guarded incident auto-creation, root-cause assistance, notification routing, model registry/versioning, and a provisioned Grafana reliability dashboard. The RCA remains explainable decision support—not an unsupported claim of causal ML.

## Stage 11 highlights
- Rule Builder API for admin-governed runtime thresholds
- 10-minute multi-event correlation with per-asset incident cooldown
- Automatic incident creation + notification routing for correlated risk
- Explainable Root Cause Assistant with evidence and recommended verification steps
- Model Registry showing production baseline and ONNX deployment seam
- Grafana reliability dashboard provisioning and Stage 11 tests

# Ashkan Industrial IoT Platform

A recruiter-ready **Industrial IoT operations and condition-monitoring platform** built with Python, FastAPI, MQTT, InfluxDB and a responsive real-time command center.

## Why this project stands out

This repository demonstrates more than a dashboard: it models an industrial telemetry workflow from sensor ingestion to operator action. MQTT data is validated, evaluated against machine-specific thresholds, persisted to a time-series database when available, streamed to the browser over WebSockets, converted into alerts, and connected to maintenance work orders and an auditable role-based workflow.

## Core capabilities

- FastAPI REST API with OpenAPI documentation
- MQTT telemetry ingestion and multi-machine simulator
- InfluxDB time-series persistence with graceful degradation
- WebSocket live updates with automatic reconnect
- Machine registry with enable/disable safety controls
- Condition thresholds, anomaly scoring and alert lifecycle
- Maintenance work orders with asset validation and completion workflow
- Role-based access: Admin, Operator and Viewer
- Signed, expiring local evaluation sessions
- Audit trail for protected operational actions
- OEE-style availability, performance and quality indicators
- Fleet risk queue and operational analytics endpoint
- Responsive, accessible industrial command-center UI
- Docker Compose environment for API, MQTT, InfluxDB and simulator
- Automated API/RBAC tests

## Architecture

```text
Sensors / Simulator
       │ MQTT
       ▼
 Mosquitto Broker
       │
       ▼
 FastAPI Ingestion ──► Threshold & anomaly engine ──► Alerts / Work Orders
       │                           │
       ├──► In-memory live cache   └──► WebSocket live stream
       │
       └──► InfluxDB time-series storage
                                      │
                                      ▼
                              Operations Dashboard
```

## Quick start with Docker

```bash
cp .env.example .env
# Change AUTH_SECRET and credentials before any non-local deployment.
docker compose up --build
```

Open the dashboard at `http://localhost:8000` and API docs at `http://localhost:8000/docs`.

## Local development

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

To generate telemetry, run `python -m app.simulator` in another terminal with an MQTT broker available.

## Demo roles

| User | Password | Role | Purpose |
|---|---|---|---|
| `admin` | `Admin@123` | Admin | Full evaluation access and audit trail |
| `operator` | `Operator@123` | Operator | Operational mutations and maintenance |
| `viewer` | `Viewer@123` | Viewer | Read-only monitoring |

These accounts are intentionally local/demo-only. Production identity should use an external identity provider and persistent user store.

## Tests

From `backend`:

```bash
pytest -q
```

The suite covers health, authentication failure, telemetry classification, role permissions, machine disabling, work-order validation and admin-only audit access.

## Production hardening roadmap

For a real plant deployment: terminate TLS at a reverse proxy, disable anonymous MQTT, use broker credentials/client certificates, replace demo users with OIDC/OAuth2, store operational state in a durable database, add rate limiting, secrets management, structured observability, CI security scanning, high availability and plant-specific OEE semantics.

## Tech stack

Python · FastAPI · Pydantic · MQTT · Eclipse Mosquitto · InfluxDB · WebSocket · Docker Compose · Vanilla JS/CSS · Pytest


## v5 — Predictive Operations Edition

This release adds recruiter-facing industrial engineering depth without turning the demo into an oversized framework:

- **Explainable predictive maintenance** — per-asset health index, failure-risk score, confidence, signal trends, risk drivers, and recommended action.
- **Digital Twin / edge registry** — firmware, MQTT protocol context, last-seen synchronization, maintenance mode, and admin-only twin updates.
- **Notification Center** — operational inbox generated from critical condition events with read state.
- **Condition-based workflow** — telemetry → risk detection → notification → work order → audit trail.
- **Quality gate** — GitHub Actions workflow runs dependency installation, pytest, and Python bytecode compilation on pushes and pull requests.

### Architecture story for interviews
The predictive module is deliberately transparent and deterministic for the portfolio demo: configured thresholds, short-window trends, and signal variability are combined into an explainable risk score. This avoids pretending that a model is trained without a labeled failure dataset. The module boundary is designed so a trained ML/ONNX service can replace the scorer later without changing the API or UI contract.

## Stage 6 — Asset 360 & Reliability Operations

This edition extends the recruiter-focused demo into a broader reliability workflow:

- **Asset 360° detail:** historical temperature/vibration visualization, current condition, health and failure-risk context.
- **Maintenance Copilot:** explainable, deterministic maintenance guidance grounded in telemetry, alerts and work orders (not presented as a trained ML model).
- **Maintenance calendar:** consolidated operations schedule derived from work-order activity.
- **Alarm Rules Engine UI/API:** admin-governed condition policies with RBAC enforcement and audit logging.
- **Progressive Web App:** installable shell with safe static-asset caching; API calls deliberately remain network-first.
- **Theme & accessibility polish:** persistent light/dark preference, keyboard focus states and improved responsive layouts.
- **Release 6.0 API:** new `/api/assets/{id}/detail`, `/api/copilot/{id}`, `/api/maintenance/calendar`, and `/api/alarm-rules` endpoints.

The "Copilot" is intentionally explainable and rules/condition based. In a production extension, its interface can be backed by a validated ML/LLM service with model governance, traceability and human approval controls.

## Stage 7 — Enterprise / Production Readiness

This edition adds an enterprise-facing security and operations layer while keeping the project easy to run locally:

- JWT-compatible HMAC access tokens plus rotating/revocable refresh tokens.
- PBKDF2 password hashing and role-based user administration (Admin / Operator / Viewer).
- Configurable demo credentials via environment variables rather than source-only secrets.
- Enterprise settings surface, KPI trend center and authenticated CSV telemetry export.
- Admin backup snapshot for portable demo-state export.
- Prometheus-style `/metrics` endpoint and Docker API health check.
- Expanded integration/security tests for token rotation, RBAC, settings, export and metrics.

> Portfolio note: the user repository and backup/settings stores remain intentionally lightweight for a self-contained demo. The interfaces are isolated so PostgreSQL/Redis-backed repositories can replace them without changing the API/UI contract.

## Stage 8 — Portfolio Flagship Edition

Stage 8 extends the platform toward a realistic Industry 4.0 reference architecture: Plant → Line → Asset hierarchy, incident lifecycle management, reliability engineering KPIs (MTBF/MTTR), estimated energy load, API-key lifecycle, HTTP rate limiting/security headers, plus PostgreSQL and Redis infrastructure foundations alongside InfluxDB. PostgreSQL is intended for durable relational workflows (identity, incidents, work orders, configuration); Redis is intended for distributed cache/rate-limit/session coordination; InfluxDB remains the time-series system of record.

> The current in-process repositories intentionally preserve a zero-migration demo experience. The Postgres/Redis services are infrastructure-ready seams for the next persistence migration rather than falsely claiming that all repositories are already durable.


## Stage 9 — True Persistence & Distributed Architecture

Stage 9 moves the operational control plane from process memory to durable infrastructure. PostgreSQL now stores users, work orders, incidents, API-key metadata, platform settings, and audit events through SQLAlchemy repositories. Alembic provides the schema baseline and the API container applies migrations before startup. Redis now backs distributed HTTP rate limiting and refresh-token revocation, so those controls work across multiple API replicas.

The observability path is also executable infrastructure rather than a diagram: FastAPI is instrumented with OpenTelemetry, an OTLP collector is included, Prometheus scrapes the API metrics endpoint, and Grafana is provisioned with Prometheus as its default datasource. InfluxDB intentionally remains the time-series store for high-frequency telemetry. This polyglot persistence split mirrors the workload instead of forcing all data into one database.

### Stage 9 service map

- **FastAPI** — REST/WebSocket application and RBAC boundary.
- **PostgreSQL + SQLAlchemy/Alembic** — durable transactional state and migrations.
- **Redis** — distributed rate limiting and token-revocation coordination.
- **InfluxDB** — telemetry/time-series history.
- **Mosquitto** — MQTT ingestion transport.
- **Prometheus + Grafana** — operational metrics and dashboards.
- **OpenTelemetry Collector** — distributed tracing pipeline foundation.

For local startup, run `docker compose up --build`. The API is on port 8000, Prometheus on 9090, Grafana on 3000, and InfluxDB on 8086. Demo credentials are for local evaluation only; replace secrets/passwords before any non-demo deployment.

## Stage 10 — Industrial Intelligence
- Domain event bus with isolated handlers and operational event timeline.
- Runtime condition-rule evaluation on every telemetry sample.
- Explainable statistical anomaly pipeline combining configured thresholds with recent per-asset baselines.
- Fleet anomaly API and Event Intelligence workspace in the product UI.
- Architecture intentionally exposes a model-adapter seam for future ONNX/MLflow deployment rather than claiming a black-box model that is not present.

## Stage 14 — Advanced MES & Production Planning
Stage 14 extends production execution with a planning/engineering layer: BOM and routing visibility, work centers, finite schedule projection, WIP, material genealogy-ready consumption APIs, SPC control limits, NCR/CAPA workflow, electronic work instructions and production cost analytics. The module is deliberately separated from core MES execution to keep domain boundaries understandable during technical review.


## Stage 15 — Smart Factory Digital Twin & Optimization
Stage 15 adds an explainable factory-level planning twin on top of MES execution. It computes capacity and bottleneck pressure from work-center/routing data, exposes OEE/throughput/energy/carbon intensity, detects production-versus-maintenance conflicts, estimates order-level quality risk, and provides a bounded what-if scenario API. The scenario engine is deterministic and returns its assumptions and explanation; it is decision support, not a claim of a validated autonomous optimizer.

**Interview story:** telemetry remains in InfluxDB, transactional workflows remain in PostgreSQL, and the factory twin consumes MES/asset state through a dedicated domain module. This keeps simulation concerns separate from execution and makes a future discrete-event solver or validated optimization service replaceable behind the same API contract.

## Stage 16 — AI Factory Copilot & Decision Intelligence

Stage 16 adds a grounded factory decision-support layer on top of the existing MES, reliability, anomaly and Digital Twin domains.

- Natural-language-style operational Q&A for OEE, asset condition, maintenance, incidents, energy and carbon estimates.
- Source-aware answers with explicit confidence, recommended actions and safety guardrails.
- Prioritized Decision Intelligence recommendations across capacity, reliability, quality, energy and incidents.
- Shift Reliability Briefing and Executive Factory Briefing generated from live application state.
- Human-approval workflow for recommendations; approval decisions are audited and **do not automatically execute plant actions**.
- Provider-independent architecture: the deterministic grounded engine works without external API keys and provides a clean seam for a future validated LLM/RAG adapter.

The Copilot is intentionally described as **decision support**, not autonomous plant control. Any future LLM integration should retain authorization, grounding, audit, prompt-injection defenses and explicit human approval for consequential actions.

## Stage 17 — Enterprise AI/RAG & Knowledge Platform

Stage 17 extends the Factory Copilot with a local, reproducible retrieval-augmented knowledge layer. Approved SOPs, equipment manuals and AI governance policies are searchable and returned as document/version citations alongside live factory context. The default implementation intentionally requires no paid LLM or external API.

### AI trust architecture
- **Grounded retrieval:** lightweight semantic lexical retrieval with asset-aware ranking; the adapter boundary can later be replaced by pgvector/Qdrant/Elasticsearch embeddings.
- **Evidence-first answers:** RAG responses include document ID, title, type, version, relevance and excerpt.
- **Prompt-injection guard:** common instruction-override and secret-exfiltration patterns are blocked before retrieval.
- **Conversation traceability:** each RAG interaction receives a conversation ID and is retained in the local governance ledger.
- **Governance metrics:** administrators can inspect query volume, blocked requests, citation coverage and knowledge-document count.
- **Safe default:** external LLM mode is disabled and all operational actions remain human-approved/read-only.

This design makes the AI story defensible in technical interviews: deterministic factory analytics and approved knowledge remain the source of truth, while an external LLM can later be introduced only as a language/reasoning adapter behind the same evidence and governance boundary.

## Stage 18 — Enterprise Security & Zero-Trust

Stage 18 adds a security-focused layer designed for technical portfolio review: fine-grained permission catalog, scoped API-key metadata, TOTP MFA enrollment with one-time recovery codes, adaptive account lockout after repeated failures, password-policy enforcement for newly created users, security-event telemetry, a Zero-Trust posture dashboard, and hardened browser headers (CSP, Permissions-Policy, frame protection and referrer policy).

The MFA implementation is intentionally local and standards-based (TOTP) so the demo does not depend on an external identity provider. For production, secrets should be encrypted with a KMS/HSM and identity should normally be federated through an enterprise IdP (OIDC/SAML). The current security dashboard is decision/support telemetry, not a claim of formal compliance certification.

## Stage 19 — Enterprise Integration & Event-Driven Platform

Stage 19 adds a failure-aware enterprise integration boundary instead of coupling ERP/MES/CMMS systems directly to telemetry ingestion.

- Transactional **PostgreSQL Outbox** with PENDING / RETRY / PUBLISHED / DLQ states
- Explicit **at-least-once** delivery semantics and event-id idempotency contract
- Signed outbound **Webhooks** using HMAC-SHA256 and `Idempotency-Key`
- Exponential retry/backoff and operator-controlled dead-letter replay
- Enterprise connector contracts for ERP, MES, CMMS and an OPC-UA edge-gateway foundation
- Kafka-compatible **Redpanda** development broker plus browser console
- Admin Integration Hub for connector state, delivery health, outbox and DLQ operations

The broker is an integration foundation: the current local dispatcher persists events before delivery and webhooks are implemented end-to-end. Kafka/Redpanda topic publishing can be enabled as a separate adapter without changing domain producers. This keeps the outbox boundary testable and avoids claiming exactly-once delivery.

## Stage 20 — Cloud Native & High Availability

Stage 20 adds a vendor-neutral Kubernetes/Helm deployment, rolling-update strategy, HPA, PodDisruptionBudget, startup/readiness/liveness probes, graceful request draining, runtime/circuit status, circuit-breaker and bulkhead foundations, Kubernetes NetworkPolicy, multi-cloud architecture guidance and a disaster-recovery runbook.

The API tier is designed to remain stateless for horizontal scaling; PostgreSQL, Redis, InfluxDB and the integration broker remain the stateful boundaries. The Helm chart intentionally expects production secrets to come from an existing Kubernetes Secret rather than committing credentials to the chart.

Useful runtime endpoints: `/health/live`, `/health/ready`, `/health/startup`, and Admin-only `/api/platform/runtime`.

## Stage 21 — Platform Engineering & GitOps

Stage 21 adds a vendor-neutral Terraform foundation, Argo CD application contract, dev/staging/prod environment values, progressive-delivery posture, runtime feature flags, SLO/error-budget visibility, a Chaos Mesh experiment, checksum-based backup verification, and CI supply-chain evidence with SBOM + Trivy scanning.

The Platform Engineering workspace exposes these concepts in the product for portfolio review. Seeded SLI observations are demonstration data; production SLOs must be calculated from real Prometheus/OpenTelemetry telemetry. Scanner output and backup checks are evidence, not compliance or restore certification.

## Local Windows quick start (without Docker)

If Docker is unavailable, run `run-local.bat` from the repository root. It creates a virtual environment, installs dependencies, uses a local SQLite database, disables MQTT for the local UI demo, and starts ForgePulse at `http://127.0.0.1:8000`.

Do not open `backend/app/static/index.html` directly for normal use. Open the application through the FastAPI server. If the UI cannot reach the API, the login form now reports a specific backend-connectivity message instead of the browser's generic `Failed to fetch`.
"# forgepulse-industrial-intelligence-platform" 
