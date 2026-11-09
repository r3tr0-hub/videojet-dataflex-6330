# DataFile lookup

`existing_datafile.py` reads an existing fixed-width ASCII corpus supplied by the operator. It does not generate new codes. In the examined backup each record used CRLF, had 24 bytes, and began with the same prefix. In ARM reader tests the final physical record was omitted even when terminated by CRLF. The model can reproduce that behavior or read the complete local file. Do not generalize the layout or end-of-file behavior to other firmware builds and data formats. No production rows are included.
