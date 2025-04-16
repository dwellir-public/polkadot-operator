# polkadot

The [Polkadot node operator](https://charmhub.io/polkadot) provides an easy-to-use way of deploying a Polkadot node, using the [Juju framework](https://juju.is/).

This repository is maintained by Dwellir, https://dwellir.com - Infrastructure provider for blockchain and web3.

## Description

[Polkadot](https://polkadot.network/) is a web3 blockchain ecosystem. This charm can be deployed as a validator, collator, bootnode, or RPC on any Polkadot derived blockchain, also known as parachains. The deployment config differs depending on the chain that is being deployed.

The charm starts the Polkadot client as a service, which takes its arguments from `/etc/default/polkadot` which in turn are set by the Juju config *service-args*. The Polkadot client itself is downloaded and installed from the config *binary-url*.

## Building

Though this charm is published on Charmhub there is also the alternative to build it locally, and to deploy it from that local build. It is built with the package charmcraft. See [charmcraft.yaml](charmcraft.yaml) for build details.

    sudo snap install charmcraft --classic
    charmcraft pack  # Assumes pwd is the polkadot-operator root directory

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

## Usage

### Deploying Polkadot

With [Juju's OLM](https://juju.is/docs/olm) bootstrapping your cloud of choice, and a Juju model created within that cloud to host the operator, the charm can be deployed as:

    juju deploy polkadot

However, there are some configs which are required by the charm to correctly install and start running the Polkadot client:

- `binary-url=...` or `docker-tag=...`
    - Note: from Polkadot release 1.1.0, the binary is split into three separate parts which means three separate URL:s will need to be set to the `binary-url` config, in a space separated list.
- `service-args="... ..."` with the tags `--chain=...` and `--rpc-port=...` set

With those configs included, a standard deployment of the Polkadot node could look like:

    juju deploy polkadot --config binary-url=https://github.com/paritytech/polkadot/releases/download/v0.9.43/polkadot --config service-args="--chain=polkadot --rpc-port=9933"

There are many more arguments available for the client, regardless of if it is the Polkadot relaychain client or a parachain client, which may or may not be relevant for your specific deployment. Read about them in detail in their respective source code, e.g. here for the [Polkadot node client](https://github.com/paritytech/polkadot), or by accessing the help menu from the client itself with either of these methods:

    # With local copy of the client available
    ./polkadot --help

    # For an already deployed charm
    juju run polkadot/0 get-node-help --format json | jq -r '.["polkadot/0"].results["help-output"]'

#### Deploying other node types

There are a number of different node types in the Polkadot ecosystem, all which use the same client software to run. That means that by changing the client's service arguments in the deployment of this charm, one can easily change which node type to deploy. Read more about the specific node types on the Polkadot docs pages; [validator](https://wiki.polkadot.network/docs/learn-validator), [collator](https://wiki.polkadot.network/docs/learn-collator), [bootnode](https://wiki.polkadot.network/docs/maintain-bootnode), [RPC](https://wiki.polkadot.network/docs/maintain-rpc).

#### Deploying a validator

    juju deploy polkadot --config binary-url=... --config service-args="--validator --chain=... --rpc-port=..."

Once a validator has been deployed, use the Juju action `get-session-key` to generate and return a new session key, which then can be used as a paramater in the extrinsic call on [polkadot.js](https://polkadot.js.org/).

#### Deploying a collator

    juju deploy polkadot --config binary-url=... --config service-args="--collator --chain=... --rpc-port=..."

Running a collator also requries setting a node key, which can be done by running the Juju action `set-node-key`. The node key itself can be generated using the [subkey tool](https://github.com/paritytech/substrate/tree/master/bin/utils/subkey).

#### Deploying a bootnode

    juju deploy polkadot --config binary-url=... --config service-args="--chain=... --rpc-port=... --listen-addr=/ip4/0.0.0.0/tcp/<port> --listen-addr=/ip4/0.0.0.0/tcp/<port>/ws"

Running a bootnode also requries setting a node key, which can be done by running the Juju action `set-node-key`. The node key itself can be generated using the [subkey tool](https://github.com/paritytech/substrate/tree/master/bin/utils/subkey).

#### Deploying an RPC node

    juju deploy polkadot --config binary-url=... --config service-args="--chain=... --name=MyRPC --rpc-port=... --rpc-methods=Safe"

### Deploying other Polkadot ecosystem chains

As mentioned at the top of the readme, [Polkadot](https://polkadot.network/) is a web3 blockchain ecosystem, sometimes referred to as the "DotSama ecosystem", which includes a number of Polkadot derived parachains. Due to them being derived from the original relaychain code, and kept up to date, this charm can easily run them as well. But since they run completely separate networks, they do need other chain specifications. For some of the chains, the specifications are included in the binary but for some of them, specifications need to be supplied using a JSON file. In [service_args.py](src/service_args.py), we define chain name aliases for some of these chains. E.g. if one uses `--chain=peregrine` in the `service-args` config, what actually happens is that both the binary **and** the JSON specification file are extracted from the `peregrine` Docker image. Then the name `peregrine` is replaced with the path to the JSON in the argument given to the blockchain client binary, so that is what's run when the charm starts the client.

For more information regarding parachains and node operations, please visit the [Polkadot wiki](https://wiki.polkadot.network/docs/learn-parachains-index).

### Juju relations/integrations

A powerful feature of the Juju framework is the ability to relate (integrate in Juju 3.x) charms to each other. By relating two charms, they exchange data based on the interface used. There are a number of existing interfaces for well-known applications and several are being employed in this charm.

#### Prometheus relation

One of the interfaces used in this charm is to connect with Prometheus, which also happens to exist [as a charm](https://charmhub.io/prometheus2). Relating this node with a Prometheus deployment will with a single action let the Prometheus instance start scraping the data generated by the node, given that Prometheus is enabled for the node client (`--prometheus-external`).

Here is an example where the Polkadot and Prometheus charms are deployed in a Juju model residing in an AWS cloud, and then related to each other:

    juju deploy polkadot <node configurations> --constraints "instance-type=t3.medium root-disk=400G"
    juju deploy prometheus2 prometheus --constraints
    juju relate polkadot:polkadot-prometheus prometheus:manual-jobs  # Polkadot node data
    juju relate polkadot:node-prometheus prometheus:manual-jobs      # Container system data

#### Add Grafana

If you want to use a [Grafana instance deployed with Juju](https://charmhub.io/grafana) in your monitoring stack:

    juju deploy grafana
    juju relate prometheus:grafana-source grafana:grafana-source
    juju run-action --wait grafana/0 get-admin-password  # Juju 2.x
    juju run grafana/0 get-admin-password                # Juju 3.x

#### The COS stack

An alternative to deploying a Prometheus instance which each node is to use what is known as the [Canonical Observability Stack](https://charmhub.io/topics/canonical-observability-stack). By levering the topology model of Juju and charm relations to automate integration, it provides an observability suite based on best-in-class, open-source observability tools.

The `cos_agent` interface is already supported by this Polkadot operator charm so if you've deployed an instance of the COS, integrate it with your node like this:

    juju deploy grafana-agent --channel edge          # In the same model as the Polkadot node
    juju relate grafana-agent <COS interfaces>
    juju relate polkadot:grafana-agent grafana-agent  # grafana-agent is also the name for the interface in this charm

Find more details on how to deploy and use COS [here](https://charmhub.io/topics/canonical-observability-stack/tutorials/instrumenting-machine-charms).

#### Using an external relaychain node

A parachain node can use an external relaychain node instead of the internal one. It's useful for scaling where multiple parachain nodes can share a relaychain node. It's also useful to get faster in sync since the parachain node does not have to sync a relaychain node by itself. This can be set with the service argument `--relay-chain-rpc-urls`, which takes one or more weboscket URLs to relaychain nodes to use. Setting multiple URLs is for fallback where the parachain node will try accessing the URLs in a round-robin fashion. Instead of setting this manually, the interface `rpc-url` can be used:

    juju relate polkadot-relay:rpc-url polkadot-para:relay-rpc-url     # Juju 2.x
    juju integrate polkadot-relay:rpc-url polkadot-para:relay-rpc-url  # Juju 3.x

Relating to multiple relaychain nodes, to have fallbacks, is supported by the interface. It's also possible to both use the `rpc-url` interface and set URLs manually in the service arguments at the same time. In the charm, the URLs from using the interface are added to the beginning of the service arguments, in the same order as they are related. Adding URLs manually should thus be considered as a fallback since as it has been mentioned, the Polkadot client selects relay chain URL in a round-robin fashion. One can for example use an external providers relaychain node as a fallback in this way, a case where it is not possible to use Juju primitives.

#### Make a node start validating (e.g. move a validator from a node to another)

To start validating, a session key generated on the node needs to be set on-chain for the validator address. This is an extrinsic, which requires paying a fee. Ideally, a proxy account account is set up for the validator account, holding just enough tokens to pay the fees. A validator account should never be used directly for this, an exception being for testnets where the tokens have no real value. The steps below describe how to configure the application for this usecase:

Add the accounts mnemonic to the model as a secret (where 'proxy-type' is only needed if this is a proxy account), example:
    
    juju add-secret mysecret mnemonic="ocean apple bridge galaxy lemon tiger velvet orbit shadow maple breeze canyon" proxy-type="Staking" --info "useful info, e.g. the public address of the account"

Grant the Polkadot application access to the secret, example:
    
    juju grant-secret mysecret polkadot

Configure the application to use the secret, example:
    
    juju config polkadot mnemonic-secret-id="secret:ctr90nhaeavjam32tflg"

Run the action to make this node start validating (where 'address' is only needed if the secret is a proxy account):
    
    juju run polkadot/0 start-validating address=<validator-address>

You can verify that this node will be validating next era:
    
    juju run polkadot/0 is-validating-next-era address=<validator-address>

## Resources

- [Polkadot](https://polkadot.network/)
- [Polkadot node on Charmhub](https://charmhub.io/polkadot)
- [polkadot-operator repo on GitHub](https://github.com/dwellir-public/polkadot-operator)
- [Dwellir](https://dwellir.com/)
