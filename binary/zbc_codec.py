"""Offline DataFlex 6330 / ZBC2.dll codec recovered from 409720.r12.SP5.

No socket, serial, printer access, command execution, or parameter writes.
Evidence and limits are in BINARY_FRAMING_RU.md. Inner messages and outer
transport blocks are distinct. This is an analysis codec, not a live driver.
"""
from __future__ import annotations
from dataclasses import dataclass
import struct

FIRST=0x01
LAST=0x02
ACK=0x04
NAK=0x08
CHECKSUM=0x10
ROUTE=0x20
LANE=0x40  # Native routes two traffic lanes; higher-level meaning is session-specific.
RESERVED=0x80

class CodecError(ValueError): pass

class StreamError(CodecError):
    """Fail-stop parse error; frames contains complete frames preceding the error."""
    def __init__(self,message: str,frames=()):
        super().__init__(message);self.frames=tuple(frames)

@dataclass(frozen=True)
class Message:
    message_type: int
    body: bytes

@dataclass(frozen=True)
class Frame:
    flags: int
    message_sequence: int
    block_sequence: int
    payload: bytes = b''
    route: int | None = None
    header_checksum: int = 0
    payload_checksum: int | None = None
    @property
    def header_size(self) -> int: return 14 if self.flags & ROUTE else 10
    @property
    def is_ack(self) -> bool: return bool(self.flags & ACK)
    @property
    def is_nak(self) -> bool: return bool(self.flags & NAK)

def _uint(value: int,bits: int,name: str) -> int:
    if not isinstance(value,int) or not 0 <= value < (1 << bits):
        raise CodecError(f'{name} must be uint{bits}')
    return value

def crc16(data: bytes) -> int:
    """Native ZBC augmented CRC, poly 0x1021/init0, no reflection/xorout.

    Update is (old<<8) ^ table[old>>8] ^ input_byte. It differs from
    the common XMODEM byte update. Check('123456789') == 0xBEEF.
    """
    crc=0
    for value in data:
        high=crc >> 8
        entry=high << 8
        for _ in range(8):
            entry=((entry << 1) ^ (0x1021 if entry & 0x8000 else 0)) & 0xffff
        crc=((crc << 8) ^ entry ^ value) & 0xffff
    return crc

def encode_message(message_type: int,body: bytes=b'') -> bytes:
    _uint(message_type,16,'message_type')
    if len(body)>0xffffffff-6: raise CodecError('inner message too long')
    return struct.pack('<HI',message_type,len(body)+6)+bytes(body)

def decode_message(data: bytes) -> Message:
    if len(data)<6: raise CodecError('truncated inner header')
    kind,total=struct.unpack_from('<HI',data)
    if total!=len(data) or total<6: raise CodecError('inner length mismatch')
    return Message(kind,bytes(data[6:]))

def encode_command(command_id: int) -> bytes:
    """CMD 0x500A. Produces bytes only, never transmits them."""
    return encode_message(0x500a,struct.pack('<H',_uint(command_id,16,'command_id')))

def encode_text_field(text: str | bytes,*,unicode_mode: bool=True,
                      length_width: int | None=None,codepage: str | None=None) -> bytes:
    """Native counted string including zero terminator and even-byte padding.

    Empty string has length zero and no terminator. For legacy single-byte
    mode supply exact bytes, or explicitly name the device's Windows codepage.
    The firmware uses CP_ACP; its actual codepage cannot be inferred here.
    """
    width=length_width if length_width is not None else (4 if unicode_mode else 2)
    if width not in (2,4): raise CodecError('length_width must be 2 or 4')
    if unicode_mode:
        if not isinstance(text,str): raise CodecError('Unicode text must be str')
        if '\0' in text: raise CodecError('native wcslen terminates at embedded NUL')
        raw=text.encode('utf-16-le')
    else:
        if isinstance(text,str):
            if codepage is None: raise CodecError('legacy str requires explicit codepage')
            raw=text.encode(codepage)
        else: raw=bytes(text)
        if b'\0' in raw: raise CodecError('native string terminates at embedded NUL')
    padded=raw+(b'\0'*(2-(len(raw)&1)) if raw else b'')
    _uint(len(padded),width*8,'text byte length')
    return len(padded).to_bytes(width,'little')+padded

