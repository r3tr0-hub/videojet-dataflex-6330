import unittest,json
from pathlib import Path
from job_codec import *
FIX=json.loads(Path(__file__).with_name('native_jobs_fixtures.json').read_text())
class NativeFixtures(unittest.TestCase):
 def test_all_selections_match_arm(self):
  for f in FIX['jobs']:
   if f['kind']=='JDU':continue
   kwargs=dict(flags=f['flags'],limit=f['limit'],update_id=f['update_id'])
   raw=encode_select(f['name'],bytes.fromhex(f['data_hex']),unicode=f['kind']=='SLU',legacy_encoding='ascii',**kwargs)
   self.assertEqual(raw.hex(),f['hex']);v=inspect_job(raw,legacy_encoding='ascii');self.assertEqual(v['name'],f['name'])
 def test_all_jdu_anomalies_match_arm(self):
  for f in FIX['jobs']:
   if f['kind']!='JDU':continue
   raw=encode_jdu_native_literal(bytes.fromhex(f['data_hex']),flags=f['flags'],limit=f['limit'],update_id=f['update_id'])
   self.assertEqual(raw.hex(),f['hex'])
   with self.assertRaises(ValueError):inspect_job(raw)
   self.assertTrue(inspect_job(raw,allow_native_jdu_length_anomaly=True)['native_jdu_length_anomaly'])
 def test_arm_responses(self):
  for k,raw in FIX['responses'].items():
   if k=='EMX':continue
   self.assertEqual(inspect_response(bytes.fromhex(raw))['kind'],k.split('_')[0])
 def test_xml_escape(self):
  raw=image_data_xml([('Имя','<&"')]);v=ET.fromstring(raw);self.assertEqual(v[0].attrib['Name'],'Имя');self.assertEqual(v[0].text,'<&"')
 def test_invalid(self):
  with self.assertRaises(ValueError):encode_select('Name',unicode=False)
  with self.assertRaises(ValueError):encode_select('N',b'X',flags=BINARY_DATA)
  raw=encode_select('N',b'<ImageData/>')
  with self.assertRaises(ValueError):inspect_job(raw[:-1])
 def test_update_id_is_conditional(self):
  self.assertEqual(encode_select('N',update_id=7),encode_select('N',update_id=99))
  self.assertEqual(inspect_job(encode_select('N',flags=SET_UPDATE_ID,update_id=99))['update_id'],99)
if __name__=='__main__':unittest.main(verbosity=2)
