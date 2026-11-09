# Windows diagnostic client

Source of the v0.1.2 diagnostic client, with the plant address replaced by the documentation placeholder 192.0.2.10. The built EXE and vendor DLLs are not bundled.

1. Build with `BUILD_WINDOWS.cmd` on Windows with the .NET Framework compiler. The client targets x86 because the tested native DLLs are x86.
2. Run the EXE. Replace the placeholder with the actual address and binary port. Begin with **TCP-чтение → Проверить всё (чтение)**. This mode does not require CLARiSOFT.
3. For native mode select a supported `ZBC2.dll` from your own installation, with its dependencies. The code checks the DLL SHA-256 before loading. See [ABI notes](docs/abi_contracts.json).
4. For preview use the separate command. `RequestBitmap` uses `CurrentImage.bmp`, flags `0x0F`, head 1 and width/height 0. See [preview notes](docs/PREVIEW_FIX_RU.md).
5. For upload, select a known-good local CIFF, set a fresh remote filename and enable **Разрешаю выбранную операцию изменения задания** in **Проверка job**. Click **Передать файл** and check the target shown in the confirmation. This is a separate operation; upload does not select the file.
6. For selection, use **Выбрать задание** and check that the current job name matches. The client checks PRINTING/IMAGING flags before a mutation, but a machine can change state after that check.

Native calls are isolated in [NativeClient.cs](src/NativeClient.cs); direct TCP in [Wire.cs](src/Wire.cs). There is no automatic retry of job mutations. For development, `SELFTEST.cmd` runs local self-tests after compilation and `DEMO.cmd` starts a synthetic UI. The mock integration suite requires a built executable and Python: `python tests/mock_integration.py`.

Reports are for local diagnostics and can contain addresses, device IDs, job data and parameter values. Inspect and remove those before posting an issue.

## Where to get ZBC2.dll

Videojet provides CLARiSOFT and CLARiTY Config installers on its [official support page](https://www.videojet.de/de/homepage/technical-support.html). Use the DLL from your installed package and keep its dependencies in the installation directory. The tested CLARiTY Config copy was installed at:

```text
C:\Program Files (x86)\CLARiCOM\CLARiTYConfig\ZBC2.dll
```

To identify that exact Windows x86 build, run in PowerShell:

```powershell
Get-FileHash -Algorithm SHA256 'C:\Program Files (x86)\CLARiCOM\CLARiTYConfig\ZBC2.dll'
```

Expected SHA-256: `dda7d181266958ec48fa7dedef890c01e85036be8a30b43f86af0dda3d611aed`.

The current vendor download may install a different build. Compare against the two supported hashes in [Inventory.cs](src/Inventory.cs). If neither matches, the client rejects the DLL. Direct TCP reading remains available without a DLL.
