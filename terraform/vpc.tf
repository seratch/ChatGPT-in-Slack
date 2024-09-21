data "aws_vpc" "vpc" {
  id      =  local.vpc["id"]

}

data "aws_subnet_ids" "subnets" {
  vpc_id = data.aws_vpc.vpc.id
}

data "aws_subnets" "subnets" {
  for_each = data.aws_subnet_ids.subnets.ids
  id       = each.value
  # availability_zone = each.value
}
