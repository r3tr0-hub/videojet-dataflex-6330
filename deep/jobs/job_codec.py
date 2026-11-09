"""OFFLINE inner-message builders/inspectors for inspected ZBC2.dll.
No socket code. Job data is bytes, NOT a count of fields. JDU literal serializer
has a declared-versus-written length anomaly; returned bytes preserve it.
"""
import struct
import xml.etree.ElementTree as ET

SEL, SLU, JDU = 0x5007, 0x5030, 0x5008
SET_UPDATE_ID, RETURN_UPDATE_ID, BINARY_DATA = 0x80000000, 0x40, 0x20

def _u32(x):
 if not isinstance(x,int) or not 0<=x<=0xffffffff:raise ValueError('expected unsigned 32-bit integer')
 return struct.pack('<I',x)

def _padded(raw):
 raw=bytes(raw)
 return raw + bytes(2-(len(raw)&1)) if raw else b''

def _counted(raw,width):
 if len(raw)>((1<<(8*width))-1):raise ValueError('counted field is too large')
 return len(raw).to_bytes(width,'little')+raw

def encode_select(name, data=b'', *, unicode=True, flags=0, limit=0, update_id=0, legacy_encoding=None):
 """Native SEL/SLU layout. Legacy requires an explicit encoding or raw name bytes."""
 data=bytes(data);_u32(flags);_u32(limit);_u32(update_id)
 if flags&BINARY_DATA and len(data)%4:raise ValueError('binary data must be a complete 4-byte serialized buffer')
 if unicode:
  if not isinstance(name,str) or '\0' in name:raise ValueError('Unicode name must be text without NUL')
  rawname=name.encode('utf-16-le');width=4;typ=SLU
 else:
  if isinstance(name,str):
   if '\0' in name:raise ValueError('embedded NUL')
   if legacy_encoding is None and name:raise ValueError('explicit legacy_encoding is required')
   rawname=name.encode(legacy_encoding or 'ascii')
  else:rawname=bytes(name)
  if b'\0' in rawname:raise ValueError('embedded NUL')
  width=2;typ=SEL
 body=_counted(_padded(rawname),width)+_u32(flags)+_u32(limit)
 if flags&SET_UPDATE_ID:body+=_u32(update_id)
 body+=_counted(_padded(data),width)
 return struct.pack('<HI',typ,len(body)+6)+body

def encode_jdu_native_literal(data=b'', *,flags=0,limit=0,update_id=0):
 """Reproduce ARM serializer 446AE1A0 including its +2 declared length anomaly.
 Not a live transaction recipe. Caller must not infer hardware acceptance.
 """
 data=bytes(data);body=_u32(flags)+_u32(limit)
 if flags&SET_UPDATE_ID:body+=_u32(update_id)
 body+=_counted(_padded(data),2)
 return struct.pack('<HI',JDU,len(body)+8)+body

def inspect_job(raw, *, legacy_encoding=None, allow_native_jdu_length_anomaly=False):
 raw=bytes(raw)
 if len(raw)<6:raise ValueError('truncated header')
 typ,declared=struct.unpack_from('<HI',raw);actual=len(raw)
 anomaly=typ==JDU and declared==actual+2
 if declared!=actual and not(anomaly and allow_native_jdu_length_anomaly):raise ValueError('declared/actual length mismatch')
 pos=6
 def take(n):
  nonlocal pos
  if n<0 or pos+n>actual:raise ValueError('truncated data')
  out=raw[pos:pos+n];pos+=n;return out
 def num(n):return int.from_bytes(take(n),'little')
 def counted(w):return take(num(w))
 out={'type':typ,'declared_length':declared,'actual_length':actual,'native_jdu_length_anomaly':anomaly}
 if typ not in (SEL,SLU,JDU):raise ValueError('unsupported job opcode')
 width=4 if typ==SLU else 2
 if typ!=JDU:
  name=counted(width)
  if typ==SLU:
   if len(name)%2:raise ValueError('odd UTF-16 field length')
   out['name']=name.decode('utf-16-le').rstrip('\0')
  else:out['name']=name.rstrip(b'\0').decode(legacy_encoding) if legacy_encoding else name.rstrip(b'\0')
 flags=num(4);out.update(flags=flags,limit=num(4),update_id=None)
 if flags&SET_UPDATE_ID:out['update_id']=num(4)
 out['data_padded']=counted(width)
 if pos!=actual:raise ValueError('trailing bytes')
 # Native 446AE598 trims trailing zero bytes for XML; for binary it rounds the
 # counted length DOWN to a multiple of 4. Preserve bytes so inspection is lossless.
 out['native_data_length']=len(out['data_padded'])&~3 if flags&BINARY_DATA else len(out['data_padded'].rstrip(b'\0'))
 return out

def image_data_xml(fields,reference_ciff=None):
 """Build the ordinary Field branch recognized at 446CC3D4 (UTF-8).
 This performs XML escaping; job-specific validity is determined downstream.
 """
 root=ET.Element('ImageData')
 if reference_ciff is not None:root.set('ReferenceCiff',str(reference_ciff))
 for name,value in fields:
  if not isinstance(name,str) or not name:raise ValueError('nonempty exact CIFF field name required')
  if '\0' in name or '\0' in str(value):raise ValueError('embedded NUL')
  ET.SubElement(root,'Field',Name=name).text=str(value)
 return ET.tostring(root,encoding='utf-8',short_empty_elements=True)

def inspect_response(raw):
 raw=bytes(raw)
 if len(raw)<6:raise ValueError('truncated response')
 typ,n=struct.unpack_from('<HI',raw)
 if n!=len(raw):raise ValueError('length mismatch')
 if typ in (0,0x500f) and n==6:return {'type':typ,'kind':'NUL' if typ==0 else 'FTC'}
 if typ==0x500d and n==8:return {'type':typ,'kind':'ERR','reason':int.from_bytes(raw[6:8],'little')}
 if typ==0x5022 and n==10:return {'type':typ,'kind':'JUC','update_id':int.from_bytes(raw[6:10],'little')}
 if typ==0x5005 and n in (6,10):return {'type':typ,'kind':'FNF','error_code':int.from_bytes(raw[6:10],'little') if n==10 else 0}
 raise ValueError('unsupported response')
