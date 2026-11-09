#!/usr/bin/env python3
"""CIFF XML data-object inspection; no rendering, evaluation or vendor runtime.

Recovered parser uses child element to choose EDataType, while XML DataType is
an independent numeric ClearStyleDataType property. Preserve both values.
"""
import argparse,json,xml.etree.ElementTree as ET
from pathlib import Path

INTERNAL_TYPES={'VarText':3,'OffsetDate':4,'SrcField':1,'CounterText':5,
                'SrcData':2,'PriceData':7,'CLARICOMSSCC':8}

def inspect_xml(data):
    root=ET.fromstring(data);objects=[]
    for obj in root.iter('Object'):
        choices=[(n,INTERNAL_TYPES[n]) for n in INTERNAL_TYPES if obj.find(n) is not None]
        objects.append({'xml_clearstyle_data_type':obj.findtext('DataType'),
                        'internal_data_type':choices[0][1] if choices else 0,
                        'internal_type_source':choices[0][0] if choices else 'no typed child (DT_FIXED)',
                        'attributes':dict(obj.attrib),'source_field_name':(obj.find('SrcField').attrib.get('SrcFieldName') if obj.find('SrcField') is not None else None)})
    return {'root':root.tag,'attributes':dict(root.attrib),'objects':objects}

def inspect_prior(root):
    results=[]
    for p in sorted(Path(root).glob('job_*.json')):
        j=json.loads(p.read_text());fields=[]
        for field in j.get('fields',[]):
            if field.get('xml'):fields.append(inspect_xml(field['xml']))
        results.append({'source':str(p),'fields':fields})
    return {'job_count':len(results),'field_count':sum(len(x['fields']) for x in results),
            'object_count':sum(len(y['objects']) for x in results for y in x['fields']),'jobs':results}

def main():
    p=argparse.ArgumentParser();p.add_argument('path');p.add_argument('--prior',action='store_true');p.add_argument('--out');a=p.parse_args()
    r=inspect_prior(a.path) if a.prior else inspect_xml(Path(a.path).read_bytes())
    s=json.dumps(r,ensure_ascii=False,indent=2)
    if a.out:Path(a.out).write_text(s)
    else:print(s)

if __name__=='__main__':main()
