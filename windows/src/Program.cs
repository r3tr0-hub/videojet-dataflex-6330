using System;
using System.IO;
using System.Linq;
using System.Diagnostics;
using System.Text;
using System.Threading;
using System.Collections.Generic;
using System.Windows.Forms;

namespace Inntek.Videojet {
public static class Program {
 public const string Version="0.1.2";
 [STAThread] public static int Main(string[] args){
  try{
   if(args.Length>=2&&args[0]=="--worker")return Worker(args[1]);
   if(args.Length>=1&&args[0]=="--selftest"){var p=args.Length>=2?args[1]:Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"selftest.txt");return SelfTests.Run(p);}
   Application.EnableVisualStyles();Application.SetCompatibleTextRenderingDefault(false);Application.Run(new MainForm(args.Contains("--demo")));return 0;
  }catch(Exception e){try{string dest=args.Length>=2&&args[0]=="--worker"?Path.GetDirectoryName(args[1]):AppDomain.CurrentDomain.BaseDirectory;File.WriteAllText(Path.Combine(dest,"startup_error.txt"),e.ToString(),Util.Utf8);}catch{}if(!args.Contains("--worker"))try{MessageBox.Show(e.Message,"Videojet Diagnostics",MessageBoxButtons.OK,MessageBoxIcon.Error);}catch{}return 1;}
 }
 static int Worker(string configPath){
  Config c=Config.Load(configPath);Directory.CreateDirectory(c.Output);int exit=1;
  using(var j=new Journal(c.Output,c.Raw)) {
   var steps=new List<object>();Func<bool> stop=()=>File.Exists(Path.Combine(c.Output,"STOP"));
   Action<string,Action> phase=(name,action)=>{j.Event("phase",name);var sw=Stopwatch.StartNew();try{action();steps.Add(Util.Obj("phase",name,"status","ok","elapsed_ms",sw.ElapsedMilliseconds));}catch(Exception e){steps.Add(Util.Obj("phase",name,"status","failed","error",e.Message,"elapsed_ms",sw.ElapsedMilliseconds));throw;}};
   try {
    j.Log("VideojetResearch Videojet Diagnostics "+Version+". Цель "+c.Host+":"+c.Port);
    try{phase("Сведения ПК",()=>Inventory.Collect(c,j));}catch(Exception e){j.Event("partial","Не удалось собрать все сведения ПК: "+e.Message+". Проверка связи продолжается.");}
    phase("TCP-порт",()=>{if(!Inventory.TcpProbe(c,j))throw new IOException("TCP-порт недоступен. Проверьте адрес, кабель, маршрут и порт в меню принтера.");});
    string dll=c.Mode=="tcp"?null:Inventory.FindDll(c);string mode=c.Mode=="auto"?(dll==null?"tcp":"native"):c.Mode;
    j.Log("Режим текущего запуска: "+mode+". Параллельные соединения не создаются.");
    if(mode=="native") {
     if(dll==null)throw new FileNotFoundException("Не найдена ZBC2.dll. Укажите файл Data/ZBC2.dll из CLARiCOM или выберите TCP-чтение.");
     using(var n=new NativeClient(c,j,stop)) {
      phase("Сеанс ZBC2",()=>n.Connect(dll));
      if(c.Operation=="read") {
       phase("Состояние и счётчики",n.Information);
       // A parameter failure must not discard already collected telemetry.
       try{phase("Дерево параметров",n.ReadParameters);}catch(Exception e){j.Event("partial",e.Message);}
       phase("Наблюдение счётчиков",n.Observe);
      }else if(c.Operation=="preview")phase("Предпросмотр текущего задания",n.GetPreview);
      else phase(c.Operation=="upload"?"Передача файла задания":"Выбор задания",n.Mutate);
     }
    }else {
     if(c.Operation!="read")throw new InvalidOperationException("В TCP-профиле есть только чтение. Для preview/job выберите ZBC2.dll.");
     using(var n=new TcpReader(c,j,stop)) {
      phase("Сеанс TCP/IRQ",n.Connect);phase("Состояние и счётчики",n.Information);
      try{phase("Дерево параметров",n.ReadParameters);}catch(Exception e){j.Event("partial",e.Message);throw new IOException("Часть данных получена; XML-чтение не завершилось. Сеанс закрыт, чтобы не смешивать поздние ответы. "+e.Message,e);}
      phase("Наблюдение счётчиков",n.Observe);
     }
    }
    exit=steps.OfType<Dictionary<string,object>>().Any(s=>Util.S(s["status"])=="failed")?2:0;
   }catch(OperationCanceledException e){j.Event("cancelled",e.Message);exit=3;}
   catch(Exception e){j.Event("error",Util.Obj("message",e.Message,"type",e.GetType().FullName,"hresult",e.HResult.ToString("X8")));exit=1;}
   finally {
    string outcome=exit==0?"Завершено":exit==2?"Получены частичные данные":exit==3?"Остановлено":"Проверка завершилась с ошибкой";
    var result=Util.Obj("version",Version,"utc",DateTime.UtcNow.ToString("o"),"target",c.Host+":"+c.Port,"operation",c.Operation,"outcome",outcome,"exit_code",exit,"changes_enabled",c.AllowChanges,"printing_confirmed",false,"steps",steps);
    j.File("result.json",Util.Json(result));j.Event("finished",result);WriteHtml(j,result);j.Log(outcome+". Данные сохранены в "+j.Folder);
   }
  }return exit;
 }
 static void WriteHtml(Journal j,Dictionary<string,object> result){
  var b=new StringBuilder("<!doctype html><html lang='ru'><meta charset='utf-8'><title>Диагностика Videojet</title><style>body{font:16px/1.5 Segoe UI,Arial;max-width:1150px;margin:40px auto;padding:0 20px;color:#203040}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ccd6df;padding:8px;text-align:left;vertical-align:top}th{background:#eaf1f7}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f3f6f8;padding:12px}h1,h2{color:#18567a}</style>");
  b.Append("<h1>Videojet DataFlex 6330 — диагностика</h1><p>"+Util.Escape(Util.S(result["outcome"]))+" · "+Util.Escape(Util.S(result["target"]))+"</p><pre>"+Util.Escape(Util.Json(result))+"</pre>");
  b.Append("<p>Результат отражает ответы текущей проверки. Открытый TCP-порт не равен рабочему сеансу, а подтверждение передачи задания не равно печати.</p><h2>Журнал</h2><table><tr><th>UTC</th><th>Событие</th><th>Данные</th></tr>");
  foreach(var e in j.Events)b.Append("<tr><td>"+Util.Escape(Util.S(e["utc"]))+"</td><td>"+Util.Escape(Util.S(e["kind"]))+"</td><td><pre>"+Util.Escape(e["data"] is string?Util.S(e["data"]):Util.Json(e["data"]))+"</pre></td></tr>");
  b.Append("</table></html>");j.File("report.html",b.ToString());
 }
}
}
