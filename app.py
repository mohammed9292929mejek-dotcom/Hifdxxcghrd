from flask import Flask, request, redirect, session, send_from_directory, jsonify
import os, html, uuid, mimetypes
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'PARTO_2026')
DATABASE_URL = os.getenv('DATABASE_URL', '')
PORT = int(os.getenv('PORT', '8080'))
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
for d in ('avatars','media','files','voice'):
    os.makedirs(os.path.join(UPLOAD_ROOT,d), exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024

class DB:
    def __init__(self):
        if not DATABASE_URL: raise RuntimeError('DATABASE_URL is not configured.')
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)
    def execute(self,*a,**k): self.cur.execute(*a,**k); return self.cur
    def fetchone(self): return self.cur.fetchone()
    def fetchall(self): return self.cur.fetchall()
    def commit(self): self.conn.commit()
    def rollback(self): self.conn.rollback()
    def close(self):
        try: self.cur.close()
        finally: self.conn.close()
def db(): return DB()
def esc(v): return html.escape(str(v or ''))
def now(): return datetime.now().isoformat(timespec='seconds')

def init_db():
    x=db()
    try:
        x.execute("""CREATE TABLE IF NOT EXISTS users(
          id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE,
          password TEXT NOT NULL, emoji TEXT DEFAULT '👤', bio TEXT DEFAULT '',
          admin INTEGER DEFAULT 0, banned INTEGER DEFAULT 0, verified INTEGER DEFAULT 0,
          pro INTEGER DEFAULT 0, language TEXT DEFAULT 'en', avatar TEXT DEFAULT '')""")
        x.execute("""CREATE TABLE IF NOT EXISTS rooms(
          id SERIAL PRIMARY KEY, name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
          kind TEXT NOT NULL, owner TEXT NOT NULL, emoji TEXT DEFAULT '💬', bio TEXT DEFAULT '',
          verified INTEGER DEFAULT 0, members INTEGER DEFAULT 0, public INTEGER DEFAULT 0, banned INTEGER DEFAULT 0)""")
        x.execute("""CREATE TABLE IF NOT EXISTS messages(
          id SERIAL PRIMARY KEY, room INTEGER, room_id INTEGER, username TEXT NOT NULL,
          text TEXT DEFAULT '', created_at TEXT DEFAULT '', created TEXT DEFAULT '',
          reply INTEGER DEFAULT 0, edited INTEGER DEFAULT 0, image TEXT DEFAULT '',
          media_type TEXT DEFAULT '', media_name TEXT DEFAULT '', media_url TEXT DEFAULT '')""")
        x.execute("""CREATE TABLE IF NOT EXISTS private_messages(
          id SERIAL PRIMARY KEY, sender TEXT NOT NULL, receiver TEXT NOT NULL,
          text TEXT DEFAULT '', created_at TEXT DEFAULT '', image TEXT DEFAULT '',
          media_type TEXT DEFAULT '', media_name TEXT DEFAULT '', media_url TEXT DEFAULT '')""")
        x.execute("""CREATE TABLE IF NOT EXISTS private_chat_state(
          id SERIAL PRIMARY KEY, owner TEXT NOT NULL, other_user TEXT NOT NULL,
          unread INTEGER DEFAULT 0, UNIQUE(owner,other_user))""")
        x.execute("""CREATE TABLE IF NOT EXISTS room_members(
          id SERIAL PRIMARY KEY, room_id INTEGER NOT NULL, username TEXT NOT NULL,
          joined_at TEXT DEFAULT '', UNIQUE(room_id,username))""")
        x.execute("""CREATE TABLE IF NOT EXISTS follows(
          id SERIAL PRIMARY KEY, follower TEXT NOT NULL, target TEXT NOT NULL,
          created_at TEXT DEFAULT '', UNIQUE(follower,target))""")
        def cols(t):
            x.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name=%s",(t,))
            return {r['column_name'] for r in x.fetchall()}
        migrations={
          'users': {'avatar':"TEXT DEFAULT ''",'language':"TEXT DEFAULT 'en'"},
          'rooms': {'verified':'INTEGER DEFAULT 0','members':'INTEGER DEFAULT 0','public':'INTEGER DEFAULT 0','banned':'INTEGER DEFAULT 0','bio':"TEXT DEFAULT ''"},
          'messages': {'room':'INTEGER','room_id':'INTEGER','created_at':"TEXT DEFAULT ''",'created':"TEXT DEFAULT ''",'reply':'INTEGER DEFAULT 0','edited':'INTEGER DEFAULT 0','image':"TEXT DEFAULT ''",'media_type':"TEXT DEFAULT ''",'media_name':"TEXT DEFAULT ''",'media_url':"TEXT DEFAULT ''"},
          'private_messages': {'created_at':"TEXT DEFAULT ''",'image':"TEXT DEFAULT ''",'media_type':"TEXT DEFAULT ''",'media_name':"TEXT DEFAULT ''",'media_url':"TEXT DEFAULT ''"}}
        for t, fields in migrations.items():
            have=cols(t)
            for n,d in fields.items():
                if n not in have: x.execute(f'ALTER TABLE {t} ADD COLUMN {n} {d}')
        x.execute("UPDATE messages SET room=room_id WHERE room IS NULL AND room_id IS NOT NULL")
        x.execute("UPDATE messages SET room_id=room WHERE room_id IS NULL AND room IS NOT NULL")
        x.execute("UPDATE messages SET created_at=%s WHERE created_at IS NULL OR created_at=''",(now(),))
        x.execute("UPDATE messages SET created=created_at WHERE created IS NULL OR created='' ")
        x.execute("SELECT id FROM users WHERE username='parto'")
        if not x.fetchone():
            x.execute("INSERT INTO users(username,email,password,emoji,bio,admin,verified,pro) VALUES(%s,%s,%s,%s,%s,1,1,1)",('parto','PRATO@B',generate_password_hash('M123'),'⚡','Official Parto'))
        else:
            x.execute("UPDATE users SET admin=1,verified=1,pro=1 WHERE username='parto'")
        x.execute("SELECT id FROM rooms WHERE username='parto'")
        if not x.fetchone():
            x.execute("INSERT INTO rooms(name,username,kind,owner,emoji,bio,verified,members,public) VALUES(%s,'parto','channel','parto','⚡','Official Parto channel',1,0,1)",('Parto',))
        else:
            x.execute("UPDATE rooms SET kind='channel',owner='parto',verified=1,public=1 WHERE username='parto'")
        x.execute("SELECT id FROM rooms WHERE username='gangs'")
        if not x.fetchone():
            x.execute("INSERT INTO rooms(name,username,kind,owner,emoji,bio,verified,members,public) VALUES(%s,'gangs','group','parto','👥','Official public group',1,0,1)",('گنگ ها',))
        else: x.execute("UPDATE rooms SET name='گنگ ها',kind='group',public=1 WHERE username='gangs'")
        x.commit()
    except Exception:
        x.rollback(); raise
    finally: x.close()

