#!/usr/bin/env python3

"""Metadata collection helpers for the geth charm."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any
from polkadot_rpc_wrapper import PolkadotRpcWrapper
from core.service_args import ServiceArgs

import ops
from charms.dwellir.blockchain_common.v1 import (
    SubstrateBlockchainMetadata,
    MetadataUploadError,
    MetadataValidationError,
    collect_and_upload,
    parse_credentials_secret_id,
)
from charms.dwellir.blockchain_common.v1 import jsonrpc as rpcrequest
from charms.dwellir.blockchain_common.v1.evm_chains import registry as evm_registry

logger = logging.getLogger(__name__)


def collect_upload_metadata(charm: Any) -> None:
    """Build metadata payloads and optionally upload them to S3."""
    logger.info("collectUploadMetadata invoked")
    credentials_secret_id = charm.model.config.get("collector-s3-credentials")
    creds = None
    if credentials_secret_id:
        try:
            creds = parse_credentials_secret_id(charm.model, credentials_secret_id)
        except MetadataValidationError as exc:
            msg = f"invalid collector-s3-credentials: {exc}"
            logger.error(msg)
            charm.unit.status = ops.BlockedStatus(msg)
            return
    else:
        logger.info("collector-s3-credentials not set; will write payload locally without upload.")

    rpc_port = ServiceArgs(charm.config, charm.rpc_urls()).rpc_port
    rpc_wrapper = PolkadotRpcWrapper(rpc_port)

    netname = None
    try:
        netname = rpc_wrapper.get_chain_name()
    except Exception as e:
        logger.warning(f"system_chain RPC failed: {e}")

    genesis_hash = None
    try:
        genesis_hash = rpc_wrapper.get_genesis_hash()
    except Exception as e:
        logger.warning(f"genesis_hash RPC failed: {e}")

    binary_path_value = charm._workload.get_binary_path()
    binver = charm._get_workload_version()
    cname_local = Path(charm._workload.get_binary_path()).name
    logger.debug(f"Local clientname: {cname_local}")

    my_blockchain = SubstrateBlockchainMetadata(
        blockchain_ecosystem="substrate",
        blockchain_network_name=netname or "unknown",
        client_name=cname_local,
        client_version=binver,
        cmdline=charm._workload.get_proc_cmdline() or "",
        binary_path=binary_path_value,
        genesis_hash=genesis_hash
    )

    try:
        upload_base = Path("/tmp/dwellir-metadata-uploader")
        no_upload = creds is None
        logger.info(
            "invoking collect_and_upload with credentials=%s, model=%s, "
            "app=%s, unit=%s, meta=%s, base_dir=%s, blockchain=%s, "
            "no_upload=%s",
            creds,
            charm.model,
            charm.app,
            charm.unit,
            charm.meta,
            upload_base,
            my_blockchain,
            no_upload,
        )

        upload_dest = collect_and_upload(
            credentials=creds,
            model=charm.model,
            app=charm.app,
            unit=charm.unit,
            meta=charm.meta,
            base_dir=upload_base,
            blockchain=my_blockchain,
            no_upload=no_upload,
        )
        logger.info(f"metadata collection and upload complete; destination: {upload_dest}")
    except ValueError as exc:
        msg = f"invalid blockchain metadata: {exc}"
        logger.error(msg)
        return
    except MetadataUploadError as exc:
        msg = f"upload failed: {exc}"
        logger.error(msg)
        return
    except Exception as exc:  # noqa: BLE001 - surface unexpected issues
        msg = f"unexpected error during update-status: {exc}"
        logger.exception(msg)
        return
