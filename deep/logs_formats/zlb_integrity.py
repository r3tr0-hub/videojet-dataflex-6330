"""Native CLARiTYLogging halfword CRC, build409720.r12.SP5. Offline only."""
import argparse
import json
from pathlib import Path
import struct


def _entry(word):
    crc, bits = 0, word << 16
    for _ in range(16):
        crc = ((crc << 1) ^ (0x10000021 if (crc ^ bits) & 0x80000000 else 0)) & 0xffffffff
        bits = (bits << 1) & 0xffffffff
    return crc


def integrity32(data):
    """Original algorithm ignores an unmatched final byte, like native len>>1.

    A log header/record supplies an even number of bytes. This is neither
    CRC32/IEEE nor the CRC16 used by ZBC2 transport.
    """
    crc = 0
    for offset in range(0, len(data) - 1, 2):
        word = int.from_bytes(data[offset:offset+2], 'little')
        crc = ((crc << 16) ^ _entry(crc >> 16) ^ word) & 0xffffffff
    return crc


def verify_block(data):
    if len(data) < 24 or data[:4] != b'ZLFB':
        raise ValueError('Not a ZLFB block')
    block, size, flags, count, checksum = struct.unpack_from('<5I', data, 4)
    if size != len(data):
        raise ValueError('Block length mismatch')
    if integrity32(data[:20]) != checksum:
        raise ValueError('Block header integrity mismatch')
    offset, events = 24, []
    while offset < len(data):
        if offset + 24 > len(data):
            raise ValueError('Truncated event')
        size = struct.unpack_from('<H', data, offset+4)[0]
        if size < 24 or size & 1 or offset+size > len(data):
            raise ValueError('Invalid event size')
        expected = struct.unpack_from('<I', data, offset+size-4)[0]
        if integrity32(data[offset:offset+size-4]) != expected:
            raise ValueError('Event integrity mismatch at '+str(offset))
        events.append({'offset':offset, 'size':size, 'integrity':expected})
        offset += size
    if len(events) != count:
        raise ValueError('Event count mismatch')
    return {'block_id':block, 'flags':flags, 'events_verified':len(events),
            'header_integrity_verified':True, 'events':events}


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('path',type=Path)
    a=p.parse_args()
    paths=sorted(a.path.glob('*.zlb')) if a.path.is_dir() else [a.path]
    rows=[dict(file=f.name, **verify_block(f.read_bytes())) for f in paths]
    print(json.dumps(rows,indent=2))
