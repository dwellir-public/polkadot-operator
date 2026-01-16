# Copyright 2025 Erik Lönroth
# See LICENSE file for licensing details.

"""Functions for managing and interacting with the workload.

The intention is that this module could be used outside the context of a charm.
"""

from __future__ import annotations

import json
import logging
import pathlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import boto3
from botocore.exceptions import BotoCoreError, ClientError, EndpointConnectionError, ParamValidationError

logger = logging.getLogger(__name__)


class UploadError(Exception):
    """Raised when the upload to the object store fails."""


@dataclass
class Credentials:
    bucket: str
    region: str
    access_key_id: str
    secret_access_key: str
    session_token: str | None
    endpoint_url: str | None
    key_prefix: str

    def object_key(self, model_name: str, model_uuid: str, unit_name: str) -> str:
        """Build the destination object key."""
        prefix = self.key_prefix or ""
        if prefix and not prefix.endswith("/"):
            prefix = f"{prefix}/"
        model_dir = f"{model_name}-{model_uuid}/"
        safe_unit = unit_name.replace("/", "-")
        return f"{prefix}{model_dir}{safe_unit}.json"


@dataclass
class BlockchainMetadata:
    """Canonical shape of the blockchain metadata section."""

    blockchain_ecosystem: str
    blockchain_network_name: str
    client_name: str
    client_version: str
    cmdline: str
    binary_path: str

    def to_dict(self) -> dict[str, Any]:
        """Return a validated dict representation.
        This controls that the resulting datastruct is consistent.
        """
        return _validate_blockchain_section(
            required_keys = {
                "blockchain_ecosystem": str,
                "blockchain_network_name": str,
                "client_name": str,
                "client_version": str,
                "cmdline": str,
                "binary_path": str,
            },
            data = {
                "blockchain_ecosystem": self.blockchain_ecosystem,
                "blockchain_network_name": self.blockchain_network_name,
                "client_name": self.client_name,
                "client_version": self.client_version,
                "cmdline": self.cmdline,
                "binary_path": self.binary_path,
            }
        )

@dataclass
class EVMBlockchainMetadata(BlockchainMetadata):
    """Canonical shape of the blockchain metadata section."""
    chain_id: int
    l1_chain_id: int | None = None
    l2_chain_id: int | None = None

    def to_dict(self) -> dict[str, Any]:
        """Return a validated dict representation.
        This controls that the resulting datastruct is consistent.
        """
        return _validate_blockchain_section(
            required_keys={
                "chain_id": int,
                "l1_chain_id": (int, type(None)),
                "l2_chain_id": (int, type(None)),
            },
            data={
                "chain_id": self.chain_id,
                "l1_chain_id": self.l1_chain_id,
                "l2_chain_id": self.l2_chain_id
            }
        ) | super().to_dict()

@dataclass
class SubstrateBlockchainMetadata(BlockchainMetadata):
    """Canonical shape of the blockchain metadata section."""

    def to_dict(self) -> dict[str, Any]:
        """Return a validated dict representation.
        This controls that the resulting datastruct is consistent.
        """
        return super().to_dict()


def _validate_blockchain_section(required_keys: dict[str, type[str | int | bool]], data: dict[str, Any]) -> dict[str, Any]:
    """Validate required blockchain keys and types, returning a normalized dict."""

    missing = [key for key in required_keys.keys() if key not in data]
    if missing:
        raise ValueError(f"missing blockchain metadata fields: {', '.join(missing)}")
    
    for key, expected_type in required_keys.items():
        value = data.get(key)
        if not isinstance(value, expected_type):
            raise ValueError(f"{key} must be of type {expected_type.__name__}")
    return data


def normalize_blockchain_metadata(blockchain: BlockchainMetadata | dict[str, Any]) -> dict[str, Any]:
    """Normalize blockchain metadata to a validated dict."""
    if isinstance(blockchain, BlockchainMetadata):
        return blockchain.to_dict()
    if not isinstance(blockchain, dict):
        raise ValueError("blockchain metadata must be a dict or BlockchainMetadata")
    return _validate_blockchain_section(blockchain)


