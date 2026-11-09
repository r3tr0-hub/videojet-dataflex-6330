using System;
using System.IO;
using System.Text;
using System.Linq;
using System.Diagnostics;
using System.Net.Sockets;
using System.Threading;
using System.Collections.Generic;

namespace Inntek.Videojet {
public class Frame {public byte Flags;public ushort Id,Block;public uint? Route;public byte[] Payload;public byte[] Bytes;}
public class Message {public ushort Id,Type;public byte[] Bytes;}
public static class Wire {
 public static Encoding LegacyEncoding=Encoding.Default;
 public static ushort Crc(byte[] bytes){uint crc=0;foreach(byte b in bytes){uint entry=(crc>>8)<<8;for(int i=0;i<8;i++)entry=((entry<<1)^((entry&0x8000)!=0?0x1021u:0))&0xffff;crc=((crc<<8)^entry^b)&0xffff;}return (ushort)crc;}
 public static byte[] Inner(ushort type,byte[] body){using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write(type);w.Write((uint)(body.Length+6));w.Write(body);return m.ToArray();}}
 public static byte[] Irq(params ushort[] tags){using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write((ushort)tags.Length);foreach(var t in tags)w.Write(t);return Inner(0x5001,m.ToArray());}}
 public static byte[] Cmv(ushort version,uint mask){using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write(version);w.Write(mask);return Inner(0x5020,m.ToArray());}}
 public static byte[] Counted(string s,bool unicode,int width){if(s.IndexOf('\0')>=0)throw new ArgumentException("NUL в строке");byte[] raw=unicode?Encoding.Unicode.GetBytes(s):LegacyEncoding.GetBytes(s);using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){int n=raw.Length==0?0:raw.Length+2-(raw.Length&1);if(width==2){if(n>65535)throw new ArgumentException("Слишком длинная строка");w.Write((ushort)n);}else if(width==4)w.Write(n);else throw new ArgumentException("Ширина длины");w.Write(raw);if(n>raw.Length)w.Write(new byte[n-raw.Length]);return m.ToArray();}}
 public static byte[] Encode(byte flags,ushort id,ushort block,byte[] payload,uint? route,int version){
  if((flags&0x80)!=0||((flags&0x20)!=0)!=route.HasValue)throw new InvalidDataException("Флаги заголовка");
  int n=(route.HasValue?14:10)+payload.Length+(((flags&0x10)!=0&&(payload.Length>0||version<=3))?2:0);if(n>65535)throw new InvalidDataException("Размер блока");
  using(var m=new MemoryStream())using(var w=new BinaryWriter(m)){w.Write((byte)0xa5);w.Write(flags);w.Write((ushort)n);w.Write(id);w.Write(block);if(route.HasValue)w.Write(route.Value);w.Write((byte)0xe4);byte sum=0;if((flags&0x10)!=0||version<=3){int total=0;foreach(byte b in m.ToArray())total+=b;sum=unchecked((byte)~total);}w.Write(sum);w.Write(payload);if((flags&0x10)!=0&&(payload.Length>0||version<=3))w.Write(Crc(payload));return m.ToArray();}
 }
 public static Frame Decode(byte[] b,int version){
  if(b.Length<10||b[0]!=0xa5||(b[1]&0x80)!=0||BitConverter.ToUInt16(b,2)!=b.Length)throw new InvalidDataException("Неверный заголовок A5");
  int h=(b[1]&0x20)!=0?14:10;if(b.Length<h||b[h-2]!=0xe4)throw new InvalidDataException("Неверная граница заголовка E4");
  if(((b[1]&0x10)!=0||version<=3)&&(b.Take(h).Sum(x=>(int)x)&255)!=255)throw new InvalidDataException("Checksum заголовка не совпала");
  byte[] raw=b.Skip(h).ToArray();if((b[1]&0x10)!=0&&raw.Length>0){if(raw.Length<2)throw new InvalidDataException("Усечённый CRC");byte[] p=raw.Take(raw.Length-2).ToArray();if(Crc(p)!=BitConverter.ToUInt16(raw,raw.Length-2))throw new InvalidDataException("CRC данных не совпал");raw=p;}
  return new Frame{Flags=b[1],Id=BitConverter.ToUInt16(b,4),Block=BitConverter.ToUInt16(b,6),Route=h==14?(uint?)BitConverter.ToUInt32(b,8):null,Payload=raw,Bytes=b};
 }
 public static string Text(BinaryReader r,bool unicode,int width){uint n=width==4?r.ReadUInt32():r.ReadUInt16();if((n&1)!=0||n>16*1024*1024||n>r.BaseStream.Length-r.BaseStream.Position)throw new InvalidDataException("Размер строки");byte[] b=r.ReadBytes((int)n);if(n==0)return "";if(unicode){if(n<2||b[n-1]!=0||b[n-2]!=0)throw new InvalidDataException("Нет UTF16 NUL");return new UnicodeEncoding(false,false,true).GetString(b,0,b.Length-2);}if(b[n-1]!=0)throw new InvalidDataException("Нет NUL");int length=Array.IndexOf(b,(byte)0);return LegacyEncoding.GetString(b,0,length);}
 public static List<Dictionary<string,object>> ParseIrp(byte[] bytes){
  var rows=new List<Dictionary<string,object>>();using(var m=new MemoryStream(bytes))using(var r=new BinaryReader(m)){
   if(bytes.Length<8||r.ReadUInt16()!=0x5002||r.ReadUInt32()!=bytes.Length)throw new InvalidDataException("Заголовок IRP");int count=r.ReadUInt16();if(count>1024)throw new InvalidDataException("Слишком много тегов");
   for(int i=0;i<count;i++){
    if(m.Length-m.Position<4)throw new InvalidDataException("Усечённый тег IRP");int tag=r.ReadUInt16(),n=r.ReadUInt16();if(n<4||n-4>m.Length-m.Position)throw new InvalidDataException("Граница тега IRP");var data=r.ReadBytes(n-4);var row=Util.Obj("tag",tag);
    using(var p=new MemoryStream(data))using(var x=new BinaryReader(p)){
     if(tag==1){row["state_flags"]=x.ReadUInt32();row["action_flags"]=x.ReadUInt32();row["error_type"]=x.ReadUInt16();row["error_text"]=Text(x,false,2);}
     else if(tag==2){row["batch_count"]=x.ReadUInt32();row["total_count"]=x.ReadUInt32();foreach(var name in new[]{"throughput","nominal_speed","short_term_speed","short_term_efficiency","long_term_speed","long_term_efficiency","trend_speed","trend_efficiency"})row[name]=x.ReadUInt16();}
     else if(tag==3||tag==8){row["job"]=Text(x,tag==8,tag==8?4:2);row["job_flags"]=x.ReadUInt32();row["products_remaining"]=x.ReadUInt32();row["selection_hmsdmy"]=Enumerable.Range(0,6).Select(k=>x.ReadUInt16()).ToArray();}
     else if(tag==4){row["machine_name"]=Text(x,false,2);row["model"]=Text(x,false,2);}
     else if(tag==5)row["lock_flags"]=x.ReadUInt32();
     else if(tag==6)row["printer_time_ymdhms"]=Enumerable.Range(0,6).Select(k=>x.ReadUInt16()).ToArray();
     else if(tag==7){row["version"]=x.ReadUInt16();row["features"]=x.ReadUInt32();}
     else if(tag==9){row["total_bytes"]=x.ReadUInt64();row["free_bytes"]=x.ReadUInt64();}
     else if(tag==10){row["iassure_supported"]=x.ReadByte()!=0;row["iassure_enabled"]=x.ReadByte()!=0;row["iassure_batch_prints"]=x.ReadUInt32();row["iassure_batch_failures"]=x.ReadUInt32();row["last_failure_hmsdmy"]=Enumerable.Range(0,6).Select(k=>x.ReadUInt16()).ToArray();}
     else{row["raw_sha256"]=Util.Hash(data);row["raw_size"]=data.Length;p.Position=p.Length;}
     if(p.Position!=p.Length)throw new InvalidDataException("Лишние байты тега "+tag);
    }rows.Add(row);
   }if(m.Position!=m.Length)throw new InvalidDataException("Лишние данные IRP");
  }return rows;
 }
}

