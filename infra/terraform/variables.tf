variable "aws_region" { type = string; default = "us-west-2" }
variable "cluster_name" { type = string; default = "openbioops-dev" }
variable "tfstate_bucket" { type = string }
variable "tfstate_lock_table" { type = string }
variable "node_group_desired" { type = number; default = 1 }
variable "node_group_min" { type = number; default = 1 }
variable "node_group_max" { type = number; default = 2 }