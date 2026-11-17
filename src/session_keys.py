"""Runtime-derived SessionKeys codecs and key-type identifiers."""

from scalecodec.base import ScaleBytes
from scalecodec.exceptions import InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException


class SessionKeyCodec:
    """Use the runtime's set_keys argument rather than a chain-name registry."""

    def __init__(self, substrate, block_hash):
        self.substrate = substrate
        self.block_hash = block_hash
        call = substrate.get_metadata_call_function("Session", "set_keys", block_hash=block_hash)
        if call is None:
            raise ValueError("Runtime does not support Session.set_keys")
        if "fields" in call.value:
            field = next((field for field in call.value["fields"] if field["name"] == "keys"), None)
            self.type_string = f"scale_info::{field['type']}" if field else None
        else:
            self.type_string = next((arg.type for arg in call.args if arg.name == "keys"), None)
        if not self.type_string:
            raise ValueError("Runtime does not describe the Session.set_keys keys argument")

    def decode(self, bundle):
        """Decode the entire bundle, rejecting truncated or trailing bytes."""
        codec = self.substrate.runtime_config.create_scale_object(self.type_string)
        try:
            codec.decode(ScaleBytes(bundle), check_remaining=True)
        except (InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException, NotImplementedError) as exc:
            raise ValueError("Session-key bundle does not match runtime metadata") from exc
        keys = codec.value_serialized
        if not isinstance(keys, dict) or not keys:
            raise ValueError("SessionKeys must be a nonempty named structure")
        return keys

    def encode(self, keys):
        """Encode named public keys in the order declared by the runtime."""
        codec = self.substrate.runtime_config.create_scale_object(self.type_string)
        return str(codec.encode(keys))

    def key_types(self, bundle):
        """Return (field, public key, key type ID) using the runtime decoder."""
        keys = self.decode(bundle)
        params = self.substrate.runtime_config.create_scale_object("Bytes").encode(bundle)
        response = self.substrate.rpc_request("state_call", ["SessionKeys_decode_session_keys", str(params), self.block_hash])
        if "error" in response:
            raise ValueError("Runtime could not decode SessionKeys")
        decoder = self.substrate.runtime_config.create_scale_object("Option<Vec<(Bytes, [u8; 4])>>")
        try:
            decoded = decoder.decode(ScaleBytes(response["result"]), check_remaining=True)
        except (InvalidScaleTypeValueException, RemainingScaleBytesNotEmptyException) as exc:
            raise ValueError("Runtime returned invalid decoded session keys") from exc
        if decoded is None or len(decoded) != len(keys):
            raise ValueError("Runtime returned an incompatible SessionKeys layout")
        result = []
        for (name, key), (public, key_type) in zip(keys.items(), decoded):
            if _hex_bytes(public) != key:
                raise ValueError("Runtime SessionKeys field order does not match metadata")
            result.append((name, key, bytes.fromhex(_hex_bytes(key_type)[2:]).decode("ascii")))
        return result


def _hex_bytes(value):
    """Normalize SCALE Bytes, including public keys that decode as UTF-8."""
    if isinstance(value, str):
        return value if value.startswith("0x") else "0x" + value.encode().hex()
    return "0x" + bytes(value).hex()