def current():
    u=session.get('user')
    if not u:return None
    x=db(); x.execute('SELECT * FROM users WHERE username=%s',(u,)); r=x.fetchone(); x.close(); return r

def is_admin(u): return bool(u and int(u.get('admin') or 0))
def is_pro(u): return bool(u and int(u.get('pro') or 0))
def badge(u):
    if not u:return ''
    return "<span class='tick'>✓</span>" if int(u.get('verified') or 0) else ''

def save_upload(fs, folder, allow):
    if not fs or not fs.filename:return None
    data=fs.read()
    if not data or len(data)>allow: raise ValueError('File is too large.')
    ext=os.path.splitext(fs.filename)[1].lower()
    safe_ext={'.jpg','.jpeg','.png','.gif','.webp','.mp4','.webm','.mov','.pdf','.txt','.zip','.rar','.doc','.docx','.xls','.xlsx','.mp3','.m4a','.ogg','.wav'}
    if ext not in safe_ext: raise ValueError('File type is not supported.')
    name=uuid.uuid4().hex+ext
    path=os.path.join(UPLOAD_ROOT,folder,name)
    with open(path,'wb') as f:f.write(data)
    return name

def file_url(folder,name): return '/uploads/'+folder+'/'+name if name else ''

CSS=r'''<style>
:root{--bg:#07080d;--card:#10131b;--card2:#151923;--text:#f7f9ff;--muted:#8e96a8;--line:#222938;--accent:#4d8dff;--accent2:#7c5cff;--danger:#ff4d67;--shadow:0 16px 50px #0008}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(circle at 20% 0,#182445 0,#07080d 38%),#07080d;color:var(--text);font-family:Inter,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}a{text-decoration:none;color:inherit}button,input,textarea,select{font:inherit}button{cursor:pointer}.app{min-height:100vh}.top{height:64px;display:flex;align-items:center;justify-content:space-between;padding:0 16px;position:sticky;top:0;z-index:10;background:#090b11dd;backdrop-filter:blur(20px);border-bottom:1px solid var(--line)}.brand{font-size:21px;font-weight:850;letter-spacing:-.5px}.brand i{color:#6d9dff;font-style:normal}.main{max-width:1180px;margin:auto;padding:18px 14px 90px}.grid{display:grid;grid-template-columns:280px 1fr;gap:16px}.card{background:linear-gradient(145deg,#121621ee,#0c0f16ee);border:1px solid var(--line);border-radius:24px;box-shadow:var(--shadow);overflow:hidden}.side{padding:14px;height:max-content;position:sticky;top:82px}.nav a{display:flex;align-items:center;gap:12px;padding:13px 14px;border-radius:15px;color:#aab1c1;margin:3px 0}.nav a:hover,.nav a.active{background:#1a2232;color:#fff}.nav b{font-size:17px}.content{min-width:0}.hero{padding:22px}.muted{color:var(--muted)}.title{font-size:26px;font-weight:850;margin:0 0 6px}.row{display:flex;align-items:center;gap:10px}.between{justify-content:space-between}.avatar{width:46px;height:46px;border-radius:15px;display:grid;place-items:center;background:#1b2332;border:1px solid #2a3345;overflow:hidden;font-size:24px;flex:none}.avatar img{width:100%;height:100%;object-fit:cover}.userline{display:flex;gap:8px;align-items:center;font-weight:750}.tick{display:inline-grid;place-items:center;width:18px;height:18px;border-radius:50%;background:#3187ff;color:white;font-size:12px}.pro{font-size:10px;padding:3px 7px;border-radius:8px;background:linear-gradient(90deg,#795cff,#c35cff);font-weight:900}.list{display:flex;flex-direction:column}.item{padding:13px 15px;border-bottom:1px solid #1c2230}.item:last-child{border-bottom:0}.btn{border:0;border-radius:14px;padding:11px 15px;background:#20283a;color:#fff;font-weight:750}.btn.primary{background:linear-gradient(135deg,#4d8dff,#705cff)}.btn.danger{background:#3a1820;color:#ff93a2}.btn.ghost{background:transparent;border:1px solid var(--line)}.input,.textarea,.select{width:100%;background:#0b0e15;border:1px solid #273044;color:#fff;border-radius:14px;padding:12px 14px;outline:none}.textarea{min-height:110px;resize:vertical}.form{display:grid;gap:11px}.form label{font-size:13px;color:#aab1c1}.search{margin-bottom:12px}.chatbox{min-height:70vh;display:flex;flex-direction:column}.chathead{padding:14px 16px;border-bottom:1px solid var(--line)}.messages{padding:15px;display:flex;flex-direction:column;gap:9px;flex:1}.bubble{max-width:82%;padding:10px 12px;border-radius:18px;background:#171d2a;border:1px solid #252d3c;align-self:flex-start}.bubble.mine{align-self:flex-end;background:#1c4d9d;border-color:#2866c9}.bubble img,.bubble video{max-width:100%;border-radius:12px;margin-top:7px}.bubble audio{width:240px;max-width:100%;margin-top:7px}.meta{font-size:11px;color:#8f9aae;margin-top:5px}.composer{padding:12px;border-top:1px solid var(--line);display:flex;gap:8px;align-items:center}.composer .input{flex:1}.iconbtn{width:44px;height:44px;border-radius:14px;border:1px solid var(--line);background:#151a25;color:white}.bottom{display:none}.pill{display:inline-flex;gap:6px;padding:7px 10px;border-radius:12px;background:#171d2a;color:#b9c2d4;font-size:12px}.profile{padding:24px;text-align:center}.bigavatar{width:92px;height:92px;border-radius:28px;margin:auto;display:grid;place-items:center;background:#192234;font-size:42px;overflow:hidden}.bigavatar img{width:100%;height:100%;object-fit:cover}.stats{display:flex;justify-content:center;gap:30px;margin:18px}.stats b{display:block;font-size:19px}.stats span{font-size:12px;color:var(--muted)}.media{border-radius:14px;max-height:330px;max-width:100%}.empty{text-align:center;padding:55px 20px;color:var(--muted)}.notice{padding:12px 14px;background:#182238;border:1px solid #2a3d65;border-radius:14px;margin-bottom:12px}.inline{display:inline}.filecard{display:flex;align-items:center;gap:10px;background:#111827;padding:10px;border-radius:13px;margin-top:7px}.filecard span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.tabs{display:flex;gap:8px;overflow:auto;padding-bottom:5px}.tabs a{white-space:nowrap}.check{accent-color:#4d8dff}@media(max-width:800px){.grid{display:block}.side{display:none}.main{padding:10px 10px 86px}.top{height:58px}.card{border-radius:20px}.bottom{display:flex;position:fixed;bottom:0;left:0;right:0;height:68px;background:#090b11ee;backdrop-filter:blur(20px);border-top:1px solid var(--line);z-index:20;justify-content:space-around}.bottom a{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;color:#8f98ab;font-size:11px}.bottom a.active{color:#fff}.bottom b{font-size:20px}.bubble{max-width:90%}.composer{position:sticky;bottom:68px;background:#090b11ee;backdrop-filter:blur(18px)}.title{font-size:22px}.hero{padding:17px}}
/* Mobile-first polish */
html{font-size:16px;-webkit-text-size-adjust:100%}
body{min-width:320px;overflow-x:hidden}
button,.btn,.iconbtn{min-height:44px}
.input,.textarea,.select{font-size:16px}
.top{padding-left:max(12px,env(safe-area-inset-left));padding-right:max(12px,env(safe-area-inset-right))}
.bottom{padding-bottom:env(safe-area-inset-bottom);height:calc(68px + env(safe-area-inset-bottom))}
.chatbox{overflow:hidden}
.messages{overscroll-behavior:contain}
.media{display:block;width:auto;height:auto;object-fit:contain}
.joinbar{justify-content:space-between}
.roomstate{margin-top:4px}
@media(max-width:800px){
 body{font-size:15px}
 .top{height:56px;padding-top:env(safe-area-inset-top)}
 .top .pill{display:none}
 .top .btn{padding:8px 11px;font-size:13px;min-height:40px}
 .brand{font-size:20px}
 .main{width:100%;max-width:none;margin:0;padding:8px 8px calc(82px + env(safe-area-inset-bottom))}
 .content{width:100%}
 .card{width:100%;border-radius:18px}
 .hero{padding:16px}
 .title{font-size:21px;line-height:1.2}
 .row{min-width:0}
 .row>*{min-width:0}
 .roomhead{flex:1}
 .actions{flex-shrink:0}
 .actions .btn{padding:9px 10px;font-size:12px}
 .chatbox{height:calc(100svh - 78px);min-height:0;border-radius:16px}
 .chathead{padding:10px 11px;position:sticky;top:0;z-index:3;background:#090b11f2;backdrop-filter:blur(18px)}
 .chathead .avatar{width:42px;height:42px}
 .messages{padding:10px 8px 12px;gap:7px;overflow-y:auto}
 .bubble{max-width:88%;padding:9px 11px;border-radius:16px;overflow-wrap:anywhere}
 .bubble .userline{font-size:12px}
 .composer{padding:8px;gap:6px;position:sticky;bottom:calc(68px + env(safe-area-inset-bottom));z-index:4}
 .composer .input{min-width:0;height:44px}
 .iconbtn{width:42px;height:42px;padding:0;display:grid;place-items:center;flex:none}
 .filecard{max-width:100%}
 .media{max-width:min(78vw,320px);max-height:260px}
 .profile{padding:22px 14px}
 .bigavatar{width:84px;height:84px}
 .stats{gap:22px}
 .form{gap:9px}
 .form .btn{width:100%}
 .hero>form.row{align-items:stretch;flex-direction:column}
 .hero>form.row .btn{width:100%}
 .item{padding:12px}
 .bottom a{min-width:56px}
}
@media(max-width:380px){
 .main{padding-left:6px;padding-right:6px}
 .actions .btn{font-size:11px;padding:8px}
 .bubble{max-width:92%}
 .composer{gap:4px}
 .composer .input{font-size:15px}
}
/* 320px compact phone layout */
@media(max-width:340px){
 html{font-size:14px}
 body{min-width:320px;font-size:13px}
 .top{height:50px;padding-left:8px;padding-right:8px}
 .brand{font-size:18px}
 .top .btn{min-height:36px;padding:7px 9px;font-size:11px}
 .main{padding:6px 4px calc(70px + env(safe-area-inset-bottom))}
 .card{border-radius:14px}
 .hero{padding:12px}
 .title{font-size:18px}
 .item{padding:9px 10px}
 .avatar{width:38px;height:38px;border-radius:12px;font-size:19px}
 .bigavatar{width:70px;height:70px;border-radius:22px;font-size:32px}
 .userline{gap:5px;font-size:13px}
 .tick{width:15px;height:15px;font-size:9px}
 .pro{font-size:8px;padding:2px 5px}
 .btn{min-height:38px;padding:8px 10px;border-radius:11px;font-size:12px}
 .input,.textarea,.select{padding:9px 10px;border-radius:11px;font-size:16px}
 .textarea{min-height:85px}
 .chatbox{height:calc(100svh - 66px);border-radius:13px}
 .chathead{padding:8px}
 .chathead .avatar{width:38px;height:38px}
 .messages{padding:8px 5px 10px;gap:5px}
 .bubble{max-width:93%;padding:7px 9px;border-radius:13px}
 .meta{font-size:9px}
 .composer{padding:5px;gap:4px;bottom:calc(60px + env(safe-area-inset-bottom))}
 .composer .input{height:38px;padding:7px 9px}
 .iconbtn{width:38px;height:38px;min-height:38px;border-radius:10px}
 .media{max-width:285px;max-height:220px}
 .filecard{padding:8px;gap:7px}
 .profile{padding:16px 9px}
 .stats{gap:16px;margin:12px}
 .stats b{font-size:16px}
 .stats span{font-size:10px}
 .bottom{height:60px}
 .bottom a{min-width:48px;font-size:9px;gap:2px}
 .bottom b{font-size:17px}
 .form{gap:7px}
 .form label{font-size:11px}
 .notice{padding:9px 10px;border-radius:11px}
 .pill{padding:5px 7px;font-size:10px}
 .tabs{gap:5px}
}
@media(max-width:320px){
 body{min-width:320px;overflow-x:auto}
 .main{padding-left:3px;padding-right:3px}
}
<style>.admin-actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:10px}.admin-actions form{margin:0}@media(max-width:420px){.admin-actions{display:grid;grid-template-columns:1fr 1fr}.admin-actions .btn{width:100%;padding:9px 7px;font-size:11px}.admin-item{padding:10px}.admin-item .muted{font-size:10px}}</style></style>'''

