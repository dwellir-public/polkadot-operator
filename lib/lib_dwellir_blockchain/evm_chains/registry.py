from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from typing import Any, Dict, Iterable, List, Optional, Tuple

_DATA_PATH = files("lib_dwellir_blockchain").joinpath("evm_chains/data/chains_mini.json")

@dataclass(frozen=True)
class Chain:
    """A minimal chain record."""
    chain_id: int
    name: str
    short_name: str
    network_id: int

    native_currency: Dict[str, Any] | None = None
    rpc: List[str] | None = None
    faucets: List[str] | None = None
    info_url: str | None = None

    @property
    def caip2(self) -> str:
        return f"eip155:{self.chain_id}"

def version() -> str:
    """Returns the vendored data version string (file mtime-based)."""
    import os
    try:
        stat = os.stat(str(_DATA_PATH))
        return f"vendored@{int(stat.st_mtime)}"
    except OSError:
        return "vendored@unknown"

@lru_cache(maxsize=1)
def _raw() -> List[Dict[str, Any]]:
    with _DATA_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)

@lru_cache(maxsize=1)
def _indexes() -> Tuple[Dict[int, Dict[str, Any]], Dict[str, List[int]], Dict[str, List[int]]]:
    by_id: Dict[int, Dict[str, Any]] = {}
    by_name: Dict[str, List[int]] = {}
    by_short: Dict[str, List[int]] = {}

    for c in _raw():
        cid = int(c["chainId"])
        by_id[cid] = c
        name = str(c.get("name", "")).strip()
        short = str(c.get("shortName", "")).strip()

        if name:
            by_name.setdefault(name, []).append(cid)
        if short:
            by_short.setdefault(short, []).append(cid)

    # Keep lists deterministic
    for d in (by_name, by_short):
        for k, v in d.items():
            v.sort()

    return by_id, by_name, by_short

def all_chains() -> List[Chain]:
    """Return all chains as Chain objects."""
    return [ _to_chain(c) for c in _raw() ]

def all_chain_ids() -> List[int]:
    """Return all chainIds sorted ascending."""
    by_id, _, _ = _indexes()
    return sorted(by_id.keys())

def get_chain(chain_id: int) -> Optional[Chain]:
    """Return a Chain by chainId, or None if unknown."""
    by_id, _, _ = _indexes()
    c = by_id.get(int(chain_id))
    return _to_chain(c) if c else None

def chain_name(chain_id: int, default: Optional[str] = None) -> Optional[str]:
    """Convenience: chainId -> name."""
    ch = get_chain(chain_id)
    return ch.name if ch else default

def chain_short_name(chain_id: int, default: Optional[str] = None) -> Optional[str]:
    """Convenience: chainId -> shortName."""
    ch = get_chain(chain_id)
    return ch.short_name if ch else default

def chain_ids_by_name(name: str) -> List[int]:
    """Exact name -> list of chainIds (usually a single element)."""
    _, by_name, _ = _indexes()
    return list(by_name.get(name, []))

def chain_ids_by_short_name(short_name: str) -> List[int]:
    """Exact shortName -> list of chainIds (usually a single element)."""
    _, _, by_short = _indexes()
    return list(by_short.get(short_name, []))

def caip2(chain_id: int) -> str:
    """Return CAIP-2 chain reference for an EVM chainId (eip155 namespace)."""
    return f"eip155:{int(chain_id)}"

def search(query: str, limit: int = 25) -> List[Chain]:
    """Case-insensitive substring search over name and shortName."""
    q = query.strip().lower()
    if not q:
        return []
    out: List[Chain] = []
    for c in _raw():
        name = str(c.get("name", "")).lower()
        short = str(c.get("shortName", "")).lower()
        if q in name or q in short:
            out.append(_to_chain(c))
            if len(out) >= limit:
                break
    return out

def _to_chain(c: Dict[str, Any]) -> Chain:
    return Chain(
        chain_id=int(c["chainId"]),
        name=str(c.get("name", "")),
        short_name=str(c.get("shortName", "")),
        network_id=int(c.get("networkId", c["chainId"])),
        native_currency=c.get("nativeCurrency"),
        rpc=c.get("rpc"),
        faucets=c.get("faucets"),
        info_url=c.get("infoURL"),
    )
