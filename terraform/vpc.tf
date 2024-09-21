data "aws_vpc" "vpc" {
  id      =  local.vpc["id"]

}



data "aws_subnets" "subnets" {
  for_each = toset(data.aws_subnets.subnets.ids)
  id       = each.value
  # availability_zone = each.value
}
