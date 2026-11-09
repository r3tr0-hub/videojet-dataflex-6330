"""Build a read request and its first binary frame; never opens a socket."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'binary'))
from parameter_queries import PATHS, collection_query
from session_recipes import encode_parameter_query
from zbc_codec import encode_frame, fragment_message

xml = collection_query(PATHS['print_settings'])
print(xml)
body = encode_parameter_query(xml, unicode_mode=True)
for frame in fragment_message(body, 1, max_payload=1986):
    print(encode_frame(frame, protocol_version=11).hex(' '))
