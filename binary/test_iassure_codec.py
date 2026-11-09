"""Checks against outputs of the extracted ARM code, plus malformed-input checks.
Run: python -m unittest discover -s . -p test_iassure_codec.py -v
For current-binary oracle regeneration see native_iassure_oracle.py.
"""
import sys,json,struct,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(HERE),str(HERE.parent/'binary_frames')]
from zbc_codec import CodecError
from iassure_codec import *

class IAssureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native=json.loads((HERE/'native_iassure_fixtures.json').read_text())

    def test_current_requests_against_real_native_serializer(self):
        for index,unicode in [(0,False),(1,True)]:
            raw=encode_current_iassure_request(unicode_mode=unicode)
            self.assertEqual(raw.hex(),self.native['requests'][index]['hex'])
            req=decode_file_request(raw)
            self.assertEqual((req.file_type,req.flags,req.head,req.width,req.height),
                             (3,0x200,1,0,0))

    def test_arbitrary_bitmap_fields_against_real_native_serializer(self):
        cases=[(2,'snapshot',0x200,1,0,0),(3,'Тест',0x201,2,640,480)]
        for index,name,flags,head,width,height in cases:
            raw=encode_bitmap_request(name,flags=flags,head=head,width=width,height=height)
            self.assertEqual(raw.hex(),self.native['requests'][index]['hex'])
            native=self.native['requests'][index]['decoded']
            req=decode_file_request(raw)
            self.assertEqual((req.flags,req.head,req.width,req.height),
                             (native['flags'],native['head'],native['width'],native['height']))

    def test_archive_requests_against_real_native_serializer(self):
        for kind,filetype in [('bmp',18),('erb',19),('txt',20)]:
            self.assertEqual(encode_archived_iassure_request(1,kind).hex(),
                             self.native['archives'][str(filetype)])

    def test_transfer_against_native_serializer_and_parser(self):
        for index,unicode in [(0,True),(1,False)]:
            case=self.native['transfers'][index]
            raw=bytes.fromhex(case['hex'])
            file=decode_file_transfer(raw,unicode_mode=unicode)
            self.assertEqual(file.file_type,case['filetype'])
            self.assertEqual(file.data.hex(),case['data_hex'])
            self.assertEqual(len(file.data),case['file_size'])
            self.assertEqual(file.trailing_padding,b'\0')

    def test_transfer_rejects_truncation_and_wrong_size(self):
        raw=bytearray.fromhex(self.native['transfers'][0]['hex'])
        struct.pack_into('<I',raw,8,0x100000)
        with self.assertRaises(CodecError):decode_file_transfer(bytes(raw))

    def test_metadata_layout_and_unknown_words_are_preserved(self):
        header=struct.pack('<6I',123,456,7,1,0,int.from_bytes(b'iAS2','little'))
        header+=struct.pack('<d6I',46000.5,1,0,25,55,999,888)
        result=decode_archive_metadata(header+'PixelScale: 100\n'.encode('utf-16-le'))
        self.assertEqual(result['failure_id'],123)
        self.assertEqual(result['timestamp_f64'],46000.5)
        self.assertEqual(result['unknown_48'],999)
        with self.assertRaises(CodecError):decode_archive_metadata(b'plain text')

    def test_bmp_magic_not_filename(self):
        palette=bytes(1024);pixels=bytes(4)
        raw=struct.pack('<2sIHHI',b'BM',0x436+4,0,0,0x436)
        raw+=struct.pack('<IiiHHIIiiII',40,4,1,1,8,0,4,0,0,256,256)+palette+pixels
        self.assertTrue(inspect_bitmap(raw)['native_iassure_layout'])
        with self.assertRaises(CodecError):inspect_bitmap(raw[:-1])

if __name__=='__main__':unittest.main()
