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
juju run polkadot/0 stop-node-service
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
juju config polkadot docker-tag='' binary-url='' snap-channel=latest/edge
```

> Adjust `snap-channel` if you want to use a different track or risk level (e.g., `stable`, `latest/beta`, etc.).

---

### 4. **Dry-Run Data Migration (Optional but Recommended)**

Run a dry migration to preview what data changes will be made:

```bash
juju run polkadot/0 migrate-data dry-run=true
```

Review the output carefully to ensure correctness.

---

### 5. **Perform the Actual Data Migration**

If the dry-run output looks good, perform the actual migration:

```bash
juju run polkadot/0 migrate-data
```

---

### 6. **Migrate the node key**

```bash
juju run polkadot/0 migrate-node-key
```

---

### 7. **Restart the Polkadot Service**

After migration completes successfully, start the service:

```bash
juju run polkadot/0 start-node-service
```

---

## ✅ Verification

You can verify the node is running and using Snap by checking:

```bash
juju ssh polkadot/0 -- snap logs -f polkadot
```
