"""Offline, read-only XML recipes for the reverse-engineered CLARiTY channel.

Produces XML text only; no network access, state changes or print commands.
The wire encoder and negotiated ANSI/Unicode mode must be applied separately.
"""
import argparse
import json
import xml.etree.ElementTree as ET

PATHS = {
 'print_settings':'Devices/PHds/1/PrintInformation',
 'ribbon':'Devices/PHds/1/Consumables/Ribbon',
 'iassure_settings':'Devices/PHds/1/IAssure/Settings',
 'iassure_detectors':'Devices/PHds/1/IAssure/Detectors',
 'performance':'Performance',
 'network':'System/TCPIP',
}

def collection_query(path,depth=1,get_flags=10):
    if not isinstance(path,str) or not path or path.startswith('/') or path.endswith('/'):
        raise ValueError('Expected a non-empty relative CLARiTY collection path')
    parts=path.split('/')
    if any(not p or p in ('.','..') or any(ord(c)<32 or 0xd800<=ord(c)<=0xdfff or ord(c) in (0xfffe,0xffff) for c in p) for p in parts):
        raise ValueError('Invalid collection path')
    if depth not in (0,1,-1):raise ValueError('Depth must be 0, 1, or -1')
    if get_flags not in (10,32):raise ValueError('Only vendor-observed read flag recipes are accepted')
    root=ET.Element('Params');node=root
    for part in parts:node=ET.SubElement(node,'Col',{'id':part})
    node.set('getFlags',str(get_flags));node.set('getDepth',str(depth))
    return '<?xml version="1.0" ?>'+ET.tostring(root,encoding='unicode')

def vendor_tcpip_query():
    # Exact literal at ZBC2 VA 0x446F6640, used at 0x446A516C.
    return '<?xml version="1.0" ?>\n<Params><Col id="System"><Col id="TCPIP" getFlags="10" getDepth="-1"/></Col></Params>\n'

def vendor_all_saved_query():
    # Exact literal at ZBC2 VA 0x44702B20; FT_CURRENTPARAMETERS path.
    return '<?xml version="1.0" ?><Params><Col id="" getFlags="32" getDepth="-1"/></Params>'

def extract_parameters(xml_text):
    root=ET.fromstring(xml_text);rows=[]
    def walk(e,path=()):
        name=e.get('id','');p=path+(name,) if name else path
        if e.tag in ('DT','DO','Evt','Fld','Num','Sta','Str','Lnk'):
            rows.append({'path':'/'.join(p),'type':e.tag,'value':e.text or '',
                         'attributes':dict(e.attrib)})
        for child in e:walk(child,p)
    walk(root)
    return rows

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--recipe',choices=['vendor_tcpip','vendor_all']+list(PATHS),default='print_settings');a=p.parse_args()
    if a.recipe=='vendor_tcpip':print(vendor_tcpip_query(),end='')
    elif a.recipe=='vendor_all':print(vendor_all_saved_query())
    else:print(collection_query(PATHS[a.recipe]))
if __name__=='__main__':main()
