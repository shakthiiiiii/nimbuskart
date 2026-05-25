# Pricing constants - USD/month for us-east-1
# Source: https://aws.amazon.com/ebs/pricing/ (Jan 2026)

EBS_COST_PER_GB_MONTH = {
    "gp3": 0.08,
    "gp2": 0.10,
    "io1": 0.125,
    "io2": 0.125,
    "st1": 0.045,
    "sc1": 0.015,
    "standard": 0.05,
}

EC2_STOPPED_ROOT_VOLUME_GB = 8
EC2_STOPPED_COST_PER_MONTH = EC2_STOPPED_ROOT_VOLUME_GB * EBS_COST_PER_GB_MONTH["gp3"]

# Source: https://aws.amazon.com/vpc/pricing/ (Jan 2026)
EIP_IDLE_COST_PER_MONTH = 3.60

DEFAULT_EBS_SIZE_GB = 20