def voice_script():
    return '''<script>
function voiceRecorder(formId,inputId,buttonId){
 const f=document.getElementById(formId),i=document.getElementById(inputId),b=document.getElementById(buttonId); if(!f||!i||!b)return;
 let rec=null,chunks=[];
 b.onclick=async()=>{
  if(rec&&rec.state==='recording'){rec.stop();b.textContent='●';b.title='Voice';return;}
  if(!navigator.mediaDevices||!navigator.mediaDevices.getUserMedia){alert('Voice recording is not supported on this browser.');return;}
  try{const stream=await navigator.mediaDevices.getUserMedia({audio:true});chunks=[];rec=new MediaRecorder(stream);rec.ondataavailable=e=>{if(e.data.size)chunks.push(e.data)};rec.onstop=()=>{stream.getTracks().forEach(t=>t.stop());const blob=new Blob(chunks,{type:'audio/webm'});const file=new File([blob],'voice-'+Date.now()+'.webm',{type:'audio/webm'});const dt=new DataTransfer();dt.items.add(file);i.files=dt.files;f.querySelector('input[name=text]').placeholder='Voice ready — press send';};rec.start();b.textContent='■';b.title='Stop recording';}catch(e){alert('Microphone permission was not granted.');}
 };
}
</script>'''

def layout(body,title='Parto',active='home'):
    u=current();
    if not u:return '<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1">'+CSS+f'<title>{esc(title)}</title></head><body>{body}</body></html>'
    links=[('home','⌂','Home','/chat'),('search','⌕','Search','/search'),('create','＋','Create','/create'),('profile','◉','Profile','/u/'+esc(u['username'])),('settings','⚙','Settings','/settings')]
    nav=''.join(f'<a class="{("active" if active==k else "")}" href="{url}"><b>{ic}</b><span>{label}</span></a>' for k,ic,label,url in links)
    bottom=''.join(f'<a class="{("active" if active==k else "")}" href="{url}"><b>{ic}</b><span>{label}</span></a>' for k,ic,label,url in links[:4])
    return '<!doctype html><html lang="en"><head><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="theme-color" content="#080a10"><title>'+esc(title)+'</title>'+CSS+'</head><body><div class="app"><header class="top"><a class="brand" href="/chat">Par<i>to</i></a><div class="row"><span class="pill">@'+esc(u['username'])+'</span><a href="/logout" class="btn ghost">Log out</a></div></header><main class="main"><div class="grid"><aside class="card side"><div class="nav">'+nav+'</div></aside><section class="content">'+body+'</section></div></main><nav class="bottom">'+bottom+'</nav></div>'+voice_script()+'</body></html>'

