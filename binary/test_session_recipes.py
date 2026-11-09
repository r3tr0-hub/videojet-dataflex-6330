import unittest
from session_recipes import *
from parameter_queries import vendor_tcpip_query, vendor_all_saved_query
from zbc_codec import decode_message, decode_text_field


class SessionRecipeTests(unittest.TestCase):
    def test_native_irq_fixture(self):
        self.assertEqual(encode_information_request().hex(), '01500c000000020001000700')

    def test_native_cmv_fixture(self):
        self.assertEqual(encode_version_offer(11, 0x000ffedf).hex(), '20500c0000000b00dffe0f00')

    def test_vendor_xml_queries(self):
        for xml in (vendor_tcpip_query(), vendor_all_saved_query()):
            m = decode_message(encode_parameter_query(xml, unicode_mode=True))
            self.assertEqual(m.message_type, 0x5112)
            value, end = decode_text_field(m.body)
            self.assertEqual((value, end), (xml, len(m.body)))

    def test_legacy_codepage_explicit(self):
        xml = vendor_all_saved_query()
        with self.assertRaises(CodecError):
            encode_parameter_query(xml, unicode_mode=False)
        m = decode_message(encode_parameter_query(xml, unicode_mode=False, modern=False, codepage='ascii'))
        self.assertEqual(m.message_type, 0x5012)

    def test_reject_write_values(self):
        with self.assertRaises(CodecError):
            encode_parameter_query('<Params><Num id="Speed">500</Num></Params>', unicode_mode=True)

    def test_bounds(self):
        for value in (-1, 65536):
            with self.assertRaises(CodecError):
                encode_information_request((value,))
            with self.assertRaises(CodecError):
                encode_version_offer(value, 0)


if __name__ == '__main__':
    unittest.main()
