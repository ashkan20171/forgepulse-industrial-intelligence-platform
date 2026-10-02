# Cloud Native & High Availability Architecture

## Runtime model
The API is stateless at the HTTP tier. Durable transactional state belongs in PostgreSQL, distributed coordination/revocation/rate-limit state in Redis, telemetry in InfluxDB, and integration events in the broker/outbox path. This allows API replicas to scale horizontally.

## Health semantics
- `/health/live`: process is alive. It deliberately does not fail because a downstream database is unavailable.
- `/health/ready`: instance may receive traffic and PostgreSQL/Redis are reachable.
- `/health/startup`: process initialization completed.

## Graceful termination
On shutdown the process enters drain mode, refuses new application traffic, waits for in-flight requests up to the configured grace period, then closes MQTT/database resources. Kubernetes also uses a preStop delay and termination grace period.

## Resilience
Adapter boundaries have a lightweight circuit-breaker/bulkhead foundation. Distributed components should use bounded retries with jitter and idempotency keys. Transactional outbox remains the delivery boundary for integration events.

## Multi-cloud mapping
- Kubernetes: AKS / EKS / GKE or any conformant cluster.
- PostgreSQL: Azure Database for PostgreSQL / Amazon RDS / Cloud SQL.
- Redis: Azure Managed Redis / ElastiCache / Memorystore.
- Object backups: Blob Storage / S3 / Cloud Storage.
- Secrets: Key Vault / Secrets Manager / Secret Manager, surfaced to Kubernetes through the platform's preferred CSI/operator integration.

## Disaster recovery targets
This repository documents a reference target, not a contractual SLA: relational backups every 6h plus WAL/PITR where supported, configuration/Helm values in source control, and restore drills at least quarterly. Define RPO/RTO per production environment and validate them with measured restore exercises.
