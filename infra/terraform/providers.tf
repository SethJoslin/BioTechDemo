terraform {
  required_version = ">= 1.2"
  backend "s3" {
    bucket = var.tfstate_bucket
    key    = "openbioops/terraform.tfstate"
    region = var.aws_region
    dynamodb_table = var.tfstate_lock_table
  }
}

provider "aws" {
  region = var.aws_region
}