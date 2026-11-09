@echo off
setlocal
cd /d "%~dp0"
set "VJ_CSC=%WINDIR%\Microsoft.NET\Framework\v4.0.30319\csc.exe"
if not exist "%VJ_CSC%" (
 echo .NET Framework C# compiler was not found.
 pause
 exit /b 1
)
"%VJ_CSC%" /nologo /target:winexe /platform:x86 /optimize+ /utf8output /codepage:65001 /win32manifest:src\app.manifest /out:Videojet6330.Diagnostics.exe /r:System.dll /r:System.Core.dll /r:System.Xml.dll /r:System.Drawing.dll /r:System.Windows.Forms.dll /r:System.Web.Extensions.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll src\*.cs
if errorlevel 1 (
 echo BUILD FAILED.
 pause
 exit /b 1
)
echo BUILD OK.
pause