def need_login(): return redirect('/login') if not session.get('user') else None

@app.route('/')
def index(): return redirect('/chat' if session.get('user') else '/login')

@app.route('/register',methods=['GET','POST'])
def register():
    msg=''
    if request.method=='POST':
        username=request.form.get('username','').strip().lower(); email=request.form.get('email','').strip(); password=request.form.get('password','')
        if len(username)<3 or len(password)<4: msg='Use a username with 3+ characters and a password with 4+ characters.'
        elif username in ('parto','gangs'): msg='That username is reserved.'
        else:
            x=db()
            try:
                x.execute('INSERT INTO users(username,email,password) VALUES(%s,%s,%s)',(username,email,generate_password_hash(password)));x.commit();session['user']=username;return redirect('/chat')
            except Exception: x.rollback();msg='Username or email already exists.'
            finally:x.close()
    body=f'''<div class="card hero"><h1 class="title">Create your Parto account</h1><p class="muted">Fast, private and mobile-first.</p><form class="form" method="post"><input class="input" name="username" placeholder="Username" required><input class="input" name="email" type="email" placeholder="Email"><input class="input" name="password" type="password" placeholder="Password" required><button class="btn primary">Create account</button><a class="btn ghost" href="/login">I already have an account</a></form><p class="muted">{esc(msg)}</p></div>'''
    return layout(body,'Register')

@app.route('/login',methods=['GET','POST'])
def login():
    msg=''
    if request.method=='POST':
        username=request.form.get('username','').strip().lower(); password=request.form.get('password','')
        x=db();x.execute('SELECT * FROM users WHERE username=%s',(username,));u=x.fetchone();x.close()
        if u and check_password_hash(u['password'],password) and not u['banned']:
            session['user']=username;return redirect('/chat')
        msg='Invalid login or account unavailable.'
    body=f'''<div class="card hero"><h1 class="title">Welcome to Parto</h1><p class="muted">Your conversations, groups and channels.</p><form class="form" method="post"><input class="input" name="username" placeholder="Username" required><input class="input" name="password" type="password" placeholder="Password" required><button class="btn primary">Log in</button><a class="btn ghost" href="/register">Create account</a></form><p class="muted">{esc(msg)}</p></div>''';return layout(body,'Login')

@app.route('/logout')
def logout(): session.clear();return redirect('/login')

@app.route('/chat')
def chat():
    r=need_login()
    if r:return r
    u=current();x=db()
    x.execute("SELECT * FROM rooms WHERE public=1 AND banned=0 ORDER BY CASE WHEN username='parto' THEN 0 WHEN username='gangs' THEN 1 ELSE 2 END,id")
    public=x.fetchall()
    x.execute("SELECT * FROM users WHERE username<>%s AND banned=0 ORDER BY username LIMIT 100",(u['username'],));users=x.fetchall();x.close()
    items=''.join(f'''<a class="item row" href="/c/{esc(r['username'])}"><div class="avatar">{esc(r['emoji'])}</div><div style="flex:1"><div class="userline">{esc(r['name'])} {badge(r)}</div><div class="muted">@{esc(r['username'])} · {esc(r['kind'])}</div></div><span class="pill">{int(r['members'] or 0)} members</span></a>''' for r in public)
    people=''.join(f'''<a class="item row" href="/u/{esc(p['username'])}"><div class="avatar">{esc(p['emoji'])}</div><div><div class="userline">@{esc(p['username'])} {badge(p)}</div><div class="muted">{esc(p['bio'])}</div></div></a>''' for p in users)
    body=f'''<div class="card hero"><div class="row between"><div><h1 class="title">Parto</h1><div class="muted">Public spaces</div></div><a class="btn primary" href="/join">Join by link</a></div></div><div class="card list" style="margin-top:12px">{items}</div><div class="card" style="margin-top:12px"><div class="hero"><h2>People</h2><p class="muted">Open a profile to follow or start a private chat.</p></div><div class="list">{people}</div></div>'''
    return layout(body,'Parto','home')

