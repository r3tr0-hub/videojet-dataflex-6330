using System;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Sockets;
using System.Collections.Generic;
using Microsoft.Win32;

namespace Inntek.Videojet {
public static class Inventory {
 public static string UnquotePath(string value) {return Environment.ExpandEnvironmentVariables((value??"").Trim().Trim(new char[]{'"'}));}
 public const string MasterClsid="c2545583-3cdd-4370-9f5c-40a3c838edcd";
 public const string DataHash="59aa84ed2cd8119a00fd4c80dc9eaa966027b3f4bccaf0de5130d3dae6b812d0";
 public const string ConfigHash="dda7d181266958ec48fa7dedef890c01e85036be8a30b43f86af0dda3d611aed";
 static readonly Dictionary<string,string> Classes=new Dictionary<string,string>{
  {"ZBC2MasterSession",MasterClsid},{"RemoteClarity","b176da66-696a-11d5-95b0-00b0d03b2f2b"},
  {"Claricom.Server","d055cf09-a7cd-11d3-80f6-005004d1164e"},{"Claricom.Client","0f349f50-df00-11d3-8112-005004d1164e"},
  {"Claricom.JobSelection","9de2f534-6ddc-4f4b-b17d-a56d5228c4b5"},{"Claricom.PrintPreview","7da01fa4-e267-11d4-8198-005004d1164e"},
  {"CLARiNET.OPC_Server.DA","8c9360d7-8dff-44d3-a51c-6d0b937a2728"},{"CL_API.CLUser_API","d34e6800-189e-4407-ab25-059abb aecf0e".Replace(" ","")}
 };
 public static List<Dictionary<string,object>> RegistryRows() {
  var rows=new List<Dictionary<string,object>>();if(!Util.Windows)return rows;
  foreach(var view in new[]{RegistryView.Registry32,RegistryView.Registry64}) {
   try { using(var root=RegistryKey.OpenBaseKey(RegistryHive.ClassesRoot,view))foreach(var cls in Classes) {
    string v=null;using(var k=root.OpenSubKey("CLSID\\{"+cls.Value+"}\\InprocServer32",false))if(k!=null)v=Convert.ToString(k.GetValue(""));
    if(String.IsNullOrWhiteSpace(v))using(var k=root.OpenSubKey("CLSID\\{"+cls.Value+"}\\LocalServer32",false))if(k!=null)v=Convert.ToString(k.GetValue(""));
    string p=UnquotePath(v);
    var r=Util.Obj("name",cls.Key,"clsid",cls.Value,"view",view.ToString(),"registered",v!=null,"server",v??"");
    try{if(System.IO.File.Exists(p)){r["sha256"]=Util.FileHash(p);r["version"]=FileVersionInfo.GetVersionInfo(p).FileVersion;}}catch(Exception e){r["file_error"]=e.Message;}
    rows.Add(r);
   }}catch(Exception e){rows.Add(Util.Obj("view",view.ToString(),"error",e.Message));}
  }return rows;
 }
 public static string FindDll(Config c) {
  if(!String.IsNullOrWhiteSpace(c.Dll)) {
   string p=Path.GetFullPath(c.Dll);
   if(Directory.Exists(p))foreach(var sub in new[]{"Data/ZBC2.dll","ZBC2.dll","CLARiTYConfig/ZBC2.dll"}){string q=Path.Combine(p,sub.Replace('/',Path.DirectorySeparatorChar));if(System.IO.File.Exists(q))return q;}
   if(System.IO.File.Exists(p))return p;
   throw new FileNotFoundException("ZBC2.dll не найдена по указанному пути.");
  }
  foreach(var r in RegistryRows())if(Util.S(r["name"])=="ZBC2MasterSession"&&Util.S(r["view"])=="Registry32") {
   string p=UnquotePath(Util.S(r["server"]));if(System.IO.File.Exists(p))return p;
  }return null;
 }
 public static void ValidateDll(string p) {
  string h=Util.FileHash(p);if(h!=DataHash&&h!=ConfigHash)throw new InvalidOperationException("ZBC2.dll другой сборки: "+h+". Адресные COM-вызовы для неё не выполняются. Выберите исследованный файл из Data или используйте режим TCP-чтения.");
 }
 public static void Collect(Config c,Journal j) {
  j.Log("Сбор сведений ПК: реестр читается без создания COM-объектов.");
  var r=Util.Obj("utc",DateTime.UtcNow.ToString("o"),"os",Environment.OSVersion.ToString(),"runtime",Environment.Version.ToString(),"process_bits",IntPtr.Size*8,"os_64",Environment.Is64BitOperatingSystem,"target_ip",c.Host,"target_port",c.Port,"operation",c.Operation,"raw_capture",c.Raw);
  var adapters=new List<object>();foreach(var n in NetworkInterface.GetAllNetworkInterfaces()) {
   try{adapters.Add(Util.Obj("name",n.Name,"status",n.OperationalStatus.ToString(),"ipv4",n.GetIPProperties().UnicastAddresses.Where(a=>a.Address.AddressFamily==AddressFamily.InterNetwork).Select(a=>a.Address.ToString()).ToArray()));}catch{}
  }r["network_adapters"]=adapters;r["com_registrations"]=RegistryRows();j.File("pc_inventory.json",Util.Json(r));j.Event("inventory",r);
  try{var p=FindDll(c);if(p!=null)j.Event("dll",Util.Obj("path",p,"sha256",Util.FileHash(p),"version",FileVersionInfo.GetVersionInfo(p).FileVersion,"supported_hash",new[]{DataHash,ConfigHash}.Contains(Util.FileHash(p))));}catch(Exception e){j.Event("dll_inventory_error",e.Message);}
 }
 public static bool TcpProbe(Config c,Journal j) {
  using(var t=new TcpClient()) {
   var sw=Stopwatch.StartNew();try{var a=t.BeginConnect(c.Host,c.Port,null,null);try{if(!a.AsyncWaitHandle.WaitOne(3000))throw new TimeoutException("Нет TCP-соединения за 3 с.");t.EndConnect(a);}finally{a.AsyncWaitHandle.Close();}
    j.Event("tcp_probe",Util.Obj("connected",true,"elapsed_ms",sw.ElapsedMilliseconds));j.Log("TCP-порт доступен. Это ещё не подтверждение протокола принтера.");return true;
   }catch(Exception e){j.Event("tcp_probe",Util.Obj("connected",false,"elapsed_ms",sw.ElapsedMilliseconds,"error",e.Message));return false;}
  }
 }
}
}
