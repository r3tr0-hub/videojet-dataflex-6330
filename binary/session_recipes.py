"""Offline ZBC2 read request recipes. Does not connect to any device.

This is not a session implementation: peer version/feature negotiation,
ACK/NAK, retries and transaction state require a higher layer.
"""
import struct
import xml.etree.ElementTree as ET
from zbc_codec import CodecError, encode_message, encode_text_field


def _u16(value):
    if not isinstance(value, int) or not 0 <= value <= 0xffff:
        raise CodecError('Expected uint16')
    return value


def encode_information_request(tags=(1, 7)):
    """IRQ 0x5001. Native initial request uses STS=1 and CMV=7."""
    tags = tuple(_u16(x) for x in tags)
    _u16(len(tags))
    return encode_message(0x5001, struct.pack('<H', len(tags)) +
                          b''.join(struct.pack('<H', x) for x in tags))


def encode_version_offer(version, features):
    """0x5020 layout only. Values must be chosen from peer/session state."""
    _u16(version)
    if not isinstance(features, int) or not 0 <= features <= 0xffffffff:
        raise CodecError('Expected uint32 features')
    return encode_message(0x5020, struct.pack('<HI', version, features))


def encode_parameter_query(xml_text, *, unicode_mode, modern=True, codepage=None):
    """Encode a collection-only read query in 0x5112 (or legacy 0x5012).

    unicode_mode is explicitly required; the negotiated flag 0x800 decides it.
    The native modern API selects legacy only if peer version <3 and the XML
    character count <=65535. This helper does not select a session mode.
    """
    root = ET.fromstring(xml_text)
    if root.tag != 'Params' or root.attrib or (root.text or '').strip():
        raise CodecError('Expected Params collection read query')
    for node in root.iter():
        if node is root:
            continue
        if node.tag != 'Col' or set(node.attrib) - {'id', 'getFlags', 'getDepth'}:
            raise CodecError('Only collection read selectors are supported')
        if 'id' not in node.attrib or (node.text or '').strip() or (node.tail or '').strip():
            raise CodecError('Unexpected value in collection query')
    if len(root) == 0:
        raise CodecError('Empty parameter query')
    return encode_message(0x5112 if modern else 0x5012,
                          encode_text_field(xml_text, unicode_mode=unicode_mode,
                                            codepage=codepage))
