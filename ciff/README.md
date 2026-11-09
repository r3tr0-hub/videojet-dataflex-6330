# CIFF label format

Observed root: `ImageDesign Version="23"`. The files are XML; preserve byte encoding, BOM and declaration together. The studied corpus includes UTF-16 files; a reader should also recognize UTF-8 and UTF-16BE. For a new job, start with a known-good CIFF from the same model, head and mode. Preserve Header/DesignedFor, ClStVersionInfo, unknown nodes and unrelated resources.

A job contains one or more SubImage nodes with SubHeader and named Field nodes. SubHeader distinguishes ImageWidth/ImageHeight from MaxImageWidth/MaxImageHeight. `hmm` means 0.01 mm; `dots` means head dots. For the examined 12 dots/mm profile, 50 mm is 5000 hmm or 600 dots. Use the head resolution of the selected profile.

| Field property | How to handle it |
| --- | --- |
| X/Y/W/H, Orientation, Origin | Work in the job's units; validate the transformed bounds |
| FldType and CLSID | Copy the native type and class from a matching exemplar |
| Data/Object/Default and CalcData | Keep these synchronized for static text; preserve the difference between expression and snapshot in dynamic fields |
| SrcField/SrcFieldName | Preserve the dependency, update references on renaming, check for cycles |
| Text/Font | The preview's font metrics are not evidence of the device's glyph metrics |
| Barcode/QR, Barcode/DataMatrix, Barcode/Code128, Barcode/EAN128 | Encode real data; recalculate W/H, keep quiet zones and quantize modules to dots |
| StaticGraphic and Embedded/File | External BMP resources and embedded formats need separate validation |

The XML `DataType` is `ClearStyleDataType` in CiffMgr. The COM `EDataType` is a separate internal category inferred from the typed child of Object. Examples: XML 4 with CounterText maps to internal 5; XML 5 with SrcField maps to internal 1. See [the model inspector](ciff_object_model.py). Do not assign XML values from the COM enum.

For simple generation, clone the Header and SubHeader, then copy one verified Field per required type. Set unique names and the desired geometry, change only confirmed properties, recalculate bounds, and parse the output again. In QR/Data Matrix validate data capacity, physical module size and margins. For GS1 distinguish AI notation from encoded bytes and preserve FNC1/GS semantics. Do not embed an XML-forbidden ASCII GS character as text.

Machine-readable aids:
- [XML vocabulary](ciff_xml_vocabulary.json): element/attribute names, not a full schema.
- [Properties and observed paths](label_creation_spec.json), [enum tokens](xml_enum_tables.json).
- [DataFlex profiles](dataflex_profiles.json): extracted values for eight combinations; verify against the actual printer.
- [Object inspector](ciff_object_model.py): Python parser for field and Object structure.

A decoder successfully reading a preview does not prove that the printer will accept the CIFF or reproduce the symbol at that physical size. Verify a generated job by opening it in a compatible loader and printing on the target head.