@app.route('/search')
def search():
    r=need_login()
    if r:return r
    q=request.args.get('q','').strip();x=db();rooms=[];users=[]
    if q:
        x.execute("SELECT * FROM rooms WHERE banned=0 AND (public=1 OR owner=%s) AND (username ILIKE %s OR name ILIKE %s) ORDER BY public DESC LIMIT 50",(u['username'],'%'+q+'%','%'+q+'%'));rooms=x.fetchall()
        x.execute("SELECT * FROM users WHERE username ILIKE %s AND banned=0 LIMIT 50",('%'+q+'%',));users=x.fetchall()
    x.close()
    rr=''.join(f'<a class="item row" href="/c/{esc(z["username"])}"><div class="avatar">{esc(z["emoji"])}</div><div><b>{esc(z["name"])}</b>{badge(z)}<div class="muted">@{esc(z["username"])}</div></div></a>' for z in rooms)
    uu=''.join(f'<a class="item row" href="/u/{esc(z["username"])}"><div class="avatar">{esc(z["emoji"])}</div><div><b>@{esc(z["username"])}</b>{badge(z)}<div class="muted">{esc(z["bio"])}</div></div></a>' for z in users)
    body=f'''<div class="card hero"><h1 class="title">Search</h1><form class="row" method="get"><input class="input" name="q" value="{esc(q)}" placeholder="Search username, group or channel"><button class="btn primary">Search</button></form></div><div class="card list" style="margin-top:12px">{rr or '<div class="empty">No spaces found.</div>'}</div><div class="card list" style="margin-top:12px">{uu or '<div class="empty">No users found.</div>'}</div>''';return layout(body,'Search','search')

