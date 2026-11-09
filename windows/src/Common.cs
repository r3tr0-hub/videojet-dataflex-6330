using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Xml;
using System.Collections;
using System.Collections.Generic;
using System.Security.Cryptography;
using System.Web.Script.Serialization;

namespace Inntek.Videojet {
public static class Util {
 public static readonly UTF8Encoding Utf8 = new UTF8Encoding(false);
 public static string Json(object o) { return new JavaScriptSerializer { MaxJsonLength=40*1024*1024, RecursionLimit=128 }.Serialize(o); }
 public static Dictionary<string,object> Obj(params object[] pairs) { var d=new Dictionary<string,object>(); for(int i=0;i<pairs.Length;i+=2)d[(string)pairs[i]]=pairs[i+1]; return d; }
 public static string Hash(byte[] b) { using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(b)).Replace("-","").ToLowerInvariant(); }
 public static string FileHash(string p) { using(var s=File.OpenRead(p))using(var h=SHA256.Create())return BitConverter.ToString(h.ComputeHash(s)).Replace("-","").ToLowerInvariant(); }
 public static string Hex(byte[] b) { return BitConverter.ToString(b).Replace("-","").ToLowerInvariant(); }
 public static string S(object v) { return v==null?"":Convert.ToString(v,System.Globalization.CultureInfo.InvariantCulture); }
 public static int I(object v) { return Convert.ToInt32(v,System.Globalization.CultureInfo.InvariantCulture); }
 public static Dictionary<string,object> Parse(string s) {return new JavaScriptSerializer {MaxJsonLength=40*1024*1024}.Deserialize<Dictionary<string,object>>(s);}
 public static bool Windows { get { return Environment.OSVersion.Platform==PlatformID.Win32NT; } }
 public static string Escape(string s) { return System.Security.SecurityElement.Escape(s??""); }
 public static XmlDocument Xml(string text) { var x=new XmlDocument();x.XmlResolver=null;using(var r=XmlReader.Create(new StringReader(text),new XmlReaderSettings {DtdProcessing=DtdProcessing.Prohibit,XmlResolver=null,MaxCharactersInDocument=16*1024*1024}))x.Load(r);return x; }
}

public static class PreviewRecipe {
 // CLARiTYConfig.exe 0x42be94..0x42bf70; flags=0x0f, head=1, width=height=0.
 // Firmware ZBC2 0x446c007c tests bit0 to generate the selected-job preview.
 public const string FileName="CurrentImage.bmp";
 public const int Flags=0x0f;
 public const short Head=1,Width=0,Height=0;
 public static byte[] WireFixture(){using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write((ushort)3);w.Write(Wire.Counted(FileName,true,4));w.Write(Flags);w.Write(Head);w.Write(Width);w.Write(Height);return Wire.Inner(0x5032,m.ToArray());}}
}

public class Config {
 public string Host="", Dll="", Mode="auto", Operation="read", Output="", JobName="", JobFile="", RemoteName="";
 public int Port=3001, ObserveSeconds=20, TimeoutSeconds=25, LegacyCodePage=0;
 public bool AllowChanges=false, Raw=false, Lane=false, FullParameters=true;
 public void Validate() {
  System.Net.IPAddress ip;
  if(!System.Net.IPAddress.TryParse(Host,out ip) || ip.AddressFamily!=System.Net.Sockets.AddressFamily.InterNetwork || ip.Equals(System.Net.IPAddress.Any) || ip.Equals(System.Net.IPAddress.Broadcast))throw new ArgumentException("Укажите IPv4-адрес принтера, например 192.0.2.10. Адрес необходимо проверить на принтере.");
  if(Port<1||Port>65535)throw new ArgumentException("Порт должен быть 1–65535.");
  if(ObserveSeconds<0||ObserveSeconds>300||TimeoutSeconds<3||TimeoutSeconds>90)throw new ArgumentException("Недопустимое время проверки.");
  if(!new[]{"auto","native","tcp"}.Contains(Mode))throw new ArgumentException("Неизвестный режим.");
  if(!new[]{"read","preview","upload","select"}.Contains(Operation))throw new ArgumentException("Неизвестная операция.");
  if(Operation=="upload"||Operation=="select") {
   if(!AllowChanges)throw new InvalidOperationException("Изменяющие операции не разрешены.");
   if(Mode=="tcp")throw new InvalidOperationException("Передача/выбор задания доступны через проверенную ZBC2.dll.");
   if(Operation=="select"&&(String.IsNullOrWhiteSpace(JobName)||JobName.IndexOf('\0')>=0||JobName.Length>1024))throw new ArgumentException("Укажите точное имя существующего задания.");
   if(Operation=="upload") {
    var p=new FileInfo(JobFile);
    if(!p.Exists||p.Length==0||p.Length>16*1024*1024||!String.Equals(p.Extension,".ciff",StringComparison.OrdinalIgnoreCase))throw new ArgumentException("Нужен существующий .ciff от 1 байта до 16 MiB.");
    if(String.IsNullOrWhiteSpace(RemoteName)||RemoteName!=Path.GetFileName(RemoteName)||RemoteName.IndexOfAny(new[]{'/', '\\', ':','\0'})>=0||!RemoteName.EndsWith(".ciff",StringComparison.OrdinalIgnoreCase))throw new ArgumentException("Имя на принтере должно быть простым именем .ciff без пути.");
   }
  }
 }
 public void Save(string path) {
  var x=new XmlDocument();var r=x.CreateElement("Diagnostics");x.AppendChild(r);
  foreach(var f in typeof(Config).GetFields()) { var e=x.CreateElement(f.Name);e.InnerText=Util.S(f.GetValue(this));r.AppendChild(e); }
  x.Save(path);
 }
 public static Config Load(string path) {
  var x=Util.Xml(File.ReadAllText(path));var c=new Config();
  foreach(var f in typeof(Config).GetFields()) { var e=x.DocumentElement[f.Name];if(e==null)continue;object value=e.InnerText;if(f.FieldType==typeof(int))value=Int32.Parse(e.InnerText);if(f.FieldType==typeof(bool))value=Boolean.Parse(e.InnerText);f.SetValue(c,value); }
  c.Validate();return c;
 }
}

