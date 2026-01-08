import json
from urllib import request, error as urlerror
from typing import Optional, Tuple, List
import socket

def _jsonrpc(url: str, method: str, params=None, timeout=2.5) -> Tuple[Optional[object], Optional[str]]:
    """
    Perform a JSON-RPC call and return (result, error_message).
    """
    if params is None:
        params = []
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode())
            if "error" in data:
                return None, f"rpc {method} error: {data['error']}"
            return data.get("result"), None
    except socket.timeout:
        return None, f"rpc {method} timeout after {timeout}s (url={url})"
    except urlerror.URLError as e:
        reason = getattr(e, "reason", e)
        return None, f"rpc {method} connection error (url={url}): {reason}"
    except Exception as e:
        return None, f"rpc {method} unexpected error (url={url}): {e}"


# Optimism RPCs

def optimism_rollupConfig(url: str) -> Tuple[Optional[object], Optional[str]]:
    return _jsonrpc(url, "optimism_rollupConfig")

def optimism_chainId(url: str) -> Tuple[Optional[object], Optional[str]]:
    return _jsonrpc(url, "optimism_chainId")

# Standard ETH RPCs
def eth_chainId(url: str) -> Tuple[Optional[object], Optional[str]]:
    return _jsonrpc(url, "eth_chainId")
