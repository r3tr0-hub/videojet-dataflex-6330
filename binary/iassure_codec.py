"""Offline iAssure file requests and stored-file inspection, 409720.r12.SP5.

This module only encodes/decodes bytes. It has no network or device access.
Put zbc_codec.py on PYTHONPATH (or beside this module).
Native evidence and boundaries: IASSURE_RU.md.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct
from zbc_codec import (CodecError, encode_message, decode_message,
                       encode_text_field, decode_text_field)

FT_BITMAP = 3
FT_IASSUREBMP = 18
FT_IASSUREERB = 19
FT_IASSURETXT = 20
CURRENT_IASSURE = 0x200

def _uint(value: int, bits: int, name: str) -> int:
    if not isinstance(value, int) or not 0 <= value < 1 << bits:
        raise CodecError(f'{name} must be uint{bits}')
    return value

def encode_file_request(file_type: int, name: str | bytes = '', *,
                        unicode_mode: bool = True, extra: bytes = b'',
                        codepage: str | None = None) -> bytes:
    """FRU 5032 / FRQ 5003; encoded name, then type-specific extension.

    Legacy names are bytes or require an explicit device codepage. Empty name
    is suitable for the current iAssure image, which the native handler replaces.
    """
    body = struct.pack('<H', _uint(file_type, 16, 'file_type'))
    if not unicode_mode and name == '':
        name = b''
    body += encode_text_field(name, unicode_mode=unicode_mode, codepage=codepage)
    return encode_message(0x5032 if unicode_mode else 0x5003, body + bytes(extra))

def encode_bitmap_request(name: str | bytes = '', *, flags: int = 0,
                          head: int = 1, width: int = 0, height: int = 0,
                          unicode_mode: bool = True,
                          codepage: str | None = None) -> bytes:
    """Matches native ZBC2 446DAC6C: flags32, head16, width16, height16."""
    extension = struct.pack('<IHHH', _uint(flags, 32, 'flags'),
                            _uint(head, 16, 'head'), _uint(width, 16, 'width'),
                            _uint(height, 16, 'height'))
    return encode_file_request(FT_BITMAP, name, unicode_mode=unicode_mode,
                               extra=extension, codepage=codepage)

def encode_current_iassure_request(*, unicode_mode: bool = True) -> bytes:
    """Retrieve latest existing capture. Does not trigger printing/capture.

    Uses flags=0200h only. Bit0001h selects print-preview in the native handler
    before the iAssure branch; combining it with0200h requests preview instead.
    Head/width/height are present for native serializer parity, but the iAssure
    branch does not use these fields to choose or resize its image.
    """
    return encode_bitmap_request(flags=CURRENT_IASSURE, unicode_mode=unicode_mode)

def encode_archived_iassure_request(failure_id: int, kind: str = 'bmp', *,
                                     unicode_mode: bool = True) -> bytes:
    """Retrieve a stored sibling by its native minimum-four-digit filename.

    The identifier must come from an actual archive/notification; this function
    does not discover stored IDs or promise that a file exists.
    """
    # The firmware passes an unsigned stored ID to the signed printf %04d.
    # Keep the supported practical counter range explicit, without inventing
    # how a wrapped/negative native counter should be discovered or requested.
    _uint(failure_id, 31, 'failure_id')
    kinds = {'bmp': FT_IASSUREBMP, 'erb': FT_IASSUREERB, 'txt': FT_IASSURETXT}
    if kind not in kinds:
        raise CodecError('archive kind must be bmp, erb, or txt')
    name = f'{failure_id:04d}.{kind}'
    return encode_file_request(kinds[kind], name if unicode_mode else name.encode('ascii'),
                               unicode_mode=unicode_mode)

@dataclass(frozen=True)
class FileRequest:
    file_type: int
    name: str | bytes
    flags: int | None = None
    head: int | None = None
    width: int | None = None
    height: int | None = None

def decode_file_request(data: bytes) -> FileRequest:
    message = decode_message(data)
    if message.message_type not in (0x5003, 0x5032):
        raise CodecError('expected FRQ5003 or FRU5032')
    if len(message.body) < 2:
        raise CodecError('missing file type')
    unicode_mode = message.message_type == 0x5032
    file_type = int.from_bytes(message.body[:2], 'little')
    name, end = decode_text_field(message.body, 2, unicode_mode=unicode_mode)
    raw = message.body[end:]
    if file_type != FT_BITMAP:
        if raw:
            raise CodecError('unsupported type-specific request extension')
        return FileRequest(file_type, name)
    if len(raw) not in (0, 4, 6, 8, 10):
        raise CodecError('incomplete or unrecognized bitmap extension')
    values = [None] * 4
    cursor = 0
    for i, size in enumerate((4, 2, 2, 2)):
        if len(raw) >= cursor + size:
            values[i] = int.from_bytes(raw[cursor:cursor+size], 'little')
            cursor += size
    return FileRequest(file_type, name, *values)

@dataclass(frozen=True)
class FileTransfer:
    file_type: int
    name: str | bytes
    data: bytes
    trailing_padding: bytes

def decode_file_transfer(data: bytes, *, unicode_mode: bool | None = None) -> FileTransfer:
    """FTX5004 / FTU5033. Remove this wrapper before opening the BMP bytes.

    Native old FTX can select string encoding using its object flag. For5004
    specify the session's encoding (False for the normal legacy object).
    FTU5033 always uses Unicode. FTY503A adds14bytes and is not covered here.
    """
    message = decode_message(data)
    if message.message_type not in (0x5004, 0x5033):
        raise CodecError('expected FTX5004 or FTU5033')
    if message.message_type == 0x5033:
        unicode_mode = True
    elif unicode_mode is None:
        raise CodecError('FTX5004 requires explicit session string encoding')
    if len(message.body) < 6:
        raise CodecError('missing file transfer fields')
    file_type, size = struct.unpack_from('<HI', message.body)
    name, start = decode_text_field(message.body, 6, unicode_mode=unicode_mode)
    end = start + size
    if end > len(message.body):
        raise CodecError('truncated transferred file')
    padding = message.body[end:]
    if padding not in (b'', b'\0'):
        raise CodecError('unexpected file transfer trailing bytes')
    return FileTransfer(file_type, name, message.body[start:end], padding)

def inspect_bitmap(data: bytes) -> dict:
    """Inspect BMP by its BM magic; .erb and .tru also use this format."""
    if len(data) < 54 or data[:2] != b'BM':
        raise CodecError('not a complete BMP header')
    file_size, pixel_offset = struct.unpack_from('<I4xI', data, 2)
    dib_size, width, height, planes, bits, compression, pixel_size = struct.unpack_from('<IiiHHII', data, 14)
    if dib_size < 40 or planes != 1 or not width or not height:
        raise CodecError('invalid BMP geometry/header')
    if pixel_offset < 14 + dib_size or pixel_offset > len(data):
        raise CodecError('invalid BMP pixel offset')
    if file_size != len(data):
        raise CodecError('BMP file size mismatch')
    if pixel_size > len(data) - pixel_offset:
        raise CodecError('truncated BMP pixels')
    return dict(width=width, height=height, bits_per_pixel=bits,
                compression=compression, dib_header_size=dib_size,
                pixel_offset=pixel_offset, pixel_size=pixel_size,
                native_iassure_layout=(dib_size == 40 and bits == 8 and
                                       compression == 0 and pixel_offset == 0x436))

def decode_archive_metadata(data: bytes) -> dict:
    """Version iAS2 of the misleadingly named .txt sibling.

    56-byte binary header + un-terminated UTF16LE text. Unknown header words
    remain explicit; timestamp is returned raw/as double without assigning a
    timezone or promising a hardware acquisition timestamp.
    """
    if len(data) < 56 or data[20:24] != b'iAS2':
        raise CodecError('expected 56-byte iAS2 metadata header')
    if (len(data)-56) & 1:
        raise CodecError('odd UTF16 metadata tail')
    words = struct.unpack_from('<14I', data)
    text = data[56:].decode('utf-16-le')
    return dict(failure_id=words[0], unknown_04=words[1], failure_type=words[2],
                vertical_flip=words[3], horizontal_flip=words[4],
                version='iAS2', timestamp_raw=data[24:32].hex(),
                timestamp_f64=struct.unpack_from('<d', data, 24)[0],
                vertical_align=words[8], horizontal_align=words[9],
                ribbon_start_pixel=words[10] & 255,
                ribbon_end_pixel=words[11] & 255,
                unknown_48=words[12], unknown_52=words[13], settings_text=text)
