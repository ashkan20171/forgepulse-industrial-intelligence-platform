# Disaster Recovery Runbook
1. Declare incident and freeze risky writes/integrations if data consistency is uncertain.
2. Confirm last healthy PostgreSQL backup/PITR point and InfluxDB backup snapshot.
3. Provision clean infrastructure from IaC/Helm; never restore into an unknown partially damaged cluster.
4. Restore PostgreSQL, then Redis only if durable Redis state is required by the environment; otherwise allow ephemeral coordination state to rebuild.
5. Restore InfluxDB telemetry and broker/outbox consumers.
6. Run migrations, `/health/startup`, `/health/ready`, smoke tests, and data reconciliation.
7. Re-enable integrations gradually and monitor DLQ/outbox backlog.
8. Record actual RPO/RTO and remediation actions in the incident review.
