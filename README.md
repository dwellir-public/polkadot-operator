# polkadot

## Description

Polkadot is a web3 blockchain. This charm can be deployed as a validator, collator, bootnode, or RPC. The deployment config differs.

The service takes its arguments from /etc/default/polkadot and is set by a *juju config service-args*.

##  Deployment from charmhub
To deploy as a standard node:

    juju deploy polkadot

### As a validator

WRITEME

### As a collator

WRITEME

### As a bootnode

WRITEME

### As a RPC

WRITEME

### In AWS
    juju deploy ./polkadot.charm binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.10/polkadot --constraints "instance-type=t3.medium root-disk=200G"
    juju deploy prometheus2 prometheus
    juju deploy grafana
    juju relate prometheus:grafana-source grafana:grafana-source
    juju relate polkadot:polkadot-scrape prometheus:scrape
    juju relate polkadot:node-scrape prometheus:scrape
    juju run-action --wait grafana/0 get-admin-password

### In LXD
    juju deploy ./polkadot.charm --config binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.10/polkadot
    juju deploy prometheus2 prometheus
    juju deploy grafana
    juju relate prometheus:grafana-source grafana:grafana-source
    juju relate polkadot:polkadot-scrape prometheus:scrape
    juju relate polkadot:node-scrape prometheus:scrape
    juju run-action --wait grafana/0 get-admin-password

## Building
Build the charm with charmcraft. See [charmcraft.yaml](charmcraft.yaml)
    
    sudo snap install charmcraft --classic
    charmcraft pack
