"""Offline lookup of existing backup rows; no network or new code generation.

This compatibility model is deliberately limited to this backup's ASCII file.
The native ARM reader omits the last physical record even when it has CR/LF.
"""
from pathlib import Path
import hashlib
import re

class ExistingDataFile:
    def __init__(self, path):
        self.path = Path(path)
        self.raw = self.path.read_bytes()
        self.sha256 = hashlib.sha256(self.raw).hexdigest()
        self.rows = self.raw.split(b'\r\n')
        if self.rows and self.rows[-1] == b'':
            self.rows.pop()
        if not self.rows or any(len(r) != 24 or not r.startswith(b'$Sf;') or len(r.split(b';')) != 5 for r in self.rows):
            raise ValueError('File does not match the supplied fixed ASCII corpus; use the native reader harness for other formats')
        for row in self.rows:
            row.decode('ascii')

    @property
    def firmware_readable_count(self):
        return max(0, len(self.rows) - 1)

    def lookup(self, decimal_counter, *, firmware_compatible=True):
        """Return an existing row verbatim; reject malformed or exhausted counters."""
        if not isinstance(decimal_counter, str) or re.fullmatch(r'[0-9]{1,9}', decimal_counter) is None:
            raise ValueError('Expected 1 to 9 decimal digits')
        index = int(decimal_counter)
        limit = self.firmware_readable_count if firmware_compatible else len(self.rows)
        if index >= limit:
            raise IndexError('End of available existing data')
        return self.rows[index].decode('ascii')

    def metadata(self):
        return {'sha256': self.sha256, 'physical_records': len(self.rows),
                'native_compatible_records': self.firmware_readable_count,
                'native_first_index': 0, 'native_last_index': self.firmware_readable_count - 1,
                'record_length': 24, 'counter_is_zero_based': True,
                'transformation': 'verbatim_existing_row_lookup'}

if __name__ == '__main__':
    import argparse, json
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    print(json.dumps(ExistingDataFile(args.file).metadata(), indent=2))
