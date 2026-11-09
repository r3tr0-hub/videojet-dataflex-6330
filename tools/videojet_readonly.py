"""Read-only diagnostic client for the saved Zipher ASCII Comms v17 grammar.

Only the listed queries may be sent. Requires an enabled TEXT port.
The supplied backup has text port 0 (disabled); TCP 3001 is BINARY.
Tested against a local simulator only, not a physical Videojet printer.
No automatic retries, polling, setting changes or print commands.
"""
import argparse
from dataclasses import dataclass
import json
import socket
import time

QUERIES = {
    'VER': 'VER', 'GST': 'STS', 'GJN': 'JOB', 'GJL': 'JBL',
    'GFT': 'FLT', 'GWN': 'WRN', 'GCL': 'GCL', 'GCS': 'GCS',
    'GHR': 'DHR', 'GVR': 'DVR', 'GPC': 'PCS', 'GTD': 'TAD',
    'QSZ': 'QSZ', 'QLN': 'QLN', 'GPD': 'DEN', 'GLS': 'LSC',
}

class ProtocolError(RuntimeError):
    pass

class CRFramer:
    def __init__(self, limit=1024*1024):
        self.buffer=bytearray()
        self.limit=limit

    def feed(self,data):
        # CRLF and a lone LF are ignored by the documented text parser.
        # A caller must pass data from a TEXT connection only.
        self.buffer.extend(data.replace(b'\n',b''))
        frames=[]
        while True:
            at=self.buffer.find(b'\r')
            if at<0:break
            if at>self.limit:raise ProtocolError('Response exceeds size limit')
            line=bytes(self.buffer[:at]);del self.buffer[:at+1]
            if line:frames.append(line)
        if len(self.buffer)>self.limit:raise ProtocolError('Unterminated response exceeds size limit')
        return frames

def fields(line):
    parts=line.split(b'|')
    if parts and parts[-1]==b'':parts.pop()
    return parts

def is_reply(query,line):
    if line in (b'ERR',b'NACK'):return True
    p=fields(line)
    if not p or p[0]!=QUERIES[query].encode('ascii'):return False
    # A short STS|state| notification is not a complete GST response.
    if query=='GST':return len(p)==6
    return True

def parse_status(line,encoding='ascii'):
    p=fields(line)
    if len(p)!=6 or p[0]!=b'STS':raise ProtocolError('Expected STS with five fields')
    try:
        return {'overall_state':int(p[1]),'error_state':int(p[2]),
                'selected_job':p[3].decode(encoding,errors='backslashreplace'),
                'batch_count':int(p[4]),'total_count':int(p[5])}
    except ValueError as ex:raise ProtocolError('Invalid numeric GST response') from ex

@dataclass
class Reply:
    query:str
    raw:bytes
    other_frames:list
    def as_dict(self,encoding='ascii'):
        result={'query':self.query,'reply':self.raw.decode(encoding,errors='backslashreplace'),
                'reply_hex':self.raw.hex(),'other_frames':[x.decode(encoding,errors='backslashreplace') for x in self.other_frames],
                'hardware_validated':False}
        if self.query=='GST' and self.raw not in (b'ERR',b'NACK'):
            result['status']=parse_status(self.raw,encoding)
        return result

def query_once(host,port,query='GST',timeout=4.0):
    if query not in QUERIES:raise ValueError('Query is not in the read-only allowlist')
    if not 1<=port<=65535:raise ValueError('Invalid port')
    if port==3001:raise ValueError('Port 3001 is binary in this backup; choose the verified TEXT port')
    if timeout<=0:raise ValueError('Timeout must be positive')
    deadline=time.monotonic()+timeout
    f=CRFramer();other=[]
    with socket.create_connection((host,port),timeout=timeout) as s:
        # The first CR resets a possibly incomplete text command parser.
        s.sendall(b'\r'+query.encode('ascii')+b'\r')
        while True:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('No matching complete response before deadline')
            s.settimeout(remaining)
            data=s.recv(65536)
            if not data:raise ProtocolError('Connection closed before the expected reply')
            frames=f.feed(data)
            match=None
            for line in frames:
                if match is None and is_reply(query,line):match=line
                else:other.append(line)
            if len(other)>1000:raise ProtocolError('Too many unrelated frames')
            if match is not None:return Reply(query,match,other)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True)
    p.add_argument('--port',required=True,type=int,help='Verified enabled TEXT port, not binary 3001')
    p.add_argument('--query',choices=sorted(QUERIES),default='GST')
    p.add_argument('--timeout',type=float,default=4.0)
    p.add_argument('--encoding',default='ascii',help='Response decoding only; ASCII requests are unchanged')
    a=p.parse_args()
    try:r=query_once(a.host,a.port,a.query,a.timeout)
    except (OSError,ValueError,ProtocolError) as ex:p.exit(2,str(ex)+'\n')
    print(json.dumps(r.as_dict(a.encoding),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
