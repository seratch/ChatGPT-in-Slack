data "aws_vpc" "vpc" {
  id      = local.use_default_vpc ? null : local.vpc["id"]
  default = local.use_default_vpc
}

data "aws_subnet_ids" "subnets" {
  vpc_id = data.aws_vpc.vpc.id
}

data "aws_subnet" "subnets" {
  for_each = data.aws_subnet_ids.subnets.ids
  vpc_id   = data.aws_vpc.vpc.id
  id       = each.value
  # availability_zone = each.value
}
