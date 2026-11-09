"""Read CLARiTY ZLFB log blocks from firmware 409720.r12.SP5.

Header and record integrity words are verified using the recovered native CRC.
No file is modified. Dates are device clock values without a known timezone.
"""
import argparse
import collections
import datetime
import json
from pathlib import Path
import struct
from zlb_integrity import verify_block

def decode(path):
    b=Path(path).read_bytes()
    verify_block(b)
    if len(b)<24 or b[:4]!=b'ZLFB':raise ValueError('Not a ZLFB block')
    block,size,version,count,integrity=struct.unpack_from('<5I',b,4)
    if size!=len(b):raise ValueError('Block length mismatch')
    events=[];o=24
    while o<len(b):
        if o+24>len(b):raise ValueError('Truncated event header')
        category,eventid,n,nargs,days,reserved=struct.unpack_from('<4HdI',b,o)
        if n<24 or o+n>len(b):raise ValueError('Bad event length')
        args=[];a=o+20
        for _ in range(nargs):
            if a+8>o+n-4:raise ValueError('Truncated argument header')
            aid,alen,kind=struct.unpack_from('<HHI',b,a)
            if alen<8 or a+alen>o+n-4:raise ValueError('Bad argument length')
            payload=b[a+8:a+alen]
            if kind==1:
                if len(payload)<2:raise ValueError('Truncated string length')
                nchars=struct.unpack_from('<H',payload)[0]
                if 2+2*nchars>len(payload):raise ValueError('Truncated string')
                value=payload[2:2+2*nchars].decode('utf-16-le')
            elif kind==2 and len(payload)>=4:value=struct.unpack_from('<i',payload)[0]
            else:value={'raw_hex':payload.hex()}
            args.append({'id':aid,'kind':kind,'value':value});a+=alen
        if a!=o+n-4:raise ValueError('Argument lengths do not cover record payload')
        timestamp=(datetime.datetime(1899,12,30)+datetime.timedelta(days=days)).isoformat(timespec='seconds')
        events.append({'file':Path(path).name,'offset':o,'size':n,'category':category,'category_name':{0:'MACHINE',1:'JOB',2:'USER'}.get(category,'UNKNOWN'),'event_id':eventid,'timestamp_device':timestamp,'timestamp_ole':days,'reserved':reserved,'arguments':args,'integrity_word':hex(struct.unpack_from('<I',b,o+n-4)[0])})
        o+=n
    if len(events)!=count:raise ValueError('Event count mismatch')
    return {'file':Path(path).name,'block_id':block,'flags':version, 'version_legacy_alias':version,'size':size,'declared_events':count,'integrity_word':hex(integrity),'integrity_verified':True,'events':events}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('path',type=Path);p.add_argument('--output',type=Path);a=p.parse_args()
    files=sorted(a.path.glob('*.zlb')) if a.path.is_dir() else [a.path]
    blocks=[decode(f) for f in files]
    text=json.dumps(blocks,ensure_ascii=False,indent=2)
    if a.output:a.output.write_text(text,encoding='utf-8')
    else:print(text)
if __name__=='__main__':main()
