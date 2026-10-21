variable "subscription_id" {
  description = "Azure subscription ID (az account show --query id -o tsv)."
  type        = string
}

variable "location" {
  description = "Azure region. Azure for Students may restrict regions; if refused, try southeastasia or centralindia."
  type        = string
  default     = "australiaeast"
}

variable "prefix" {
  description = "Name prefix for every resource."
  type        = string
  default     = "urbanpulse"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,20}$", var.prefix))
    error_message = "Use 3-21 lowercase letters, digits or '-', starting with a letter."
  }
}

# --- Free-tier guard rails ---------------------------------------------------------------------
# These validations stop a plan before it can create anything outside the free allowance.

variable "vm_size" {
  description = "VM size. Only free-tier x64 sizes are allowed."
  type        = string
  default     = "Standard_B1s"

  validation {
    # Standard_B2pts_v2 is also free, but it is ARM-based and does not run this x64 image.
    condition     = contains(["Standard_B1s", "Standard_B2ats_v2"], var.vm_size)
    error_message = "Only free-tier sizes are allowed: Standard_B1s or Standard_B2ats_v2."
  }
}

variable "os_disk_size_gb" {
  description = "OS disk size. The free allowance covers P6 disks, which are 64 GiB Premium SSDs."
  type        = number
  default     = 64

  validation {
    # A smaller disk is billed as P4 or lower, which the free allowance does not cover.
    condition     = var.os_disk_size_gb == 64
    error_message = "Keep the OS disk at 64 GiB so it is billed as a free P6 disk."
  }
}

# --- Access ------------------------------------------------------------------------------------

variable "admin_username" {
  description = "Linux admin user. cloud-init.yaml expects 'azureuser'."
  type        = string
  default     = "azureuser"
}

variable "ssh_public_key_path" {
  description = "Path to the SSH public key allowed to log in."
  type        = string
  default     = "~/.ssh/urbanpulse_ed25519.pub"
}

variable "ssh_allowed_cidr" {
  description = "Source address range allowed to SSH, normally your own IP as x.x.x.x/32."
  type        = string

  validation {
    condition     = can(cidrhost(var.ssh_allowed_cidr, 0))
    error_message = "Must be a CIDR range such as 203.0.113.10/32."
  }
}

variable "dns_label" {
  description = "Optional DNS label for a free <label>.<region>.cloudapp.azure.com address. Must be unique in the region."
  type        = string
  default     = null
}

# --- Application -------------------------------------------------------------------------------

variable "repo_url" {
  description = "Public git repository the VM clones on first boot."
  type        = string
  default     = "https://github.com/Sri0401/project27.git"
}

# --- Cost alert --------------------------------------------------------------------------------

variable "budget_email" {
  description = "Email for budget alerts. Leave empty to skip creating the budget."
  type        = string
  default     = ""
}

variable "budget_amount" {
  description = "Monthly budget for the resource group, in your billing currency."
  type        = number
  default     = 5
}
