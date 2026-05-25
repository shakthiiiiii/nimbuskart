# Submission - DevOps Engineer Assignment

**Candidate name:** [YOUR FULL NAME]
**Email:** [YOUR EMAIL]
**Date submitted:** [DATE]
**Hours spent (approximate):** 8

## Deliverables checklist

- [x] Part A: Terraform code under /terraform applies cleanly on LocalStack
- [x] Part A: terraform validate and terraform fmt -check both pass
- [x] Part B: Janitor script runs in --dry-run mode and produces report.json
- [x] Part B: GitHub Actions workflow runs green on a fresh PR
- [x] Part B: --delete mode respects Protected=true tag
- [x] Part C: DESIGN.md is present and within 2 pages

## Walkthrough video

Link: [ADD YOUR LOOM/YOUTUBE LINK HERE]
Length: max 5 minutes

## Sample report

Path: samples/report.example.json

## Known limitations

- LocalStack does not fully emulate StateTransitionReason so stopped-EC2 scanner reports 0 days in CI
- EIP age_days is always 0 because AWS API does not return allocation timestamp
- Multi-account scanning not implemented
- RDS and ElastiCache orphan detection not implemented

## AI usage disclosure

See README.md AI usage disclosure section.