def decode_text_field(data: bytes,offset: int=0,*,unicode_mode: bool=True,
                      length_width: int | None=None,codepage: str | None=None
                     ) -> tuple[str | bytes,int]:
    width=length_width if length_width is not None else (4 if unicode_mode else 2)
    if width not in (2,4): raise CodecError('length_width must be 2 or 4')
    if offset<0 or len(data)<offset+width: raise CodecError('truncated string length')
    count=int.from_bytes(data[offset:offset+width],'little');end=offset+width+count
    if len(data)<end: raise CodecError('truncated string data')
    raw=bytes(data[offset+width:end])
    if count and (count&1): raise CodecError('native text byte length must be even')
    if unicode_mode:
        if raw:
            if not raw.endswith(b'\0\0'): raise CodecError('missing Unicode terminator')
            raw=raw[:-2]
        try: value=raw.decode('utf-16-le')
        except UnicodeDecodeError as exc: raise CodecError('invalid UTF16LE') from exc
    else:
        if raw:
            if not raw.endswith(b'\0'): raise CodecError('missing legacy terminator')
            raw=raw[:-1]
            if raw.endswith(b'\0'): raw=raw[:-1]
        value=raw.decode(codepage) if codepage else raw
    return value,end

def encode_frame(frame: Frame,*,protocol_version: int=11) -> bytes:
    flags=_uint(frame.flags,8,'flags')
    if flags & RESERVED: raise CodecError('native receiver rejects reserved flag 0x80')
    _uint(frame.message_sequence,16,'message_sequence');_uint(frame.block_sequence,16,'block_sequence')
    if bool(flags&ROUTE)!=(frame.route is not None): raise CodecError('route presence must match flag0x20')
    if frame.route is not None: _uint(frame.route,32,'route')
    payload=bytes(frame.payload)
    trailer=struct.pack('<H',crc16(payload)) if flags&CHECKSUM and (payload or protocol_version<=3) else b''
    size=frame.header_size+len(payload)+len(trailer)
    _uint(size,16,'outer total length')
    header=struct.pack('<BBHHH',0xa5,flags,size,frame.message_sequence,frame.block_sequence)
    if frame.route is not None: header+=struct.pack('<I',frame.route)
    header+=b'\xe4'
    checksum=(~sum(header))&0xff if flags&CHECKSUM or protocol_version<=3 else 0
    return header+bytes([checksum])+payload+trailer

def decode_frame(data: bytes,*,verify: bool=True) -> Frame:
    if len(data)<10: raise CodecError('truncated transport header')
    start,flags,total,seq,block=struct.unpack_from('<BBHHH',data)
    if start!=0xa5: raise CodecError('invalid start marker')
    if flags&RESERVED: raise CodecError('native receiver rejects flag0x80')
    header_size=14 if flags&ROUTE else 10
    if total!=len(data) or total<header_size: raise CodecError('outer length mismatch')
    if data[header_size-2]!=0xe4: raise CodecError('invalid header end marker')
    route=struct.unpack_from('<I',data,8)[0] if flags&ROUTE else None
    hsum=data[header_size-1]
    if verify and flags&CHECKSUM and sum(data[:header_size])&0xff!=0xff:
        raise CodecError('header checksum mismatch')
    raw=bytes(data[header_size:]);psum=None
    if flags&CHECKSUM:
        if len(raw)==1: raise CodecError('CRC flag with one remaining byte')
        if len(raw)>=2:
            raw,tail=raw[:-2],raw[-2:];psum=struct.unpack('<H',tail)[0]
            if verify and crc16(raw)!=psum: raise CodecError('payload checksum mismatch')
    return Frame(flags,seq,block,raw,route,hsum,psum)

