# polkadot

## Description

Polkadot is a web3 blockchain ecosystem. This charm can be deployed as a validator, collator, bootnode, or RPC on any Polkadot derived blockchain, also known as parachains. The deployment config differs depending on the chain that is being deployed.

The charm starts the Polkadot client as a service, which takes its arguments from /etc/default/polkadot and is set by the juju config *service-args*. The Polkadot client itself is downloaded and installed from the config *binary-url*.

##  Deployment from charmhub

To deploy as a standard node:

    juju deploy polkadot

### As a validator

WRITEME

### As a collator

WRITEME

### As a bootnode

WRITEME

### As an RPC

WRITEME

### In AWS

    juju deploy polkadot binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.10/polkadot --constraints "instance-type=t3.medium root-disk=200G"
    juju deploy prometheus2 prometheus
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs
    juju relate polkadot:node-prometheus prometheus:manual-jobs

### In LXD

    juju deploy polkadot --config binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.10/polkadot
    juju deploy prometheus2 prometheus
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs
    juju relate polkadot:node-prometheus prometheus:manual-jobs

### With grafana

If you're using a local grafana deployment in your monitoring stack:

    juju deploy grafana
    juju relate prometheus:grafana-source grafana:grafana-source
    juju run-action --wait grafana/0 get-admin-password

## Building

Build the charm with charmcraft. See [charmcraft.yaml](charmcraft.yaml)
    
    sudo snap install charmcraft --classic
    charmcraft pack