@dataclass
class JujuTopology:
    """Canonical shape of juju topology metadata.
    https://documentation.ubuntu.com/observability/track-2/reference/juju-topology-labels/
    {
                "model": self.model,
                "model_uuid": self.model_uuid,
                "application": self.application,
                "unit": self.unit,
                "charm": self.charm,
            }
    """

    model: str
    model_uuid: str
    application: str
    unit: str
    charm: str | None

    @classmethod
    def from_juju(cls, model: Any, app: Any, unit: Any, meta: Any) -> "JujuTopology":
        """Build topology from juju objects, with minimal caller effort."""
        return cls(
            model=str(getattr(model, "name", "")),
            model_uuid=str(getattr(model, "uuid", "")),
            application=str(getattr(app, "name", "")),
            unit=str(getattr(unit, "name", "")),
            charm=getattr(meta, "name", None) if meta else None
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a validated dict representation."""
        return _validate_topology(
            {
                "model": self.model,
                "model_uuid": self.model_uuid,
                "application": self.application,
                "unit": self.unit,
                "charm": self.charm,
            }
        )


def _validate_topology(topology: dict[str, Any]) -> dict[str, Any]:
    """Validate required topology keys and types, returning a normalized dict."""
    required_keys = ("model", "model_uuid", "application", "unit", "charm")
    missing = [key for key in required_keys if key not in topology]
    if missing:
        raise ValueError(f"missing juju topology fields: {', '.join(missing)}")

    def _require_str(key: str) -> str:
        value = topology.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{key} must be a non-empty string")
        return value

    charm = topology.get("charm")
    if charm is not None and (not isinstance(charm, str) or not charm.strip()):
        raise ValueError("charm must be a non-empty string when provided")

    return {
        "model": _require_str("model"),
        "model_uuid": _require_str("model_uuid"),
        "application": _require_str("application"),
        "unit": _require_str("unit"),
        "charm": charm,
    }


def parse_credentials(raw: str) -> Credentials:
    """Parse JSON config string into Credentials for S3 (or compatible) upload."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"must be valid JSON: {exc.msg}") from exc

    if not isinstance(data, dict):
        raise ValueError("config must be a JSON object")

    required = ("bucket", "region", "access_key_id", "secret_access_key")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"missing required fields: {', '.join(missing)}")

    key_prefix = str(data.get("key_prefix") or "uploads/")

    return Credentials(
        bucket=str(data["bucket"]),
        region=str(data["region"]),
        access_key_id=str(data["access_key_id"]),
        secret_access_key=str(data["secret_access_key"]),
        session_token=data.get("session_token"),
        endpoint_url=data.get("endpoint_url"),
        key_prefix=key_prefix,
    )


def _relation_details(model: Any, app: Any, unit: Any, meta: Any) -> list[dict[str, Any]]:
    """Collect relation metadata and databags."""
    relations_payload: list[dict[str, Any]] = []
    for relation_name, relation_list in model.relations.items():
        for relation in relation_list:
            relation_meta = meta.relations.get(relation_name) if meta and getattr(meta, "relations", None) else None
            interface_name = getattr(relation_meta, "interface_name", None) if relation_meta else None
            remote_app = relation.app.name if relation.app else None
            local_app_data = dict(relation.data[app])
            remote_app_data = dict(relation.data[relation.app]) if relation.app else {}
            remote_units = [
                {"unit": remote_unit.name, "data": dict(relation.data[remote_unit])} for remote_unit in relation.units
            ]
            relations_payload.append(
                {
                    "name": relation_name,
                    "id": relation.id,
                    "interface": interface_name,
                    "remote_app": remote_app,
                    "endpoints": {
                        "local": f"{app.name}:{relation_name}",
                        "remote": remote_app,
                    },
                    "local_unit_data": dict(relation.data[unit]),
                    "remote_units": remote_units,
                    "app_data": {
                        "local": local_app_data,
                        "remote": remote_app_data,
                    },
                }
            )
    return relations_payload


