# Cloudburst AWS Deployment (Terraform)

This deploys a Cloudburst-native runtime on AWS EC2.
It is intentionally separate from Lambda/SeBS deployment paths.

## Topology

- 1x VPC
- 2x public subnets
- 1x Anna node (default)
- 1x Cloudburst scheduler node
- Nx Cloudburst executor nodes (Auto Scaling Group)
- 1x client node (for benchmark driving)

## Files

- `versions.tf`, `providers.tf`: Terraform and provider settings
- `variables.tf`: deployment parameters
- `network.tf`: VPC/subnets/routing
- `security.tf`: security groups
- `iam.tf`: IAM role + instance profile
- `compute.tf`: instances, launch templates, ASG
- `outputs.tf`: IPs and IDs for follow-up scripts
- `user_data/*.tftpl`: bootstrap templates per node role

## Quick Start

From `master-sebs/`:

```bash
./integrations/cloudburst/deploy_cloudburst_aws.sh init
./integrations/cloudburst/deploy_cloudburst_aws.sh plan
./integrations/cloudburst/deploy_cloudburst_aws.sh apply
./integrations/cloudburst/deploy_cloudburst_aws.sh output
```

Destroy:

```bash
./integrations/cloudburst/deploy_cloudburst_aws.sh destroy
```

## Configuration

Copy `terraform.tfvars.example` to `terraform.tfvars` and adjust:

- `aws_region`
- `admin_cidr`
- `key_pair_name`
- instance types and executor counts
- `cloudburst_repo_url` / `cloudburst_repo_ref`
- `enable_auto_start`

## Notes

- This is a scaffold for Cloudburst-native orchestration and repeatability.
- You may still need to tailor Cloudburst/Anna startup commands to match your chosen architecture and consistency-mode experiments.
- No Lambda resources are created here.
