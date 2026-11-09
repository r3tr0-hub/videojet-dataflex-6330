"""Read the recovered 156-byte SQLite snapshot layout; no DB writes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
import xml.etree.ElementTree as ET


def snapshot_paths(config):
    return [n.attrib['id'] for n in ET.parse(config).getroot().find('SnapshotParams')]


def decode_snapshot(blob,paths):
    if len(blob)!=156:
        raise ValueError('Expected native snapshot sizeof=156')
    # Cache writer copies128 bytes to object+0x1c; earlier28 bytes are not CSV.
    payload=blob[28:156]
    if b'\0' not in payload:
        raise ValueError('Unterminated snapshot CSV')
    text=payload.split(b'\0',1)[0]
    parts=text.split(b',')
    if len(parts)!=len(paths) or not all(re.fullmatch(rb'-?[0-9]+',x) for x in parts):
        raise ValueError('Snapshot fields do not match configuration')
    return {'opaque_prefix_hex':blob[:28].hex(),
            'values_raw':{p:int(v) for p,v in zip(paths,parts)},
            'csv':text.decode('ascii')}


def decode_database(db,config):
    paths=snapshot_paths(config)
    connection=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True)
    rows=[]
    try:
        for row in connection.execute('SELECT id,snapshot_crnt,snapshot_1_min,snapshot_5_min FROM event_log ORDER BY id'):
            for column,blob in zip(('snapshot_crnt','snapshot_1_min','snapshot_5_min'),row[1:]):
                if blob is not None:
                    rows.append({'event_row_id':row[0],'column':column,'sha256':hashlib.sha256(blob).hexdigest(),**decode_snapshot(blob,paths)})
    finally:
        connection.close()
    return rows


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('database',type=Path)
    p.add_argument('config',type=Path)
    p.add_argument('--output',type=Path)
    a=p.parse_args()
    text=json.dumps(decode_database(a.database,a.config),ensure_ascii=False,indent=2)
    if a.output:a.output.write_text(text,encoding='utf-8')
    else:print(text)
