terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 4.26"
    }
  }
}

# Configure the AWS Provider
provider "aws" {
  region = local.region
}