// Bounded diagnostic profile. It sends ONLY IRQ, negotiated CMV, and generated
// collection-only XML reads. File/job/command send operations do not exist here.
public sealed class TcpReader:IDisposable {
 readonly Config C;readonly Journal J;readonly Func<bool> stop;TcpClient client;NetworkStream stream;ushort nextId;int version=2;uint features;int xmlIndex;
 readonly List<Message> messages=new List<Message>();readonly Dictionary<string,MemoryStream> partial=new Dictionary<string,MemoryStream>();readonly Dictionary<string,ushort> expected=new Dictionary<string,ushort>();
 readonly Dictionary<string,string> seen=new Dictionary<string,string>();readonly Queue<string> seenOrder=new Queue<string>();long received;
 public TcpReader(Config c,Journal j,Func<bool> cancel){C=c;J=j;stop=cancel;Wire.LegacyEncoding=c.LegacyCodePage==0?Encoding.Default:Encoding.GetEncoding(c.LegacyCodePage);}
 void Cancel(){if(stop())throw new OperationCanceledException("Проверка остановлена.");}
 void Send(byte[] b){Cancel();stream.WriteTimeout=3000;stream.Write(b,0,b.Length);J.Event("wire_tx",J.Raw?Util.Obj("bytes",b.Length,"hex",Util.Hex(b)):Util.Obj("bytes",b.Length,"sha256",Util.Hash(b)));}
 byte[] Exactly(int n,Stopwatch sw){byte[] b=new byte[n];int at=0;while(at<n){Cancel();if(sw.Elapsed.TotalSeconds>C.TimeoutSeconds)throw new TimeoutException("Нет полного ответа TCP за "+C.TimeoutSeconds+" с.");if(!stream.DataAvailable){if(client.Client.Poll(0,SelectMode.SelectRead)&&client.Client.Available==0)throw new EndOfStreamException("Принтер закрыл TCP-соединение.");Thread.Sleep(10);continue;}int k=stream.Read(b,at,n-at);if(k==0)throw new EndOfStreamException();at+=k;received+=k;if(received>64*1024*1024)throw new InvalidDataException("Лимит сеанса 64 MiB.");}return b;}
 Frame Receive(Stopwatch sw) {
  var start=Exactly(4,sw);if(start[0]!=0xa5)throw new InvalidDataException("Ответ не начинается с A5. Возможно, выбран другой сервис/порт.");int n=BitConverter.ToUInt16(start,2);if(n<10)throw new InvalidDataException("Размер блока <10");var b=start.Concat(Exactly(n-4,sw)).ToArray();var f=Wire.Decode(b,version);
  J.Event("wire_rx",J.Raw?Util.Obj("bytes",b.Length,"hex",Util.Hex(b)):Util.Obj("bytes",b.Length,"sha256",Util.Hash(b),"flags",f.Flags,"id",f.Id,"block",f.Block));return f;
 }
 void Accept(Frame f) {
  if((f.Flags&12)!=0)return;
  string group=f.Id+":"+((f.Flags&64)!=0)+":"+f.Route;string blockKey=group+":"+f.Block;string hash=Util.Hash(f.Bytes);
  byte ackFlags=(byte)(f.Flags|4);if(version<=3)ackFlags=(byte)(ackFlags&~16);uint? route=f.Route.HasValue?(uint?)((f.Route.Value>>16)|(f.Route.Value<<16)):null;
  if(seen.ContainsKey(blockKey)){if(seen[blockKey]!=hash)throw new InvalidDataException("Конфликтующий повтор блока.");Send(Wire.Encode(ackFlags,f.Id,f.Block,new byte[0],route,version));return;}
  if((f.Flags&1)!=0){if(f.Block!=0||partial.ContainsKey(group)||partial.Count>=8)throw new InvalidDataException("Неверный FIRST");partial[group]=new MemoryStream();expected[group]=0;}
  if(!partial.ContainsKey(group)||expected[group]!=f.Block)throw new InvalidDataException("Фрагменты пришли не по порядку.");
  var p=partial[group];if(p.Length+f.Payload.Length>16*1024*1024)throw new InvalidDataException("Сообщение >16 MiB");p.Write(f.Payload,0,f.Payload.Length);expected[group]++;
  seen[blockKey]=hash;seenOrder.Enqueue(blockKey);while(seenOrder.Count>128)seen.Remove(seenOrder.Dequeue());Send(Wire.Encode(ackFlags,f.Id,f.Block,new byte[0],route,version));
  if((f.Flags&2)!=0){var bytes=p.ToArray();p.Dispose();partial.Remove(group);expected.Remove(group);if(bytes.Length<6)throw new InvalidDataException("Усечённое внутреннее сообщение");messages.Add(new Message{Id=f.Id,Type=BitConverter.ToUInt16(bytes,0),Bytes=bytes});if(messages.Count>64)throw new InvalidDataException("Очередь ответов переполнена");}
 }
 Message Exchange(byte[] body) {
  if(body.Length>1986)throw new InvalidDataException("Запрос диагностики не должен превышать один блок.");ushort id=++nextId;byte flags=(byte)(0x13|(C.Lane?64:0));byte[] request=Wire.Encode(flags,id,0,body,null,version);var sw=Stopwatch.StartNew();bool acked=false;int tries=0;Send(request);
  while(sw.Elapsed.TotalSeconds<C.TimeoutSeconds){
   for(int i=0;i<messages.Count;i++)if(messages[i].Id==id){var msg=messages[i];messages.RemoveAt(i);if(msg.Type==0x500d)throw new IOException("ERR: "+(msg.Bytes.Length>=8?BitConverter.ToUInt16(msg.Bytes,6).ToString():"усечённый"));return msg;}
   var f=Receive(sw);
   if((f.Flags&12)!=0){if(f.Id==id&&f.Block==0&&((f.Flags^flags)&64)==0){if((f.Flags&8)!=0){if(++tries>2)throw new IOException("Повторные NAK от принтера.");Send(request);}else acked=true;}continue;}
   Accept(f);
   if(acked)J.Log("Получен блок прикладного ответа; транспортный ACK отдельно от результата запроса.");
  }throw new TimeoutException("Истёк таймаут прикладного ответа.");
 }
 public void Connect() {
  client=new TcpClient();var a=client.BeginConnect(C.Host,C.Port,null,null);try{if(!a.AsyncWaitHandle.WaitOne(3000))throw new TimeoutException("TCP connect >3 с");client.EndConnect(a);}finally{a.AsyncWaitHandle.Close();}stream=client.GetStream();
  var response=Exchange(Wire.Irq(1,7));if(response.Type!=0x5002)throw new InvalidDataException("На начальный IRQ нет IRP.");var rows=Wire.ParseIrp(response.Bytes);var cmv=rows.FirstOrDefault(r=>Util.I(r["tag"])==7);
  if(cmv!=null){version=Math.Min(11,Util.I(cmv["version"]));features=Convert.ToUInt32(cmv["features"])&0xffedf;if(version<2)throw new InvalidDataException("Версия протокола ниже2");}
  foreach(var row in rows)J.Event("information",row);
  if((features&2)!=0)Exchange(Wire.Cmv((ushort)version,features));
  J.Event("connected",Util.Obj("transport","tcp_diagnostic","version",version,"features",features,"lane",C.Lane,"legacy_codepage",Wire.LegacyEncoding.CodePage,"legacy_codepage_printer_confirmed",false,"profile","bounded read-only diagnostic; hardware validation pending"));
 }
 public void Information(){var r=Exchange(Wire.Irq(1,2,4,6,7,8,9,10));if(r.Type!=0x5002)throw new InvalidDataException("Ожидался IRP");foreach(var row in Wire.ParseIrp(r.Bytes))J.Event("information",row);}
 public void ReadParameters() {
  string q=Parameters.Query(C.FullParameters?"":"Devices/PHds/1/PrintInformation",true);bool unicode=(features&0x800)!=0;ushort type=version<3?(ushort)0x5012:(ushort)0x5112;var msg=Exchange(Wire.Inner(type,Wire.Counted(q,unicode,unicode?4:2)));
  if(msg.Type!=0x5013&&msg.Type!=0x5113)throw new InvalidDataException("Нет XML-ответа. Тип "+msg.Type.ToString("X4"));
  if(BitConverter.ToUInt32(msg.Bytes,2)!=msg.Bytes.Length)throw new InvalidDataException("Длина XML-сообщения");
  using(var b=new MemoryStream(msg.Bytes,6,msg.Bytes.Length-6))using(var r=new BinaryReader(b)){string xml=Wire.Text(r,unicode,unicode?4:2);if(b.Position!=b.Length)throw new InvalidDataException("Хвост XML-сообщения");Parameters.Save(xml,J,"parameters_"+(++xmlIndex).ToString("D2"));}
 }
 public void Observe(){var sw=Stopwatch.StartNew();double next=3;while(sw.Elapsed.TotalSeconds<C.ObserveSeconds){Cancel();Thread.Sleep(30);if(sw.Elapsed.TotalSeconds>=next){Information();next=sw.Elapsed.TotalSeconds+3;}}}
 public void Dispose(){foreach(var p in partial.Values)p.Dispose();if(stream!=null)stream.Dispose();if(client!=null)client.Close();}
}
}
