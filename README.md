# polkadot

The [Polkadot node operator](https://charmhub.io/polkadot) provides an easy-to-use way of deploying a Polkadot node, using the [Juju framework](https://juju.is/).

This repository is maintained by Dwellir, https://dwellir.com - Infrastructure provider for blockchain and web3.

## Description

[Polkadot](https://polkadot.network/) is a web3 blockchain ecosystem. This charm can be deployed as a validator, collator, bootnode, or RPC on any Polkadot derived blockchain, also known as parachains. The deployment config differs depending on the chain that is being deployed.

The charm starts the Polkadot client as a service, which takes its arguments from `/etc/default/polkadot` which in turn are set by the Juju config *service-args*. The Polkadot client itself is downloaded and installed from the config *binary-url*.

## Usage

With [Juju's OLM](https://juju.is/docs/olm) bootstrapping your cloud of choice, and a Juju model created within that cloud to host the operator, the charm can be deployed as:

    juju deploy polkadot

However, there are some configs which are required by the charm to correctly install and start running the Polkadot client:

- `binary-url=...` or `docker-tag=...`
- `service-args="... ..."` with the tags `--chain=...` and `--rpc-port=...` set

With those configs included, a standard deployment of the Polkadot node could look like:

    juju deploy polkadot --config binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.43/polkadot --config service-args="--chain=polkadot --rpc-port=9933"

There are many more arguments available for the Polkadot client, which may or may not be relevant for your specific deployment. Read about them in detail in the [Polkadot node client](https://github.com/paritytech/polkadot) source code or by accessing the help menu from the client itself:

    ./polkadot --help

### Deploying other node types

There are a number of different node types in the Polkadot ecosystem, all which use the same client software to run. That means that by changing the client's service arguments in the deployment of this charm, one can easily change which node type to deploy. Read more about the specific node types on the Polkadot docs pages; [validator](https://wiki.polkadot.network/docs/learn-validator), [collator](https://wiki.polkadot.network/docs/learn-collator), [bootnode](https://wiki.polkadot.network/docs/maintain-bootnode), [RPC](https://wiki.polkadot.network/docs/maintain-rpc).

#### Deploying a validator

    juju deploy polkadot --config binary-url=... --config service-args="--validator --chain=... --rpc-port=..."

#### Deploying a collator

    juju deploy polkadot --config binary-url=... --config service-args="--collator --chain=... --rpc-port=..."

#### Deploying a bootnode

    juju deploy polkadot --config binary-url=... --config service-args="--chain=... --rpc-port=... --listen-addr=/ip4/0.0.0.0/tcp/<port> --listen-addr=/ip4/0.0.0.0/tcp/<port>/ws"

#### Deploying an RPC node

    juju deploy polkadot --config binary-url=... --config service-args="--chain=... --name=MyRPC --rpc-port=... --rpc-methods=Safe"

### In AWS

    juju deploy polkadot <node configurations> --constraints "instance-type=t3.medium root-disk=200G"
    juju deploy prometheus2 prometheus
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs
    juju relate polkadot:node-prometheus prometheus:manual-jobs

### In LXD

    juju deploy polkadot <node configurations>
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
