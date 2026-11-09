using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Collections;
using System.Collections.Generic;

namespace Inntek.Videojet {
public static class SelfTests {
 static byte[] Bytes(string hex){return Enumerable.Range(0,hex.Length/2).Select(i=>Convert.ToByte(hex.Substring(i*2,2),16)).ToArray();}
 static void Check(bool ok,string why){if(!ok)throw new Exception(why);}
 static void Reject(Action a,string why){bool rejected=false;try{a();}catch{rejected=true;}Check(rejected,why);}
 public static int Run(string file){
  var log=new List<string>();int cases=0;try {
   Check(Inventory.UnquotePath("  \"C:\\Program Files (x86)\\CLARiCOM\\Data\\ZBC2.dll\"  ")=="C:\\Program Files (x86)\\CLARiCOM\\Data\\ZBC2.dll","quoted registry DLL path");cases++;
   Check(Inventory.UnquotePath(null)=="","null registry path");cases++;
   Check(Wire.Crc(Encoding.ASCII.GetBytes("123456789"))==0xbeef,"native CRC");cases++;
   var preview=Util.Parse(File.ReadAllText(Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"tests/preview_recipe.json")));Check(Util.Hex(PreviewRecipe.WireFixture())==Util.S(preview["hex"]),"vendor preview generation request");cases++;
   Check(Util.Hex(Wire.Irq(1,7))=="01500c000000020001000700","IRQ1/7");cases++;
   Check(Util.Hex(Wire.Cmv(11,0xffedf))=="20500c0000000b00dffe0f00","CMV");cases++;
   foreach(int version in new[]{2,3,4,11})foreach(byte flags in new byte[]{3,0x13,0x33,7,0x17,0x37})foreach(byte[] payload in new[]{new byte[0],new byte[]{1,2,3},Encoding.ASCII.GetBytes("123456789")}){
    uint? route=(flags&0x20)!=0?(uint?)0x89abcdef:null;byte[] b=Wire.Encode(flags,0x1234,0x5678,payload,route,version);var f=Wire.Decode(b,version);Check(f.Payload.SequenceEqual(payload)&&f.Id==0x1234&&f.Block==0x5678&&f.Route==route,"frame roundtrip");cases++;
   }
   var corrupt=Wire.Encode(0x13,1,0,new byte[]{1,2,3},null,11);corrupt[10]^=1;Reject(()=>Wire.Decode(corrupt,11),"bad CRC accepted");cases++;
   Reject(()=>Parameters.Rows("<!DOCTYPE p [<!ENTITY a SYSTEM 'file:///secret'>]><Params>&a;</Params>"),"DTD accepted");cases++;
   string xml="<Params><Col id='Device'><Str id='Name'>6330</Str><Str id='Password'>super_secret</Str><Col id='Secret'><Num id='a'>987654</Num></Col></Col></Params>";
   string safe=Parameters.Sanitize(xml,false);Check(!safe.Contains("super_secret")&&!safe.Contains("987654")&&safe.Contains("6330"),"redaction");cases++;
   Check(Parameters.Rows(safe).Count==3,"parameter walk");cases++;
   Check(Util.Xml(Parameters.Query("System/TCPIP",true)).SelectNodes("/Params/Col[@id='System']/Col[@id='TCPIP'][@getFlags='10']").Count==1,"read query");cases++;
   var c=new Config{Host="127.0.0.1",Operation="select",JobName="test.ciff"};Reject(c.Validate,"write without permission accepted");cases++;
   c.Operation="read";c.Validate();c.Host="0.0.0.0";Reject(c.Validate,"wildcard target accepted");cases++;
   var parsed=Util.Parse(Util.Json(Util.Obj("data",new[]{Util.Obj("path","a","type","Str","value","b","attributes",new Dictionary<string,string>())})));Check(parsed["data"] is IEnumerable,"GUI event arrays");cases++;
   string tests=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"tests");string pc=Path.Combine(tests,"native_pc_fixtures.json");
   if(File.Exists(pc)) {
    var d=Util.Parse(File.ReadAllText(pc));int frameCases=0;
    foreach(Dictionary<string,object> r in (IEnumerable)d["frames"]){byte flags=Convert.ToByte(r["flags"]);var got=Wire.Encode(flags,0x1234,0x5678,Bytes(Util.S(r["payload_hex"])),(flags&0x20)!=0?(uint?)0x89abcdef:null,Util.I(r["version"]));Check(Util.Hex(got)==Util.S(r["hex"]),"x86 frame fixture");frameCases++;cases++;}
    foreach(Dictionary<string,object> r in (IEnumerable)d["strings"]){byte[] got=Wire.Counted(Util.S(r["text"]),true,Util.I(r["width"]));Check(Util.Hex(got)==Util.S(r["hex"]),"x86 Unicode fixture");cases++;}
    log.Add("x86 frame fixtures: "+frameCases+" PASS; Unicode fixtures: PASS");
   }else throw new FileNotFoundException("Нет tests/native_pc_fixtures.json");
   string irp=Path.Combine(tests,"native_irp_fixtures.json");
   var array=new System.Web.Script.Serialization.JavaScriptSerializer().DeserializeObject(File.ReadAllText(irp));int irpCases=0;
   foreach(Dictionary<string,object> r in (IEnumerable)array){var rows=Wire.ParseIrp(Bytes(Util.S(r["hex"])));Check(rows.Count>0,"IRP records");irpCases++;cases++;}
   log.Add("ARM-native IRP fixtures: "+irpCases+" PASS");
   log.Add("PASS: "+cases+" checks. No printer/network/COM/vendor DLL access.");log.Add("Live Windows COM and physical printer are not covered by self-test.");File.WriteAllLines(file,log,Util.Utf8);return 0;
  }catch(Exception e){log.Add("FAIL after "+cases+" checks: "+e);File.WriteAllLines(file,log,Util.Utf8);return 1;}
 }
}
}
