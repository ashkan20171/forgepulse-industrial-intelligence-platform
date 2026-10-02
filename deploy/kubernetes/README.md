# Kubernetes deployment
Use the Helm chart in `deploy/helm/iiot`. Production databases/brokers should normally be managed services or dedicated operators, not sidecars in the API deployment.

Create `iiot-secrets` with AUTH_SECRET, POSTGRES_URL, INFLUXDB_TOKEN and any provider credentials before installation.
