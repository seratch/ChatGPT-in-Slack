data "aws_vpc" "vpc" {
  id      =  local.vpc["id"]

}


data "aws_subnets" "subnets" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.vpc.id]
  }
}