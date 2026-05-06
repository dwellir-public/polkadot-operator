# Build, Test, and Deploy

This document captures the validated local workflow for the `polkadot` v2
`machine_observability` provider update using the model
`alloy-sub-e2e-20260419`.

## Goals

- publish the full v2 `machine_observability` payload from `polkadot`
- keep the running node healthy during the charm refresh
- verify that `alloy-sub` continues to render metrics and logs correctly from
  the updated provider payload

## Local Verification

Run the repo checks first:

```bash
cd /home/erik/dwellir-public/polkadot-operator
tox -e unit
```

Optional:

```bash
tox -e lint
```

Note:

- `tox -e unit` passed for the v2 `machine_observability` update.
- `tox -e lint` still reports a large pre-existing repo-wide flake8 backlog and
  is not a clean gate for this specific change yet.

## Build

Build the 24.04 charm artifact used by the local model:

```bash
cd /home/erik/dwellir-public/polkadot-operator
charmcraft pack --platform ubuntu@24.04:amd64
```

Expected artifact:

```bash
polkadot_ubuntu@24.04-amd64.charm
```

## Refresh In `alloy-sub-e2e-20260419`

Refresh the running `polkadot` application in place:

```bash
juju refresh -m alloy-sub-e2e-20260419 polkadot \
  --path /home/erik/dwellir-public/polkadot-operator/polkadot_ubuntu@24.04-amd64.charm
```

Wait for the queued `upgrade-charm` hook to complete before validating the
relation data.

## Validate Model Status

```bash
juju status -m alloy-sub-e2e-20260419 polkadot alloy-sub --relations
```

Expected:

- `polkadot` remains `active`
- `alloy-sub` remains `active`
- the `machine-observability` relation remains present

## Validate Published v2 Payload

Inspect the subordinate relation data:

```bash
juju show-unit -m alloy-sub-e2e-20260419 alloy-sub/0
```

Expected under the `machine-observability` relation:

- `schema_version: 2`
- `source_topology.application: polkadot`
- `source_topology.unit: polkadot/0`
- one metrics target at `localhost:9615`
- the expected service name for the deployed workload type

## Validate Rendered Alloy Config

Inspect the rendered Alloy config on the subordinate unit:

```bash
juju ssh -m alloy-sub-e2e-20260419 alloy-sub/0 \
  'sudo sed -n "1,260p" /etc/alloy/config.alloy'
```

Expected rendered content:

- a `prometheus.scrape "polkadot"` block
- `juju_application = "polkadot"`
- `juju_unit = "polkadot/0"`
- `juju_charm = "polkadot"`
- a journald source for the published systemd unit

## Validate Metrics Endpoint

```bash
juju ssh -m alloy-sub-e2e-20260419 polkadot/0 \
  'curl -g -fsS http://[::1]:9615/metrics | head'
```

Expected:

- the Polkadot metrics endpoint responds successfully
- `alloy-sub` remains active after consuming the refreshed v2 payload
