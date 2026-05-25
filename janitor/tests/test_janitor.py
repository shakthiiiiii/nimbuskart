import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, str(Path(__file__).parent.parent))

import janitor as j
from constants import EBS_COST_PER_GB_MONTH

REGION = "us-east-1"
REQUIRED_TAGS = [
    {"Key": "Project", "Value": "NimbusKart"},
    {"Key": "Environment", "Value": "staging"},
    {"Key": "Owner", "Value": "devops-team"},
    {"Key": "ManagedBy", "Value": "terraform"},
]


def make_ec2():
    return boto3.client("ec2", region_name=REGION)


@mock_aws
def test_detects_available_ebs_volume():
    ec2 = make_ec2()
    vol = ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=20,
        VolumeType="gp3",
        TagSpecifications=[{"ResourceType": "volume", "Tags": REQUIRED_TAGS}],
    )
    findings = j.scan_orphan_ebs(ec2)
    assert any(f["resource_id"] == vol["VolumeId"] for f in findings)


@mock_aws
def test_detects_unassociated_eip():
    ec2 = make_ec2()
    addr = ec2.allocate_address(Domain="vpc")
    findings = j.scan_idle_eips(ec2)
    assert any(f["resource_id"] == addr["AllocationId"] for f in findings)


@mock_aws
def test_detects_volume_missing_tags():
    ec2 = make_ec2()
    vol = ec2.create_volume(AvailabilityZone="us-east-1a", Size=10, VolumeType="gp3")
    findings = j.scan_untagged_resources(ec2)
    vol_findings = [f for f in findings if f["resource_id"] == vol["VolumeId"]]
    assert vol_findings


@mock_aws
def test_fully_tagged_volume_not_flagged():
    ec2 = make_ec2()
    ec2.create_volume(
        AvailabilityZone="us-east-1a",
        Size=10,
        VolumeType="gp3",
        TagSpecifications=[{"ResourceType": "volume", "Tags": REQUIRED_TAGS}],
    )
    findings = j.scan_untagged_resources(ec2)
    assert findings == []


def test_is_protected_true():
    assert j.is_protected({"Protected": "true"}) is True
    assert j.is_protected({"Protected": "True"}) is True


def test_is_protected_false():
    assert j.is_protected({"Protected": "false"}) is False
    assert j.is_protected({}) is False


def test_report_schema():
    findings = [{
        "resource_id": "vol-abc123",
        "resource_type": "ebs_volume",
        "reason": "unattached",
        "age_days": 21,
        "estimated_monthly_cost_usd": 8.00,
        "tags": {"Project": None, "Environment": None, "Owner": None},
        "suggested_action": "delete",
        "safe_to_auto_delete": False,
    }]
    report = j.build_report(findings, "000000000000", "us-east-1")
    assert "scan_timestamp" in report
    assert "account_id" in report
    assert "region" in report
    assert report["summary"]["total_orphans"] == 1


def test_ebs_monthly_cost():
    cost = j.ebs_monthly_cost(100, "gp3")
    assert cost == 100 * EBS_COST_PER_GB_MONTH["gp3"]
