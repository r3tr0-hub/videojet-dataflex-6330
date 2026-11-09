import json
import unittest
from pathlib import Path
from iassure_archive import *


class ArchiveListingTests(unittest.TestCase):
    def test_native_directory_requests(self):
        fixtures = json.loads(Path(__file__).with_name('native_directory_request_fixtures.json').read_text())
        for fixture in fixtures:
            self.assertEqual(encode_iassure_directory_request(unicode_mode=fixture['unicode']).hex(), fixture['hex'])

    def test_utf16_listing_and_partial_siblings(self):
        # Synthetic XML following the native generator schema; not a device capture.
        xml = '<?xml version="1.0" encoding="UTF-16"?><Folder Name=""><File Name="0001.bmp" Type="18" Size="123" DateModified="46000.5"/><File Name="0001.txt" Type="20"/><File Name="0002.erb" Type="19"/><File Name="unknown" Type="18"/></Folder>'
        entries = decode_iassure_directory(xml.encode('utf-16'))
        self.assertEqual([e['failure_id'] for e in entries], [1,1,2,None])
        self.assertEqual(entries[0]['attributes']['DateModified'], '46000.5')

    def test_reject_wrong_content(self):
        for xml in (b'<Params/>', b'<Folder><File Name="a"/></Folder>', b'<Folder><File Name="a" Type="-1"/></Folder>', b'<Folder>'):
            with self.assertRaises(CodecError):
                decode_iassure_directory(xml)


if __name__ == '__main__':
    unittest.main()
