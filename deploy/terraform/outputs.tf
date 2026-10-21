output "public_ip" {
  description = "Public IP address of the VM."
  value       = azurerm_public_ip.main.ip_address
}

output "website_url" {
  description = "Website address. It responds about 10 minutes after the first apply, once cloud-init has finished."
  value       = "http://${coalesce(azurerm_public_ip.main.fqdn, azurerm_public_ip.main.ip_address)}"
}

output "api_docs_url" {
  value = "http://${coalesce(azurerm_public_ip.main.fqdn, azurerm_public_ip.main.ip_address)}/api/docs"
}

output "ssh_command" {
  value = "ssh -i ${trimsuffix(var.ssh_public_key_path, ".pub")} ${var.admin_username}@${azurerm_public_ip.main.ip_address}"
}

output "check_progress_command" {
  value = "ssh -i ${trimsuffix(var.ssh_public_key_path, ".pub")} ${var.admin_username}@${azurerm_public_ip.main.ip_address} \"sudo tail -n 20 /var/log/cloud-init-output.log; docker ps\""
}
