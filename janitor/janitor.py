#!/usr/bin/env python3
"""
Cost Janitor - NimbusKart orphaned-resource scanner.
Usage:
    python janitor.py [--dry-run] [--delete] [--region REGION]
                      [--stopped-days N] [--output DIR]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError

from constants import (
    DEFAULT_EBS_SIZE_GB,
    EBS_COST_PER_GB_MONTH,
    EIP_IDLE_COST_PER_MONTH,
    EC2_STOPPED_COST_PER_MONTH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger("janitor")

REQUIRED_TAGS = {"Project", "Environment", "Owner"}


def tags_as_dict(tag_list):
    return {t["Key"]: t["Value"] for t in (tag_list or [])}


def is_protected(tags):
    return tags.get("Protected", "").lower() == "true"


def missing_required_tags(tags):
    return [k for k in REQUIRED_TAGS if not tags.get(k)]


def age_days(dt):
    now = datetime.now(timezone.utc)
    return (now - dt).days


def ebs_monthly_cost(size_gb, volume_type):
    rate = EBS_COST_PER_GB_MONTH.get(volume_type, EBS_COST_PER_GB_MONTH["gp3"])
    return round(size_gb * rate, 2)


def scan_orphan_ebs(ec2):
    findings = []
    paginator = ec2.get_paginator("describe_volumes")
    for page in paginator.paginate(Filters=[{"Name": "status", "Values": ["available"]}]):
        for vol in page["Volumes"]:
            tags = tags_as_dict(vol.get("Tags", []))
            size = vol.get("Size", DEFAULT_EBS_SIZE_GB)
            vtype = vol.get("VolumeType", "gp3")
            created = vol["CreateTime"]
            findings.append({
                "resource_id": vol["VolumeId"],
                "resource_type": "ebs_volume",
                "reason": "unattached",
                "age_days": age_days(created),
                "estimated_monthly_cost_usd": ebs_monthly_cost(size, vtype),
                "tags": {k: tags.get(k) for k in REQUIRED_TAGS},
                "suggested_action": "delete",
                "safe_to_auto_delete": not is_protected(tags),
                "_raw_tags": tags,
            })
    return findings


def scan_stopped_ec2(ec2, stopped_days_threshold):
    findings = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["stopped"]}]
    ):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                tags = tags_as_dict(inst.get("Tags", []))
                stop_time = None
                reason_str = inst.get("StateTransitionReason", "")
                if "(" in reason_str and ")" in reason_str:
                    try:
                        time_str = reason_str.split("(")[1].rstrip(")")
                        stop_time = datetime.strptime(
                            time_str, "%Y-%m-%d %H:%M:%S GMT"
                        ).replace(tzinfo=timezone.utc)
                    except ValueError:
                        pass
                if stop_time is None:
                    stop_time = inst.get("LaunchTime", datetime.now(timezone.utc))
                days_stopped = age_days(stop_time)
                if days_stopped < stopped_days_threshold:
                    continue
                findings.append({
                    "resource_id": inst["InstanceId"],
                    "resource_type": "ec2_instance",
                    "reason": f"stopped for {days_stopped} days (threshold: {stopped_days_threshold})",
                    "age_days": days_stopped,
                    "estimated_monthly_cost_usd": EC2_STOPPED_COST_PER_MONTH,
                    "tags": {k: tags.get(k) for k in REQUIRED_TAGS},
                    "suggested_action": "terminate",
                    "safe_to_auto_delete": not is_protected(tags),
                    "_raw_tags": tags,
                })
    return findings


def scan_idle_eips(ec2):
    findings = []
    response = ec2.describe_addresses()
    for addr in response.get("Addresses", []):
        if addr.get("InstanceId") or addr.get("NetworkInterfaceId"):
            continue
        tags = tags_as_dict(addr.get("Tags", []))
        findings.append({
            "resource_id": addr.get("AllocationId", addr.get("PublicIp", "unknown")),
            "resource_type": "elastic_ip",
            "reason": "not associated with any instance or network interface",
            "age_days": 0,
            "estimated_monthly_cost_usd": EIP_IDLE_COST_PER_MONTH,
            "tags": {k: tags.get(k) for k in REQUIRED_TAGS},
            "suggested_action": "release",
            "safe_to_auto_delete": not is_protected(tags),
            "_raw_tags": tags,
        })
    return findings


def scan_untagged_resources(ec2):
    findings = []
    paginator = ec2.get_paginator("describe_instances")
    for page in paginator.paginate(
        Filters=[{"Name": "instance-state-name", "Values": ["running", "stopped"]}]
    ):
        for reservation in page["Reservations"]:
            for inst in reservation["Instances"]:
                tags = tags_as_dict(inst.get("Tags", []))
                missing = missing_required_tags(tags)
                if not missing:
                    continue
                findings.append({
                    "resource_id": inst["InstanceId"],
                    "resource_type": "ec2_instance",
                    "reason": f"missing required tags: {', '.join(missing)}",
                    "age_days": age_days(inst.get("LaunchTime", datetime.now(timezone.utc))),
                    "estimated_monthly_cost_usd": 0.0,
                    "tags": {k: tags.get(k) for k in REQUIRED_TAGS},
                    "suggested_action": "tag",
                    "safe_to_auto_delete": False,
                    "_raw_tags": tags,
                })
    vol_paginator = ec2.get_paginator("describe_volumes")
    for page in vol_paginator.paginate():
        for vol in page["Volumes"]:
            tags = tags_as_dict(vol.get("Tags", []))
            missing = missing_required_tags(tags)
            if not missing:
                continue
            findings.append({
                "resource_id": vol["VolumeId"],
                "resource_type": "ebs_volume",
                "reason": f"missing required tags: {', '.join(missing)}",
                "age_days": age_days(vol["CreateTime"]),
                "estimated_monthly_cost_usd": 0.0,
                "tags": {k: tags.get(k) for k in REQUIRED_TAGS},
                "suggested_action": "tag",
                "safe_to_auto_delete": False,
                "_raw_tags": tags,
            })
    return findings


def delete_finding(ec2, finding, dry_run):
    if not finding["safe_to_auto_delete"]:
        return "skipped (protected)"
    if dry_run:
        return "skipped (dry-run)"
    rid = finding["resource_id"]
    rtype = finding["resource_type"]
    try:
        if rtype == "ebs_volume":
            ec2.delete_volume(VolumeId=rid)
            return "deleted"
        elif rtype == "ec2_instance":
            ec2.terminate_instances(InstanceIds=[rid])
            return "terminated"
        elif rtype == "elastic_ip":
            ec2.release_address(AllocationId=rid)
            return "released"
        else:
            return f"skipped (no action for {rtype})"
    except ClientError as e:
        return f"error: {e.response['Error']['Message']}"


def build_report(findings, account_id, region):
    total_waste = sum(f["estimated_monthly_cost_usd"] for f in findings)
    clean_findings = [
        {k: v for k, v in f.items() if not k.startswith("_")} for f in findings
    ]
    return {
        "scan_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "account_id": account_id,
        "region": region,
        "summary": {
            "total_orphans": len(clean_findings),
            "estimated_monthly_waste_usd": round(total_waste, 2),
        },
        "findings": clean_findings,
    }


def build_markdown(report):
    lines = [
        "# Cost Janitor Report",
        "",
        f"**Scan time:** {report['scan_timestamp']}  ",
        f"**Account:** {report['account_id']}  ",
        f"**Region:** {report['region']}",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "|--------|-------|",
        f"| Total orphans found | {report['summary']['total_orphans']} |",
        f"| Estimated monthly waste | ${report['summary']['estimated_monthly_waste_usd']:.2f} |",
        "",
    ]
    if not report["findings"]:
        lines.append("No orphaned resources found.")
        return "\n".join(lines)
    lines += [
        "## Findings",
        "",
        "| Resource ID | Type | Reason | Age (days) | Est. Monthly Cost | Safe to Delete |",
        "|-------------|------|--------|-----------|-------------------|----------------|",
    ]
    for f in report["findings"]:
        safe = "Yes" if f["safe_to_auto_delete"] else "No (protected)"
        lines.append(
            f"| `{f['resource_id']}` | {f['resource_type']} | {f['reason']} "
            f"| {f['age_days']} | ${f['estimated_monthly_cost_usd']:.2f} | {safe} |"
        )
    lines += ["", "---", "*Generated by Cost Janitor*"]
    return "\n".join(lines)


def parse_args():
    parser = argparse.ArgumentParser(description="Cost Janitor")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", default=True)
    mode.add_argument("--delete", action="store_true", default=False)
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--stopped-days", type=int, default=14)
    parser.add_argument("--endpoint-url", default=os.environ.get("AWS_ENDPOINT_URL", None))
    parser.add_argument("--output", default=".")
    return parser.parse_args()


def main():
    args = parse_args()
    delete_mode = args.delete
    dry_run = not delete_mode

    log.info("Starting Cost Janitor  region=%s  mode=%s", args.region, "delete" if delete_mode else "dry-run")

    kwargs: dict[str, Any] = {"region_name": args.region}
    if args.endpoint_url:
        kwargs["endpoint_url"] = args.endpoint_url

    ec2 = boto3.client("ec2", **kwargs)

    try:
        sts = boto3.client("sts", **kwargs)
        account_id = sts.get_caller_identity()["Account"]
    except Exception:
        account_id = "000000000000"

    log.info("Scanning for orphaned EBS volumes...")
    orphan_ebs = scan_orphan_ebs(ec2)

    log.info("Scanning for stopped EC2 instances (threshold: %d days)...", args.stopped_days)
    stopped_ec2 = scan_stopped_ec2(ec2, args.stopped_days)

    log.info("Scanning for idle Elastic IPs...")
    idle_eips = scan_idle_eips(ec2)

    log.info("Scanning for resources with missing required tags...")
    untagged = scan_untagged_resources(ec2)

    seen = set()
    all_findings = []
    for finding in orphan_ebs + stopped_ec2 + idle_eips + untagged:
        rid = finding["resource_id"]
        if rid not in seen:
            seen.add(rid)
            all_findings.append(finding)

    log.info("Total findings: %d", len(all_findings))

    if delete_mode:
        for finding in all_findings:
            status = delete_finding(ec2, finding, dry_run=False)
            log.info("  %s (%s): %s", finding["resource_id"], finding["resource_type"], status)
            finding["delete_status"] = status

    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    report = build_report(all_findings, account_id, args.region)
    markdown = build_markdown(report)

    json_path = output_dir / "report.json"
    md_path = output_dir / "report.md"

    json_path.write_text(json.dumps(report, indent=2))
    md_path.write_text(markdown)

    log.info("Report written to %s", json_path)
    log.info("Markdown written to %s", md_path)

    if dry_run and all_findings:
        log.warning("Orphans detected - exiting with code 1")
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