public class Journal:IDisposable {
 readonly object gate=new object();readonly StreamWriter writer;bool disposed;public readonly string Folder;public bool Raw;
 public readonly List<Dictionary<string,object>> Events=new List<Dictionary<string,object>>();
 public Journal(string folder,bool raw) {Folder=Path.GetFullPath(folder);Directory.CreateDirectory(Folder);Raw=raw;writer=new StreamWriter(new FileStream(Path.Combine(Folder,"events.jsonl"),FileMode.Create,FileAccess.Write,FileShare.ReadWrite),Util.Utf8);writer.AutoFlush=true;}
 public void Event(string kind,object data) { lock(gate) {if(disposed)return;var e=Util.Obj("utc",DateTime.UtcNow.ToString("o"),"kind",kind,"data",data);Events.Add(e);writer.WriteLine(Util.Json(e)); } }
 public void Log(string text) {Event("log",text);}
 public void File(string name,string content) {System.IO.File.WriteAllText(Path.Combine(Folder,name),content,Util.Utf8);}
 public void Dispose() {lock(gate){disposed=true;writer.Dispose();}}
}

public class ParameterRow {public string path,type,value; public Dictionary<string,string> attributes;}
public static class Parameters {
 public static string Query(string path,bool all) {
  var x=new XmlDocument();var root=x.CreateElement("Params");x.AppendChild(root);XmlElement n=root;
  foreach(string part in (String.IsNullOrEmpty(path)?new[]{""}:path.Split(new char[]{'/'}))) {var ch=x.CreateElement("Col");ch.SetAttribute("id",part);n.AppendChild(ch);n=ch;}
  n.SetAttribute("getFlags","10");n.SetAttribute("getDepth",all?"-1":"1");return x.OuterXml;
 }
 public static bool Secret(string key) {key=(key??"").ToLowerInvariant();return new[]{"password","passwd","passcode","secret","licensekey","licencekey","activationkey","privatekey","accesstoken","checkcode","unlockcode"}.Any(key.Contains);}
 static void Redact(XmlElement e,bool inherited) {
  bool hide=inherited||Secret(e.GetAttribute("id"))||Secret(e.Name);
  foreach(XmlAttribute a in e.Attributes)if((hide&&a.Name!="id")||Secret(a.Name))a.Value="[СКРЫТО]";
  foreach(XmlNode ch in e.ChildNodes) {
   if(ch is XmlElement)Redact((XmlElement)ch,hide);
   else if(hide&&(ch.NodeType==XmlNodeType.Text||ch.NodeType==XmlNodeType.CDATA))ch.Value="[СКРЫТО]";
  }
 }
 public static string Sanitize(string xml,bool raw) {var x=Util.Xml(xml);if(!raw)Redact(x.DocumentElement,false);return x.OuterXml;}
 public static List<ParameterRow> Rows(string xml) {var x=Util.Xml(xml);var rows=new List<ParameterRow>();Walk(x.DocumentElement,"",rows);return rows;}
 static void Walk(XmlElement e,string path,List<ParameterRow> rows) {
  string id=e.GetAttribute("id");string here=String.IsNullOrEmpty(id)?path:(path.Length==0?id:path+"/"+id);
  bool leaf=!e.ChildNodes.OfType<XmlElement>().Any();
  if(e.Name!="Params"&&!new[]{"Col","Folder","ZipFolder"}.Contains(e.Name)) {
   var attrs=new Dictionary<string,string>();foreach(XmlAttribute a in e.Attributes)attrs[a.Name]=a.Value;
   string value=leaf?e.InnerText:"";rows.Add(new ParameterRow{path=here,type=e.Name,value=value,attributes=attrs});
  }
  foreach(XmlElement ch in e.ChildNodes.OfType<XmlElement>())Walk(ch,here,rows);
 }
 public static void Save(string xml,Journal j,string prefix) {
  if(Util.Xml(xml).DocumentElement.LocalName!="Params")throw new InvalidDataException("Получен XML другого типа, а не дерево Params.");
  string safe=Sanitize(xml,j.Raw);var rows=Rows(safe);if(rows.Count==0)throw new InvalidDataException("Дерево не содержит доступных параметров.");j.File(prefix+".xml",safe);j.File(prefix+".json",Util.Json(rows));
  var csv=new StringBuilder("\uFEFFПуть;Тип;Значение;Атрибуты\r\n");foreach(var r in rows)csv.AppendLine(String.Join(";",new[]{r.path,r.type,r.value,Util.Json(r.attributes)}.Select(v=>"\""+v.Replace("\"","\"\"")+"\"")));
  j.File(prefix+".csv",csv.ToString());j.Event("parameters",rows);j.Log("Параметры: получено строк "+rows.Count+". Файл "+prefix+".xml");
 }
}
}
