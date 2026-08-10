"""
OSC Controller
Dispatches raw UDP/OSC bundles over localhost:9000 / localhost:57120.
"""
import socket
import struct
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger("osc_controller")

OSC_PORT_9000 = 9000
OSC_PORT_57120 = 57120
OSC_BUNDLE_PREFIX = b"#bundle\x00"
OSC_MESSAGE_PREFIX = b"/"


def _encode_osc_address(address: str) -> bytes:
    if not address.startswith("/"):
        address = "/" + address
    padded = address.encode("utf-8") + b"\x00"
    padded = padded + b"\x00" * ((4 - len(padded) % 4) % 4)
    return padded


def _encode_osc_type_tag(types: str) -> bytes:
    tag = "," + types
    padded = tag.encode("utf-8") + b"\x00"
    padded = padded + b"\x00" * ((4 - len(padded) % 4) % 4)
    return padded


def _encode_osc_argument(value: Any) -> bytes:
    if isinstance(value, int):
        return struct.pack(">i", value)
    if isinstance(value, float):
        return struct.pack(">f", value)
    if isinstance(value, str):
        encoded = value.encode("utf-8") + b"\x00"
        padded = encoded + b"\x00" * ((4 - len(encoded) % 4) % 4)
        return padded
    if isinstance(value, bytes):
        padded = value + b"\x00" * ((4 - len(value) % 4) % 4)
        return padded
    return b""


def build_osc_message(address: str, args: List[Any] = None) -> bytes:
    """Build a single OSC message packet."""
    msg = _encode_osc_address(address)
    args = args or []
    type_tag = ""
    for arg in args:
        if isinstance(arg, int):
            type_tag += "i"
        elif isinstance(arg, float):
            type_tag += "f"
        elif isinstance(arg, str):
            type_tag += "s"
        else:
            type_tag += "s"
    msg += _encode_osc_type_tag(type_tag)
    for arg in args:
        msg += _encode_osc_argument(arg)
    return msg


def build_osc_bundle(messages: List[bytes], timetag: float = 0.0) -> bytes:
    """Build an OSC bundle containing multiple messages."""
    bundle = OSC_BUNDLE_PREFIX
    timetag_bytes = struct.pack(">dd", 0, timetag)
    bundle += timetag_bytes
    for msg in messages:
        size = struct.pack(">I", len(msg))
        bundle += size + msg
    return bundle


def send_osc(address: str, args: List[Any] = None, port: int = OSC_PORT_9000, host: str = "localhost") -> bool:
    """Send a single OSC message to the given host:port."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        msg = build_osc_message(address, args)
        sock.sendto(msg, (host, port))
        sock.close()
        logger.info(f"OSC message sent to {host}:{port} {address} {args}")
        return True
    except Exception as e:
        logger.error(f"OSC send failed: {e}")
        return False


def send_osc_bundle(messages: List[Dict[str, Any]], port: int = OSC_PORT_9000, host: str = "localhost") -> bool:
    """Send an OSC bundle containing multiple messages."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        osc_msgs = []
        for msg_def in messages:
            address = msg_def.get("address", "/")
            args = msg_def.get("args", [])
            osc_msgs.append(build_osc_message(address, args))
        bundle = build_osc_bundle(osc_msgs)
        sock.sendto(bundle, (host, port))
        sock.close()
        logger.info(f"OSC bundle sent to {host}:{port} ({len(osc_msgs)} messages)")
        return True
    except Exception as e:
        logger.error(f"OSC bundle send failed: {e}")
        return False


def dispatch_osc_sync(
    address: str,
    args: List[Any] = None,
    port_9000: bool = True,
    port_57120: bool = True,
) -> Dict[str, bool]:
    """Dispatch OSC message to both standard ports simultaneously."""
    results = {}
    if port_9000:
        results["9000"] = send_osc(address, args, port=OSC_PORT_9000)
    if port_57120:
        results["57120"] = send_osc(address, args, port=OSC_PORT_57120)
    return results