def build_payload(
    model: Any,
    app: Any,
    unit: Any,
    meta: Any,
    timestamp: datetime,
    extra_sections: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble the payload containing juju topology, relations, juju application config and optional extra_sections"""
    normalized_extra_sections = dict(extra_sections) if extra_sections else {}
    if "blockchain" in normalized_extra_sections:
        normalized_extra_sections["blockchain"] = normalize_blockchain_metadata(normalized_extra_sections["blockchain"])

    relations = _relation_details(model, app, unit, meta)
    
    # Assemble the JujuTopology
    topology = JujuTopology.from_juju(model=model, app=app, unit=unit, meta=meta).to_dict()

    config_copy = dict(model.config)
    # Redact secret_access_key from collector-s3-credentials if present to avoid leaking secrets.
    if "collector-s3-credentials" in config_copy:
        try:
            cfg = json.loads(config_copy["collector-s3-credentials"])
            if isinstance(cfg, dict) and "secret_access_key" in cfg:
                cfg["secret_access_key"] = "REDACTED"
                config_copy["collector-s3-credentials"] = json.dumps(cfg)
        except (TypeError, json.JSONDecodeError):
            pass

    payload: dict[str, Any] = {
        "juju_topology": topology,
        "juju_application_config": config_copy,
        "juju_unit_relations": relations,
        "timestamp_utc": timestamp.isoformat(),
    }
    if normalized_extra_sections:
        payload.update(normalized_extra_sections)

    logger.info("Generated payload with %d relations", len(relations))
    return payload


def write_payload(payload: dict[str, Any], unit_name: str, timestamp: datetime, base_dir: pathlib.Path) -> pathlib.Path:
    """Write the payload to a JSON file and return its path."""
    base_dir.mkdir(parents=True, exist_ok=True)
    safe_unit = unit_name.replace("/", "-")
    filename = f"{safe_unit}.json"
    path = base_dir / filename
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote payload to %s", path)
    return path


def upload_payload_file(
    credentials: Credentials,
    payload_path: pathlib.Path,
    model_name: str,
    model_uuid: str,
    unit_name: str,
    timestamp: datetime,
) -> None:
    """Upload the payload JSON to S3 or an S3-compatible backend."""
    if not payload_path.exists():
        raise UploadError(f"payload path does not exist: {payload_path}")

    session = boto3.session.Session(
        aws_access_key_id=credentials.access_key_id,
        aws_secret_access_key=credentials.secret_access_key,
        aws_session_token=credentials.session_token,
        region_name=credentials.region,
    )
    client = session.client("s3", endpoint_url=credentials.endpoint_url)

    key = credentials.object_key(model_name=model_name, model_uuid=model_uuid, unit_name=unit_name)
    try:
        client.put_object(
            Bucket=credentials.bucket,
            Key=key,
            Body=payload_path.read_bytes(),
            ContentType="application/json",
        )
    except (ClientError, EndpointConnectionError, BotoCoreError, ParamValidationError) as exc:
        raise UploadError(str(exc)) from exc

    logger.info("Uploaded %s to s3://%s/%s", payload_path, credentials.bucket, key)


def collect_and_upload(
    *,
    credentials: Credentials | None,
    model: Any,
    app: Any,
    unit: Any,
    meta: Any,
    base_dir: pathlib.Path = pathlib.Path("/tmp/metadata-uploader"),
    timestamp: datetime | None = None,
    extra_sections: dict[str, Any] | None = None,
    no_upload: bool = False,
) -> pathlib.Path:
    """High-level helper: parse config, build payload, write, and upload."""

    ts = timestamp or datetime.now(timezone.utc)
    payload = build_payload(
        model=model,
        app=app,
        unit=unit,
        meta=meta,
        timestamp=ts,
        extra_sections=extra_sections,
    )
    payload_path = write_payload(payload=payload, unit_name=unit.name, timestamp=ts, base_dir=base_dir)
    if not no_upload and credentials:
        upload_payload_file(
            credentials=credentials,
            payload_path=payload_path,
            model_name=model.name,
            model_uuid=model.uuid,
            unit_name=unit.name,
            timestamp=ts,
        )
    return payload_path
