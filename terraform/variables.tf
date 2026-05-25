variable "region" {
  type    = string
  default = "us-east-1"
}
variable "project" {
  type    = string
  default = "NimbusKart"
}
variable "environment" {
  type    = string
  default = "staging"
}
variable "owner" {
  type    = string
  default = "devops-team"
}
variable "ssh_allowed_cidr" {
  type    = string
  default = "10.0.0.0/8"
}
variable "instance_type" {
  type    = string
  default = "t3.micro"
}
variable "ami_id" {
  type    = string
  default = "ami-0c55b159cbfafe1f0"
}
variable "ebs_orphan_size_gb" {
  type    = number
  default = 20
}
