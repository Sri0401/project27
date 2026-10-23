# Deploying to Azure for Students at no cost

The whole stack runs on **one Linux B1s VM** with Docker Compose. Every choice below matches what Azure's free services cover.

> **Recommended: use Terraform instead.** [../terraform/](../terraform/) creates exactly this setup as code, with validations that block non-free sizes and disks. This page is the manual alternative through the portal, and it explains the cost rules both routes follow.

## How the cost works

| Resource | Setting | Free allowance |
|---|---|---|
| VM | **Standard_B1s**, Linux, **only one** | 750 hours a month for 12 months. One VM running all month uses about 744 hours |
| OS disk | **Premium SSD, 64 GiB (P6)** | Two P6 disks a month. The default 30 GiB disk is a **P4**, which the allowance does **not** cover |
| Public IP | Standard, static | **Not in the free list.** About US$3–4 a month, taken from your student credit |
| Outbound data | Website traffic | 100 GB a month free, far more than a portfolio site uses |
| Virtual network, network security group | Default | Free |
| Boot diagnostics, backup, Defender, monitoring | **Off** | Not needed. Turning them on could cost credit |

Azure for Students doesn't use a credit card. Anything that isn't free is taken from the US$100 credit, and if the credit runs out the subscription is disabled rather than billed. Your free allowances end **12 months after the subscription started**. Hover over the info icon on the "Top free services" tile to see the exact date, and delete the VM before then.

## Step 0: set a budget alert (2 minutes)

In the portal, go to **Cost Management > Budgets > + Add**.

1. Set scope to *Azure for Students*, amount **US$5**, reset period monthly.
2. Add alerts at **50% Actual** and **100% Forecasted**, using your email address.

A budget only sends emails. It doesn't stop anything, but it tells you early if something starts using credit.

## Step 1: push the latest code

The VM clones https://github.com/Sri0401/project27 when it first starts, so commit and push before creating it.

## Step 2: create the VM from the Free services page

Microsoft recommends this route because it preselects the free options. Go to **portal.azure.com**, search for **Free services**, then find **Linux Virtual Machine** and click **Create**.

**Basics tab**

| Field | Value |
|---|---|
| Resource group | **Create new**: `urbanpulse-rg` |
| Virtual machine name | `urbanpulse-vm` |
| Region | `Australia East`. If it's refused by policy or capacity, try `Southeast Asia` or `Central India` |
| Availability options | No infrastructure redundancy required |
| Security type | Standard |
| Image | **Ubuntu Server 24.04 LTS - x64 Gen2** |
| Size | **Standard_B1s** (it should say *free services eligible*) |
| Authentication type | SSH public key |
| Username | **`azureuser`** (exactly this, because the setup script expects it) |
| SSH public key source | Generate new key pair, named `urbanpulse-key` |
| Public inbound ports | Allow selected ports: **HTTP (80)** and **SSH (22)** |

**Disks tab**

- OS disk type: **Premium SSD (locally-redundant storage)**
- OS disk size: click **Change size** and choose **64 GiB (P6)**. This is the step that's easy to miss.
- Tick **Delete with VM**.

**Networking tab**: keep the defaults (new virtual network, new Standard public IP). Tick **Delete public IP and NIC when VM is deleted**.

**Management tab**: Microsoft Defender for Cloud **off**, Auto-shutdown **off** (750 hours already covers running all the time), Backup **off**.

**Monitoring tab**: Boot diagnostics **Disable**, Alerts **off**.

**Advanced tab**: in **Custom data**, paste the entire contents of [`cloud-init.yaml`](cloud-init.yaml). The VM runs it on first boot to install Docker, clone the repo, generate random passwords and start the stack.

**Review + create**: check that the summary shows **Standard B1s** and a **64 GiB** disk. Click **Create**, then **download the private key** when prompted (`urbanpulse-key.pem`). You can't download it again later. Keep it out of the git repo, for example in `C:\Users\<you>\.ssh\`.

## Step 3: wait for it to build (about 10 minutes)

A B1s VM is small, so building the Java and Python images takes a while. Get the **Public IP address** from the VM's Overview page, then run in PowerShell:

```powershell
ssh -i $HOME\.ssh\urbanpulse-key.pem azureuser@<public-ip> "sudo tail -n 30 /var/log/cloud-init-output.log; docker ps"
```

When all of `web`, `api`, `postgres` and `mongo` show as **healthy**, open `http://<public-ip>` and `http://<public-ip>/api/docs`.

Your generated API key, needed to add datasets, is in `.env` on the VM:

```powershell
ssh -i $HOME\.ssh\urbanpulse-key.pem azureuser@<public-ip> "grep API_KEY ~/urbanpulse/.env"
```

If SSH complains that the key's permissions are too open, run: `icacls $HOME\.ssh\urbanpulse-key.pem /inheritance:r /grant:r "$($env:USERNAME):R"`

## Step 4: lock down SSH

On the VM, go to **Networking > Network settings**, open the inbound **SSH** rule and set **Source** to *My IP address*. Port 80 stays open to everyone.

## Step 5: check costs after 24–48 hours

Usage takes up to two days to appear.

- **Subscription > Overview > Top free services**: *Virtual Machines, BS Series* and *P6 Disks* should show usage **within limit**.
- **Cost Management > Cost analysis**: only the public IP address should show any cost.

## Automatic deployment from GitHub

The VM updates itself. Every 5 minutes it deploys the latest commit on `main` once CI has passed for it, health-checks the result and rolls back on failure. cloud-init sets this up, so no secrets or open SSH port are needed. See [../vm/README.md](../vm/README.md).

## Stopping and removing

- **Stop (deallocate)**: VM Overview > **Stop**. The VM hours stop counting, but the disk and public IP remain. Stopping isn't needed to stay free.
- **Delete everything**: Resource groups > `urbanpulse-rg` > **Delete resource group**. Do this before your 12 free months end.
