# Platform Engineering & GitOps

Stage 21 separates application delivery from runtime configuration. Terraform describes the infrastructure contract; Argo CD reconciles Helm state; environment values keep dev/staging/prod differences explicit. Progressive delivery is represented as a canary/blue-green strategy contract rather than pretending a service mesh is already installed.

## Reliability governance
The application exposes SLO posture and error-budget remaining for portfolio demonstration. Production SLOs should be computed from Prometheus/OTel SLIs, not the seeded demo observations.

## Supply chain
CI generates an SBOM and runs dependency/container scans. Scanner findings are evidence for review, not a certification. Backup verification checks integrity; a real DR exercise must also perform restore and application-level validation.
