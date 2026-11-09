import socket
import threading
import time
import unittest
from videojet_readonly import CRFramer,ProtocolError,is_reply,parse_status,query_once

class ReadOnlyTests(unittest.TestCase):
    def test_split_tcp_frames_and_crlf(self):
        f=CRFramer()
        self.assertEqual(f.feed(b'\r\nSTS|3|0|Jo'),[])
        self.assertEqual(f.feed(b'b|1|10|\r\nPRS\r'),[b'STS|3|0|Job|1|10|',b'PRS'])
    def test_limit_on_partial_and_complete_frames(self):
        with self.assertRaises(ProtocolError):CRFramer(4).feed(b'12345')
        with self.assertRaises(ProtocolError):CRFramer(4).feed(b'12345\r')
    def test_async_state_is_not_gst(self):
        self.assertFalse(is_reply('GST',b'STS|3|'))
        self.assertTrue(is_reply('GST',b'STS|3|0|TEST|22|100|'))
    def test_status_and_malformed_numeric(self):
        self.assertEqual(parse_status(b'STS|4|2|My Job|12|99|')['total_count'],99)
        with self.assertRaises(ProtocolError):parse_status(b'STS|x|0|TEST|12|99|')
    def test_stop_print_and_wrong_port_blocked(self):
        for cmd in ['PRN','SST|3|','CAF','JDA|x=y|','DEL|1|x|']:
            with self.assertRaises(ValueError):query_once('127.0.0.1',43211,cmd)
        with self.assertRaises(ValueError):query_once('127.0.0.1',3001,'GST')
    def run_server(self,chunks):
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        port=listener.getsockname()[1];received=[];errors=[]
        def serve():
            try:
                conn,_=listener.accept()
                with conn:
                    conn.settimeout(2);data=b''
                    while not data.endswith(b'GST\r'):data+=conn.recv(256)
                    received.append(data)
                    for chunk in chunks:
                        conn.sendall(chunk)
                        time.sleep(.005)
            except Exception as ex:errors.append(ex)
            finally:listener.close()
        thread=threading.Thread(target=serve,daemon=True);thread.start()
        return port,thread,received,errors
    def test_real_socket_fragmentation_and_async(self):
        p,t,rx,errors=self.run_server([b'STS|4|\rPRS\rSTS|3|0|Te',b'st|2|12|\r\n'])
        r=query_once('127.0.0.1',p,'GST');t.join(2)
        self.assertEqual(rx,[b'\rGST\r']);self.assertFalse(errors)
        self.assertEqual(r.as_dict()['status']['total_count'],12)
        self.assertEqual(r.other_frames,[b'STS|4|',b'PRS'])
    def test_error_reply_preserved(self):
        p,t,rx,errors=self.run_server([b'ERR\r']);r=query_once('127.0.0.1',p,'GST');t.join(2)
        self.assertEqual(r.raw,b'ERR');self.assertFalse(errors)
    def test_connection_closed_mid_frame(self):
        p,t,rx,errors=self.run_server([b'STS|3|0|x|'])
        with self.assertRaises(ProtocolError):query_once('127.0.0.1',p,'GST')
        t.join(2);self.assertFalse(errors)
if __name__=='__main__':unittest.main(verbosity=2)
