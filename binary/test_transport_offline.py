"""Transport checks using native vectors and synthetic stream failures."""
import unittest
from zbc_codec import *

class TransportTests(unittest.TestCase):
 def test_native_vectors(self):
  self.assertEqual(crc16(b"123456789"),0xbeef)
  vectors=[(0x13,b'123',11,'a5130f0034127856e4403132334114'),
           (0x13,b'',11,'a5130a0034127856e445'),
           (0x13,b'',3,'a5130c0034127856e4430000'),
           (0x33,b'123',11,'a533130034127856efcdab89e42c3132334114')]
  for flags,payload,version,expected in vectors:
   frame=Frame(flags,0x1234,0x5678,payload,0x89abcdef if flags&ROUTE else None)
   result=encode_frame(frame,protocol_version=version)
   self.assertEqual(result.hex(),expected)
 def test_fragmented_stream_and_reassembly(self):
  message=encode_message(0x5112,encode_text_field('<Params>'+('Ж'*300)+'</Params>'))
  frames=fragment_message(message,0x33,max_payload=37,route=0x10002)
  stream=FrameStream();reassembler=Reassembler();out=[]
  wire=b''.join(encode_frame(frame) for frame in frames)
  for i in range(0,len(wire),7):
   for frame in stream.feed(wire[i:i+7]):
    result=reassembler.add(frame)
    if result:out.append(result)
  stream.finish();reassembler.finish();self.assertEqual(out,[decode_message(message)])
 def test_corruption_and_truncation(self):
  wire=bytearray(encode_frame(Frame(0x13,1,0,encode_command(4))))
  for index in (1,4,8,10,len(wire)-1):
   damaged=wire.copy();damaged[index]^=1
   with self.assertRaises(CodecError):decode_frame(damaged)
  with self.assertRaises(CodecError):decode_frame(bytes(wire[:-1]))
  s=FrameStream();s.feed(bytes(wire[:-1]))
  with self.assertRaises(CodecError):s.finish()
 def test_size_and_order_limits(self):
  with self.assertRaises(CodecError):FrameStream().feed(b'\xa5\x03\x01\x00')
  with self.assertRaises(CodecError):decode_message(b'\x00'*6)
  with self.assertRaises(CodecError):encode_frame(Frame(0x80,1,0))
  with self.assertRaises(CodecError):Reassembler().add(Frame(2,1,1,b'abc'))
  r=Reassembler();r.add(Frame(1,1,0,b'abc'))
  with self.assertRaises(CodecError):r.add(Frame(2,1,2,b'def'))
 def test_stream_error_preserves_prior_frames(self):
  wire=encode_frame(Frame(0x13,1,0,encode_command(4)))
  parser=FrameStream()
  with self.assertRaises(StreamError) as caught:parser.feed(wire+b'X'*1000000)
  self.assertEqual(len(caught.exception.frames),1);self.assertEqual(caught.exception.frames[0].payload,encode_command(4))
  self.assertEqual(len(parser.buffer),0)
  with self.assertRaises(StreamError):parser.feed(wire)
 def test_incomplete_and_bounded_reassembly(self):
  r=Reassembler(max_pending=1,max_buffered_bytes=4)
  r.add(Frame(1,1,0,b'abc'))
  with self.assertRaises(CodecError):r.finish()
  with self.assertRaises(CodecError):r.add(Frame(1,2,0,b'X'))
  with self.assertRaises(CodecError):r.add(Frame(0,1,1,b'XX'))
  self.assertEqual(r.buffered_bytes,3)
  fresh=Reassembler(max_message_size=6)
  with self.assertRaises(CodecError):fresh.add(Frame(1,4,0,b'1234567'))
  self.assertEqual(fresh.pending,{})
  self.assertEqual(fresh.add(Frame(3,4,0,encode_message(0x5001))),Message(0x5001,b''))
 def test_legacy_strings_and_nul(self):
  for raw in (b'',b'A',b'AB',b'ABC'):
   encoded=encode_text_field(raw,unicode_mode=False)
   self.assertEqual(decode_text_field(encoded,unicode_mode=False),(raw,len(encoded)))
  with self.assertRaises(CodecError):encode_text_field('A\0B')
  with self.assertRaises(CodecError):encode_text_field('Ж',unicode_mode=False)

