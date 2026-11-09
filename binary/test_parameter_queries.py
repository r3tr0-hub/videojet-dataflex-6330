import unittest
import xml.etree.ElementTree as ET
from parameter_queries import collection_query,extract_parameters,vendor_tcpip_query

class QueryTests(unittest.TestCase):
    def test_exact_vendor_recipe(self):
        root=ET.fromstring(vendor_tcpip_query())
        self.assertEqual(root.find("./Col[@id='System']/Col").attrib,{'id':'TCPIP','getFlags':'10','getDepth':'-1'})
    def test_proposal_is_read_only_and_escapes_names(self):
        x=collection_query('Devices/PHds/1/Some & Collection')
        root=ET.fromstring(x);leaves=list(root.iter())
        self.assertTrue(all(e.tag in ('Params','Col') and (e.text or '').strip()=='' for e in leaves))
        self.assertEqual(leaves[-1].get('id'),'Some & Collection')
        self.assertEqual(leaves[-1].get('getFlags'),'10')
        self.assertEqual(leaves[-1].get('getDepth'),'1')
    def test_reject_path_traversal_and_control_characters(self):
        for p in ['../Devices','Devices//PHds','/System','System/','System/\nTCPIP','System/\tTCPIP','System/\x01TCPIP']:
            with self.assertRaises(ValueError):collection_query(p)
    def test_typed_response_preserves_raw_scale(self):
        x='<Params><Col id="Devices"><Col id="PHds"><Col id="1"><Num id="X" numType="NumTenthsmm">45</Num><Str id="Text">A&amp;B</Str></Col></Col></Col></Params>'
        r=extract_parameters(x)
        self.assertEqual(r[0]['path'],'Devices/PHds/1/X');self.assertEqual(r[0]['value'],'45')
        self.assertEqual(r[1]['value'],'A&B')
if __name__=='__main__':unittest.main()
