"""Offline iAssure directory request and XML listing decoder.

Recovered native DirectoryListing contract; no network or filesystem writes.
"""
import re
import struct
import xml.etree.ElementTree as ET
from zbc_codec import CodecError, encode_text_field
from iassure_codec import encode_file_request


def encode_iassure_directory_request(*, unicode_mode=True):
    subdirectory = '' if unicode_mode else b''
    extra = struct.pack('<I', 0x800) + encode_text_field(subdirectory, unicode_mode=unicode_mode)
    return encode_file_request(7, unicode_mode=unicode_mode, extra=extra)


def decode_iassure_directory(xml_bytes):
    """Decode the content of DirectoryListing.xml after removing FTX wrapper.

    DateModified remains a numeric string without a guessed timezone.
    Unknown fields and unmatched filenames are retained in attributes.
    """
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        raise CodecError('Invalid DirectoryListing XML') from exc
    if root.tag != 'Folder':
        raise CodecError('DirectoryListing root must be Folder')
    result = []
    for node in root.iter('File'):
        if not {'Name', 'Type'} <= node.attrib.keys():
            raise CodecError('Directory File requires Name and Type')
        raw_type = node.attrib['Type']
        if not re.fullmatch(r'[0-9]+', raw_type) or int(raw_type) > 0xffff:
            raise CodecError('Invalid file type')
        kind = int(raw_type)
        match = re.fullmatch(r'([0-9]+)\.(bmp|erb|txt)', node.attrib['Name'])
        archive_id = None
        if match and kind == {'bmp':18, 'erb':19, 'txt':20}[match[2]]:
            archive_id = int(match[1])
        result.append({'name':node.attrib['Name'], 'file_type':kind,
                       'failure_id':archive_id, 'attributes':dict(node.attrib)})
    return result