class FrameStream:
    """Strict offline incremental parser; buffers at most max_frame_size bytes.

    On malformed input, clears pending bytes and enters a failed state. The
    StreamError.frames tuple preserves complete frames preceding the error.
    Create a fresh parser at a known capture boundary to resume after an error.
    """
    def __init__(self,max_frame_size: int=65535):
        if not 10<=max_frame_size<=65535: raise CodecError('invalid max_frame_size')
        self.buffer=bytearray();self.max_frame_size=max_frame_size;self.failed=False
    def feed(self,data: bytes) -> list[Frame]:
        if self.failed: raise StreamError('parser is in failed state')
        incoming=memoryview(data);position=0;frames=[]
        try:
            while position<len(incoming) or len(self.buffer)>=4:
                if len(self.buffer)<4:
                    take=min(4-len(self.buffer),len(incoming)-position)
                    self.buffer.extend(incoming[position:position+take]);position+=take
                if self.buffer and self.buffer[0]!=0xa5: raise CodecError('stream does not start with A5')
                if len(self.buffer)<4: break
                flags=self.buffer[1];total=int.from_bytes(self.buffer[2:4],'little')
                minimum=14 if flags&ROUTE else 10
                if not minimum<=total<=self.max_frame_size: raise CodecError('invalid outer frame length')
                take=min(total-len(self.buffer),len(incoming)-position)
                self.buffer.extend(incoming[position:position+take]);position+=take
                if len(self.buffer)<total: break
                frames.append(decode_frame(bytes(self.buffer)));self.buffer.clear()
            return frames
        except CodecError as exc:
            self.buffer.clear();self.failed=True
            raise StreamError(str(exc),frames) from exc
    def finish(self) -> None:
        if self.failed: raise CodecError('parser is in failed state')
        if self.buffer: raise CodecError('truncated final transport block')

class Reassembler:
    """Strict offline reassembly. ACK/NAK blocks are returned separately by FrameStream.

    Session replay/retransmission policy is deliberately left to the caller.
    Group key uses sequence, lane flag, route; duplicate blocks are rejected.
    """
    def __init__(self,max_message_size: int=16*1024*1024,*,max_pending: int=64,
                 max_buffered_bytes: int=32*1024*1024):
        if min(max_message_size,max_pending,max_buffered_bytes)<1: raise CodecError('invalid reassembly limits')
        self.pending={};self.max_message_size=max_message_size
        self.max_pending=max_pending;self.max_buffered_bytes=max_buffered_bytes
    @property
    def buffered_bytes(self) -> int:
        return sum(len(body) for _,body in self.pending.values())
    def finish(self) -> None:
        if self.pending: raise CodecError('incomplete logical message: missing LAST block')
    def add(self,frame: Frame) -> Message | None:
        if frame.flags&(ACK|NAK): return None
        key=(frame.message_sequence,bool(frame.flags&LANE),frame.route)
        if frame.flags&FIRST:
            if frame.block_sequence!=0: raise CodecError('first block sequence must be zero')
            if key in self.pending: raise CodecError('duplicate first block')
            if len(self.pending)>=self.max_pending: raise CodecError('pending message limit')
            expected,body=0,bytearray()
        else:
            if key not in self.pending: raise CodecError('block without first block')
            expected,body=self.pending[key]
        if frame.block_sequence!=expected: raise CodecError('out-of-order or duplicate block')
        if len(body)+len(frame.payload)>self.max_message_size: raise CodecError('message size limit')
        if self.buffered_bytes+len(frame.payload)>self.max_buffered_bytes: raise CodecError('aggregate reassembly memory limit')
        if frame.flags&LAST:
            result=decode_message(bytes(body)+frame.payload)
            self.pending.pop(key,None);return result
        body.extend(frame.payload)
        self.pending[key]=((expected+1)&0xffff,body)
        return None

def fragment_message(data: bytes,message_sequence: int,*,max_payload: int=1986,
                     checksums: bool=True,lane: bool=False,route: int | None=None
                    ) -> list[Frame]:
    """Offline split; 1986 reflects native fragment budget 2000 minus14.
    This heuristic is not a strict total-wire-length limit (route+CRC adds16).
    Native budget is transport-specific; a driver must use its actual limit.
    """
    decode_message(data)
    if not 1<=max_payload<=65519: raise CodecError('invalid fragment payload size')
    chunks=[data[i:i+max_payload] for i in range(0,len(data),max_payload)]
    if len(chunks)>65536: raise CodecError('too many transport blocks')
    result=[]
    for i,payload in enumerate(chunks):
        flags=(FIRST if i==0 else 0)|(LAST if i==len(chunks)-1 else 0)
        flags|=CHECKSUM if checksums else 0;flags|=LANE if lane else 0;flags|=ROUTE if route is not None else 0
        result.append(Frame(flags,message_sequence,i,payload,route))
    return result
