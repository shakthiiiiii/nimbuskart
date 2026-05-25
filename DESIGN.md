# DESIGN.md - Cost Janitor: Hardening, Scale, and Multi-Cloud

## Multi-cloud reality

When GCP is added, use a provider abstraction layer with these module boundaries:
- base.py: abstract CloudProvider class with scan() returning list of Finding objects
- aws.py: AwsProvider implementing CloudProvider using boto3
- gcp.py: GcpProvider implementing CloudProvider using google-cloud-compute
- models.py: Finding dataclass that is provider-agnostic

Adding GCP means writing GcpProvider only. The orchestrator and report generation change zero lines.

## Permissions

### Dry-run minimal IAM policy

{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "JanitorReadOnly",
      "Effect": "Allow",
      "Action": [
        "ec2:DescribeVolumes",
        "ec2:DescribeInstances",
        "ec2:DescribeAddresses",
        "ec2:DescribeTags",
        "sts:GetCallerIdentity"
      ],
      "Resource": "*"
    }
  ]
}

Delete mode adds ec2:DeleteVolume, ec2:TerminateInstances, ec2:ReleaseAddress
via a separate role requiring MFA and human approval gate.

## Safety net

1. Race condition: volume attached between scan and delete
Janitor scans available volumes, then a deployment attaches one before deletion runs.
Guardrail: Re-check volume state immediately before deletion.
Enforce minimum age_days >= 7 before any EBS is eligible for auto-deletion.

2. Stopped instance is a scheduled maintenance window
NimbusKart stops a database instance every Sunday for backups.
If Janitor runs Monday before restart it terminates the database.
Guardrail: Default stopped_days=14. Send Slack notification giving owner
24 hours to add Protected=true before deletion runs.

## Observability

Metric: janitor.findings.total | Source: CloudWatch | Alert if > 20
Metric: janitor.waste.estimated_usd_month | Source: CloudWatch | Alert if > 500
Metric: janitor.scan.duration_seconds | Source: Timer around main() | Alert if > 300s
Metric: janitor.deletions.failures | Source: Count error statuses | Alert if > 0
Metric: janitor.findings.by_type | Source: resource_type dimension | Week-over-week trend

## What I did not build

Multi-account support, RDS/ElastiCache scanning, Slack notifications, and
Terraform S3 remote state backend were consciously excluded to keep the
submission focused and reproducible within the time budget.
