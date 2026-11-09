"""Developer integration tests against a local synthetic printer only.

Python is used only by these developer tests, not by the Windows application.
On Linux set VJ_MONO to a mono runtime. The tests never target the plant LAN.
"""
from pathlib import Path
import json,os,socket,struct,subprocess,threading,time,unittest,xml.etree.ElementTree as E
from reference_codec import Frame,encode_frame,decode_frame,encode_message,encode_text_field,fragment_message

ROOT=Path(__file__).resolve().parents[1]
FIX=json.loads((ROOT/'tests/native_irp_fixtures.json').read_text())
COMBINED=bytes.fromhex(next(x['hex'] for x in FIX if x['tag']=='combined'))
HELLO=bytes.fromhex(next(x['hex'] for x in FIX if x['tag']==7))
HELLO=HELLO[:-4]+struct.pack('<I',0x802)

def read_exact(s,n):
    b=b''
    while len(b)<n:
        x=s.recv(n-len(b))
        if not x:raise EOFError
        b+=x
    return b

def recv_frame(s):
    h=read_exact(s,4);return decode_frame(h+read_exact(s,int.from_bytes(h[2:4],'little')-4))

class Mock:
    def __init__(self,scenario):
        self.scenario=scenario;self.requests=[];self.error=None;self.xml_sent=False;self.nak=False
        self.sock=socket.socket();self.sock.bind(('127.0.0.1',0));self.port=self.sock.getsockname()[1];self.sock.listen();self.sock.settimeout(15)
        self.thread=threading.Thread(target=self.run,daemon=True);self.thread.start()
    def ack(self,s,f,version,negative=False):
        flags=f.flags|(8 if negative else 4)
        if version<=3:flags&=~16
        s.sendall(encode_frame(Frame(flags,f.message_sequence,f.block_sequence),protocol_version=version))
    def reply(self,s,f,body,version,duplicate=False,badcrc=False):
        for i,block in enumerate(fragment_message(body,f.message_sequence,max_payload=1986)):
            raw=encode_frame(block,protocol_version=version)
            if badcrc:
                raw=raw[:-1]+bytes([raw[-1]^1]);s.sendall(raw);return
            for j in range(0,len(raw),7):s.sendall(raw[j:j+7])
            a=recv_frame(s);assert a.flags&4 and a.message_sequence==f.message_sequence
            if duplicate and i==0:
                s.sendall(raw);a=recv_frame(s);assert a.flags&4
    def run(self):
        try:
            # Worker first performs a no-payload TCP port probe.
            s,_=self.sock.accept();s.settimeout(5);assert s.recv(1)==b'';s.close()
            s,_=self.sock.accept();s.settimeout(10);s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY,1)
            with s:
                if self.scenario=='http':
                    s.recv(4096);s.sendall(b'HTTP/1.1 200 OK\r\n\r\n');return
                version=2
                while True:
                    try:f=recv_frame(s)
                    except EOFError:return
                    if f.flags&12:continue
                    assert f.payload[:2] in (b'\x01\x50',b'\x20\x50',b'\x12\x51',b'\x12\x50'),f.payload[:2]
                    typ=int.from_bytes(f.payload[:2],'little');self.requests.append(typ)
                    if self.scenario=='timeout':time.sleep(5);return
                    if not self.nak and self.scenario in ('normal','cancel'):
                        self.ack(s,f,version,True);retry=recv_frame(s);assert retry==f;self.nak=True
                    self.ack(s,f,version)
                    if typ==0x5001:
                        tags=struct.unpack_from('<H',f.payload,6)[0]
                        self.reply(s,f,HELLO if tags==2 else COMBINED,version,badcrc=self.scenario=='badcrc')
                        if self.scenario=='badcrc':return
                    elif typ==0x5020:
                        version=struct.unpack_from('<H',f.payload,6)[0]
                        self.reply(s,f,encode_message(0),version)
                    else:
                        assert typ==0x5112
                        q=f.payload[10:].decode('utf-16-le').rstrip('\0');root=E.fromstring(q)
                        assert root.tag=='Params' and all(x.tag=='Col' for x in list(root.iter())[1:])
                        assert all(x.get('getFlags') in (None,'10') for x in root.iter())
                        xml='<Params><Col id="Synthetic"><Str id="Password">SERVER_ONLY_SECRET</Str>'+''.join(f'<Num id="N{i}">{i}</Num>' for i in range(240))+'</Col></Params>'
                        self.reply(s,f,encode_message(0x5113,encode_text_field(xml,unicode_mode=True)),version,duplicate=True);self.xml_sent=True
        except Exception as e:
            if self.scenario not in ('cancel','badcrc','timeout','http'):self.error=repr(e)
        finally:self.sock.close()

class LiveProfileTests(unittest.TestCase):
    def invoke(self,scenario,observe=0):
        server=Mock(scenario);out=ROOT/'tests/runs'/scenario;out.mkdir(parents=True,exist_ok=True)
        for p in out.iterdir():p.unlink()
        cfg=E.Element('Diagnostics')
        for k,v in {'Host':'127.0.0.1','Port':server.port,'Mode':'tcp','Operation':'read','Output':str(out),'TimeoutSeconds':3,'ObserveSeconds':observe,'Raw':'False','AllowChanges':'False'}.items():E.SubElement(cfg,k).text=str(v)
        E.ElementTree(cfg).write(out/'request.xml',encoding='utf-8')
        cmd=[str(ROOT/'Videojet6330.Diagnostics.exe'),'--worker',str(out/'request.xml')]
        if os.environ.get('VJ_MONO'):cmd.insert(0,os.environ['VJ_MONO'])
        p=subprocess.Popen(cmd,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        if scenario=='cancel':
            deadline=time.time()+15
            while time.time()<deadline and not (out/'parameters_01.xml').exists():time.sleep(.03)
            self.assertTrue((out/'parameters_01.xml').exists());(out/'STOP').write_text('stop')
        stdout,stderr=p.communicate(timeout=20);server.thread.join(timeout=2)
        self.assertIsNone(server.error,server.error)
        self.assertTrue((out/'result.json').exists(),stderr.decode(errors='replace'))
        self.assertTrue((out/'report.html').exists())
        result=json.loads((out/'result.json').read_text())
        return server,out,p.returncode,result
    def test_01_complete_read_with_nak_duplicate_and_fragmented_xml(self):
        server,out,code,r=self.invoke('normal');self.assertEqual(code,0,r)
        self.assertEqual(len(json.loads((out/'parameters_01.json').read_text())),241)
        for p in out.iterdir():self.assertNotIn(b'SERVER_ONLY_SECRET',p.read_bytes(),p.name)
        self.assertIn(0x5112,server.requests)
        self.assertEqual(r['printing_confirmed'],False)
    def test_02_corrupt_crc_is_error_not_connected(self):
        _,out,code,r=self.invoke('badcrc');self.assertEqual(code,1);self.assertIn('CRC',(out/'events.jsonl').read_text())
    def test_03_open_http_port_is_not_a_printer_session(self):
        _,out,code,r=self.invoke('http');self.assertEqual(code,1);self.assertIn('A5',(out/'events.jsonl').read_text())
    def test_04_timeout_ends_worker(self):
        _,out,code,r=self.invoke('timeout');self.assertEqual(code,1);self.assertEqual(r['exit_code'],1)
    def test_05_cancel_keeps_already_received_data(self):
        _,out,code,r=self.invoke('cancel',observe=30);self.assertEqual(code,3);self.assertTrue((out/'parameters_01.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
