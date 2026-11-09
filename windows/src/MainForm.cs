using System;
using System.IO;
using System.IO.Compression;
using System.Linq;
using System.Text;
using System.Drawing;
using System.Diagnostics;
using System.Collections;
using System.Collections.Generic;
using System.Windows.Forms;

namespace Inntek.Videojet {
public class MainForm:Form {
 readonly bool demo;TextBox host,dll,jobFile,jobName,remote,filter;NumericUpDown port,seconds,timeout;ComboBox mode;CheckBox full,raw,lane,changes;
 Button read,preview,stop,export,open,upload,select;Label status,banner;TabControl tabs;DataGridView states,parameters,pc;TextBox log;PictureBox image;
 Process child;Timer timer;string folder;long eventOffset;DateTime started,stopRequested;bool stopping;List<ParameterRow> rows=new List<ParameterRow>();
 Dictionary<string,DataGridViewRow> stateRows=new Dictionary<string,DataGridViewRow>();string observedJob="";readonly List<Control> locked=new List<Control>();
 static readonly Dictionary<string,string> Names=new Dictionary<string,string>{
  {"state_flags","Флаги состояния"},{"action_flags","Флаги действий"},{"error_type","Тип ошибки"},{"error_text","Ошибка / предупреждение"},
  {"batch_count","Счётчик партии"},{"total_count","Общий счётчик"},{"throughput","Темп, исходное значение"},{"nominal_speed","Номинальная скорость, raw"},
  {"short_term_speed","Краткосрочная скорость, raw"},{"short_term_efficiency","Краткосрочная эффективность, raw"},{"long_term_speed","Долгосрочная скорость, raw"},
  {"long_term_efficiency","Долгосрочная эффективность, raw"},{"trend_speed","Тренд скорости, raw"},{"trend_efficiency","Тренд эффективности, raw"},
  {"job","Текущее задание"},{"job_flags","Флаги задания"},{"products_remaining","Осталось продукции"},{"machine_name","Имя принтера"},{"model","Модель"},
  {"printer_ole_date","Время принтера, OLE DATE"},{"selection_ole_date","Время выбора задания, OLE DATE"},{"printer_time_ymdhms","Время принтера: год/месяц/день/ч/м/с"},
  {"selection_hmsdmy","Выбор: ч/м/с/день/месяц/год"},{"free_bytes","Свободно байт"},{"total_bytes","Всего байт"},{"iassure_supported","iAssure поддерживается"},
  {"iassure_enabled","iAssure включён"},{"iassure_batch_prints","iAssure: отпечатки партии"},{"iassure_batch_failures","iAssure: ошибки партии"},
  {"last_failure_hmsdmy","iAssure: время последней ошибки"},{"version","Версия протокола"},{"features","Маска возможностей"}
 };
 public MainForm(bool demonstration) {
  demo=demonstration;Text="VideojetResearch · Videojet 6330 Diagnostics "+Program.Version;ClientSize=new Size(1170,790);MinimumSize=new Size(1050,740);StartPosition=FormStartPosition.CenterScreen;Font=new Font("Segoe UI",10);BackColor=Color.FromArgb(243,246,249);AutoScaleMode=AutoScaleMode.Dpi;
  var root=new TableLayoutPanel{Dock=DockStyle.Fill,RowCount=4,ColumnCount=1,Padding=new Padding(14)};root.RowStyles.Add(new RowStyle(SizeType.Absolute,48));root.RowStyles.Add(new RowStyle(SizeType.Absolute,170));root.RowStyles.Add(new RowStyle(SizeType.Percent,100));root.RowStyles.Add(new RowStyle(SizeType.Absolute,34));Controls.Add(root);
  var heading=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=2};heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,65));heading.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,35));heading.Controls.Add(new Label{Text="VIDEOJET 6330  /  Диагностика",AutoSize=true,Font=new Font("Segoe UI",18,FontStyle.Bold),ForeColor=Color.FromArgb(20,70,100),Anchor=AnchorStyles.Left},0,0);banner=new Label{Text=demo?"ДЕМОНСТРАЦИЯ · данные не с принтера":"По умолчанию — только чтение",AutoSize=true,ForeColor=demo?Color.DarkOrange:Color.DarkGreen,Anchor=AnchorStyles.Right};heading.Controls.Add(banner,1,0);root.Controls.Add(heading,0,0);
  var settings=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=8,RowCount=4};for(int i=0;i<8;i++)settings.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,i==1||i==5?20:10));
  foreach(int h in new[]{36,36,38,46})settings.RowStyles.Add(new RowStyle(SizeType.Absolute,h));
  settings.Controls.Add(L("IP принтера"),0,0);host=new TextBox{Text="192.0.2.10",Dock=DockStyle.Fill};settings.Controls.Add(host,1,0);settings.Controls.Add(L("Порт"),2,0);port=new NumericUpDown{Minimum=1,Maximum=65535,Value=3001,Dock=DockStyle.Fill};settings.Controls.Add(port,3,0);
  settings.Controls.Add(L("Режим"),4,0);mode=new ComboBox{DropDownStyle=ComboBoxStyle.DropDownList,Dock=DockStyle.Fill};mode.Items.AddRange(new object[]{"Авто","ZBC2.dll","TCP-чтение"});mode.SelectedIndex=0;settings.Controls.Add(mode,5,0);settings.SetColumnSpan(mode,3);
  settings.Controls.Add(L("ZBC2.dll"),0,1);dll=new TextBox{Dock=DockStyle.Fill};settings.Controls.Add(dll,1,1);settings.SetColumnSpan(dll,5);var browse=Btn("Выбрать…",()=>{using(var d=new OpenFileDialog{Filter="ZBC2.dll|ZBC2.dll|DLL|*.dll",Title="Выберите Data\\ZBC2.dll из распакованного CLARiCOM"})if(d.ShowDialog()==DialogResult.OK)dll.Text=d.FileName;});settings.Controls.Add(browse,6,1);settings.SetColumnSpan(browse,2);
  var opts=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false,AutoScroll=true};opts.Controls.Add(L("Наблюдение, с:"));seconds=new NumericUpDown{Minimum=0,Maximum=300,Value=20,Width=63};opts.Controls.Add(seconds);opts.Controls.Add(L("Таймаут, с:"));timeout=new NumericUpDown{Minimum=3,Maximum=90,Value=30,Width=63};opts.Controls.Add(timeout);full=new CheckBox{Text="Все доступные параметры",Checked=true,AutoSize=true};raw=new CheckBox{Text="Полные ответы и трафик",AutoSize=true};lane=new CheckBox{Text="TCP: канал 0x40",AutoSize=true};opts.Controls.Add(full);opts.Controls.Add(raw);opts.Controls.Add(lane);settings.Controls.Add(opts,0,2);settings.SetColumnSpan(opts,8);
  var bar=new FlowLayoutPanel{Dock=DockStyle.Fill,WrapContents=false,AutoScroll=true};read=Btn("Проверить всё (чтение)",()=>Start("read"));read.BackColor=Color.FromArgb(20,91,132);read.ForeColor=Color.White;read.Width=215;preview=Btn("Получить preview",()=>Start("preview"));stop=Btn("Остановить",Stop);stop.Enabled=false;export=Btn("Собрать ZIP",Export);open=Btn("Папка отчёта",()=>{if(folder!=null)Process.Start(folder);});bar.Controls.AddRange(new Control[]{read,preview,stop,export,open});settings.Controls.Add(bar,0,3);settings.SetColumnSpan(bar,8);root.Controls.Add(settings,0,1);
  tabs=new TabControl{Dock=DockStyle.Fill};states=Grid("Показатель","Значение","Время UTC");AddTab("Состояние и счётчики",states);parameters=Grid("Путь","Тип","Значение","Свойства");var paramPanel=new TableLayoutPanel{Dock=DockStyle.Fill,RowCount=2};paramPanel.RowStyles.Add(new RowStyle(SizeType.Absolute,35));paramPanel.RowStyles.Add(new RowStyle(SizeType.Percent,100));filter=new TextBox{Dock=DockStyle.Fill};filter.TextChanged+=(s,e)=>RenderParameters();paramPanel.Controls.Add(filter,0,0);paramPanel.Controls.Add(parameters,0,1);AddTab("Параметры",paramPanel);
  pc=Grid("Компонент","Реестр","Найден","Путь / SHA-256");AddTab("ПО на ПК",pc);
  image=new PictureBox{Dock=DockStyle.Fill,SizeMode=PictureBoxSizeMode.Zoom,BackColor=Color.White};AddTab("Предпросмотр",image);
  BuildJobTab();log=new TextBox{Dock=DockStyle.Fill,Multiline=true,ReadOnly=true,ScrollBars=ScrollBars.Both,WordWrap=false,Font=new Font("Consolas",9)};AddTab("Журнал",log);root.Controls.Add(tabs,0,2);status=new Label{Dock=DockStyle.Fill,Text="Укажите актуальный IP. Адрес 192.0.2.10 взят из прежнего снимка и требует проверки.",TextAlign=ContentAlignment.MiddleLeft};root.Controls.Add(status,0,3);
  locked.AddRange(new Control[]{host,port,mode,dll,browse,seconds,timeout,full,raw,lane,read,preview,upload,select,changes,jobName,jobFile,remote});
  timer=new Timer{Interval=200};timer.Tick+=(s,e)=>TickWorker();FormClosing+=(s,e)=>{if(child!=null&&!child.HasExited){if(MessageBox.Show("Остановить диагностику и закрыть окно? При передаче файла результат может остаться неопределённым.","Диагностика",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes){e.Cancel=true;return;}try{child.Kill();}catch{} }};
  if(demo)Shown+=(s,e)=>Demo();
 }
 Label L(string s){return new Label{Text=s,AutoSize=true,Anchor=AnchorStyles.Left,Margin=new Padding(3,6,3,3)};}
 Button Btn(string s,Action click){var b=new Button{Text=s,AutoSize=false,Width=145,Height=32,FlatStyle=FlatStyle.Flat,Margin=new Padding(3)};b.Click+=(o,e)=>{try{click();}catch(Exception ex){MessageBox.Show(this,ex.Message,"Диагностика",MessageBoxButtons.OK,MessageBoxIcon.Error);}};return b;}
 DataGridView Grid(params string[] cols){var g=new DataGridView{Dock=DockStyle.Fill,ReadOnly=true,AllowUserToAddRows=false,AllowUserToDeleteRows=false,RowHeadersVisible=false,AutoSizeColumnsMode=DataGridViewAutoSizeColumnsMode.Fill,BackgroundColor=Color.White,SelectionMode=DataGridViewSelectionMode.FullRowSelect,MultiSelect=true};foreach(var c in cols)g.Columns.Add(c,c);return g;}
 void AddTab(string title,Control childControl){var t=new TabPage(title);t.Padding=new Padding(6);t.Controls.Add(childControl);tabs.TabPages.Add(t);}
 void BuildJobTab(){
  var t=new TableLayoutPanel{Dock=DockStyle.Fill,ColumnCount=3,RowCount=8,Padding=new Padding(12)};t.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,220));t.ColumnStyles.Add(new ColumnStyle(SizeType.Percent,100));t.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute,180));
  var info=L("Только готовый совместимый CIFF. Кнопки ниже изменяют файлы / активное задание принтера.\nПередача файла и выбор задания — два отдельных действия. Команды запуска печати отсутствуют.");info.AutoSize=true;t.Controls.Add(info,0,0);t.SetColumnSpan(info,3);
  t.Controls.Add(L("Локальный .ciff"),0,1);jobFile=new TextBox{Dock=DockStyle.Fill};t.Controls.Add(jobFile,1,1);t.Controls.Add(Btn("Выбрать файл…",()=>{using(var d=new OpenFileDialog{Filter="Готовое задание CIFF|*.ciff"})if(d.ShowDialog()==DialogResult.OK){jobFile.Text=d.FileName;remote.Text="DIAG_"+DateTime.Now.ToString("yyyyMMdd_HHmmss")+".ciff";}}),2,1);
  t.Controls.Add(L("Имя файла на принтере"),0,2);remote=new TextBox{Dock=DockStyle.Fill,Text="DIAG_"+DateTime.Now.ToString("yyyyMMdd_HHmmss")+".ciff"};t.Controls.Add(remote,1,2);upload=Btn("Передать файл",()=>Start("upload"));t.Controls.Add(upload,2,2);
  t.Controls.Add(L("Существующее задание"),0,3);jobName=new TextBox{Dock=DockStyle.Fill};t.Controls.Add(jobName,1,3);select=Btn("Выбрать задание",()=>Start("select"));t.Controls.Add(select,2,3);
  t.Controls.Add(Btn("Из текущего",()=>jobName.Text=observedJob),1,4);
  changes=new CheckBox{Text="Разрешаю выбранную операцию изменения задания",AutoSize=true,ForeColor=Color.DarkRed};t.Controls.Add(changes,0,5);t.SetColumnSpan(changes,3);
  var note=L("Операции job доступны через исследованную ZBC2.dll. Файл может заменить одноимённый файл на принтере.\nВыбор существующего задания меняет активное задание. После отмены/таймаута сначала проверьте аппарат, затем решайте о повторе.\nПри неизвестном состоянии либо PRINTING/IMAGING клиент блокирует эти действия. Это дополнительная проверка, не блокировка механизма принтера.");t.Controls.Add(note,0,6);t.SetColumnSpan(note,3);AddTab("Проверка job",t);
 }
 Config Make(string op){return new Config{Host=host.Text.Trim(),Port=(int)port.Value,Dll=dll.Text.Trim(),Mode=new[]{"auto","native","tcp"}[mode.SelectedIndex],ObserveSeconds=(int)seconds.Value,TimeoutSeconds=(int)timeout.Value,FullParameters=full.Checked,Raw=raw.Checked,Lane=lane.Checked,Operation=op,AllowChanges=changes.Checked,JobFile=jobFile.Text.Trim(),JobName=jobName.Text.Trim(),RemoteName=remote.Text.Trim()};}
 void Start(string operation){
  if(demo)throw new InvalidOperationException("Демонстрационный режим: подключения и изменения отключены. Запустите START.cmd.");
  if(child!=null&&!child.HasExited)throw new InvalidOperationException("Дождитесь завершения или нажмите Остановить.");
  Config c=Make(operation);if(operation=="read"||operation=="preview")c.AllowChanges=false;c.Validate();
  if(c.Raw&&MessageBox.Show(this,"Полные ответы могут содержать параметры сети, тексты заданий и защищённые значения. Сохранить их в локальный отчёт?","Полные данные",MessageBoxButtons.YesNo,MessageBoxIcon.Question)!=DialogResult.Yes)return;
  if(operation=="upload"||operation=="select"){
   string target=operation=="upload"?"ПЕРЕДАТЬ файл «"+c.RemoteName+"»\nВозможна замена одноимённого файла.":"ВЫБРАТЬ существующее задание «"+c.JobName+"»\nАктивное задание будет изменено.";
   if(MessageBox.Show(this,target+"\n\nПринтер "+c.Host+":"+c.Port+"\nПродолжить?","Проверка задания",MessageBoxButtons.YesNo,MessageBoxIcon.Warning)!=DialogResult.Yes)return;
   c.Mode="native";
  }
  string baseDir=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"Reports");try{Directory.CreateDirectory(baseDir);}catch{baseDir=Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"VideojetResearch","VideojetDiagnostics","Reports");Directory.CreateDirectory(baseDir);}
  folder=Path.Combine(baseDir,DateTime.Now.ToString("yyyyMMdd_HHmmss_fff")+"_"+operation);Directory.CreateDirectory(folder);c.Output=folder;c.Save(Path.Combine(folder,"request.xml"));
  states.Rows.Clear();stateRows.Clear();parameters.Rows.Clear();rows.Clear();pc.Rows.Clear();log.Clear();observedJob="";eventOffset=0;stopping=false;if(image.Image!=null){image.Image.Dispose();image.Image=null;}started=DateTime.UtcNow;
  var psi=new ProcessStartInfo(Application.ExecutablePath,"--worker \""+Path.Combine(folder,"request.xml")+"\""){UseShellExecute=false,CreateNoWindow=true,WorkingDirectory=AppDomain.CurrentDomain.BaseDirectory};child=Process.Start(psi);
  foreach(var ctl in locked)ctl.Enabled=false;stop.Enabled=true;export.Enabled=false;changes.Checked=false;status.Text="Выполняется проверка. Можно остановить. Отчёт: "+folder;timer.Start();
 }
 void Stop(){if(child==null||child.HasExited)return;File.WriteAllText(Path.Combine(folder,"STOP"),"stop",Util.Utf8);stopRequested=DateTime.UtcNow;stopping=true;stop.Enabled=false;status.Text="Остановка…";}
 void TickWorker(){
  try{ReadEvents();if(child==null)return;
   double limit=(double)seconds.Value+4*(double)timeout.Value+45;
   if(!child.HasExited&&((stopping&&(DateTime.UtcNow-stopRequested).TotalSeconds>5)||(DateTime.UtcNow-started).TotalSeconds>limit)){
    child.Kill();Log("Рабочий процесс прерван по таймауту. Результат последней операции может быть неопределённым.");
    File.WriteAllText(Path.Combine(folder,"worker_timeout.txt"),"Worker stopped by parent. Inspect printer before retrying a modifying operation.",Util.Utf8);
   }
   if(child.HasExited){ReadEvents();timer.Stop();int code=child.ExitCode;status.Text=code==0?"Проверка завершена. Сохраните ZIP отчёта.":"Завершено с замечаниями / ошибкой (код "+code+"). Сохраните ZIP: там уже собранные данные.";
    foreach(var ctl in locked)ctl.Enabled=true;stop.Enabled=false;export.Enabled=true;child.Dispose();child=null;
    string p=Path.Combine(folder,"preview.bmp");if(File.Exists(p))try{using(var s=File.OpenRead(p))using(var im=Image.FromStream(s)){if(im.Width<=8192&&im.Height<=8192)image.Image=new Bitmap(im);}}catch(Exception e){Log("Не удалось показать bitmap: "+e.Message);}
   }
  }catch(Exception e){Log("Ошибка чтения журнала: "+e.Message);}
 }
 void ReadEvents(){string p=Path.Combine(folder,"events.jsonl");if(!File.Exists(p))return;using(var f=new FileStream(p,FileMode.Open,FileAccess.Read,FileShare.ReadWrite)){f.Position=eventOffset;using(var m=new MemoryStream()){f.CopyTo(m);var bytes=m.ToArray();int end=Array.LastIndexOf(bytes,(byte)10);if(end<0)return;string s=Util.Utf8.GetString(bytes,0,end+1);eventOffset+=end+1;foreach(string line in s.Split(new char[]{'\n'}))if(!String.IsNullOrWhiteSpace(line))Event(Util.Parse(line));}}}
 void Event(Dictionary<string,object> e){
  string kind=Util.S(e["kind"]),utc=Util.S(e["utc"]);object data=e["data"];
  if(kind=="information"){
   var r=(Dictionary<string,object>)data;foreach(var v in r){if(v.Key=="tag")continue;string title=Names.ContainsKey(v.Key)?Names[v.Key]:v.Key;string value=v.Value is Array?Util.Json(v.Value):Util.S(v.Value);
    if(v.Key=="state_flags"){uint flags=Convert.ToUInt32(v.Value);string[] names={"PWRDWN","ONLINE","FAULT","WARNING","IMAGING","PRINTING","WAITINGDATA"};value="0x"+flags.ToString("X8")+" · "+String.Join(", ",Enumerable.Range(0,7).Where(i=>(flags&(1u<<i))!=0).Select(i=>names[i]));}
    if(v.Key=="job")observedJob=value;
    if(!stateRows.ContainsKey(v.Key)){int i=states.Rows.Add(title,value,utc);stateRows[v.Key]=states.Rows[i];}else{stateRows[v.Key].Cells[1].Value=value;stateRows[v.Key].Cells[2].Value=utc;}
   }
  }else if(kind=="parameters"){
   rows=new List<ParameterRow>();foreach(var item in (IEnumerable)data){var r=(Dictionary<string,object>)item;rows.Add(new ParameterRow{path=Util.S(r["path"]),type=Util.S(r["type"]),value=Util.S(r["value"]),attributes=((Dictionary<string,object>)r["attributes"]).ToDictionary(v=>v.Key,v=>Util.S(v.Value))});}RenderParameters();
  }else if(kind=="inventory"){
   var r=(Dictionary<string,object>)data;foreach(var item in (IEnumerable)r["com_registrations"]){var q=(Dictionary<string,object>)item;pc.Rows.Add(q.ContainsKey("name")?q["name"]:"Ошибка",q.ContainsKey("view")?q["view"]:"",q.ContainsKey("registered")?q["registered"]:false,q.ContainsKey("server")?q["server"]:q.ContainsKey("error")?q["error"]:"");}
  }
  if(kind=="phase")status.Text=Util.S(data)+"…";
  if(kind!="wire_tx"&&kind!="wire_rx"&&kind!="information"&&kind!="parameters"&&kind!="inventory")Log(utc+"  "+kind+"  "+(data is string?Util.S(data):Util.Json(data)));
 }
 void RenderParameters(){parameters.Rows.Clear();string q=filter.Text.Trim();foreach(var r in rows)if(q.Length==0||(r.path+" "+r.value).IndexOf(q,StringComparison.OrdinalIgnoreCase)>=0)parameters.Rows.Add(r.path,r.type,r.value,Util.Json(r.attributes));}
 void Log(string s){if(log.TextLength>300000)log.Text=log.Text.Substring(log.TextLength-150000);log.AppendText(s+Environment.NewLine);}
 void Export(){if(folder==null)throw new InvalidOperationException("Сначала выполните проверку.");if(child!=null&&!child.HasExited)throw new InvalidOperationException("Сначала завершите проверку.");using(var d=new SaveFileDialog{Filter="Диагностический отчёт ZIP|*.zip",FileName="Videojet6330_Diagnostics_"+Path.GetFileName(folder)+".zip"})if(d.ShowDialog()==DialogResult.OK){if(Path.GetFullPath(d.FileName).StartsWith(Path.GetFullPath(folder)+Path.DirectorySeparatorChar,StringComparison.OrdinalIgnoreCase))throw new InvalidOperationException("ZIP нужно сохранить вне папки текущего отчёта.");if(File.Exists(d.FileName))File.Delete(d.FileName);ZipFile.CreateFromDirectory(folder,d.FileName,CompressionLevel.Optimal,false);MessageBox.Show(this,"Отчёт готов:\n"+d.FileName,"Диагностика",MessageBoxButtons.OK,MessageBoxIcon.Information);}}
 void Demo(){foreach(var c in locked)c.Enabled=false;stop.Enabled=false;export.Enabled=false;open.Enabled=false;Event(Util.Obj("utc",DateTime.UtcNow.ToString("o"),"kind","information","data",Util.Obj("tag",1,"state_flags",10,"error_type",1,"error_text","ДЕМО: пример предупреждения")));Event(Util.Obj("utc",DateTime.UtcNow.ToString("o"),"kind","information","data",Util.Obj("tag",2,"batch_count",12345,"total_count",678901,"throughput",120)));Event(Util.Obj("utc",DateTime.UtcNow.ToString("o"),"kind","information","data",Util.Obj("tag",8,"job","DEMO_ONLY.ciff")));status.Text="Демонстрация интерфейса. Сеть, DLL и принтер не используются.";}
}
}
