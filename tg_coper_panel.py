"""TG_Coper DarkGlass — glass UI, Telegram channel monitoring and automatic copying."""
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox
from threading import Thread
import asyncio, concurrent.futures, json, re, urllib.request, urllib.error, os
from datetime import datetime
from PIL import Image, ImageTk, ImageEnhance, ImageDraw
from copy_engine import CopyEngine
# Keep user data beside the executable when frozen; never write into PyInstaller's temp extraction folder.
RESOURCE_BASE=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
if getattr(sys,'frozen',False):
 BASE=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'TG_Coper'
else:
 BASE=Path(__file__).resolve().parent
BASE.mkdir(parents=True,exist_ok=True)
BGIMG=RESOURCE_BASE/'ui_background.png'
SPLASHIMG=RESOURCE_BASE/'tg_coper_splash.png'
STATE_FILE=BASE/'tg_coper_state.json'
LOG_DIR=BASE/'logs'
JOURNAL_CHUNK_LINES=100
C={'text':'#f5efff','muted':'#b9b3ef','pink':'#f64cff','purple':'#a35cff','blue':'#40cfff','green':'#47ffd0'}
class App:
 def __init__(self,root):
  self.root=root; root.title('TG_Coper — Dark Glass'); root.geometry('1360x840'); root.minsize(1180,740); root.configure(bg='#08051b')
  self.canvas=tk.Canvas(root,bg='#08051b',bd=0,highlightthickness=0); self.canvas.pack(fill='both',expand=True)
  self.sources=[]; self.source_enabled={}; self.running=False; self.entry=''; self.active='Главная'; self.telegram_user=None; self.auth_manager=None; self.flags=[True,True,True]; self.counts=[0,0,0]; self.image=None; self.bg_photo=None; self._wallpaper_pil=None; self._glass_photo_refs=[]; self.api_id=None; self.api_hash=None; self.phone=None; self.destination=''; self.tags=''; self.signature=''; self.interval=15; self.include_keywords=''; self.exclude_keywords='реклама, продам, услуги'; self.timezone_name='Europe/Moscow'; self.start_time='11:00'; self.end_time='23:00'; self.daily_limit=10; self.manual_review=False; self.engine=None; self.monitor_future=None; self.stats_history=[]; self.count_offsets={'copied':0,'copy_errors':0}; self.views_range='24 часа'; self.stats_future=None; self.stats_busy=False; self.stats_last='Ещё не собиралась'; self.stats_enabled=True; self.network_log=[]; self.journal_page=0; self.search_query=''; self.search_focus=False; self._load_journal(); self._network_event('INFO','Сетевой журнал запущен'); self._network_event('INFO','HTTPS-проверка выполняется по кнопке «Проверить связь»'); self._network_event('INFO','Telegram API: ожидание проверки сохранённой сессии'); self.auth_start_status='Проверка авторизации ещё не запускалась'; self._load_state()
  self.canvas.bind('<Configure>',self.redraw); self.canvas.bind('<Button-1>',self.click); self.canvas.bind('<Key>',self.key); self.canvas.bind('<Return>',lambda e:self.add_source()); self.canvas.bind_all('<MouseWheel>',self._mousewheel); self.canvas.bind_all('<Button-4>',lambda e:self._scroll_units(-3)); self.canvas.bind_all('<Button-5>',lambda e:self._scroll_units(3)); self.canvas.focus_set()
  self.vscroll=tk.Scrollbar(root,orient='vertical',command=self.canvas.yview); self.canvas.configure(yscrollcommand=self.vscroll.set); self.vscroll.place(relx=0.99,rely=0.12,relheight=0.82,anchor='ne'); self.redraw()
 def _read_all_journal(self):
  rows=[]
  try:
   for path in sorted(LOG_DIR.glob('journal_*.jsonl')):
    for line in path.read_text(encoding='utf-8').splitlines():
     try: rows.append(json.loads(line))
     except (ValueError,TypeError): pass
  except OSError: pass
  return rows if rows else list(self.network_log)
 def _load_journal(self):
  """Restore the latest 100 journal events; complete history is kept in numbered JSONL chunks."""
  try:
   files=sorted(LOG_DIR.glob('journal_*.jsonl'))
   rows=[]
   for path in files:
    for line in path.read_text(encoding='utf-8').splitlines():
     try: rows.append(json.loads(line))
     except (ValueError,TypeError): pass
   self.network_log=rows[-100:]
  except OSError: self.network_log=[]
 def _append_journal_file(self, item):
  try:
   LOG_DIR.mkdir(parents=True,exist_ok=True)
   files=sorted(LOG_DIR.glob('journal_*.jsonl'))
   current=files[-1] if files else LOG_DIR/'journal_001.jsonl'
   try:
    if current.exists():
     with current.open('r',encoding='utf-8') as fh: line_count=sum(1 for _ in fh)
    else: line_count=0
   except OSError: line_count=0
   if line_count>=JOURNAL_CHUNK_LINES:
    try: number=int(current.stem.split('_')[-1])+1
    except ValueError: number=len(files)+1
    current=LOG_DIR/f'journal_{number:03d}.jsonl'
   with current.open('a',encoding='utf-8') as fh: fh.write(json.dumps(item,ensure_ascii=False)+'\n')
  except OSError:
   pass
 def _network_event(self, level, message):
  """Persist every event; keep only the latest 100 in RAM for a responsive UI."""
  now=datetime.now(); stamp=now.strftime('%H:%M:%S')
  if not hasattr(self,'network_log'): self.network_log=[]
  item={'time':stamp,'timestamp':now.isoformat(timespec='seconds'),'level':str(level).upper(),'message':str(message)[:500]}
  self.network_log.append(item); self.network_log=self.network_log[-100:]
  self._append_journal_file(item)
 def _scroll_units(self, units):
  if self.active in ('Журнал','Источники'): self.canvas.yview_scroll(units,'units')
 def _mousewheel(self,event):
  if self.active in ('Журнал','Источники'):
   delta=-1 if getattr(event,'delta',0)>0 else 1
   self.canvas.yview_scroll(delta*3,'units')
 def _load_state(self):
  try:
   data=json.loads(STATE_FILE.read_text(encoding='utf-8'))
   self.sources=list(dict.fromkeys(data.get('sources', [])))
   self.source_enabled={str(k): bool(v) for k,v in data.get('source_enabled', {}).items()}
   for src in self.sources: self.source_enabled.setdefault(src, True)
   self.flags=list(data.get('flags', [True,True,True]))[:3]
   self.flags += [True] * (3-len(self.flags))
   self.api_id=data.get('api_id'); self.api_hash=data.get('api_hash'); self.phone=data.get('phone')
   self.counts=list(data.get('counts',[0,0,0]))[:3]; self.counts += [0]*(3-len(self.counts)); self.count_offsets=data.get('count_offsets',{'copied':0,'copy_errors':0})
   self.destination=data.get('destination',''); self.tags=data.get('tags',''); self.signature=data.get('signature',''); self.interval=int(data.get('interval',15) or 15); self.include_keywords=data.get('include_keywords',''); self.exclude_keywords=data.get('exclude_keywords','реклама, продам, услуги'); self.timezone_name=data.get('timezone_name','Europe/Moscow'); self.start_time=data.get('start_time','11:00'); self.end_time=data.get('end_time','23:00'); self.daily_limit=int(data.get('daily_limit',10) or 10); self.manual_review=bool(data.get('manual_review',False)); self.stats_history=list(data.get('stats_history',[]))[-10000:]; self.views_range=data.get('views_range','24 часа')
  except (OSError, ValueError, TypeError):
   pass
 def _save_state(self):
  data={'sources':self.sources, 'source_enabled':self.source_enabled, 'flags':self.flags, 'api_id':self.api_id, 'api_hash':self.api_hash, 'phone':self.phone, 'counts':self.counts, 'count_offsets':self.count_offsets, 'destination':self.destination, 'tags':self.tags, 'signature':self.signature, 'interval':self.interval, 'include_keywords':self.include_keywords, 'exclude_keywords':self.exclude_keywords, 'timezone_name':self.timezone_name, 'start_time':self.start_time, 'end_time':self.end_time, 'daily_limit':self.daily_limit, 'manual_review':self.manual_review, 'stats_history':self.stats_history[-10000:], 'views_range':self.views_range}
  tmp=STATE_FILE.with_suffix('.tmp')
  try:
   tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8'); tmp.replace(STATE_FILE)
   self._secure_file(STATE_FILE)
  except OSError as exc:
   self.lastlog='Не удалось сохранить настройки: '+str(exc)[:80]
 def _secure_file(self, path):
  # State/session files contain Telegram credentials or authorization tokens.
  # POSIX permissions are tightened; Windows keeps its normal user ACL behavior.
  try:
   import os
   if os.name == 'posix' and Path(path).exists(): Path(path).chmod(0o600)
  except OSError:
   pass
 def rounded(self,x1,y1,x2,y2,r=20,outline='#773dff',width=1,tags=()):
  # Outline-only rounded rectangle: wallpaper remains visible inside every panel.
  c=self.canvas; pts=[]
  import math
  for cx,cy,a0 in [(x2-r,y1+r,-90),(x2-r,y2-r,0),(x1+r,y2-r,90),(x1+r,y1+r,180)]:
   for i in range(7):
    a=math.radians(a0+i*90/6); pts.extend([cx+r*math.cos(a),cy+r*math.sin(a)])
  c.create_line(*pts,fill=outline,width=width,smooth=True,tags=tags)
 def text(self,x,y,s,size=11,color=None,bold=False,anchor='w',tags=()):
  self.canvas.create_text(x,y,text=s,fill=color or C['text'],font=('Segoe UI',size,'bold' if bold else 'normal'),anchor=anchor,tags=tags)
 def button(self,x,y,w,h,label,action,color=None,size=10):
  tag='btn_'+action.replace(' ','_')
  self.glass_region(x,y,x+w,y+h,min(18,h/2),'#100a29',202)
  # Bind the entire button surface, not only its border and label.
  for item_id in self.canvas.find_overlapping(x, y, x+w, y+h):
   self.canvas.addtag_withtag(tag, item_id)
  self.rounded(x,y,x+w,y+h, min(18,h/2),color or C['purple'],1,(tag,))
  self.text(x+w/2,y+h/2,label,size,C['text'],True,'center',(tag,)); self.canvas.tag_bind(tag,'<Enter>',lambda e:self.canvas.config(cursor='hand2')); self.canvas.tag_bind(tag,'<Leave>',lambda e:self.canvas.config(cursor='')); self.canvas.tag_bind(tag,'<Button-1>',lambda e,a=action:self.dispatch(a))
 def glass_region(self,x1,y1,x2,y2,r=18,shade='#100a29',alpha=176):
  """Draw a readable glass surface while retaining a dimmed view of the wallpaper."""
  if not getattr(self,'_wallpaper_pil',None):
   self.canvas.create_rectangle(x1,y1,x2,y2,fill=shade,outline='')
   return
  x1i=max(0,int(x1)); y1i=max(0,int(y1)); x2i=min(self._wallpaper_pil.width,int(x2)); y2i=min(self._wallpaper_pil.height,int(y2))
  if x2i<=x1i or y2i<=y1i: return
  crop=self._wallpaper_pil.crop((x1i,y1i,x2i,y2i)).convert('RGBA')
  # Blend a deep-purple tint over the actual wallpaper crop, rather than using a flat opaque panel.
  tint=Image.new('RGBA',crop.size,shade); tint.putalpha(max(0,min(255,int(alpha))))
  crop=Image.alpha_composite(crop,tint)
  mask=Image.new('L',crop.size,0); draw=ImageDraw.Draw(mask)
  draw.rounded_rectangle((0,0,crop.width-1,crop.height-1),radius=max(2,int(r)),fill=255)
  crop.putalpha(mask)
  photo=ImageTk.PhotoImage(crop)
  self._glass_photo_refs.append(photo)
  self.canvas.create_image(x1i,y1i,image=photo,anchor='nw')
 def icon(self,x,y,kind,color,size=12):
  """Small crisp vector icons drawn on the existing canvas; no emoji font dependency."""
  c=self.canvas; r=size/2; tag='icon_'+kind
  if kind in ('home','source','settings','filter','journal','stats','about','users','views','checked','clock','processed','published','errors','telegram'):
   # faint neon tile, matching the existing glass theme
   c.create_oval(x-r-4,y-r-4,x+r+4,y+r+4,outline=color,width=1)
  if kind=='home':
   c.create_line(x-r,y,x,y-r,x+r,y,fill=color,width=2); c.create_line(x-r+2,y-1,x-r+2,y+r,x+r-2,y+r,x+r-2,y-1,fill=color,width=2); c.create_rectangle(x-2,y+2,x+2,y+r,outline=color,width=1)
  elif kind in ('source','journal'):
   for j in range(3):
    yy=y-r+2+j*4; c.create_oval(x-r+1,yy-1,x-r+3,yy+1,fill=color,outline=color); c.create_line(x-r+6,yy,x+r,yy,fill=color,width=1)
  elif kind=='settings':
   c.create_oval(x-r+2,y-r+2,x+r-2,y+r-2,outline=color,width=2); c.create_oval(x-2,y-2,x+2,y+2,outline=color,width=1)
   for a,b in [(0,-1), (1,0),(0,1),(-1,0)]: c.create_line(x+a*(r-1),y+b*(r-1),x+a*r,y+b*r,fill=color,width=2)
  elif kind=='filter':
   c.create_line(x-r,y-r,x+r,y-r,x+2,y,x+2,y+r,x-2,y+r,x-2,y, x-r,y-r,fill=color,width=2)
  elif kind=='stats' or kind=='views':
   c.create_line(x-r,y+r,x-r,y-r,fill=color,width=1); c.create_line(x-r,y+r,x+r,y+r,fill=color,width=1); c.create_line(x-r+2,y+2,x-2,y-1,x+2,y+1,x+r-1,y-r+1,fill=color,width=2,smooth=True)
  elif kind in ('users','processed'):
   c.create_oval(x-3,y-r,x+3,y-r+6,outline=color,width=1); c.create_arc(x-r,y-1,x+r,y+r+3,start=0,extent=180,style='arc',outline=color,width=2)
  elif kind=='published':
   c.create_line(x-r,y,x-1,y+r-2,x+r,y-r,fill=color,width=2); c.create_line(x-1,y+r-2,x+1,y+1,fill=color,width=1)
  elif kind=='errors':
   c.create_line(x-r,y-r,x+r,y+r,fill=color,width=2); c.create_line(x+r,y-r,x-r,y+r,fill=color,width=2)
  elif kind=='checked':
   c.create_line(x-r,y,x-1,y+r-3,x+r,y-r,fill=color,width=2)
  elif kind=='clock':
   c.create_oval(x-r,y-r,x+r,y+r,outline=color,width=1); c.create_line(x,y,x,y-r+2,fill=color,width=2); c.create_line(x,y,x+r-2,y+2,fill=color,width=2)
  elif kind=='about':
   c.create_oval(x-1,y-r,x+1,y-r+2,fill=color,outline=color); c.create_line(x,y-2,x,y+r,fill=color,width=2)
  elif kind=='telegram':
   c.create_polygon(x-r,y,x+r,y-r,x+r-3,y+r,x+1,y+2,x-2,y+4,fill='',outline=color,width=1)
 def panel(self,x1,y1,x2,y2,title=None,accent=None):
  self.glass_region(x1,y1,x2,y2,22,'#100a29',184)
  self.rounded(x1,y1,x2,y2,22,accent or '#7447df',1)
  if title:self.text(x1+18,y1+22,title,11,C['text'],True)
 def redraw(self,event=None):
  old_yview=self.canvas.yview()[0] if hasattr(self,'canvas') else 0
  c=self.canvas; w=max(800,c.winfo_width()); h=max(600,c.winfo_height()); c.delete('all'); self._glass_photo_refs=[]
  try:
   im=Image.open(BGIMG).convert('RGB')
   # cover crop to canvas dimensions, so this is one uninterrupted wallpaper behind all controls
   ratio=max(w/im.width,h/im.height); im=im.resize((int(im.width*ratio),int(im.height*ratio)),Image.Resampling.LANCZOS)
   left=(im.width-w)//2; top=(im.height-h)//2; im=im.crop((left,top,left+w,top+h))
   im=ImageEnhance.Brightness(im).enhance(0.70); self._wallpaper_pil=im.copy()
   self.bg_photo=ImageTk.PhotoImage(im); c.create_image(0,0,image=self.bg_photo,anchor='nw',tags=('wallpaper',))
  except Exception: c.configure(bg='#08051b')
  # transparent shell: outlines only, never opaque panel fills
  self.rounded(10,10,w-10,h-10,30,'#9c42ff',1)
  self.text(30,43,'◆',28,C['blue'],True); self.text(70,43,'TG_COPER',22,C['text'],True); self.text(72,66,'Telegram workspace',9,C['muted'])
  search_tag='global_search'; search_x1=330; search_x2=min(760,w-390); self.glass_region(search_x1,23,search_x2,62,19,'#100a29',190); self.rounded(search_x1,23,search_x2,62,19,C['blue'] if self.search_focus else '#7547e8',1,(search_tag,)); search_label=('⌕   '+self.search_query) if self.search_query else '⌕   Поиск по источникам и журналу…'; self.text(352,43,search_label,10,C['text'] if self.search_query else C['muted'],tags=(search_tag,)); self.canvas.tag_bind(search_tag,'<Button-1>',lambda e:self.focus_search()); self.canvas.tag_bind(search_tag,'<Enter>',lambda e:self.canvas.config(cursor='xterm')); self.canvas.tag_bind(search_tag,'<Leave>',lambda e:self.canvas.config(cursor=''))
  self.button(w-365,22,145,38,('● Telegram подключён' if self.telegram_user else '↗ Авторизация'), 'auth', C['blue'] if self.telegram_user else C['pink'], 9); self.text(w-195,42,'☾    ⚙',14,C['purple'],True)
  c.create_line(20,82,w-20,82,fill='#6e37da',width=1)
  left=24; sidew=max(180,int(w*.22)); gap=14; mainx=left+sidew+gap; rightw=max(230,int(w*.25)); rightx=w-rightw-24; centerw=rightx-mainx-gap
  # sidebar
  self.panel(left,98,left+sidew,h-24,None,'#8c3eea')
  nav=[('home','Главная'),('source','Источники'),('settings','Настройки'),('filter','Фильтры'),('journal','Журнал'),('stats','Статистика'),('about','О программе')]
  yy=120
  for icon,name in nav:
   act='nav_'+name; col=C['pink'] if self.active==name else C['purple']; self.rounded(left+12,yy,left+sidew-12,yy+43,20,col,2 if self.active==name else 1,(act,)); self.icon(left+31,yy+22,icon,col,10); self.text(left+48,yy+22,name,10,C['text'],self.active==name,tags=(act,)); c.tag_bind(act,'<Button-1>',lambda e,n=name:self.nav(n)); yy+=51
  self.text(left+22,yy+8,'БЫСТРЫЕ ДЕЙСТВИЯ',9,C['muted'],True); yy+=25
  for label,act,col in [('＋  Новый источник','new_source',C['blue']),('↻  Проверить ссылки','check',C['purple']),('⟲  Сбросить результаты','reset',C['pink'])]:
   self.button(left+12,yy,sidew-24,38,label,act,col,9); yy+=46
  self.rounded(left+12,h-142,left+sidew-12,h-40,18,'#8a43e8',1)
  self.text(left+27,h-120,'●  СТАТУС',9,C['green'],True); self.text(left+27,h-96,'Мониторинг активен' if self.running else 'Работа остановлена',10,C['text'],True); self.text(left+27,h-67,('Telegram: '+self.telegram_user if self.telegram_user else 'Telegram: не подключён'),8,C['muted'])
  # Every navigation item opens a real section view; every section has an explicit return button.
  if self.active!='Главная':
   self.draw_section_view(w,h,mainx)
   extra=(116+34*getattr(self,'journal_display_count',len(self.network_log))+190) if self.active=='Журнал' else (260+len(self.sources)*32 if self.active=='Источники' else h)
   self.canvas.configure(scrollregion=(0,0,w,max(h,extra)))
   self.vscroll.lift()
   if self.active in ('Журнал','Источники') and old_yview>0: self.canvas.yview_moveto(old_yview)
   else: self.canvas.yview_moveto(0)
   return
  # Dashboard: prominent neon action tiles matching the supplied reference.
  content_right=w-24; content_w=content_right-mainx
  tile_y=100; tile_h=128; tile_gap=12; tile_w=min(150,(content_w*.62-2*tile_gap)/3)
  def action_tile(x,y,ww,hh,title,action,accent,glyph):
   tag='dash_tile_'+action
   self.glass_region(x,y,x+ww,y+hh,20,'#100724',222)
   self.rounded(x,y,x+ww,y+hh,20,accent,2,(tag,))
   self.canvas.create_oval(x+ww/2-25,y+19,x+ww/2+25,y+69,outline=accent,width=2,tags=(tag,))
   if glyph=='play': self.canvas.create_polygon(x+ww/2-7,y+31,x+ww/2+11,y+44,x+ww/2-7,y+57,fill=accent,outline=accent,tags=(tag,))
   elif glyph=='stop': self.canvas.create_rectangle(x+ww/2-8,y+36,x+ww/2+8,y+52,fill=accent,outline=accent,tags=(tag,))
   else:
    self.icon(x+ww/2,y+44,'settings',accent,24)
   self.text(x+ww/2,y+91,title,12,accent,True,'center',(tag,))
   self.text(x+ww/2,y+111,{'start':'Запустить мониторинг','stop':'Остановить мониторинг','settings':'Параметры копирования'}[action],7,C['muted'],False,'center',(tag,))
   self.canvas.tag_bind(tag,'<Button-1>',lambda e,a=action:self.dispatch(a))
   self.canvas.tag_bind(tag,'<Enter>',lambda e:self.canvas.config(cursor='hand2'))
   self.canvas.tag_bind(tag,'<Leave>',lambda e:self.canvas.config(cursor=''))
  for i,(title,action,accent,glyph) in enumerate([
   ('▶  ЗАПУСТИТЬ','start',C['pink'],'play'),
   ('■  ОСТАНОВИТЬ','stop',C['blue'],'stop'),
   ('⚙  НАСТРОЙКИ','settings',C['purple'],'gear')]):
   action_tile(mainx+i*(tile_w+tile_gap),tile_y,tile_w,tile_h,title,action,accent,glyph)
  # Status card on the right of the large controls.
  status_x=mainx+3*(tile_w+tile_gap); status_w=content_right-status_x
  self.panel(status_x,tile_y,content_right,tile_y+tile_h,'СТАТУС',C['green'])
  self.text(status_x+15,tile_y+48,'Состояние:',9,C['muted'])
  self.text(status_x+90,tile_y+48,'АКТИВЕН' if self.running else 'ОСТАНОВЛЕН',9,C['green'] if self.running else C['pink'],True)
  self.text(status_x+15,tile_y+73,'Обработано',9,C['muted']); self.text(content_right-15,tile_y+73,str(self.counts[0]),10,C['text'],True,'e')
  self.text(status_x+15,tile_y+94,'Опубликовано',9,C['muted']); self.text(content_right-15,tile_y+94,str(self.counts[1]),10,C['text'],True,'e')
  self.text(status_x+15,tile_y+113,'Ошибки',9,C['muted']); self.text(content_right-15,tile_y+113,str(self.counts[2]),10,C['pink'] if self.counts[2] else C['text'],True,'e')
  # Source quick-switches directly under the large action buttons, as in the reference.
  src_y=240; src_h=70
  self.panel(mainx,src_y,content_right,src_y+src_h,'ИСТОЧНИКИ • БЫСТРОЕ ВКЛ/ВЫКЛ',C['purple'])
  if self.sources:
   visible_sources=self.sources[:min(4,max(1,int(content_w//210)))]
   sw_gap=8; sw_w=(content_w-24-(len(visible_sources)-1)*sw_gap)/max(1,len(visible_sources))
   for i,src in enumerate(visible_sources):
    sx=mainx+12+i*(sw_w+sw_gap); sy=src_y+34; enabled=self.source_enabled.get(src,True); tag='source_toggle_'+str(i)
    self.glass_region(sx,sy,sx+sw_w,sy+26,12,'#100a29',210)
    self.rounded(sx,sy,sx+sw_w,sy+26,12,C['green'] if enabled else '#756b91',1,(tag,))
    self.text(sx+9,sy+13,('@'+src.lstrip('@'))[:max(8,int(sw_w/8)-7)],8,C['text'] if enabled else C['muted'],True,tags=(tag,))
    tx=sx+sw_w-29; ty=sy+6
    self.rounded(tx,ty,tx+20,ty+14,8,C['green'] if enabled else '#756b91',1,(tag,))
    self.canvas.create_oval(tx+(10 if enabled else 2),ty+2,tx+(18 if enabled else 10),ty+10,fill=C['green'] if enabled else C['muted'],outline='',tags=(tag,))
    self.canvas.tag_bind(tag,'<Button-1>',lambda e,source=src:self.toggle_source(source))
    self.canvas.tag_bind(tag,'<Enter>',lambda e:self.canvas.config(cursor='hand2')); self.canvas.tag_bind(tag,'<Leave>',lambda e:self.canvas.config(cursor=''))
   if len(self.sources)>len(visible_sources): self.text(content_right-12,src_y+15,'+'+str(len(self.sources)-len(visible_sources))+' ещё',8,C['muted'],anchor='e')
  else:
   self.text(mainx+16,src_y+46,'Добавьте источники в разделе «Источники» — переключатели появятся здесь.',9,C['muted'])
  # Real history graph and recent events.
  chart_x=mainx; chart_y=322; chart_h=min(238,h-425); chart_w=content_w*.59
  events_x=chart_x+chart_w+12; events_w=content_right-events_x
  self.panel(chart_x,chart_y,chart_x+chart_w,chart_y+chart_h,'ДИНАМИКА ПРОСМОТРОВ',C['purple'])
  self.text(chart_x+16,chart_y+40,'ПЕРИОД',8,C['muted'],True)
  ranges=[('3 часа','3h'),('24 часа','24h'),('7 дней','7d'),('30 дней','30d'),('Всё','all')]
  rx=chart_x+78
  for label,key in ranges:
   bw=48 if label!='24 часа' else 57
   tag='views_range_'+key
   self.glass_region(rx,chart_y+29,rx+bw,chart_y+51,8,'#100a29',205)
   self.rounded(rx,chart_y+29,rx+bw,chart_y+51,8,C['green'] if self.views_range==label else C['purple'],1,(tag,))
   self.text(rx+bw/2,chart_y+40,label,7,C['text'],self.views_range==label,'center',(tag,))
   self.canvas.tag_bind(tag,'<Button-1>',lambda e,l=label:self.set_views_range(l))
   rx+=bw+5
  vals=[]
  from datetime import datetime, timedelta
  cutoff={'3 часа':timedelta(hours=3),'24 часа':timedelta(hours=24),'7 дней':timedelta(days=7),'30 дней':timedelta(days=30)}.get(self.views_range)
  now=datetime.now()
  for item in self.stats_history:
   stamp=item.get('timestamp')
   try:
    dt=datetime.fromisoformat(stamp) if stamp else datetime.strptime(item.get('time',''),'%d.%m %H:%M').replace(year=now.year)
    if dt.tzinfo is not None:
     dt=dt.astimezone().replace(tzinfo=None)
   except (ValueError,TypeError,OverflowError):
    dt=None
   # Limited periods only include records with a valid timestamp inside that window.
   if cutoff is None or (dt is not None and timedelta(0) <= now-dt <= cutoff):
    vals.append(int(item.get('views',0) or 0))
  vals=vals[-48:]
  gx1,gy1,gx2,gy2=chart_x+43,chart_y+70,chart_x+chart_w-18,chart_y+chart_h-30
  mx=max(vals) if vals else 0
  # Numeric Y-axis labels and grid; scale is derived only from collected measurements.
  scale_top=max(4, int(((mx + 3) // 4) * 4))
  for j in range(5):
   yy=gy2-j*(gy2-gy1)/4
   tick=round(scale_top*j/4)
   c.create_line(gx1,yy,gx2,yy,fill='#40336f',width=1)
   self.text(gx1-7,yy,str(tick),7,C['muted'],anchor='e')
  c.create_line(gx1,gy1,gx1,gy2,fill='#6f5ba6',width=1)
  if len(vals)>=1:
   points=[]
   for i,v in enumerate(vals): points.extend([gx1+4+i*(gx2-gx1-8)/max(1,len(vals)-1),gy2-4-(v/scale_top)*(gy2-gy1-8)])
   if len(points)>=4: c.create_line(*points,fill=C['blue'],width=2,smooth=True)
   for i,v in enumerate(vals):
    px,py=points[2*i],points[2*i+1]; c.create_oval(px-2.5,py-2.5,px+2.5,py+2.5,fill=C['pink'],outline='')
   # Always show exact latest measurement, plus start/end labels for the selected window.
   px,py=points[-2],points[-1]
   label_y=max(gy1+8,py-12)
   self.text(px,label_y,f'{vals[-1]:,}'.replace(',',' '),8,C['text'],True,'center')
   self.text(gx1,gy2+13,'Начало периода',7,C['muted']); self.text(gx2,gy2+13,'Последний замер',7,C['muted'],anchor='e')
  else: self.text((gx1+gx2)/2,(gy1+gy2)/2,'График появится после подключения Telegram\nи сбора первых замеров статистики.',9,C['muted'],anchor='center')
  self.panel(events_x,chart_y,content_right,chart_y+chart_h,'ПОСЛЕДНИЕ СОБЫТИЯ',C['blue'])
  event_items=[('●',getattr(self,'lastlog','TG_Coper готов. Добавьте источники.'),C['green']),('●','Мониторинг: '+('активен' if self.running else 'остановлен'),C['blue'] if self.running else C['muted']),('●','Telegram: '+('подключён' if self.telegram_user else 'не подключён'),C['green'] if self.telegram_user else C['pink']),('●','Источников активно: '+str(sum(1 for src in self.sources if self.source_enabled.get(src,True)))+' / '+str(len(self.sources)),C['purple']),('●','Опубликовано: '+str(self.counts[1])+' • Ошибок: '+str(self.counts[2]),C['muted'])]
  for i,(dot,msg,col) in enumerate(event_items):
   yy=chart_y+58+i*32; c.create_oval(events_x+17,yy-4,events_x+25,yy+4,fill=col,outline=''); self.text(events_x+35,yy,msg[:46],8 if events_w<300 else 9,C['text'] if i==0 else C['muted'])
   if i<len(event_items)-1: c.create_line(events_x+17,yy+14,content_right-15,yy+14,fill='#3b2c66',width=1)
  # Compact status footer with the source cadence and destination.
  bar_y=chart_y+chart_h+12; bar_h=max(74,min(92,h-24-bar_y))
  self.panel(mainx,bar_y,content_right,bar_y+bar_h,'МОНИТОРИНГ',C['green'])
  status_col=C['green'] if self.running else C['muted']; self.icon(mainx+27,bar_y+52,'telegram',status_col,12)
  self.text(mainx+48,bar_y+43,'Мониторинг '+('активен' if self.running else 'остановлен'),10,status_col,True)
  self.text(mainx+48,bar_y+64,'Интервал: '+str(self.interval)+' сек. • Источников: '+str(len(self.sources))+' • Назначение: '+(self.destination.strip() or 'не задан'),8,C['muted'])
  # Network activity console in the remaining dashboard space.
  net_y=bar_y+102; net_bottom=h-24
  if net_bottom-net_y>72:
   self.panel(mainx,net_y,content_right,net_bottom,'СЕТЕВОЙ ЛОГ • TELEGRAM / HTTPS / МОНИТОРИНГ',C['blue'])
   entries=self.network_log[-4:]
   if not entries:
    self.text(mainx+16,net_y+43,'Сетевых событий пока нет. Запусти проверку связи или подключи Telegram.',9,C['muted'])
   else:
    for i,item in enumerate(reversed(entries)):
     yy=net_y+40+i*24
     level=item.get('level','INFO'); color=C['green'] if level in ('OK','INFO') else C['pink'] if level in ('ERROR','WARN') else C['blue']
     self.text(mainx+15,yy,item.get('time','--:--:--'),8,C['muted'])
     self.text(mainx+78,yy,level,8,color,True)
     self.text(mainx+130,yy,item.get('message','')[:max(20,int((content_w-150)/7))],8,C['text'] if i==0 else C['muted'])
  self.canvas.configure(scrollregion=(0,0,max(w,self.canvas.winfo_width()),h))
  self.vscroll.lift(); self.canvas.yview_moveto(0)
 def draw_section_view(self,w,h,mainx):
  c=self.canvas; x1=mainx; x2=w-24; y1=98; y2=h-24
  accents={'Источники':'#5d53ff','Настройки':'#8651ef','Фильтры':'#40cfff','Журнал':'#6738ce','О программе':'#3d9cff'}
  self.panel(x1,y1,x2,y2,self.active.upper(),accents.get(self.active,'#8651ef'))
  self.button(x2-344,y1+12,160,36,'↻ Обновить сейчас','stats_refresh',C['blue'],9) if self.active=='Статистика' else self.button(x2-184,y1+12,160,36,'×  На главную','home',C['blue'],10)
  if self.active=='Источники':
   self.text(x1+24,y1+66,'ИСТОЧНИКИ TELEGRAM',11,C['muted'],True)
   self.text(x1+24,y1+91,'Добавляйте публичные каналы — мониторинг использует подключённый аккаунт.',10,C['text'])
   bx=x1+24; by=y1+116; bw=min(440,(x2-x1)-220)
   self.glass_region(bx,by,bx+bw,by+42,14,'#100a29',210); self.rounded(bx,by,bx+bw,by+42,14,C['blue'],1,('section_entry',))
   self.text(bx+12,by+21,self.entry or '@имя_канала или ссылка t.me',10,C['text'] if self.entry else C['muted'],tags=('section_entry',))
   c.tag_bind('section_entry','<Button-1>',lambda e:self.focus_entry())
   self.button(bx+bw+12,by,bw*0+130,42,'＋ Добавить','add',C['pink'],9)
   self.button(bx+bw+152,by,145,42,'↻ Проверить','check',C['purple'],9)
   self.text(x1+24,by+72,'ДОБАВЛЕННЫЕ КАНАЛЫ',10,C['muted'],True)
   filtered_sources=[src for src in self.sources if self._matches_search(src)]
   if filtered_sources:
    for i,src in enumerate(filtered_sources):
     yy=by+102+i*32; enabled=self.source_enabled.get(src,True); self.glass_region(x1+24,yy,x2-24,yy+27,10,'#100a29',165)
     self.text(x1+38,yy+14,('●  ' if enabled else '○  ')+src,10,C['text'] if enabled else C['muted'])
     toggle_tag=f'section_src_toggle_{i}'; self.rounded(x2-112,yy+4,x2-73,yy+23,9,C['green'] if enabled else '#756b91',1,(toggle_tag,)); self.text(x2-92,yy+13,'ON' if enabled else 'OFF',7,C['text'],True,'center',(toggle_tag,)); c.tag_bind(toggle_tag,'<Button-1>',lambda e,source=src:self.toggle_source(source))
     remove_tag=f'section_src_remove_{i}'; self.rounded(x2-62,yy+4,x2-34,yy+23,8,C['pink'],1,(remove_tag,)); self.text(x2-48,yy+13,'×',11,C['text'],True,'center',(remove_tag,)); c.tag_bind(remove_tag,'<Button-1>',lambda e,source=src:self.remove_source(source))
   else: self.text(x1+24,by+105,('По запросу ничего не найдено.' if self.sources and self.search_query else 'Пока нет источников. Введи @username или t.me/ссылку выше.'),10,C['muted'])
  elif self.active=='Фильтры':
   self.text(x1+24,y1+66,'КЛЮЧЕВЫЕ СЛОВА И РАСПИСАНИЕ',11,C['muted'],True)
   self.text(x1+24,y1+92,'Ниже отображаются именно новые параметры копирования.',10,C['text'])
   card_y=y1+112; card_h=142
   self.glass_region(x1+24,card_y,x2-24,card_y+card_h,16,'#100a29',190)
   self.text(x1+42,card_y+22,'ВКЛЮЧАТЬ',8,C['blue'],True)
   self.text(x1+132,card_y+22,(self.include_keywords or 'Все публикации, если поле пустое')[:max(16,int((x2-x1-210)/7))],9,C['text'])
   self.text(x1+42,card_y+49,'ИСКЛЮЧАТЬ',8,C['pink'],True)
   self.text(x1+132,card_y+49,(self.exclude_keywords or 'Не задано')[:max(16,int((x2-x1-210)/7))],9,C['text'])
   self.text(x1+42,card_y+76,'ВРЕМЯ',8,C['blue'],True)
   self.text(x1+132,card_y+76,f'{self.start_time}–{self.end_time} • {self.timezone_name}',9,C['text'])
   self.text(x1+42,card_y+103,'ЛИМИТ',8,C['blue'],True)
   self.text(x1+132,card_y+103,f'до {self.daily_limit} публикаций в день • интервал проверки {self.interval} сек.',9,C['text'])
   self.text(x1+42,card_y+126,'Ручная проверка: '+('ВКЛ' if self.manual_review else 'ВЫКЛ'),8,C['green'] if self.manual_review else C['muted'])
   self.button(x1+24,card_y+card_h+12,min(320,x2-x1-48),42,'✎  Изменить фильтры и расписание','filter_settings',C['purple'],9)
   self.text(x1+24,card_y+card_h+74,'ДОПОЛНИТЕЛЬНАЯ ОБРАБОТКА',10,C['muted'],True)
   labels=[('Удалять ссылки из текста',0),('Добавлять подпись канала',1),('Дополнять публикации тегами',2)]
   for i,(label,index) in enumerate(labels):
    yy=card_y+card_h+94+i*55; self.glass_region(x1+24,yy,x2-24,yy+43,12,'#100a29',190)
    self.rounded(x1+42,yy+10,x1+86,yy+33,11,C['green'] if self.flags[index] else '#655b85',2,(f'section_flag_{index}',))
    self.text(x1+64,yy+21,'✓' if self.flags[index] else '×',11,C['text'],True,'center',(f'section_flag_{index}',))
    self.text(x1+105,yy+21,label,10,C['text'],True)
    self.text(x2-45,yy+21,'ВКЛ' if self.flags[index] else 'ВЫКЛ',9,C['green'] if self.flags[index] else C['muted'],True,'e')
    c.tag_bind(f'section_flag_{index}','<Button-1>',lambda e,j=index:self.toggle(j))
  elif self.active=='Статистика':
   latest=self.stats_history[-1] if self.stats_history else {}
   metrics=[('Подписчики назначения',latest.get('subscribers') if latest.get('subscribers') is not None else '—','users',C['blue']),('Просмотры последних постов',latest.get('views') if latest.get('views') is not None else '—','views',C['pink']),('Источники проверены',latest.get('sources_checked','—'),'checked',C['green']),('Последнее обновление',self.stats_last,'clock',C['purple'])]
   cell=(x2-x1-48)/4
   for i,(label,value,kind,accent) in enumerate(metrics):
    xx=x1+24+i*cell; self.icon(xx+12,y1+68,kind,accent,9); self.text(xx+27,y1+70,label,9,C['muted']); self.text(xx+27,y1+98,str(value),13,C['blue'] if i<3 else C['text'],True)
   self.text(x1+24,y1+142,'ДИНАМИКА ПРОСМОТРОВ',10,C['muted'],True)
   gx1,gy1,gx2,gy2=x1+48,y1+175,x1+(x2-x1)*0.63,y2-48
   vals=[int(z.get('views',0) or 0) for z in self.stats_history[-24:]]
   mx=max(vals) if vals else 0; scale_top=max(4,int(((mx+3)//4)*4))
   for j in range(5):
    yy=gy2-j*(gy2-gy1)/4; tick=round(scale_top*j/4)
    c.create_line(gx1,yy,gx2,yy,fill='#49376f',width=1)
    self.text(gx1-8,yy,str(tick),8,C['muted'],anchor='e')
   c.create_line(gx1,gy1,gx1,gy2,fill='#9a7ce8'); c.create_line(gx1,gy2,gx2,gy2,fill='#9a7ce8')
   if vals:
    points=[]
    for i,v in enumerate(vals): points.extend([gx1+8+i*(gx2-gx1-16)/max(1,len(vals)-1),gy2-8-v/scale_top*(gy2-gy1-25)])
    if len(points)>=4: c.create_line(*points,fill=C['blue'],width=2,smooth=True)
    for i,v in enumerate(vals):
     xx=gx1+8+i*(gx2-gx1-16)/max(1,len(vals)-1); yy=gy2-8-v/scale_top*(gy2-gy1-25); c.create_oval(xx-3,yy-3,xx+3,yy+3,fill=C['pink'],outline='')
    self.text(points[-2],max(gy1+10,points[-1]-13),f'{vals[-1]:,}'.replace(',',' '),8,C['text'],True,'center')
   else: self.text((gx1+gx2)/2,(gy1+gy2)/2,'Данных пока нет — подключи Telegram и нажми «Обновить».',9,C['muted'],anchor='center')
   hx=x1+(x2-x1)*0.67
   self.text(hx,y1+142,'ИСТОРИЯ ЗАМЕРОВ',10,C['muted'],True)
   for i,z in enumerate(reversed(self.stats_history[-8:])):
    yy=y1+180+i*42
    self.text(hx,yy,z.get('time','—'),8,C['muted'])
    self.text(hx,yy+16,'Подписчики: '+str(z.get('subscribers','—'))+' • Просмотры: '+str(z.get('views','—')),8,C['text'])
   self.text(x1+24,y2-26,'Автосбор: '+('включён' if self.stats_enabled else 'выключен')+' • '+self.stats_last,9,C['green'],True)
   self.button(x2-174,y1+12,150,36,'×  На главную','home',C['purple'],9)
  elif self.active=='Журнал':
   self.text(x1+24,y1+66,'СОБЫТИЯ И СЕТЕВОЙ ЖУРНАЛ',11,C['muted'],True)
   self.text(x1+24,y1+91,'Поиск сверху фильтрует события по времени, уровню и тексту.',9,C['muted'])
   entries=list(reversed(self._read_all_journal()))
   self.journal_display_count=len(entries)
   if getattr(self,'lastlog',''):
    entries.insert(0,{'time':datetime.now().strftime('%H:%M:%S'),'level':'INFO','message':self.lastlog})
   entries=[item for item in entries if self._matches_search(' '.join(str(item.get(k,'')) for k in ('time','level','message')))]
   top=y1+116; row_h=34; max_rows=len(entries)
   self.text(x1+30,top,'ВРЕМЯ',8,C['muted'],True); self.text(x1+112,top,'УРОВЕНЬ',8,C['muted'],True); self.text(x1+210,top,'СОБЫТИЕ',8,C['muted'],True)
   if not entries: self.text(x1+30,top+46,'Ничего не найдено. Измени или очисти поисковый запрос.',10,C['muted'])
   for i,item in enumerate(entries[:max_rows]):
    yy=top+20+i*row_h; level=str(item.get('level','INFO')).upper(); col=C['pink'] if level in ('ERROR','WARN') else C['green'] if level=='OK' else C['blue']
    self.glass_region(x1+24,yy,x2-24,yy+29,9,'#100a29',150)
    self.text(x1+31,yy+15,item.get('time','—'),8,C['muted'])
    self.text(x1+112,yy+15,level,8,col,True)
    self.text(x1+210,yy+15,str(item.get('message',''))[:max(18,int((x2-x1-260)/7))],8,C['text'])
   self.text(x1+24,top+20+len(entries)*row_h+8,'Найдено событий: '+str(len(entries))+' • В памяти 100 последних; полный журнал сохранён в logs/',9,C['muted'])
   self.button(x1+24,top+45+len(entries)*row_h,170,30,'↻ Проверить источники','check',C['purple'],8)
  elif self.active=='Настройки':
   self.text(x1+24,y1+68,'ОСНОВНЫЕ НАСТРОЙКИ',11,C['muted'],True)
   self.text(x1+24,y1+96,'Канал назначения: '+(self.destination or 'не задан'),11,C['text'])
   self.text(x1+24,y1+126,'Интервал проверки: '+str(self.interval)+' сек.',11,C['text'])
   self.text(x1+24,y1+156,'Теги: '+(self.tags or 'не заданы'),11,C['text'])
   self.text(x1+24,y1+186,'Подпись: '+(self.signature or 'не задана'),11,C['text'])
   self.text(x1+24,y1+216,'Фильтры и расписание настраиваются во вкладке «Фильтры».',10,C['muted'])
   self.button(x1+24,y1+270,210,44,'⚙ Изменить настройки','settings',C['purple'],10)
  else:
   self.text(x1+24,y1+68,'TG_Coper — рабочее пространство Telegram',14,C['text'],True)
   self.text(x1+24,y1+104,'Мониторинг каналов, сбор статистики и копирование публикаций.',11,C['muted'])
   self.text(x1+24,y1+139,'Авторизация: '+(self.telegram_user or getattr(self,'auth_start_status','не проверена')),10,C['green'] if self.telegram_user else C['pink'])
   self.text(x1+24,y1+171,'Источников: '+str(len(self.sources))+'    •    Подписчики: '+str((self.stats_history[-1] if self.stats_history else {}).get('subscribers','—')),11,C['text'])
   self.text(x1+24,y1+205,'Интерфейс использует локальный фон и не требует графического ускорения.',10,C['muted'])
 def draw_stats_view(self):
  c=self.canvas; w=max(800,c.winfo_width()); h=max(600,c.winfo_height()); c.delete('all'); self._glass_photo_refs=[]
  try:
   im=Image.open(BGIMG).convert('RGB'); ratio=max(w/im.width,h/im.height); im=im.resize((int(im.width*ratio),int(im.height*ratio)),Image.Resampling.LANCZOS); im=im.crop(((im.width-w)//2,(im.height-h)//2,(im.width-w)//2+w,(im.height-h)//2+h)); im=ImageEnhance.Brightness(im).enhance(0.70); self._wallpaper_pil=im.copy(); self.bg_photo=ImageTk.PhotoImage(im); c.create_image(0,0,image=self.bg_photo,anchor='nw')
  except Exception: pass
  self.rounded(10,10,w-10,h-10,30,'#9c42ff',1); self.text(30,42,'◆  TG_COPER  /  СТАТИСТИКА',20,C['text'],True)
  self.button(w-365,22,160,38,'↻  Обновить сейчас','stats_refresh',C['blue'],10); self.button(w-190,22,160,38,'×  На главную','home',C['purple'],10)
  self.text(32,85,'Сбор раз в 30 минут • фоновый сетевой запрос • без GPU-вычислений',10,C['muted'])
  self.panel(24,110,w-24,195,'ОБЗОР','#5d53ff')
  latest=self.stats_history[-1] if self.stats_history else {}
  metrics=[('Подписчики назначения',latest.get('subscribers') if latest.get('subscribers') is not None else '—','users',C['blue']),('Просмотры последних постов',latest.get('views') if latest.get('views') is not None else '—','views',C['pink']),('Источники проверены',latest.get('sources_checked','—'),'checked',C['green']),('Последнее обновление',self.stats_last,'clock',C['purple'])]
  cell=(w-80)/4
  for i,(label,value,kind,accent) in enumerate(metrics):
   x=42+i*cell; self.icon(x+10,141,kind,accent,9); self.text(x+25,143,label,9,C['muted']); self.text(x+25,169,str(value),15,C['blue'] if i<3 else C['text'],True)
  self.panel(24,210,w*.65, h-110,'ДИНАМИКА ПРОСМОТРОВ','#8651ef')
  self.panel(w*.65+10,210,w-24,h-110,'ИСТОРИЯ ЗАМЕРОВ','#3d9cff')
  x1,y1,x2,y2=62,260,w*.65-25,h-155
  vals=[int(z.get('views',0) or 0) for z in self.stats_history[-24:]]
  mx=max(vals) if vals else 0; scale_top=max(4,int(((mx+3)//4)*4))
  for j in range(5):
   yy=y2-j*(y2-y1)/4; tick=round(scale_top*j/4)
   c.create_line(x1,yy,x2,yy,fill='#49376f',width=1)
   self.text(x1-8,yy,str(tick),8,C['muted'],anchor='e')
  c.create_line(x1,y1,x1,y2,fill='#9a7ce8'); c.create_line(x1,y2,x2,y2,fill='#9a7ce8')
  if vals:
   points=[]
   for i,v in enumerate(vals): points.extend([x1+8+i*(x2-x1-16)/max(1,len(vals)-1),y2-8-v/scale_top*(y2-y1-25)])
   if len(points)>=4: c.create_line(*points,fill=C['blue'],width=2,smooth=True)
   for i,v in enumerate(vals):
    xx,yy=points[2*i],points[2*i+1]; c.create_oval(xx-3,yy-3,xx+3,yy+3,fill=C['pink'],outline='')
   px,py=points[-2],points[-1]; self.text(px,max(y1+10,py-14),f'{vals[-1]:,}'.replace(',',' '),9,C['text'],True,'center')
   self.text(x1,y2+14,'Старые замеры',8,C['muted']); self.text(x2,y2+14,'Последний',8,C['muted'],anchor='e')
  else: self.text((x1+x2)/2,(y1+y2)/2,'Данных пока нет. Нужна авторизация и канал назначения.',10,C['muted'],anchor='center')
  hist=self.stats_history[-8:]
  for i,z in enumerate(reversed(hist)):
   yy=250+i*35
   self.text(w*.65+30,yy,z.get('time','—'),8,C['muted'])
   self.text(w*.65+30,yy+15,'Подписчики: '+str(z.get('subscribers','—'))+'  •  Просмотры: '+str(z.get('views','—')),8,C['text'])
  self.text(32,h-44,'Автосбор: '+('включён' if self.stats_enabled else 'выключен')+' • '+self.stats_last,9,C['green'],True)
 def start_stats_scheduler(self):
  if getattr(self,'_stats_scheduler_started',False): return
  self._stats_scheduler_started=True
  self.root.after(3000,self._stats_tick)
 def _stats_tick(self):
  if self.stats_enabled and not self.stats_busy and self.telegram_user and self.auth_manager and self.auth_manager.client:
   self._collect_stats(manual=False)
  self.root.after(1800000,self._stats_tick)
 def _collect_stats(self,manual=False):
  if self.stats_busy:
   if manual: self.lastlog='Сбор статистики уже выполняется.'
   return
  if not self.telegram_user or not self.auth_manager or not self.auth_manager.client:
   self.stats_last='Нет подключения Telegram'
   if manual: self.lastlog='Для статистики сначала подключи Telegram.'; self.redraw()
   return
  self.stats_busy=True; self.stats_last='Сбор данных…'
  if self.active=='Статистика': self.draw_stats_view()
  fut=self.auth_manager.submit(self.auth_manager.collect_channel_stats(self.sources,self.destination))
  def poll():
   if not fut.done(): self.root.after(250,poll); return
   try:
    data=fut.result(); from datetime import datetime
    data['time']=datetime.now().strftime('%d.%m %H:%M'); data['timestamp']=datetime.now().isoformat(timespec='seconds'); self.stats_history.append(data); self.stats_history=self.stats_history[-10000:]
    self.stats_last=data['time']; self._save_state(); self.lastlog='Статистика обновлена: подписчики '+str(data.get('subscribers','—'))+', просмотры '+str(data.get('views','—'))
   except Exception as exc: self.stats_last='Ошибка: '+str(exc)[:80]; self.lastlog='Не удалось обновить статистику: '+str(exc)[:120]
   self.stats_busy=False; self.redraw()
   if self.active=='Статистика': self.draw_stats_view()
  self.root.after(250,poll)
 def focus_entry(self):
  self.search_focus=False; self.entry_focus=True
  if self.active!='Источники': self.active='Источники'
  self.canvas.focus_set(); self.redraw()
 def focus_search(self):
  self.entry_focus=False; self.search_focus=True; self.canvas.focus_set(); self.redraw()
 def _matches_search(self, value):
  query=str(getattr(self,'search_query','')).strip().casefold()
  return not query or query in str(value).casefold()
 def clear_search(self):
  self.search_query=''; self.search_focus=False; self.redraw()
 def key(self,e):
  if getattr(self,'search_focus',False):
   if e.keysym=='Escape': self.search_focus=False
   elif e.keysym=='BackSpace': self.search_query=self.search_query[:-1]
   elif e.keysym in ('Return','KP_Enter'): self.search_focus=False
   elif e.char and e.char.isprintable() and e.keysym not in ('Tab',): self.search_query+=e.char
   self.redraw(); return 'break'
  if not getattr(self,'entry_focus',False): return
  if e.keysym=='BackSpace': self.entry=self.entry[:-1]
  elif e.keysym in ('Return','KP_Enter'): self.add_source(); return 'break'
  elif e.char and e.char.isprintable() and e.keysym not in ('Tab',): self.entry+=e.char
  self.redraw(); return 'break'
 def click(self,e):
  # click is handled by tagged graphical controls, not by cursor-coordinate hit zones
  pass
 def nav(self,n):
  self.active=n; self.lastlog='Открыт раздел «'+n+'».'; self.redraw()
  if n=='Настройки': self.root.after(50,self.settings_dialog)
 def add_source(self):
  if self.running:
   self.lastlog='Останови мониторинг перед добавлением источника.'; self.entry=''; self.entry_focus=False; self.redraw(); return
  s=self.entry.strip()
  if not s:
   self.lastlog='Введите @имя канала или ссылку на Telegram.'
  else:
   s=s.removeprefix('https://t.me/').removeprefix('http://t.me/').removeprefix('https://telegram.me/').removeprefix('http://telegram.me/').removeprefix('t.me/').removeprefix('telegram.me/').strip('/')
   s=s.split('?',1)[0].split('#',1)[0]
   if s.startswith('s/'): s=s[2:]
   if '/' in s: s=s.split('/',1)[0]
   if s.startswith('@'): s=s[1:]
   if not re.fullmatch(r'[A-Za-z0-9_]{5,}', s):
    self.lastlog='Неверный источник. Укажи публичный @username или ссылку t.me.'
   elif s.lower() in {x.lower() for x in self.sources}:
    self.lastlog='Этот источник уже добавлен: @'+s
   else:
    s='@'+s; self.sources.append(s); self.source_enabled[s]=True; self.lastlog='Источник сохранён: '+s; self._save_state()
  self.entry=''; self.entry_focus=False; self.redraw()
 def remove_source(self, source):
  if source not in self.sources:
   self.lastlog='Источник уже удалён: '+source; self.redraw(); return
  # When monitoring is running, disable the source before removing it from the UI.
  # The engine's source_enabled callback will then skip it on the next pass.
  self.source_enabled[source]=False
  self.sources=[item for item in self.sources if item != source]
  if not self.running: self.source_enabled.pop(source,None)
  self._save_state(); self.lastlog='Источник удалён из списка: '+source
  self._network_event('INFO',self.lastlog); self.redraw()
 def start(self):
  if self.running:
   self.lastlog='Мониторинг уже запущен.'; self.redraw(); return
  if not self.sources:
   self.lastlog='Сначала добавьте хотя бы один канал-источник.'; self.redraw(); return
  if not self.destination.strip():
   self.active='Настройки'; self.lastlog='Укажите канал назначения в Настройках.'; self.redraw(); self.root.after(50,self.settings_dialog); return
  if not self.telegram_user or not self.auth_manager or not self.auth_manager.client:
   self.lastlog='Сначала подключите Telegram-аккаунт.'; self.open_auth(); self.redraw(); return
  try:
   self.engine=CopyEngine(self.auth_manager.client, BASE, self._engine_log)
   self.running=True; self.counts[0]=0; self.lastlog='Подготовка мониторинга…'; self.redraw()
   def count_cb(value):
    if value:
     self.root.after(0, self._increment_copied, value)
   active_sources=[src for src in self.sources if self.source_enabled.get(src, True)]
   if not active_sources:
    self.running=False; self.lastlog='Включите хотя бы один источник на главном экране.'; self.redraw(); return
   self.monitor_future=self.auth_manager.submit(self.engine.run(list(self.sources), self.destination.strip(), self.tags if self.flags[2] else '', self.signature if self.flags[1] else '', self.flags[0], self.interval, count_cb, lambda source: self.source_enabled.get(source, True), on_processed=lambda value: self.root.after(0, self._increment_processed, value), include_keywords=self.include_keywords, exclude_keywords=self.exclude_keywords, timezone_name=self.timezone_name, start_time=self.start_time, end_time=self.end_time, daily_limit=self.daily_limit, manual_review=self.manual_review, on_review=self._review_candidate))
   self.root.after(250, self._watch_monitor)
  except Exception as exc:
   self.running=False; self.lastlog='Не удалось запустить: '+str(exc)[:150]; self.redraw()
 async def _review_candidate(self, source, message):
  """Ask the desktop user before copying a link-heavy/promotional candidate."""
  result=concurrent.futures.Future()
  preview=(getattr(message,'message','') or '(публикация без текста)')[:1600]
  def ask():
   try:
    answer=messagebox.askyesno('Ручная проверка публикации', 'Источник: '+str(source)+'\nПубликация ID: '+str(getattr(message,'id','?'))+'\n\n'+preview+'\n\nКопировать эту публикацию?', parent=self.root)
    result.set_result(bool(answer))
   except Exception as exc:
    result.set_exception(exc)
  self.root.after(0,ask)
  return await asyncio.wrap_future(result)
 def _engine_log(self, message):
  try: self.root.after(0, self._set_log, message)
  except Exception: pass
 def _set_log(self, message):
  self.lastlog=message
  low=str(message).lower()
  level='ERROR' if any(k in low for k in ('ошиб','error','недоступ','не удалось','timeout')) else 'INFO'
  self._network_event(level, message)
  if self.engine:
   try:
    st=self.engine.stats(); self.counts[1]=max(0,st['copied']-int(self.count_offsets.get('copied',0))); self.counts[2]=max(0,st.get('copy_errors',0)-int(self.count_offsets.get('copy_errors',0))); self._save_state()
   except Exception: pass
  self.redraw()
 def _increment_processed(self, value):
  if value:
   self.counts[0]+=int(value); self._save_state(); self.redraw()
 def set_views_range(self,label):
  if label not in ('3 часа','24 часа','7 дней','30 дней','Всё'): return
  self.views_range=label
  self._save_state()
  self.lastlog='Период динамики просмотров: '+label
  self.redraw()
 def _increment_copied(self, value):
  if self.engine:
   try:
    st=self.engine.stats(); self.counts[1]=max(0,st['copied']-int(self.count_offsets.get('copied',0))); self.counts[2]=max(0,st.get('copy_errors',0)-int(self.count_offsets.get('copy_errors',0)))
   except Exception: self.counts[1]+=value
  self._save_state(); self.redraw()
 def _watch_monitor(self):
  if not self.monitor_future: return
  if not self.monitor_future.done():
   self.root.after(400, self._watch_monitor); return
  try: self.monitor_future.result()
  except Exception as exc: self.lastlog='Мониторинг завершился с ошибкой: '+str(exc)[:160]
  self.running=False; self.monitor_future=None; self._network_event('ERROR' if 'ошиб' in str(getattr(self,'lastlog','')).lower() else 'INFO', str(getattr(self,'lastlog','Мониторинг завершён'))); self.redraw()
 def stop(self):
  if self.engine:
   try:
    if self.auth_manager and self.auth_manager.loop.is_running(): self.auth_manager.loop.call_soon_threadsafe(self.engine.stop)
    else: self.engine.stop()
   except Exception: self.engine.stop()
  self.running=False; self.lastlog='Остановка мониторинга запрошена.'; self.redraw()
 def toggle_source(self,source):
  self.source_enabled[source]=not self.source_enabled.get(source,True)
  self._save_state(); self.lastlog='Источник '+source+' '+('включён.' if self.source_enabled[source] else 'выключен.'); self._network_event('INFO',self.lastlog); self.redraw()
 def toggle(self,i): self.flags[i]=not self.flags[i]; self._save_state(); self.lastlog='Параметры сохранены.'; self.redraw()
 def reset(self):
  try:
   stats=self.engine.stats() if self.engine else {'copied':self.counts[1],'copy_errors':self.counts[2]}
   self.count_offsets={'copied':int(stats.get('copied',0)),'copy_errors':int(stats.get('copy_errors',stats.get('errors',0)))}
  except Exception: self.count_offsets={'copied':self.counts[1],'copy_errors':self.counts[2]}
  self.counts=[0,0,0]; self._save_state(); self.lastlog='Отображаемые счётчики сброшены; история публикаций сохранена.'; self._network_event('INFO',self.lastlog); self.redraw()
 def check(self):
  if not self.sources:
   self.lastlog='Сначала добавь хотя бы один источник.'
  elif not self.telegram_user or not self.auth_manager or not self.auth_manager.client:
   self.lastlog='Для проверки источников сначала подключи Telegram-аккаунт.'
  else:
   self.lastlog='Проверяем доступность источников через Telegram…'; self._network_event('TX','Telegram API: проверка '+str(len(self.sources))+' источников'); self.redraw()
   fut=self.auth_manager.submit(self.auth_manager.check_sources(self.sources))
   def done(results):
    good=sum(1 for _,ok,_ in results if ok); bad=len(results)-good; self._save_state()
    self.lastlog=f'Проверка завершена: доступно {good}, ошибок {bad}.'; self._network_event('OK' if bad==0 else 'WARN',f'Проверка источников завершена: доступно {good}, ошибок {bad}')
    self.source_results=results; self.redraw()
   self._poll_future(fut,done); return
  self.redraw()
 def open_auth(self):
  win=tk.Toplevel(self.root); win.title('Авторизация Telegram'); win.geometry('520x590'); win.resizable(False,False); win.configure(bg='#100b29'); win.transient(self.root); win.update_idletasks(); win.geometry(f"520x590+{self.root.winfo_rootx()+(self.root.winfo_width()-520)//2}+{self.root.winfo_rooty()+(self.root.winfo_height()-590)//2}"); win.grab_set()
  cv=tk.Canvas(win,width=520,height=590,bg='#100b29',highlightthickness=0); cv.pack(fill='both',expand=True)
  # Glass-style rounded border, real Tk widgets on top
  self._draw_auth_round(cv,12,12,508,578,24,'#9c42ff',2)
  cv.create_text(30,34,text='TELEGRAM  /  АВТОРИЗАЦИЯ',anchor='w',fill='#f5efff',font=('Segoe UI',16,'bold'))
  cv.create_text(30,66,text='Проверка сайта не требует API ID, API HASH или входа',anchor='w',fill='#47ffd0',font=('Segoe UI',9,'bold'))
  labels=['API ID','API HASH','Номер телефона','Код из Telegram','Пароль 2FA (если включён)']
  self.auth_vars=[tk.StringVar(value=str(self.api_id or '')),tk.StringVar(value=self.api_hash or ''),tk.StringVar(value=self.phone or ''),tk.StringVar(),tk.StringVar()]
  self.auth_entries=[]
  y=100
  for i,label in enumerate(labels):
   cv.create_text(32,y,text=label,anchor='w',fill='#b9b3ef',font=('Segoe UI',10,'bold'))
   ent=tk.Entry(win,textvariable=self.auth_vars[i],bg='#19113b',fg='#f5efff',insertbackground='white',relief='flat',font=('Segoe UI',11),highlightthickness=1,highlightbackground='#6240b9',highlightcolor='#40cfff',show='•' if i in (1,4) else '')
   cv.create_window(32,y+22,width=456,height=32,anchor='nw',window=ent)
   self.auth_entries.append(ent); y+=65
  self.auth_status=tk.StringVar(value='«Проверить связь» проверяет только доступность telegram.org. API ID/HASH нужны отдельно — только для входа в аккаунт.')
  status_label=tk.Label(win,textvariable=self.auth_status,bg='#100b29',fg='#47ffd0',anchor='w',justify='left',wraplength=450,font=('Segoe UI',8))
  cv.create_window(32,532,width=456,height=32,anchor='nw',window=status_label)
  self.auth_window=win
  self.auth_check_btn=tk.Button(win,text='Проверить связь',command=self.auth_check_connection,bg='#153d7d',fg='white',activebackground='#2477c8',relief='flat',font=('Segoe UI',9,'bold'),cursor='hand2')
  cv.create_window(32,468,width=145,height=36,anchor='nw',window=self.auth_check_btn)
  self.auth_code_btn=tk.Button(win,text='Получить код',command=self.auth_request_code,bg='#6226c9',fg='white',activebackground='#8d37ef',relief='flat',font=('Segoe UI',9,'bold'),cursor='hand2')
  cv.create_window(187,468,width=145,height=36,anchor='nw',window=self.auth_code_btn)
  self.auth_login_btn=tk.Button(win,text='Войти',command=self.auth_login,bg='#153d7d',fg='white',activebackground='#2477c8',relief='flat',font=('Segoe UI',9,'bold'),cursor='hand2',state='disabled')
  cv.create_window(342,468,width=145,height=36,anchor='nw',window=self.auth_login_btn)
  self.auth_connection_ok=False
  if self.telegram_user: self.auth_status.set('Уже подключён: '+self.telegram_user)
 def _draw_auth_round(self,cv,x1,y1,x2,y2,r,color,width):
  import math
  pts=[]
  for cx,cy,a0 in [(x2-r,y1+r,-90),(x2-r,y2-r,0),(x1+r,y2-r,90),(x1+r,y1+r,180)]:
   for i in range(7):
    a=math.radians(a0+i*90/6); pts.extend([cx+r*math.cos(a),cy+r*math.sin(a)])
  cv.create_line(*pts,fill=color,width=width,smooth=True)
 def _auth_manager(self):
  if self.auth_manager is None: self.auth_manager=TelegramAuthManager()
  return self.auth_manager
 def _poll_future(self,future,success):
  if not future.done():
   self.root.after(150,lambda:self._poll_future(future,success)); return
  try: result=future.result(); success(result)
  except Exception as exc:
   msg=str(exc)
   self.auth_status.set(('Нет связи с Telegram. ' if ('недоступен' in msg.lower() or 'соедин' in msg.lower() or 'timeout' in msg.lower()) else 'Ошибка: ')+msg[:115])
   if hasattr(self,'auth_connection_ok') and not self.auth_connection_ok:
    self.auth_code_btn.config(state='disabled')
   self.auth_login_btn.config(state='disabled')
  if hasattr(self,'auth_check_btn'): self.auth_check_btn.config(state='normal')
  if getattr(self,'auth_connection_ok',False) and not (self.auth_login_btn['state']=='normal'):
   self.auth_code_btn.config(state='normal')
 def auth_check_connection(self):
  # This check intentionally tests the public Telegram website only; it must not
  # require developer API credentials or imply that account authorization works.
  self.auth_connection_ok=False
  self.auth_check_btn.config(state='disabled'); self.auth_code_btn.config(state='disabled'); self.auth_login_btn.config(state='disabled')
  self.auth_status.set('Проверяю HTTPS-доступ к telegram.org. Данные авторизации не используются…')
  self._network_event('TX','HTTPS GET https://telegram.org/ — проверка доступности')
  self.redraw()
  manager=self._auth_manager(); future=manager.submit(manager.check_website_connection())
  def done(ok):
   self.auth_connection_ok=bool(ok)
   if ok:
    self._network_event('OK','HTTPS telegram.org: ответ получен; сайт доступен')
    self.auth_status.set('Связь есть: сайт telegram.org ответил. Проверка завершена — API ID не нужен. Для входа в аккаунт отдельно заполни API ID, API HASH и телефон.')
    self.auth_code_btn.config(state='normal')
   else:
    self._network_event('ERROR','HTTPS telegram.org: нет ответа / проверка не пройдена')
    self.auth_status.set('Сайт telegram.org недоступен из этой системы. Проверь интернет, DNS, VPN/Tor или прокси.')
    self.auth_code_btn.config(state='disabled')
   self.auth_check_btn.config(state='normal')
  self._poll_future(future,done)
 def auth_request_code(self):
  if not getattr(self,'auth_connection_ok',False):
   self.auth_status.set('Сначала нажми «Проверить связь» для проверки доступности telegram.org. Доступность API проверяется отдельно при входе.')
   return
  try: api_id=int(self.auth_vars[0].get().strip())
  except ValueError: self.auth_status.set('API ID должен быть числом.'); return
  api_hash=self.auth_vars[1].get().strip(); phone=self.auth_vars[2].get().strip()
  if api_id <= 0 or not re.fullmatch(r'[0-9a-fA-F]{32}', api_hash) or not re.fullmatch(r'\+?[0-9]{7,15}', phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')):
   self.auth_status.set('Проверь API ID, API HASH (32 символа) и номер телефона в международном формате.'); return
  self.api_id=api_id; self.api_hash=api_hash; self.phone=phone.replace(' ','').replace('-','').replace('(','').replace(')',''); self._save_state()
  self.auth_status.set('Подключаемся к Telegram и запрашиваем код…'); self.auth_code_btn.config(state='disabled'); self.auth_login_btn.config(state='disabled')
  self._network_event('TX','Telegram API: запрос кода авторизации отправлен'); self.redraw()
  f=self._auth_manager().submit(self._auth_manager().request_code(api_id,api_hash,phone))
  def done(result):
   self.auth_status.set('Код отправлен в Telegram. Введи его в поле «Код из Telegram».')
   self._network_event('OK','Telegram API: код авторизации отправлен')
   self.auth_vars[3].set(''); self.auth_entries[3].focus_set(); self.auth_login_btn.config(state='normal')
  self._poll_future(f,done)
 def auth_login(self):
  code=self.auth_vars[3].get().strip(); password=self.auth_vars[4].get()
  if not code and not password: self.auth_status.set('Сначала запроси и введи код из Telegram.'); return
  self.auth_status.set('Проверяем код…'); self.auth_login_btn.config(state='disabled')
  manager=self._auth_manager()
  f=manager.submit(manager.sign_in(code,password))
  def done(result):
   if result=='PASSWORD_REQUIRED':
    self.auth_status.set('Telegram запросил пароль 2FA. Введи его в последнем поле и нажми «Войти» ещё раз.')
    self.auth_vars[3].set(''); self.auth_entries[4].focus_set(); return
   self.telegram_user=result or 'Авторизован'; self._network_event('OK','Telegram API: авторизация успешна ('+self.telegram_user+')'); self.lastlog='Telegram авторизован: '+self.telegram_user; self.auth_status.set('Успешный вход: '+self.telegram_user); self._save_state(); self.redraw()
   self.auth_window.after(900,self.auth_window.destroy)
  self._poll_future(f,done)
 def settings_dialog(self, mode='general'):
  win=tk.Toplevel(self.root); win.withdraw(); win.title('Фильтры и расписание' if mode=='filters' else 'Основные настройки TG_Coper'); win.geometry('620x650' if mode=='filters' else '620x500'); win.resizable(False,False); win.configure(bg='#100b29'); win.transient(self.root); win.protocol('WM_DELETE_WINDOW',lambda:(setattr(self,'active','Главная'),win.destroy(),self.redraw()))
  tk.Label(win,text=('ФИЛЬТРЫ И РАСПИСАНИЕ' if mode=='filters' else 'ОСНОВНЫЕ НАСТРОЙКИ'),bg='#100b29',fg='#f5efff',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=24,pady=(18,10))
  general_fields=[('Канал назначения (@username или t.me)',self.destination),('Теги через пробел или запятую',self.tags),('Подпись канала',self.signature),('Интервал проверки, секунд (5–300)',str(self.interval))]
  filter_fields=[('Ключевые слова для включения (через запятую; пусто = все)',self.include_keywords),('Ключевые слова для исключения (через запятую)',self.exclude_keywords),('Часовой пояс (например Europe/Moscow)',self.timezone_name),('Начало окна публикации (ЧЧ:ММ)',self.start_time),('Окончание окна публикации (ЧЧ:ММ)',self.end_time),('Максимум публикаций в день (1–100)',str(self.daily_limit))]
  fields=filter_fields if mode=='filters' else general_fields
  vars_=[]
  for label,value in fields:
   tk.Label(win,text=label,bg='#100b29',fg='#b9b3ef',font=('Segoe UI',8,'bold')).pack(anchor='w',padx=24,pady=(5,1))
   v=tk.StringVar(value=value); vars_.append(v)
   tk.Entry(win,textvariable=v,bg='#19113b',fg='#f5efff',insertbackground='white',relief='flat',font=('Segoe UI',9)).pack(fill='x',padx=24,ipady=4)
  review_var=tk.BooleanVar(value=self.manual_review)
  if mode=='filters':
   tk.Checkbutton(win,text='Ручная проверка сомнительных публикаций (по умолчанию выключена)',variable=review_var,bg='#100b29',fg='#f5efff',selectcolor='#19113b',activebackground='#100b29',activeforeground='#f5efff',font=('Segoe UI',8)).pack(anchor='w',padx=20,pady=(8,2))
   tk.Label(win,text='Фильтруется текст поста, не имя исходного сообщества. Исключения отбрасываются автоматически. Окно и лимит применяются к копированию.',bg='#100b29',fg='#b9b3ef',wraplength=570,justify='left',font=('Segoe UI',8)).pack(anchor='w',padx=24,pady=7)
  def save():
   try:
    if mode=='filters':
     daily_limit=int(vars_[5].get().strip())
     if not 1 <= daily_limit <= 100: raise ValueError('Дневной лимит должен быть от 1 до 100.')
     import datetime as _dt
     _dt.datetime.strptime(vars_[3].get().strip(),'%H:%M'); _dt.datetime.strptime(vars_[4].get().strip(),'%H:%M')
     if vars_[4].get().strip() <= vars_[3].get().strip(): raise ValueError('Окончание должно быть позже начала в пределах одного дня.')
     from zoneinfo import ZoneInfo
     ZoneInfo(vars_[2].get().strip())
     self.include_keywords=vars_[0].get().strip(); self.exclude_keywords=vars_[1].get().strip(); self.timezone_name=vars_[2].get().strip(); self.start_time=vars_[3].get().strip(); self.end_time=vars_[4].get().strip(); self.daily_limit=daily_limit; self.manual_review=review_var.get()
    else:
     dest=vars_[0].get().strip().removeprefix('https://t.me/').removeprefix('http://t.me/').removeprefix('t.me/').strip('/')
     if dest.startswith('@'): dest=dest[1:]
     if dest and not re.fullmatch(r'[A-Za-z0-9_]{5,}',dest): raise ValueError('Укажите @username публичного канала или ссылку t.me.')
     interval=int(vars_[3].get().strip())
     if not 5 <= interval <= 300: raise ValueError('Интервал должен быть от 5 до 300 секунд.')
     self.destination=('@'+dest) if dest else ''; self.tags=vars_[1].get().strip(); self.signature=vars_[2].get().strip(); self.interval=interval
    self._save_state(); self.lastlog=('Фильтры и расписание сохранены.' if mode=='filters' else 'Основные настройки сохранены.'); win.destroy(); self.redraw()
   except Exception as exc:
    messagebox.showerror('Проверьте параметры',str(exc) or 'Неверный формат параметров.',parent=win); return
  tk.Button(win,text='Сохранить настройки',command=save,bg='#6226c9',fg='white',activebackground='#8d37ef',relief='flat',font=('Segoe UI',10,'bold')).pack(fill='x',padx=24,pady=(4,16),ipady=7)
  win.update_idletasks(); win.deiconify(); win.lift(); win.after_idle(lambda w=win: w.grab_set() if w.winfo_exists() and w.winfo_viewable() else None)
 def dispatch(self,action):
  {'home':lambda:self.nav('Главная'),'start':self.start,'stop':self.stop,'add':self.add_source,'new_source':self.focus_entry,'check':self.check,'reset':self.reset,'settings':lambda:self.settings_dialog('general'),'filter_settings':lambda:self.settings_dialog('filters'),'auth':self.open_auth,'stats_refresh':lambda:self._collect_stats(manual=True)}.get(action,lambda:self.nav(action[4:]) if action.startswith('nav_') else None)()
class TelegramAuthManager:
 def __init__(self):
  self.loop=asyncio.new_event_loop(); self.client=None; self.phone=None; self.phone_code_hash=None; self._session_lock_handle=None; self._thread=Thread(target=self._run,daemon=True); self._thread.start()
 def _run(self): asyncio.set_event_loop(self.loop); self.loop.run_forever()
 def submit(self,coro): return asyncio.run_coroutine_threadsafe(coro,self.loop)
 def _acquire_session_lock(self):
  """Prevent two TG_Coper processes from opening the same Telethon session concurrently."""
  if self._session_lock_handle is not None:
   return
  lock_path=Path(__file__).resolve().parent/'telegram_user_session.lock'
  handle=open(lock_path,'a+')
  try:
   if os.name == 'posix':
    import fcntl
    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
   elif os.name == 'nt':
    import msvcrt
    handle.seek(0); handle.write('0'); handle.flush(); handle.seek(0)
    msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
  except (OSError, BlockingIOError):
   handle.close()
   raise RuntimeError('Файл Telegram-сессии уже используется другим процессом TG_Coper. Закрой вторую копию программы и повтори.')
  self._session_lock_handle=handle
 def _secure_session_file(self):
  try:
   import os
   path=Path(__file__).resolve().parent/'telegram_user_session.session'
   if os.name == 'posix' and path.exists(): path.chmod(0o600)
  except OSError: pass
 async def restore_session(self, api_id, api_hash):
  from telethon import TelegramClient
  self._acquire_session_lock()
  self.client=TelegramClient(str(Path(__file__).resolve().parent/'telegram_user_session'),api_id,api_hash)
  await self.client.connect()
  self._secure_session_file()
  if await self.client.is_user_authorized():
   me=await self.client.get_me(); return ('@'+me.username) if me.username else (me.first_name or 'Telegram пользователь')
  await self.client.disconnect(); self.client=None; return None
 async def check_website_connection(self):
  """Check HTTPS reachability of the official Telegram website without credentials."""
  def request_site():
   req=urllib.request.Request('https://telegram.org/', headers={'User-Agent':'TG_Coper connectivity check/1.0'})
   with urllib.request.urlopen(req, timeout=8) as response:
    status=getattr(response,'status',200)
    # Reading a tiny amount confirms the HTTPS response body can be received.
    response.read(256)
    if not 200 <= int(status) < 400:
     raise RuntimeError('HTTP status '+str(status))
    return True
  try:
   return await asyncio.to_thread(request_site)
  except Exception as exc:
   raise RuntimeError('Сайт telegram.org недоступен: '+str(exc)[:140]) from exc
 async def request_code(self,api_id,api_hash,phone):
  try: from telethon import TelegramClient
  except ImportError: raise RuntimeError('Telethon не установлен. Запусти install_requirements.bat и повтори.')
  if self.client: await self.client.disconnect()
  self._acquire_session_lock()
  self.client=TelegramClient(str(Path(__file__).resolve().parent/'telegram_user_session'),api_id,api_hash)
  await self.client.connect()
  self._secure_session_file(); self.phone=phone
  sent=await self.client.send_code_request(phone); self.phone_code_hash=sent.phone_code_hash
  return True
 async def sign_in(self,code,password=''):
  from telethon.errors import SessionPasswordNeededError
  if not self.client or not self.phone: raise RuntimeError('Сначала запроси код.')
  try:
   if not self.client.is_connected():
    await self.client.connect()
   from telethon.tl.functions.help import GetConfigRequest
   await self.client(GetConfigRequest())
  except Exception as exc:
   raise RuntimeError('Нет подтверждённого соединения с Telegram. Проверь интернет/VPN/Tor и повтори. Детали: '+str(exc)[:100]) from exc
  try:
   if password: await self.client.sign_in(password=password)
   else: await self.client.sign_in(phone=self.phone,code=code,phone_code_hash=self.phone_code_hash)
  except SessionPasswordNeededError: return 'PASSWORD_REQUIRED'
  me=await self.client.get_me()
  return ('@'+me.username) if me.username else (me.first_name or 'Telegram пользователь')
 async def collect_channel_stats(self, sources, destination):
  """Low-frequency Telegram API snapshot. No GPU work; bounded message reads."""
  from telethon.tl.functions.channels import GetFullChannelRequest
  result={'subscribers':None,'views':None,'sources_checked':0}
  targets=[]
  if destination.strip(): targets.append(destination.strip())
  targets.extend(s for s in sources if s not in targets)
  for index,target in enumerate(targets):
   try:
    entity=await self.client.get_entity(target)
    full=await self.client(GetFullChannelRequest(entity))
    chat=getattr(full,'full_chat',None)
    count=getattr(chat,'participants_count',None)
    if index==0 and destination.strip() and count is not None: result['subscribers']=int(count)
    if index==0 and destination.strip():
     result['views']=0
     async for msg in self.client.iter_messages(entity,limit=10):
      result['views']+=int(getattr(msg,'views',0) or 0)
    result['sources_checked']+=1
   except Exception:
    continue
  return result
 async def check_sources(self, sources):
  results=[]
  for source in sources:
   name=source.lstrip('@')
   try:
    entity=await self.client.get_entity(name)
    title=getattr(entity,'title',None) or getattr(entity,'username',None) or name
    results.append((source, True, str(title)))
   except Exception as exc:
    results.append((source, False, str(exc)[:120]))
  return results

def show_startup_splash():
 """Show the branded Dark Glass screen before initializing the main window."""
 splash=tk.Tk()
 splash.overrideredirect(True)
 splash.configure(bg='#050719')
 try:
  with Image.open(SPLASHIMG) as source:
   image=source.convert('RGB')
   image.thumbnail((min(1100,splash.winfo_screenwidth()-80), min(760,splash.winfo_screenheight()-100)),Image.Resampling.LANCZOS)
  photo=ImageTk.PhotoImage(image)
  splash._splash_photo=photo
  w,h=image.size
  splash.geometry(f'{w}x{h}+{(splash.winfo_screenwidth()-w)//2}+{(splash.winfo_screenheight()-h)//2}')
  tk.Label(splash,image=photo,borderwidth=0,highlightthickness=0).pack()
 except Exception:
  splash.geometry('560x180')
  tk.Label(splash,text='TG_Coper',font=('Segoe UI',30,'bold'),fg='#40cfff',bg='#050719').pack(pady=(35,8))
  tk.Label(splash,text='Запуск приложения…',font=('Segoe UI',12),fg='#b9b3ef',bg='#050719').pack()
 splash.update_idletasks()
 return splash

def main():
 splash=show_startup_splash()
 splash.after(2200,splash.destroy)
 splash.mainloop()
 root=tk.Tk(); app=App(root)
 session_path=BASE/'telegram_user_session.session'
 if app.api_id and app.api_hash and session_path.exists():
  app.auth_start_status='Проверка сохранённой сессии…'; app._network_event('INFO','Запуск: проверяю сохранённую Telegram-сессию'); app.redraw()
  def restore():
   try:
    manager=app._auth_manager(); fut=manager.submit(manager.restore_session(int(app.api_id), app.api_hash))
    def poll():
     if not fut.done(): root.after(250,poll); return
     try:
      who=fut.result()
      if who:
       app.telegram_user=who; app.auth_start_status='ПОДТВЕРЖДЕНА'; app.lastlog='Восстановлена Telegram-сессия: '+who; app._network_event('OK','Авторизация подтверждена при запуске: '+who)
      else:
       app.auth_start_status='НЕ АВТОРИЗОВАНА'; app.lastlog='Файл сессии найден, но Telegram не подтвердил авторизацию.'; app._network_event('WARN',app.lastlog)
      app.redraw()
     except Exception as exc:
      app.auth_start_status='ОШИБКА ПРОВЕРКИ'; app.lastlog='Сохранённая сессия не восстановлена: '+str(exc)[:160]; app._network_event('ERROR',app.lastlog); app.redraw()
    poll()
   except Exception as exc:
    app.auth_start_status='ОШИБКА ЗАПУСКА'; app.lastlog='Не удалось начать проверку сессии: '+str(exc)[:140]; app._network_event('ERROR',app.lastlog); app.redraw()
  root.after(300,restore)
 elif not session_path.exists():
  app.auth_start_status='Файл сессии не найден'; app._network_event('WARN','Запуск: telegram_user_session.session не найден')
 elif not app.api_id or not app.api_hash:
  app.auth_start_status='Нужны API ID и API HASH'; app._network_event('WARN','Сессия найдена, но API ID/HASH отсутствуют в настройках')
 for act in ['start','stop','add','new_source','check','reset','settings']:
  root.bind_all('<Button-1>',lambda e:None,add='+')
 # canvas button tags dispatch based on tag suffix
 for act in ['start','stop','add','new_source','check','reset','settings']:
  app.canvas.tag_bind('btn_'+act,'<Button-1>',lambda e,a=act:app.dispatch(a))
 app.start_stats_scheduler()
 root.mainloop()
if __name__=='__main__': main()
