output "vpc_id" {
  value = module.network.vpc_id
}
output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}
output "bucket_name" {
  value = aws_s3_bucket.logs.id
}
output "web_instance_ids" {
  value = aws_instance.web[*].id
}
output "orphan_ebs_volume_id" {
  value = aws_ebs_volume.orphan.id
}
