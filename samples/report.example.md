# Cost Janitor Report

**Scan time:** 2026-01-15T10:00:00Z
**Account:** 000000000000
**Region:** us-east-1

## Summary

| Metric | Value |
|--------|-------|
| Total orphans found | 2 |
| Estimated monthly waste | $5.20 |

## Findings

| Resource ID | Type | Reason | Age (days) | Est. Monthly Cost | Safe to Delete |
|-------------|------|--------|-----------|-------------------|----------------|
| vol-0abc123def456789a | ebs_volume | unattached | 21 | $1.60 | Yes |
| eipalloc-0a1b2c3d4e5f67890 | elastic_ip | not associated | 0 | $3.60 | No |
