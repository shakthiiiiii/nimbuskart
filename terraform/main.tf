terraform {
  required_version = ">= 1.3.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region                      = var.region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  endpoints {
    ec2 = "http://localhost:4566"
    s3  = "http://localhost:4566"
    iam = "http://localhost:4566"
  }
}

locals {
  common_tags = {
    Project     = var.project
    Environment = var.environment
    Owner       = var.owner
    ManagedBy   = "terraform"
  }
}

module "network" {
  source           = "./modules/network"
  ssh_allowed_cidr = var.ssh_allowed_cidr
  tags             = local.common_tags
}

resource "aws_instance" "web" {
  count                  = 2
  ami                    = var.ami_id
  instance_type          = var.instance_type
  subnet_id              = module.network.public_subnet_ids[count.index]
  vpc_security_group_ids = [module.network.web_security_group_id]
  tags = merge(local.common_tags, {
    Name = "${var.project}-${var.environment}-web-${count.index + 1}"
    Tier = "web"
  })
}

resource "aws_s3_bucket" "logs" {
  bucket = "${lower(var.project)}-${var.environment}-logs"
  tags   = local.common_tags
}

resource "aws_s3_bucket_versioning" "logs" {
  bucket = aws_s3_bucket.logs.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_public_access_block" "logs" {
  bucket                  = aws_s3_bucket.logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_ebs_volume" "orphan" {
  availability_zone = "us-east-1a"
  size              = var.ebs_orphan_size_gb
  type              = "gp3"
  tags = merge(local.common_tags, {
    Name    = "${var.project}-${var.environment}-orphan-ebs"
    Purpose = "test-fixture-do-not-attach"
  })
}
