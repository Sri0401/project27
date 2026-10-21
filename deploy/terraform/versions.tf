terraform {
  # Works with Terraform >= 1.6 and with OpenTofu (the open-source fork).
  required_version = ">= 1.6.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.14"
    }
  }

  # State is kept locally (terraform.tfstate, which git ignores). A remote backend
  # in Azure Storage would be standard for a team, but it would use student credit.
}

provider "azurerm" {
  features {
    resource_group {
      # Lets `terraform destroy` remove the group even if something was added by hand.
      prevent_deletion_if_contains_resources = false
    }
  }
  subscription_id = var.subscription_id
}
