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

### Juju relations/integrations

a is Prometheus, which also exists [as a charm](https://charmhub.io/prometheus2)

#### In LXD

    juju deploy polkadot <node configurations>
    juju deploy prometheus2 prometheus
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs
    juju relate polkadot:node-prometheus prometheus:manual-jobs

#### In AWS

    juju deploy polkadot <node configurations> --constraints "instance-type=t3.medium root-disk=200G"
    juju deploy prometheus2 prometheus
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs
    juju relate polkadot:node-prometheus prometheus:manual-jobs

#### Add Grafana

If you want to use a [Grafana instance deployed with Juju](https://charmhub.io/grafana) in your monitoring stack:

    juju deploy grafana
    juju relate prometheus:grafana-source grafana:grafana-source
    juju run-action --wait grafana/0 get-admin-password

## Building

Though this charm is published on Charmhub there is also the alternative to build it locally, and to deploy it from that local build. It is built with the package charmcraft. See [charmcraft.yaml](charmcraft.yaml) for build details.
    
    sudo snap install charmcraft --classic
    charmcraft pack  # assumes pwd is the polkadot-operator root directory

## System requirements

*Disclaimer: the system requriements to run a node in the Polkadot ecosystem varies, both depending on which chain is being run and which type of node it is. The example below should therefore be vetted against updated and reliable resources depending on your deployment specifications.*

This list of reference hardware is from [the official Polkadot docs](https://wiki.polkadot.network/docs/maintain-guides-how-to-validate-polkadot) and is an example of good practice for a validator node:

- CPU
  - x86-64 compatible;
  - Intel Ice Lake, or newer (Xeon or Core series); AMD Zen3, or newer (EPYC or Ryzen);
  - 4 physical cores @ 3.4GHz;
  - Simultaneous multithreading disabled (Hyper-Threading on Intel, SMT on AMD);
  - Prefer single-threaded performance over higher cores count.
- Storage
  - An NVMe SSD of 1 TB (As it should be reasonably sized to deal with blockchain growth). An estimation of current chain snapshot sizes can be found [here](https://paranodes.io/DBSize). In general, the latency is more important than the throughput.
- Memory
  - 32 GB DDR4 ECC.
- System
  - Linux Kernel 5.16 or newer.
- Network
  - The minimum symmetric networking speed is set to 500 Mbit/s (= 62.5 MB/s). This is required to support a large number of parachains and allow for proper congestion control in busy network situations.