@app.route('/join',methods=['GET','POST'])
def join():
    r=need_login()
    if r:return r
    u=current();msg=''
    if request.method=='POST':
        val=request.form.get('link','').strip().rstrip('/')
        user=val.split('/')[-1].lstrip('@').lower()
        x=db()
        try:
            x.execute('SELECT id FROM rooms WHERE username=%s',(user,));room=x.fetchone()
            if not room:
                msg='Channel or group not found.'
            else:
                x.execute('INSERT INTO room_members(room_id,username,joined_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(room['id'],u['username'],now()))
                x.execute('UPDATE rooms SET members=(SELECT COUNT(*) FROM room_members WHERE room_id=%s) WHERE id=%s',(room['id'],room['id']))
                x.commit()
                return redirect('/c/'+user)
        except Exception:
            x.rollback();msg='Could not join this space.'
        finally:x.close()
    body=f'''<div class="card hero"><h1 class="title">Join by link</h1><p class="muted">Paste a Parto channel or group link/username.</p><form class="form" method="post"><input class="input" name="link" placeholder="parto.app/c/username or @username" required><button class="btn primary">Join</button></form><p class="muted">{esc(msg)}</p></div>''';return layout(body,'Join')

@app.route('/c/<username>')
def room(username):
    r=need_login()
    if r:return r
    u=current();x=db();x.execute('SELECT * FROM rooms WHERE username=%s',(username,));room=x.fetchone()
    if room and int(room.get('banned') or 0) and room['owner']!=u['username'] and not is_admin(u):
        x.close();return layout('<div class="card empty">This space is unavailable.</div>','Unavailable')
    if not room:x.close();return layout('<div class="card empty">Channel or group not found.</div>','Not found')
    x.execute('SELECT * FROM room_members WHERE room_id=%s AND username=%s',(room['id'],u['username']));joined=bool(x.fetchone())
    x.execute('SELECT * FROM messages WHERE room_id=%s OR room=%s ORDER BY id ASC LIMIT 300',(room['id'],room['id']));msgs=x.fetchall();x.close()
    if room['public'] and not joined:
        x=db();x.execute('INSERT INTO room_members(room_id,username,joined_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(room['id'],u['username'],now()));x.execute('UPDATE rooms SET members=(SELECT COUNT(*) FROM room_members WHERE room_id=%s) WHERE id=%s',(room['id'],room['id']));x.commit();x.close();joined=True
    bubbles=''
    for m in msgs:
        media=''
        mt=m.get('media_type') or ''
        url=m.get('media_url') or ''
        if mt.startswith('image/'): media=f'<img class="media" src="{esc(url)}">'
        elif mt.startswith('video/'): media=f'<video class="media" controls src="{esc(url)}"></video>'
        elif mt.startswith('audio/'): media=f'<audio controls src="{esc(url)}"></audio>'
        elif url: media=f'<a class="filecard" href="{esc(url)}" download><b>FILE</b><span>{esc(m.get("media_name"))}</span></a>'
        bubbles+=f'<div class="bubble {"mine" if m["username"]==u["username"] else ""}"><div class="userline">@{esc(m["username"])}</div>{("<div>"+esc(m.get("text"))+"</div>") if m.get("text") else ""}{media}<div class="meta">{esc(m.get("created_at"))}</div></div>'
    owner=room['owner']==u['username'] or is_admin(u)
    can_post=(room['kind']=='group' and joined) or owner
    form=''
    if can_post:
        form=f'''<form id="chatForm" class="composer" action="/send/{room['id']}" method="post" enctype="multipart/form-data"><input class="input" name="text" placeholder="Message"><label class="iconbtn" title="Photo / Video / File">＋<input id="mediaInput" type="file" name="media" hidden></label><button type="button" class="iconbtn" id="recordBtn" title="Voice">●</button><button class="iconbtn" title="Send">➤</button></form><script>voiceRecorder('chatForm','mediaInput','recordBtn')</script>'''
    elif room['kind']=='channel':
        form='<div class="composer"><span class="muted">This channel is read-only for members.</span></div>'
    else:
        form=f'''<div class="composer joinbar"><span class="muted">Join this group to send messages.</span><form method="post" action="/join"><input type="hidden" name="link" value="@{esc(room['username'])}"><button class="btn primary">Join group</button></form></div>'''
    edit=f'<a class="btn ghost" href="/edit-room/{room["id"]}">Edit</a>' if owner else ''
    join_state='<span class="pill">Joined</span>' if joined else '<span class="pill">Not joined</span>'
    body=f'''<div class="card chatbox"><div class="chathead row between"><div class="row roomhead"><div class="avatar">{esc(room['emoji'])}</div><div><div class="userline">{esc(room['name'])} {badge(room)}</div><div class="muted">@{esc(room['username'])} · {int(room['members'] or 0)} members</div><div class="roomstate">{join_state}</div></div></div><div class="row actions">{edit}<button class="btn ghost" type="button" onclick="navigator.clipboard&&navigator.clipboard.writeText(location.href)">Share</button></div></div><div class="messages">{bubbles or '<div class="empty">No messages yet.</div>'}</div>{form}</div>''';return layout(body,room['name'],'home')

@app.route('/send/<int:room_id>',methods=['POST'])
def send_room(room_id):
    r=need_login()
    if r:return r
    u=current();x=db();x.execute('SELECT * FROM rooms WHERE id=%s',(room_id,));room=x.fetchone()
    if room and int(room.get('banned') or 0) and room['owner']!=u['username'] and not is_admin(u):
        x.close();return redirect('/chat')
    if not room:x.close();return redirect('/chat')
    x.execute('SELECT 1 FROM room_members WHERE room_id=%s AND username=%s',(room_id,u['username']))
    joined=bool(x.fetchone())
    if not (room['owner']==u['username'] or is_admin(u) or (room['kind']=='group' and joined)):
        x.close();return redirect('/c/'+room['username'])
    text=request.form.get('text','').strip();fs=request.files.get('media'); media_url='';media_type='';media_name=''
    try:
        if fs and fs.filename:
            name=save_upload(fs,'media',24*1024*1024);media_url=file_url('media',name);media_type=mimetypes.guess_type(fs.filename)[0] or 'application/octet-stream';media_name=fs.filename[:180]
        x.execute('INSERT INTO messages(room,room_id,username,text,created_at,created,media_type,media_name,media_url) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)',(room_id,room_id,u['username'],text,now(),now(),media_type,media_name,media_url));x.commit()
    except Exception:x.rollback()
    finally:x.close()
    return redirect('/c/'+room['username'])

@app.route('/create',methods=['GET','POST'])
def create():
    r=need_login()
    if r:return r
    u=current();msg=''
    if request.method=='POST':
        name=request.form.get('name','').strip();username=request.form.get('username','').strip().lower().replace(' ','');kind=request.form.get('kind','group');bio=request.form.get('bio','').strip();emoji=request.form.get('emoji','💬')[:4]
        if len(username)<3 or not username.isalnum():msg='Username must be 3+ letters/numbers.'
        else:
            x=db()
            try:x.execute('INSERT INTO rooms(name,username,kind,owner,emoji,bio,public) VALUES(%s,%s,%s,%s,%s,%s,0)',(name,username,kind,u['username'],emoji,bio));x.commit();x.execute('SELECT id FROM rooms WHERE username=%s',(username,));rid=x.fetchone()['id'];x.execute('INSERT INTO room_members(room_id,username,joined_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(rid,u['username'],now()));x.commit();return redirect('/c/'+username)
            except Exception:x.rollback();msg='That username is already used.'
            finally:x.close()
    body=f'''<div class="card hero"><h1 class="title">Create a space</h1><p class="muted">User-created groups/channels stay hidden from the public list. Share their link to invite people.</p><form class="form" method="post"><input class="input" name="name" placeholder="Name" required><input class="input" name="username" placeholder="Unique username" required><select class="select" name="kind"><option value="group">Group</option><option value="channel">Channel</option></select><input class="input" name="emoji" value="💬" maxlength="4"><textarea class="textarea" name="bio" placeholder="Bio"></textarea><button class="btn primary">Create</button></form><p class="muted">{esc(msg)}</p></div>''';return layout(body,'Create','create')

@app.route('/edit-room/<int:rid>',methods=['GET','POST'])
def edit_room(rid):
    r=need_login()
    if r:return r
    u=current();x=db();x.execute('SELECT * FROM rooms WHERE id=%s',(rid,));room=x.fetchone();x.close()
    if not room:return redirect('/chat')
    if room['owner']!=u['username'] and not is_admin(u):return redirect('/c/'+room['username'])
    msg=''
    if request.method=='POST':
        name=request.form.get('name','').strip();username=request.form.get('username','').strip().lower().replace(' ','');bio=request.form.get('bio','').strip();emoji=request.form.get('emoji','💬')[:4]
        x=db()
        try:x.execute('UPDATE rooms SET name=%s,username=%s,bio=%s,emoji=%s WHERE id=%s',(name,username,bio,emoji,rid));x.commit();return redirect('/c/'+username)
        except Exception:x.rollback();msg='Could not save. Username may be taken.'
        finally:x.close()
    body=f'''<div class="card hero"><h1 class="title">Edit {esc(room['kind'].title())}</h1><form class="form" method="post"><input class="input" name="name" value="{esc(room['name'])}" placeholder="Name" required><input class="input" name="username" value="{esc(room['username'])}" placeholder="Username" required><input class="input" name="emoji" value="{esc(room['emoji'])}" maxlength="4"><textarea class="textarea" name="bio" placeholder="Bio">{esc(room['bio'])}</textarea><button class="btn primary">Save changes</button><a class="btn ghost" href="/c/{esc(room['username'])}">Cancel</a></form><p class="muted">{esc(msg)}</p></div>''';return layout(body,'Edit')

@app.route('/u/<username>')
def profile(username):
    r=need_login()
    if r:return r
    u=current();x=db();x.execute('SELECT * FROM users WHERE username=%s',(username,));p=x.fetchone()
    if not p:x.close();return layout('<div class="card empty">User not found.</div>','Profile')
    x.execute('SELECT COUNT(*) AS c FROM follows WHERE target=%s',(username,));followers=x.fetchone()['c'];x.execute('SELECT COUNT(*) AS c FROM follows WHERE follower=%s',(username,));following=x.fetchone()['c'];x.execute('SELECT 1 FROM follows WHERE follower=%s AND target=%s',(u['username'],username));following_me=bool(x.fetchone());x.close()
    avatar=f'<img src="/uploads/avatars/{esc(p["avatar"])}">' if p.get('avatar') else esc(p['emoji'])
    follow='' if u['username']==username else f'<form method="post" action="/follow/{esc(username)}"><button class="btn primary">{"Following ✓" if following_me else "Follow"}</button></form>'
    body=f'''<div class="card profile"><div class="bigavatar">{avatar}</div><h1 class="title">@{esc(p['username'])} {badge(p)} {"<span class='pro'>PRO</span>" if p['pro'] else ''}</h1><p class="muted">{esc(p['bio'])}</p><div class="stats"><div><b>{followers}</b><span>Followers</span></div><div><b>{following}</b><span>Following</span></div></div><div class="row" style="justify-content:center">{follow}<a class="btn ghost" href="/private/{esc(username)}">Message</a>{('<a class="btn ghost" href="/edit-profile">Edit profile</a>' if u['username']==username else '')}</div></div>''';return layout(body,'Profile','profile')

@app.route('/follow/<username>',methods=['POST'])
def follow(username):
    r=need_login()
    if r:return r
    u=current()
    if username==u['username']:return redirect('/u/'+username)
    x=db();x.execute('SELECT 1 FROM follows WHERE follower=%s AND target=%s',(u['username'],username))
    if x.fetchone():x.execute('DELETE FROM follows WHERE follower=%s AND target=%s',(u['username'],username))
    else:x.execute('INSERT INTO follows(follower,target,created_at) VALUES(%s,%s,%s) ON CONFLICT DO NOTHING',(u['username'],username,now()))
    x.commit();x.close();return redirect('/u/'+username)

@app.route('/edit-profile',methods=['GET','POST'])
def edit_profile():
    r=need_login()
    if r:return r
    u=current();msg=''
    if request.method=='POST':
        bio=request.form.get('bio','').strip();emoji=request.form.get('emoji','👤')[:4];language=request.form.get('language','en')
        x=db()
        try:
            avatar=u.get('avatar') or ''
            fs=request.files.get('avatar')
            if fs and fs.filename:
                if not is_pro(u): raise ValueError('Profile photo is available for PRO accounts.')
                avatar=save_upload(fs,'avatars',5*1024*1024)
            x.execute('UPDATE users SET bio=%s,emoji=%s,language=%s,avatar=%s WHERE username=%s',(bio,emoji,language,avatar,u['username']));x.commit();return redirect('/u/'+u['username'])
        except ValueError as e: x.rollback();msg=str(e)
        except Exception: x.rollback();msg='Could not save profile.'
        finally:x.close()
    body=f'''<div class="card hero"><h1 class="title">Edit profile</h1><form class="form" method="post" enctype="multipart/form-data"><label>Username</label><input class="input" value="@{esc(u['username'])}" disabled><label>Bio</label><textarea class="textarea" name="bio">{esc(u['bio'])}</textarea><label>Avatar emoji</label><input class="input" name="emoji" value="{esc(u['emoji'])}" maxlength="4"><label>Profile photo (PRO)</label><input class="input" type="file" name="avatar" accept="image/*"><label>Language</label><select class="select" name="language"><option value="en">English</option><option value="fa" {'selected' if u['language']=='fa' else ''}>فارسی</option></select><button class="btn primary">Save profile</button></form><p class="muted">{esc(msg)}</p></div>''';return layout(body,'Edit profile','profile')

@app.route('/private/<username>')
def private(username):
    r=need_login()
    if r:return r
    u=current();x=db();x.execute('SELECT * FROM users WHERE username=%s',(username,));p=x.fetchone();x.execute('SELECT * FROM private_messages WHERE (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s) ORDER BY id ASC LIMIT 300',(u['username'],username,username,u['username']));msgs=x.fetchall();x.close()
    if not p:return redirect('/chat')
    bubbles=''
    for m in msgs:
        mt=m.get('media_type') or '';url=m.get('media_url') or '';media=''
        if mt.startswith('image/'):media=f'<img class="media" src="{esc(url)}">'
        elif mt.startswith('video/'):media=f'<video class="media" controls src="{esc(url)}"></video>'
        elif mt.startswith('audio/'):media=f'<audio controls src="{esc(url)}"></audio>'
        elif url:media=f'<a class="filecard" href="{esc(url)}" download><b>FILE</b><span>{esc(m.get("media_name"))}</span></a>'
        bubbles+=f'<div class="bubble {"mine" if m["sender"]==u["username"] else ""}"><div>{esc(m.get("text"))}</div>{media}<div class="meta">@{esc(m["sender"])} · {esc(m.get("created_at"))}</div></div>'
    form=f'''<form id="privateForm" class="composer" action="/private-send/{esc(username)}" method="post" enctype="multipart/form-data"><input class="input" name="text" placeholder="Message"><label class="iconbtn" title="Photo / Video / File">＋<input id="privateMediaInput" type="file" name="media" hidden></label><button type="button" class="iconbtn" id="privateRecordBtn" title="Voice">●</button><button class="iconbtn">➤</button></form><script>voiceRecorder("privateForm","privateMediaInput","privateRecordBtn")</script>'''
    body=f'''<div class="card chatbox"><div class="chathead row"><a href="/u/{esc(username)}" class="row"><div class="avatar">{esc(p['emoji'])}</div><div><div class="userline">@{esc(username)} {badge(p)}</div><div class="muted">Private chat</div></div></a></div><div class="messages">{bubbles or '<div class="empty">Start the conversation.</div>'}</div>{form}</div>''';return layout(body,'Chat')

@app.route('/private-send/<username>',methods=['POST'])
def private_send(username):
    r=need_login()
    if r:return r
    u=current();text=request.form.get('text','').strip();fs=request.files.get('media');url='';mt='';mn='';x=db()
    try:
        if fs and fs.filename:
            name=save_upload(fs,'media',24*1024*1024);url=file_url('media',name);mt=mimetypes.guess_type(fs.filename)[0] or 'application/octet-stream';mn=fs.filename[:180]
        x.execute('INSERT INTO private_messages(sender,receiver,text,created_at,media_type,media_name,media_url) VALUES(%s,%s,%s,%s,%s,%s,%s)',(u['username'],username,text,now(),mt,mn,url));x.commit()
    except Exception:x.rollback()
    finally:x.close()
    return redirect('/private/'+username)

@app.route('/settings')
def settings():
    r=need_login()
    if r:return r
    u=current()
    body=f'''<div class="card hero"><h1 class="title">Settings</h1><div class="list"><a class="item row between" href="/edit-profile"><span>Edit profile</span><b>›</b></a><a class="item row between" href="/pro"><span>Parto PRO</span><b>›</b></a>{('<a class="item row between" href="/admin"><span>Admin panel</span><b>›</b></a>' if is_admin(u) else '')}<a class="item row between" href="/logout"><span>Log out</span><b>›</b></a></div><p class="muted">Current language: {esc(u['language'])}</p></div>''';return layout(body,'Settings','settings')

@app.route('/pro')
def pro():
    r=need_login()
    if r:return r
    body='''<div class="card hero"><span class="pro">PRO</span><h1 class="title">Parto PRO</h1><p class="muted">Profile photos, larger media and premium features.</p><div class="list"><div class="item">✓ Profile photo</div><div class="item">✓ Media sharing</div><div class="item">✓ Premium profile</div></div></div>''';return layout(body,'PRO')

@app.route('/admin')
def admin():
    r=need_login()
    if r:return r
    u=current()
    if not is_admin(u):return redirect('/chat')
    x=db();x.execute('SELECT * FROM users ORDER BY id DESC LIMIT 150');users=x.fetchall();x.execute('SELECT * FROM rooms ORDER BY id DESC LIMIT 150');rooms=x.fetchall();x.close()
    us=[]
    for z in users:
        protected=z['username']=='parto'
        ban_form='' if protected else f'<form method="post" action="/admin/user-ban"><input type="hidden" name="id" value="{z["id"]}"><button class="btn {"primary" if z["banned"] else "danger"}">{"Unban user" if z["banned"] else "Ban user"}</button></form>'
        us.append(f'<div class="item admin-item"><div class="row between"><div><b>@{esc(z["username"])}</b> {badge(z)} {("<span class='pro'>PRO</span>" if z["pro"] else "")}<div class="muted">ID {z["id"]} · {"BANNED" if z["banned"] else "Active"}</div></div><a class="btn ghost" href="/u/{esc(z["username"])}">Profile</a></div><div class="admin-actions"><form method="post" action="/admin/toggle"><input type="hidden" name="id" value="{z["id"]}"><button class="btn ghost">{"Unverify" if z["verified"] else "Verify user"}</button></form><form method="post" action="/admin/pro"><input type="hidden" name="id" value="{z["id"]}"><button class="btn ghost">{"Remove PRO" if z["pro"] else "Give PRO"}</button></form>{ban_form}</div></div>')
    rs=[]
    for z in rooms:
        protected=z['username'] in ('parto','gangs')
        ban_form='' if protected else f'<form method="post" action="/admin/room-ban"><input type="hidden" name="id" value="{z["id"]}"><button class="btn {"primary" if z["banned"] else "danger"}">{"Unban space" if z["banned"] else "Ban space"}</button></form>'
        rs.append(f'<div class="item admin-item"><div class="row between"><div><b>{esc(z["name"])}</b> {badge(z)}<div class="muted">@{esc(z["username"])} · {esc(z["kind"])} · owner @{esc(z["owner"])}</div><div class="muted">{"BANNED" if z["banned"] else "Active"} · {"Verified" if z["verified"] else "Not verified"}</div></div><a class="btn ghost" href="/c/{esc(z["username"])}">Open</a></div><div class="admin-actions"><form method="post" action="/admin/room"><input type="hidden" name="id" value="{z["id"]}"><button class="btn ghost">{"Unverify" if z["verified"] else "Verify " + z["kind"]}</button></form>{ban_form}</div></div>')
    body=f'<div class="card"><div class="hero"><h1 class="title">Admin Control Center</h1><p class="muted">Verify users, groups and channels. Give PRO. Ban or unban accounts and spaces.</p></div><div class="list">{"".join(us) or "<div class='empty'>No users.</div>"}</div></div><div class="card" style="margin-top:12px"><div class="hero"><h2>Groups & Channels</h2></div><div class="list">{"".join(rs) or "<div class='empty'>No spaces.</div>"}</div></div>'
    return layout(body,'Admin','settings')

@app.post('/admin/toggle')
def admin_toggle():
    u=current()
    if not is_admin(u):return redirect('/chat')
    target=request.form.get('id');x=db();x.execute('SELECT username,verified FROM users WHERE id=%s',(target,));z=x.fetchone()
    if not z or z['username']=='parto':x.close();return redirect('/admin')
    x.execute('UPDATE users SET verified=%s WHERE id=%s',(0 if z['verified'] else 1,target));x.commit();x.close();return redirect('/admin')

@app.post('/admin/pro')
def admin_pro():
    u=current()
    if not is_admin(u):return redirect('/chat')
    target=request.form.get('id');x=db();x.execute('SELECT username,pro FROM users WHERE id=%s',(target,));z=x.fetchone()
    if not z or z['username']=='parto':x.close();return redirect('/admin')
    x.execute('UPDATE users SET pro=%s WHERE id=%s',(0 if z['pro'] else 1,target));x.commit();x.close();return redirect('/admin')

@app.post('/admin/user-ban')
def admin_user_ban():
    u=current()
    if not is_admin(u):return redirect('/chat')
    target=request.form.get('id');x=db();x.execute('SELECT username,banned FROM users WHERE id=%s',(target,));z=x.fetchone()
    if not z or z['username'] in ('parto',u['username']):x.close();return redirect('/admin')
    x.execute('UPDATE users SET banned=%s WHERE id=%s',(0 if z['banned'] else 1,target));x.commit();x.close();return redirect('/admin')

@app.post('/admin/room')
def admin_room():
    u=current()
    if not is_admin(u):return redirect('/chat')
    target=request.form.get('id');x=db();x.execute('SELECT username,verified FROM rooms WHERE id=%s',(target,));z=x.fetchone()
    if not z or z['username'] in ('parto','gangs'):x.close();return redirect('/admin')
    x.execute('UPDATE rooms SET verified=%s WHERE id=%s',(0 if z['verified'] else 1,target));x.commit();x.close();return redirect('/admin')

@app.post('/admin/room-ban')
def admin_room_ban():
    u=current()
    if not is_admin(u):return redirect('/chat')
    target=request.form.get('id');x=db();x.execute('SELECT username,banned FROM rooms WHERE id=%s',(target,));z=x.fetchone()
    if not z or z['username'] in ('parto','gangs'):x.close();return redirect('/admin')
    x.execute('UPDATE rooms SET banned=%s WHERE id=%s',(0 if z['banned'] else 1,target));x.commit();x.close();return redirect('/admin')

@app.route('/uploads/<folder>/<name>')
def uploads(folder,name):
    if folder not in ('avatars','media','files','voice'):return ('',404)
    return send_from_directory(os.path.join(UPLOAD_ROOT,folder),name,as_attachment=False)

@app.route('/health')
def health():
    try:
        x=db();x.execute('SELECT 1');x.close();return jsonify(status='ok',database='ok')
    except Exception as e:return jsonify(status='error',database='error',detail=str(e)),500

@app.errorhandler(RequestEntityTooLarge)
def too_large(e):return ('File too large.',413)
@app.errorhandler(404)
def not_found(e):return layout('<div class="card empty">Page not found.</div>','404') if session.get('user') else redirect('/login')

init_db()
if __name__=='__main__': app.run(host='0.0.0.0',port=PORT,debug=False)
