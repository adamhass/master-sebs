# Boki AWS Deployment (Terraform)

This deploys a Boki-native runtime scaffold on AWS EC2.
It is intentionally separate from Lambda/SeBS deployment paths.

## Topology

- 1x VPC
- 2x public subnets
- 1x ZooKeeper node
- 1x controller node
- Nx sequencer nodes
- Nx storage nodes
- Nx engine nodes
- 1x gateway node
- 1x client node

## Files

- `versions.tf`, `providers.tf`: Terraform and provider settings
- `variables.tf`: deployment parameters
- `network.tf`: VPC/subnets/routing
- `security.tf`: security groups
- `iam.tf`: IAM role + instance profile
- `compute.tf`: EC2 nodes and role bootstrap wiring
- `outputs.tf`: IPs and connection outputs
- `user_data/*.tftpl`: bootstrap templates per role

## Quick Start

From `master-sebs/`:

```bash
./integrations/boki/deploy_boki_aws.sh init
./integrations/boki/deploy_boki_aws.sh plan
./integrations/boki/deploy_boki_aws.sh apply
./integrations/boki/deploy_boki_aws.sh output
```

Destroy:

```bash
./integrations/boki/deploy_boki_aws.sh destroy
```

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` and adjust:

- `aws_region`
- `admin_cidr`
- `key_pair_name`
- role counts and instance types
- `boki_repo_url` / `boki_repo_ref`
- `func_config_content` (optional)
- `enable_auto_build`, `enable_auto_start`

## Notes

- User-data writes role start scripts under `/opt/boki/start-*.sh`.
- ZooKeeper runs as a Docker container (`zookeeper:3.9`) on the ZooKeeper node.
- This is a reproducible research scaffold; tune security, observability, and startup ordering for your target experiments.
