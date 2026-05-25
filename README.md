# NimbusKart - Cost Hygiene and Automation

## Overview

This repository contains FinOps automation for NimbusKart staging environment.
It provisions AWS infrastructure (VPC, EC2, S3, orphaned EBS) using Terraform
against LocalStack, then runs a Python Cost Janitor that detects wasteful
resources and produces structured JSON and Markdown reports. A GitHub Actions
workflow wires these together so every PR automatically scans for orphans.

## How to run locally

Prerequisites: Docker Desktop running, Python 3.11+, Terraform 1.7+, WSL2

    git clone https://github.com/YOUR_USERNAME/nimbuskart-devops-assignment.git
    cd nimbuskart-devops-assignment
    docker run --rm -d -p 4566:4566 -e SERVICES=ec2,s3,sts --name localstack localstack/localstack:3.4
    pip install terraform-local
    pip install -r janitor/requirements.txt
    cd terraform
    tflocal init && tflocal validate && tflocal apply -auto-approve
    cd ../janitor
    pytest tests/ -v
    python janitor.py --dry-run --region us-east-1 --endpoint-url http://localhost:4566 --output ./output
    cat output/report.json
    docker stop localstack

## Architecture

    .github/workflows/cost-janitor.yml
            |-- Start LocalStack
            |-- tflocal apply
            |-- pytest tests/
            |-- janitor.py --dry-run
            |-- Upload report artifacts
            |-- Post PR comment if orphans found

    terraform/
      main.tf
      variables.tf
      outputs.tf
      modules/network/

    janitor/
      janitor.py
      constants.py
      requirements.txt
      tests/test_janitor.py

## Decisions and deviations

- SSH CIDR changed from 0.0.0.0/0 to 10.0.0.0/8 - open SSH to the world is a critical security risk
- Added S3 public access block - logging bucket must never be world-readable
- S3 bucket name uses deterministic suffix to avoid multi-environment collisions
- EBS orphan volume tagged Purpose=test-fixture-do-not-attach for clarity
- Unit tests use moto not LocalStack - faster and self-contained for unit testing

## Trade-offs

With one more week: multi-account STS role chaining, RDS and ElastiCache
scanning, GCP provider implementation, S3 remote state backend, and
JSON structured logging to CloudWatch.

## AI usage disclosure

- Claude used for architecture review and DESIGN.md provider abstraction pattern
- GitHub Copilot used for GitHub Actions YAML boilerplate
- AI got wrong: suggested old moto @mock_ec2 decorator; current moto v5 uses @mock_aws
- Written manually: scan_stopped_ec2 StateTransitionReason parsing logic
