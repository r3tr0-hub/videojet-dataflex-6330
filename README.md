# Videojet DataFlex 6330 protocol research

Independent interoperability notes, source code and offline test vectors for the Videojet DataFlex 6330. Firmware examined: **409720.r12.SP5**. [Русская документация](README.ru.md).

| Task | Start here | Evidence |
| --- | --- | --- |
| Read status, counts and parameter tree | [Windows diagnostic source](windows/), [binary session](binary/SESSION_PARAMETERS_RU.md) | Direct TCP and Windows ZBC2 reading confirmed on one 6330 |
| Read and change parameters | [XML, flags, access checks](parameters/PARAMETERS_ACCESS_RU.md), [parameter catalog](parameters/catalog.csv), [units](deep/parameters/PARAMETER_UNITS_RUNTIME_RU.md) | Read on hardware; write semantics recovered offline, arbitrary writes not verified |
| Upload CIFF, select jobs, update fields and inspect queue | [Job protocol](deep/jobs/JOBS_QUEUES_UPLOAD_RU.md), [operator workflow](windows/README.md) | Upload through Windows ZBC2 reported successful; queue/field recipes tested offline |
| Read the current label preview | [Preview recipe](windows/docs/PREVIEW_FIX_RU.md) | Two successful BMP retrieval reports |
| Generate and inspect labels | [CIFF format](ciff/README.md), [XML vocabulary](ciff/ciff_xml_vocabulary.json) | Sample-backed structure, not an official XSD |
| Implement a transport | [A5/E4 framing](binary/BINARY_FRAMING_RU.md), [session and keepalive](deep/session/SESSION_IRP_KEEPALIVE_RU.md) | Native reference vectors, offline codecs |
| Use the text interface | [ASCII command catalog](PROTOCOL_CATALOG_RU.md), [read-only client](tools/videojet_readonly.py) | Catalog recovered from resources; client tested with a simulator |
| Investigate counters, iAssure, logs and data files | [Research index](README.ru.md#дополнительные-исследования) | Offline research; applicability depends on hardware/options |

The binary and text channels are different. The tested binary port was **TCP 3001**; read your device configuration rather than assuming the text port is enabled. Binary block ACK, application result, readback, and physical printing are distinct checks.

## Quick start

Run the offline tests (Python 3.10+; no printer or vendor DLL needed):

```sh
python3 run_tests.py
python3 binary/parameter_queries.py --recipe print_settings
```

On Windows, build `windows/BUILD_WINDOWS.cmd`, run the resulting EXE, enter your printer address, select **TCP-чтение** and run **Проверить всё (чтение)**. For upload or preview, use the supported Windows x86 ZBC2 DLL supplied by your own installation and see [the workflow](windows/README.md). The program has no parameter write feature; that path is documented for implementation and controlled verification.

Use the included [offline XML read example](examples/read_print_settings.py) to inspect the request and binary framing without contacting a printer.

This is independent research, unaffiliated with Videojet. No firmware, vendor binaries, plant captures, active settings, or production CIFF files are distributed here. [License](LICENSE) covers the original implementation and explanatory text.
