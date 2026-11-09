using System;
using System.IO;
using System.Linq;
using System.Threading;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Collections.Generic;
using System.Windows.Forms;

namespace Inntek.Videojet {
// Slots are generated/checked against the supplied x86 MSFT type libraries.
// Only the two SHA-256 allowlisted DLLs may supply these interfaces.
public sealed class ComRef:IDisposable {
 public IntPtr Ptr; public ComRef(IntPtr ptr) {if(ptr==IntPtr.Zero)throw new COMException("NULL COM pointer");Ptr=ptr;}
 public static ComRef Query(IntPtr p,string iid) {var g=new Guid(iid);IntPtr q;Check(Marshal.QueryInterface(p,ref g,out q));return new ComRef(q);}
 public static void Check(int hr) {if(hr<0)Marshal.ThrowExceptionForHR(hr);}
 public T At<T>(int offset) where T:class {return Marshal.GetDelegateForFunctionPointer(Marshal.ReadIntPtr(Marshal.ReadIntPtr(Ptr),offset/4*IntPtr.Size),typeof(T)) as T;}
 public int Int(int slot) {int x;Check(At<GetInt>(slot)(Ptr,out x));return x;}
 public short Short(int slot) {short x;Check(At<GetShort>(slot)(Ptr,out x));return x;}
 public double Double(int slot) {double x;Check(At<GetDouble>(slot)(Ptr,out x));return x;}
 public string Text(int slot) {IntPtr b;Check(At<GetPtr>(slot)(Ptr,out b));try{return b==IntPtr.Zero?"":Marshal.PtrToStringBSTR(b);}finally{if(b!=IntPtr.Zero)Marshal.FreeBSTR(b);}}
 public void Dispose() {if(Ptr!=IntPtr.Zero){Marshal.Release(Ptr);Ptr=IntPtr.Zero;}}
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int GetInt(IntPtr self,out int value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int GetShort(IntPtr self,out short value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int GetDouble(IntPtr self,out double value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int GetPtr(IntPtr self,out IntPtr value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int Item(IntPtr self,int index,out IntPtr value);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] public delegate int Save(IntPtr self,[MarshalAs(UnmanagedType.BStr)]string file);
}

[ComVisible(true),Guid("30b58696-a83c-4a1d-a87f-f923c16e5d41"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IErrorMonitor {
 [PreserveSig] int OnCommsError(int id);
 [PreserveSig] int OnProtocolError(int id,int reason);
}
[ComVisible(true),Guid("0fd14bed-f388-49cf-bb37-4fbe3889793e"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IResponseMonitor {
 [PreserveSig] int OnCommsError(int id);
 [PreserveSig] int OnProtocolError(int id,int reason);
 [PreserveSig] int OnSuccess(int id);
 [PreserveSig] int OnMessage(int id,[In]ref Guid iid,IntPtr message);
}
[ComVisible(true),Guid("1c03f20e-07a9-4254-bbe4-ccced0649c8f"),InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface ISendProgressMonitor { [PreserveSig] int OnSendProgress(int id,double progress); }

public class Reply {public bool Success,Failed;public int Messages;public string Error="";}
[ComVisible(true),ClassInterface(ClassInterfaceType.None)]
public class ResponseMonitor:IErrorMonitor,IResponseMonitor,ISendProgressMonitor {
 readonly object gate=new object();readonly Dictionary<int,Reply> replies=new Dictionary<int,Reply>();readonly NativeClient owner;public ResponseMonitor(NativeClient c){owner=c;}
 Reply Get(int id){if(!replies.ContainsKey(id))replies[id]=new Reply();return replies[id];}
 public Reply State(int id) {lock(gate){var r=Get(id);return new Reply{Success=r.Success,Failed=r.Failed,Messages=r.Messages,Error=r.Error};}}
 public int OnCommsError(int id){lock(gate){var r=Get(id);r.Failed=true;r.Error="Ошибка связи";}owner.J.Event("native_error",Util.Obj("id",id,"error","comms"));return 0;}
 public int OnProtocolError(int id,int reason){lock(gate){var r=Get(id);r.Failed=true;r.Error="Отказ протокола: "+reason;}owner.J.Event("native_error",Util.Obj("id",id,"reason",reason));return 0;}
 public int OnSuccess(int id){lock(gate)Get(id).Success=true;owner.J.Event("native_success",Util.Obj("id",id,"meaning","transaction confirmation; not proof of printing"));return 0;}
 public int OnMessage(int id,ref Guid iid,IntPtr message) {
  try{owner.ReadMessage(id,iid,message);lock(gate)Get(id).Messages++;}
  catch(Exception e){lock(gate){Get(id).Failed=true;Get(id).Error=e.Message;}owner.J.Event("decode_error",Util.Obj("id",id,"iid",iid.ToString(),"error",e.Message));}
  return 0;
 }
 public int OnSendProgress(int id,double progress){owner.J.Event("progress",Util.Obj("id",id,"raw_progress",progress));return 0;}
}

public sealed class NativeClient:IDisposable {
 public readonly Journal J;readonly Config C;readonly Func<bool> stop;ComRef session;ResponseMonitor monitor;int xmlIndex,infoResponses;
 public string CurrentJob="";public uint? StateFlags;
 public const string MasterIid="65fe7e6e-6373-470a-b15f-7369171878a3";
 public const string InfoIid="016827a4-422d-483b-9b3f-323557fdfa11";
 public const string TagIid="9ea3599c-164c-4f0b-95d6-89e468be6369";
 public const string XmlIid="69fe9248-7f94-405e-9c58-6c57f0b30ce2";
 public const string FileIid="456a427e-5a2b-41cb-9dcb-66bb8399e6b0";
 public NativeClient(Config c,Journal j,Func<bool> cancel){C=c;J=j;stop=cancel;}
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr LoadLibraryEx(string name,IntPtr reserved,uint flags);
 [DllImport("kernel32.dll",CharSet=CharSet.Ansi,ExactSpelling=true,SetLastError=true)] static extern IntPtr GetProcAddress(IntPtr module,string name);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int ClassFactory([In]ref Guid clsid,[In]ref Guid iid,out IntPtr factory);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Create(IntPtr self,IntPtr outer,[In]ref Guid iid,out IntPtr obj);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SetTcp(IntPtr self,[MarshalAs(UnmanagedType.BStr)]string host,int port);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int RequestInfo(IntPtr self,short count,IntPtr tags,[MarshalAs(UnmanagedType.IUnknown)]object monitor,out int id);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int SendXml(IntPtr self,[MarshalAs(UnmanagedType.BStr)]string xml,[MarshalAs(UnmanagedType.IUnknown)]object monitor,out int id);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Bitmap(IntPtr self,[MarshalAs(UnmanagedType.BStr)]string name,int flags,short head,short width,short height,[MarshalAs(UnmanagedType.IUnknown)]object monitor,out int id);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Upload(IntPtr self,int type,[MarshalAs(UnmanagedType.BStr)]string name,[MarshalAs(UnmanagedType.BStr)]string local,[MarshalAs(UnmanagedType.IUnknown)]object monitor,out int id);
 [UnmanagedFunctionPointer(CallingConvention.StdCall)] delegate int Select(IntPtr self,[MarshalAs(UnmanagedType.BStr)]string name,int flags,int limit,short count,IntPtr data,[MarshalAs(UnmanagedType.IUnknown)]object monitor,out int id);
 void CheckStop(){if(stop())throw new OperationCanceledException("Проверка остановлена пользователем.");}
 void Pump(int ms){var sw=Stopwatch.StartNew();while(sw.ElapsedMilliseconds<ms){CheckStop();Application.DoEvents();Thread.Sleep(10);}}
 void Wait(int id,bool message){var sw=Stopwatch.StartNew();while(sw.Elapsed.TotalSeconds<C.TimeoutSeconds){CheckStop();var r=monitor.State(id);if(r.Failed)throw new IOException(r.Error);if(message?r.Messages>0:r.Success)return;Pump(30);}throw new TimeoutException("Нет "+(message?"прикладного ответа":"подтверждения транзакции")+" на запрос "+id+" за "+C.TimeoutSeconds+" с.");}
 public void Connect(string dll) {
  if(!Util.Windows)throw new PlatformNotSupportedException("Native COM проверяется на Windows.");
  if(IntPtr.Size!=4)throw new InvalidOperationException("Нужен x86-процесс.");
  dll=Path.GetFullPath(dll);Inventory.ValidateDll(dll);J.Log("ZBC2.dll: "+dll);J.Log("Создание объекта через DllGetClassObject, без регистрации DLL.");
  IntPtr module=LoadLibraryEx(dll,IntPtr.Zero,8);if(module==IntPtr.Zero)throw new System.ComponentModel.Win32Exception(Marshal.GetLastWin32Error(),"Не удалось загрузить ZBC2.dll");
  // Keep the native module mapped until worker exit: callbacks/threads may outlive Release.
  IntPtr entry=GetProcAddress(module,"DllGetClassObject");if(entry==IntPtr.Zero)throw new EntryPointNotFoundException("DllGetClassObject");
  var factory=(ClassFactory)Marshal.GetDelegateForFunctionPointer(entry,typeof(ClassFactory));var clsid=new Guid(Inventory.MasterClsid);var fiid=new Guid("00000001-0000-0000-C000-000000000046");IntPtr p;
  ComRef.Check(factory(ref clsid,ref fiid,out p));
  using(var f=new ComRef(p)){var iid=new Guid(MasterIid);IntPtr m;ComRef.Check(f.At<Create>(12)(f.Ptr,IntPtr.Zero,ref iid,out m));session=new ComRef(m);}
  monitor=new ResponseMonitor(this);ComRef.Check(session.At<SetTcp>(16)(session.Ptr,C.Host,C.Port));var sw=Stopwatch.StartNew();
  while(sw.Elapsed.TotalSeconds<C.TimeoutSeconds){int state=session.Int(20);if(state==2){J.Event("connected",Util.Obj("transport","native","version",session.Int(32),"feature_mask",unchecked((uint)session.Int(36)).ToString("X8")));return;}Pump(100);}
  throw new TimeoutException("ZBC2 не перешла в CONNECTED. Проверьте IP/порт и текущего сетевого клиента принтера.");
 }
 public void Information() {
  int before=infoResponses;int[] tags={1,2,4,6,7,8};IntPtr p=Marshal.AllocCoTaskMem(tags.Length*4);int id;
  try{Marshal.Copy(tags,0,p,tags.Length);ComRef.Check(session.At<RequestInfo>(40)(session.Ptr,(short)tags.Length,p,monitor,out id));}finally{Marshal.FreeCoTaskMem(p);}
  Wait(id,true);if(infoResponses==before)throw new InvalidDataException("Нет распознанного информационного ответа.");
 }
 public void ReadParameters(){int before=xmlIndex;int id;string xml=Parameters.Query(C.FullParameters?"":"Devices/PHds/1/PrintInformation",true);J.Log(C.FullParameters?"Чтение полного доступного дерева Params…":"Чтение PrintInformation…");ComRef.Check(session.At<SendXml>(112)(session.Ptr,xml,monitor,out id));Wait(id,true);if(xmlIndex==before)throw new InvalidDataException("Нет распознанного XML-ответа параметров.");}
 public void Observe() {var sw=Stopwatch.StartNew();double next=3;while(sw.Elapsed.TotalSeconds<C.ObserveSeconds){Pump(100);if(sw.Elapsed.TotalSeconds>=next){Information();next=sw.Elapsed.TotalSeconds+3;}}}
 public void GetPreview(){Information();if(String.IsNullOrWhiteSpace(CurrentJob))throw new InvalidOperationException("Не получено текущее задание. Preview не запрашивается.");J.Event("preview_request",Util.Obj("observed_job",CurrentJob,"name",PreviewRecipe.FileName,"flags",PreviewRecipe.Flags,"head",PreviewRecipe.Head,"width",PreviewRecipe.Width,"height",PreviewRecipe.Height));int id;ComRef.Check(session.At<Bitmap>(56)(session.Ptr,PreviewRecipe.FileName,PreviewRecipe.Flags,PreviewRecipe.Head,PreviewRecipe.Width,PreviewRecipe.Height,monitor,out id));Wait(id,true);if(!File.Exists(Path.Combine(J.Folder,"preview.bmp")))throw new IOException("Ответ получен, но bitmap не передан. Проверьте имя задания и поддержку RequestBitmap.");}
 public void Mutate() {
  C.Validate();Information();if(!StateFlags.HasValue)throw new InvalidOperationException("Состояние аппарата неизвестно. Операция заблокирована.");
  if((StateFlags.Value&0x30)!=0)throw new InvalidOperationException("Аппарат сообщает PRINTING/IMAGING. Операция заблокирована: сначала приведите оборудование в подходящий тестовый режим.");
  int id;
  if(C.Operation=="upload") {
   J.Event("write_intent",Util.Obj("operation","upload_ciff","remote_name",C.RemoteName,"bytes",new FileInfo(C.JobFile).Length,"sha256",Util.FileHash(C.JobFile),"select_after_upload",false));
   ComRef.Check(session.At<Upload>(64)(session.Ptr,1,C.RemoteName,Path.GetFullPath(C.JobFile),monitor,out id));Wait(id,false);
   J.Event("job_result",Util.Obj("operation","upload","transaction_confirmed",true,"selection_confirmed",false,"printing_confirmed",false));
   J.Log("Передача подтверждена компонентом. Автоматический выбор задания не выполнялся.");
  } else {
   J.Event("write_intent",Util.Obj("operation","select_existing","name",C.JobName));
   ComRef.Check(session.At<Select>(84)(session.Ptr,C.JobName,0,0,0,IntPtr.Zero,monitor,out id));Wait(id,false);
   bool selected=false;var sw=Stopwatch.StartNew();while(sw.Elapsed.TotalSeconds<10){Information();if(String.Equals(CurrentJob,C.JobName,StringComparison.OrdinalIgnoreCase)){selected=true;break;}Pump(400);}
   J.Event("job_result",Util.Obj("operation","select","transaction_confirmed",true,"selection_confirmed",selected,"observed_job",CurrentJob,"printing_confirmed",false));
   if(!selected)throw new IOException("Транзакция подтверждена, но текущее имя задания не совпало с запрошенным. Печать не подтверждена.");
  }
 }
 public void ReadMessage(int id,Guid iid,IntPtr p) {
  J.Event("native_message",Util.Obj("id",id,"iid",iid.ToString()));
  if(iid.ToString()==InfoIid){using(var info=ComRef.Query(p,InfoIid)){
   int count=info.Int(12);if(count<0||count>1024)throw new InvalidDataException("Количество тегов вне лимита.");
   for(int i=0;i<count;i++){IntPtr t;ComRef.Check(info.At<ComRef.Item>(16)(info.Ptr,i,out t));if(t==IntPtr.Zero)continue;using(var tag=new ComRef(t))ReadTag(tag);}
   infoResponses++;
  }} else if(iid.ToString()==XmlIid) {
   using(var xml=ComRef.Query(p,XmlIid)) {string s=xml.Text(12);Parameters.Save(s,J,"parameters_"+(++xmlIndex).ToString("D2"));}
  } else if(iid.ToString()==FileIid) {
   using(var file=ComRef.Query(p,FileIid)) {
    int type=file.Int(12),size=file.Int(16);string remote=file.Text(20);if(size<0||size>16*1024*1024)throw new InvalidDataException("Файл ответа превышает лимит 16 MiB.");
    if(type!=3&&type!=7) {J.Event("file_ignored",Util.Obj("type",type,"name",remote,"bytes",size));return;}
    string dest=Path.Combine(J.Folder,type==3?"preview.bmp":"directory.xml");ComRef.Check(file.At<ComRef.Save>(28)(file.Ptr,dest));J.Event("file_received",Util.Obj("type",type,"name",remote,"local",Path.GetFileName(dest),"bytes",new FileInfo(dest).Length));
   }
  } else if(iid.ToString()=="8352f878-e0ce-40fa-a357-49c660250f7b")throw new FileNotFoundException("Принтер ответил FileNotFound.");
 }
 void ReadTag(ComRef tag) {
  int id;using(var baseTag=ComRef.Query(tag.Ptr,TagIid))id=baseTag.Int(12);
  var r=Util.Obj("tag",id);
  if(id==1)using(var t=ComRef.Query(tag.Ptr,"8508eac2-f58a-4d66-a6e3-4ee3b032a9f0")) {uint state=unchecked((uint)t.Int(16));StateFlags=state;r["state_flags"]=state;r["action_flags"]=unchecked((uint)t.Int(20));r["error_type"]=t.Short(24);r["error_text"]=t.Text(28);}
  else if(id==2)using(var t=ComRef.Query(tag.Ptr,"d5da9a73-fece-48f6-8c9b-8911ae631b5c")) {
   r["batch_count"]=unchecked((uint)t.Int(16));r["total_count"]=unchecked((uint)t.Int(20));string[] names={"throughput","nominal_speed","short_term_speed","short_term_efficiency","long_term_speed","long_term_efficiency","trend_speed","trend_efficiency"};for(int k=0;k<names.Length;k++)r[names[k]]=unchecked((ushort)t.Short(24+k*4));
  }
  else if(id==3||id==8)using(var t=ComRef.Query(tag.Ptr,"2443df83-9788-4e1a-8e27-eb04cbd8013c")){CurrentJob=t.Text(16);r["job"]=CurrentJob;r["job_flags"]=unchecked((uint)t.Int(20));r["products_remaining"]=unchecked((uint)t.Int(24));r["selection_ole_date"]=t.Double(28);}
  else if(id==4)using(var t=ComRef.Query(tag.Ptr,"0a83a2bf-dae6-4460-8e60-20fddcb24f69")){r["machine_name"]=t.Text(16);r["model"]=t.Text(20);}
  else if(id==6)using(var t=ComRef.Query(tag.Ptr,"7308b172-3b8c-49db-9763-e1fb53443ebf")){r["printer_ole_date"]=t.Double(16);}
  else r["typed_decoder"]="not implemented; tag retained";
  J.Event("information",r);
 }
 public void Dispose(){if(session!=null){session.Dispose();session=null;}GC.KeepAlive(monitor);}
}
}
