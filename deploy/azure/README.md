# Deploying to Azure (Azure for Students)

The whole stack runs on one **Standard_B1s** Linux VM using Docker Compose. With an Azure for Students subscription, the free services list has normally included 750 hours a month of a B1s Linux VM and two 64 GB P6 managed disks. Small extras, such as the public IP address, come out of your student credit.

> Free offers change. Before you start, check the **Free services** blade in the Azure portal and set a **budget alert** in Cost Management. Delete the resources when you no longer need them (`bash teardown.sh`).

## 1. Push the repo to GitHub

The VM clones your repo, so it needs to be public, or you can add a deploy key later.

## 2. Provision the VM from Azure Cloud Shell

Open https://shell.azure.com and choose **Bash**. Cloud Shell is free and already signed in, so you do not need to install anything.

```bash
git clone https://github.com/Sri0401/project27.git
cd project27/deploy/azure
bash provision.sh https://github.com/Sri0401/project27.git
```

Optional overrides: `LOCATION=southeastasia RG=my-rg bash provision.sh ...`. Azure for Students can limit which regions you may use. If you get a `RequestDisallowedByPolicy` or capacity error, try another region.

The script prints the public IP. After 5 to 10 minutes, open `http://<ip>`.

## 3. Continuous deployment with GitHub Actions (optional)

[`.github/workflows/deploy.yml`](../../.github/workflows/deploy.yml) connects to the VM over SSH after every green CI run on `main`, then runs `git pull` and `docker compose up -d --build`.

1. Create a key pair just for deployments, in Cloud Shell:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/urbanpulse_deploy -N ""
   ssh-copy-id -i ~/.ssh/urbanpulse_deploy.pub azureuser@<ip>
   cat ~/.ssh/urbanpulse_deploy   # copy the private key
   ```
2. In GitHub, go to **Settings > Secrets and variables > Actions** and add:
   - `AZURE_VM_HOST`: the VM's public IP
   - `AZURE_VM_USER`: `azureuser`
   - `AZURE_VM_SSH_KEY`: the private key from step 1
3. Under **Settings > Environments**, create an environment called `production`. You can add a required reviewer so that every deployment needs approval.

## Hardening ideas (good interview talking points)

- Restrict SSH (port 22) in the network security group to your own IP address.
- Add HTTPS: point a free DNS name at the VM (Azure gives each public IP a `*.cloudapp.azure.com` label) and use Caddy or certbot with Let's Encrypt.
- Move the data to managed services: Azure Database for PostgreSQL Flexible Server, and Azure Cosmos DB for MongoDB (it has a free tier). Then change only `DATABASE_URL` and `MONGO_URL`.
- Push images to GitHub Container Registry from CI so the VM pulls them instead of building them.
