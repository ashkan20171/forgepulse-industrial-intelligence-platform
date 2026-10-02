terraform { required_version = ">= 1.6.0" }
variable "environment" { type=string; validation { condition=contains(["dev","staging","prod"],var.environment); error_message="Use dev, staging or prod." } }
variable "region" { type=string; default="eu-central" }
locals { tags={ application="ashkan-iiot" environment=var.environment managed_by="terraform" } }
output "platform_contract" { value={ environment=var.environment region=var.region capabilities=["kubernetes","postgresql","redis","object-storage","secret-manager"] } }
