# Polkadot Snap Upgrade Process

This guide describes the steps required to upgrade the Polkadot node to use the **Snap-based deployment** in a Juju-managed environment.

---

## ⚠️ Prerequisites

* Snap installed on the unit machine(s)
* The `juju` CLI installed and authenticated

---

## 🛠️ Upgrade Steps

### 1. **Stop the Polkadot service**

Before making any changes, stop the running service to ensure a clean transition:

```bash
juju run polkadot/leader stop-node-service
```

---

### 2. **Upgrade the Charm**

Refresh the charm on the unit using the new Snap-based build:

```bash
juju refresh polkadot --force-units --channel latest/edge/develop --switch polkadot
```
> Adjust `charm-channel` if you want to use a different track or risk level (e.g., `stable`, `latest/beta`, etc.).
You can also use the development branch `latest/edge/develop`

---

### 3. **Configure Charm to Use Snap**

Update the charm configuration to switch from binary or Docker to the Snap-based runtime:

```bash
juju config polkadot docker-tag='' binary-url='' snap-channel=latest/stable snap-name=polkadot
```

> Adjust `snap-channel` if you want to use a different track or risk level (e.g., `stable`, `latest/beta`, etc.).
>
> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

---

### 4. **Dry-Run Data Migration (Optional but Recommended)**

Run a dry migration to preview what data changes will be made:

```bash
juju run polkadot/leader migrate-data snap-name=polkadot dry-run=true
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

Review the output carefully to ensure correctness.

---

### 5. **Perform the Actual Data Migration**

If the dry-run output looks good, perform the actual migration:

```bash
juju run polkadot/leader migrate-data snap-name=polkadot
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

---

### 6. **Migrate the node key**

```bash
juju run polkadot/leader migrate-node-key snap-name=polkadot
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

---

### 7. **Restart the Polkadot Service**

After migration completes successfully, start the service:

```bash
juju run polkadot/leader start-node-service
```

---

## ✅ Verification

You can verify the node is running and using Snap by checking:

```bash
juju ssh polkadot/leader -- journalctl -fu snap.polkadot.polkadot.service
```

---

## 🔄 Reverting to Binary or Docker Deployment

If you need to revert from the Snap-based deployment back to either Binary or Docker, follow these steps:

### 1. **Stop the Polkadot service**

First, stop the running service:

```bash
juju run polkadot/leader stop-node-service
```

---

### 2. **Configure Charm to Use Binary or Docker**

Update the charm configuration to switch from Snap to either Binary or Docker:

For Binary deployment:
```bash
juju config polkadot snap-channel='' snap-name='' binary-url='https://github.com/paritytech/polkadot/releases/download/v1.0.0/polkadot' binary-sha256-url='https://github.com/paritytech/polkadot/releases/download/v1.0.0/polkadot.sha256'
```
> Replace the URLs with the appropriate binary URL and SHA256 URL for your desired version.

OR

For Docker deployment:
```bash
juju config polkadot snap-channel='' snap-name='' docker-tag='latest'
```
> Replace 'latest' with your desired Docker tag.

---

### 3. **Dry-Run Data Migration (Optional but Recommended)**

Run a dry migration to preview what data changes will be made:

```bash
juju run polkadot/leader migrate-data snap-name=polkadot reverse=true dry-run=true
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

Review the output carefully to ensure correctness.

---

### 4. **Perform the Actual Data Migration**

If the dry-run output looks good, perform the actual migration:

```bash
juju run polkadot/leader migrate-data snap-name=polkadot reverse=true
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

---

### 5. **Migrate the node key**

```bash
juju run polkadot/leader migrate-node-key snap-name=polkadot reverse=true
```

> The `snap-name` parameter can be one of:
> - `polkadot` - for relay chain nodes
> - `polkadot-parachain` - for parachain and system parachain nodes

---

### 6. **Restart the Polkadot Service**

After migration completes successfully, start the service:

```bash
juju run polkadot/leader start-node-service
```

---

### 7. **Verification**

You can verify the node is running correctly by checking the logs:

For Binary deployment:
```bash
juju ssh polkadot/leader -- journalctl -fu polkadot.service
```
