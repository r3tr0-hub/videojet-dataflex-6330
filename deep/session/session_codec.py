"""Strict offline IRP (0x5002) and negotiation helpers for inspected ZBC2.
No connection, scheduling, printer command or automatic code-page choice.
"""
from dataclasses import dataclass
import struct
MAX_VERSION=11
FEATURE_MASK=0x000FFEDF
@dataclass(frozen=True)
class Record:
    tag:int
    payload:bytes

def field(raw,unicode=False):
    raw=raw.encode('utf-16-le') if unicode else bytes(raw)
    contains_nul=any(raw[i:i+2]==b'\0\0' for i in range(0,len(raw),2)) if unicode else b'\0' in raw
    if contains_nul:
        raise ValueError('Embedded NUL')
    value=raw+bytes(2-(len(raw)&1)) if raw else b''
    return struct.pack('<I' if unicode else '<H',len(value))+value

def read_field(data,offset=0,unicode=False):
    width=4 if unicode else 2
    if offset+width>len(data):raise ValueError('Truncated string length')
    count=int.from_bytes(data[offset:offset+width],'little');offset+=width
    if count&1 or offset+count>len(data):raise ValueError('Invalid string boundary')
    raw=data[offset:offset+count]
    if count:
        if unicode:
            if count<2 or raw[-2:]!=b'\0\0':raise ValueError('Missing UTF16 terminator')
            raw=raw[:-2]
            if any(raw[i:i+2]==b'\0\0' for i in range(0,len(raw),2)):raise ValueError('Embedded UTF16 NUL')
        else:
            if raw[-1:]!=b'\0':raise ValueError('Missing legacy terminator')
            raw=raw.split(b'\0',1)[0]
            if field(raw)[2:]!=data[offset:offset+count]:raise ValueError('Invalid legacy padding')
    return raw.decode('utf-16-le') if unicode else raw,offset+count

def encode_irp(records):
    records=list(records)
    if len(records)>65535:raise ValueError('Too many records')
    body=struct.pack('<H',len(records))
    for rec in records:
        if not 0<=rec.tag<=65535 or len(rec.payload)>65531:raise ValueError('Record out of range')
        body+=struct.pack('<HH',rec.tag,len(rec.payload)+4)+bytes(rec.payload)
    return struct.pack('<HI',0x5002,len(body)+6)+body

def decode_irp(data,max_size=1<<20):
    if len(data)<8 or len(data)>max_size:raise ValueError('IRP size')
    typ,size,count=struct.unpack_from('<HIH',data)
    if typ!=0x5002 or size!=len(data):raise ValueError('IRP header/length')
    records=[];offset=8
    for _ in range(count):
        if offset+4>len(data):raise ValueError('Truncated record')
        tag,size=struct.unpack_from('<HH',data,offset)
        if size<4 or offset+size>len(data):raise ValueError('Record boundary')
        records.append(Record(tag,bytes(data[offset+4:offset+size])));offset+=size
    if offset!=len(data):raise ValueError('Trailing or uncounted data')
    return records

def make_record(tag,*values):
    if tag==1:a,b,c,text=values;payload=struct.pack('<IIH',a,b,c)+field(text)
    elif tag==2:payload=struct.pack('<II8H',*values)
    elif tag in (3,8):text,a,b,*timestamp=values;payload=field(text,tag==8)+struct.pack('<II6H',a,b,*timestamp)
    elif tag==4:payload=field(values[0])+field(values[1])
    elif tag==5:payload=struct.pack('<I',*values)
    elif tag==6:payload=struct.pack('<6H',*values)
    elif tag==7:payload=struct.pack('<HI',*values)
    elif tag==9:payload=struct.pack('<QQ',*values)
    elif tag==10:
        supported,enabled,prints,failures,*timestamp=values
        payload=struct.pack('<BBII6H',bool(supported),bool(enabled),prints,failures,*timestamp)
    else:raise ValueError('Unsupported typed record, use Record for unknown tag')
    return Record(tag,payload)

def interpret_record(rec):
    d=rec.payload;t=rec.tag
    try:
        if t==1:
            a,b,c=struct.unpack_from('<IIH',d);text,end=read_field(d,10)
            if end!=len(d):raise ValueError('Extra STS bytes')
            return dict(tag=t,status_flags=a,raw_object_field_54=b,error_state=c,status_text_bytes=text)
        if t==7:
            a,b=struct.unpack('<HI',d);return dict(tag=t,version=a,features=b)
        if t==2:
            names=('batch_count','total_count','throughput','nominal_speed','short_term_speed','short_term_efficiency','long_term_speed','long_term_efficiency','trend_speed','trend_efficiency')
            return dict(tag=t,**dict(zip(names,struct.unpack('<II8H',d))))
        if t==9:
            total_bytes,free_available_bytes=struct.unpack('<QQ',d);return dict(tag=t,total_bytes=total_bytes,free_available_bytes=free_available_bytes)
        if t==10:
            supported,enabled,prints,failures,*ts=struct.unpack('<BBII6H',d)
            return dict(tag=t,supported=bool(supported),enabled=bool(enabled),batch_prints=prints,batch_failures=failures,last_failure_hmsdmy=ts)
        if t in (3,8):
            text,end=read_field(d,unicode=t==8);a,b,*ts=struct.unpack('<II6H',d[end:])
            return dict(tag=t,job=text,reserved_a=a,reserved_b=b,timestamp_hmsdmy=ts)
        if t==4:
            a,end=read_field(d);b,end=read_field(d,end)
            if end!=len(d):raise ValueError('Extra tag4 bytes')
            return dict(tag=t,first_bytes=a,second_bytes=b)
        if t==5:return dict(tag=t,value=struct.unpack('<I',d)[0])
        if t==6:return dict(tag=t,timestamp_ymdhms=struct.unpack('<6H',d))
        return dict(tag=t,raw_payload=d)
    except (struct.error,UnicodeError) as exc:raise ValueError('Malformed typed IRP record') from exc

def negotiate(peer_version,peer_features,compatibility=False,cmv_present=True):
    """Mirrors only version/feature arithmetic in worker 0x446A4F00–4FB4.
    compatibility is opaque device+0x520F4 flag, never inferred from transport.
    """
    if not cmv_present:return 2,0
    if not 0<=peer_version<=65535 or not 0<=peer_features<=0xffffffff:raise ValueError('Peer fields out of range')
    version=min(peer_version,MAX_VERSION);features=peer_features&FEATURE_MASK
    if compatibility and version==4:version=3;features&=0x1f
    return version,features

def sts_flags(overall,error,imaging_progress):
    """Pure reconstruction of producer 0x446C1BBC–1C48."""
    flags=1 if 0<=overall<=2 else 2 if overall==3 else 0
    reason=0
    if error==1:flags|=8;reason=1
    elif error==2:flags|=4;reason=2
    if imaging_progress in (1,4,6,10):flags|=0x10
    return flags,reason
