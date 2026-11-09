import os
import unittest,struct,json
from pathlib import Path
from session_codec import *
class CodecTest(unittest.TestCase):
 def test_native_fixtures(self):
  fixtures=json.loads((Path(__file__).parent/'native_irp_fixtures.json').read_text())
  for item in fixtures:
   wire=bytes.fromhex(item['hex']);records=decode_irp(wire)
   self.assertEqual(encode_irp(records),wire)
   for rec in records:interpret_record(rec)
 def test_boundaries(self):
  good=encode_irp([make_record(7,11,0xffedf)])
  for bad in [good[:-1],good+b'\0',good[:6]+b'\2\0'+good[8:],good[:10]+b'\3\0'+good[12:]]:
   with self.assertRaises(ValueError):decode_irp(bad)
 def test_unknown_retained(self):
  records=[Record(0x7777,b'\0\xff\x12')];self.assertEqual(decode_irp(encode_irp(records)),records)
 def test_negotiation(self):
  self.assertEqual(negotiate(50,0xffffffff),(11,FEATURE_MASK))
  self.assertEqual(negotiate(4,0xffffffff,True),(3,0x1f))
  self.assertEqual(negotiate(5,0xffffffff,True),(5,FEATURE_MASK))
  self.assertEqual(negotiate(11,0xffffffff,cmv_present=False),(2,0))
 def test_sts(self):
  self.assertEqual(sts_flags(0,0,0),(1,0));self.assertEqual(sts_flags(3,1,4),(26,1));self.assertEqual(sts_flags(-1,2,10),(20,2))
 def test_no_implicit_encoding(self):
  self.assertEqual(read_field(field(b'ABC')),(b'ABC',6));self.assertEqual(read_field(field('АБ',True),unicode=True),('АБ',10))
  with self.assertRaises(ValueError):field(b'A\0B')
  with self.assertRaises(ValueError):field('A\0B',True)
@unittest.skipUnless(os.environ.get("ZBC2_DLL") or os.environ.get("VJ_BIN_ROOT"), "requires caller-supplied ARM ZBC2.dll")
class NativeComparison(unittest.TestCase):
 def test_native_negotiation(self):
  from native_session_oracle import Oracle
  o=Oracle()
  for version in (0,2,3,4,5,11,12,65535):
   for features in (0,0xffffffff,0x800,2):
    for compat in (False,True):self.assertEqual(o.negotiation(version,features,compat),negotiate(version,features,compat))
 def test_native_idle_probe(self):
  from native_session_oracle import Oracle
  o=Oracle();r=o.idle_probe();self.assertEqual(r['wait_arguments'][0][3],10000);self.assertEqual(r['selected_request'],r['expected_irq'])
  o=Oracle();self.assertEqual(o.idle_probe(True)['wait_arguments'][0][3],2000)
 def test_native_serializers(self):
  from native_session_oracle import Oracle
  o=Oracle()
  cases=[(1,(0x11223344,0x55667788,2,b'OK')),(1,(0,0,0,b'')),(2,(1,2,3,4,5,6,7,8,9,10)),(3,(b'ABC',1,2,3,4,5,6,7,8)),(8,('АБ😀',1,2,3,4,5,6,7,8)),(4,(b'A',b'BC')),(5,(0x12345678,)),(6,(2026,11,5,12,34,56)),(7,(11,0xffedf)),(9,(0x1122334455667788,0x8877665544332211)),(10,(1,1,123456,42,12,34,56,5,11,2026))]
  for tag,values in cases:self.assertEqual(o.message([(tag,values)]),encode_irp([make_record(tag,*values)]))
  self.assertEqual(o.message(cases),encode_irp([make_record(t,*v) for t,v in cases]))
if __name__=='__main__':unittest.main()
