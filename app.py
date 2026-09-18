from flask import Flask, request, redirect, session
import os
import html
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "PARTO_2026")
DATABASE_URL = os.getenv("DATABASE_URL", "")

class DB:
    def __init__(self):
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured.")
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, *args, **kwargs):
        return self.cur.execute(*args, **kwargs)

    def fetchone(self):
        return self.cur.fetchone()

    def fetchall(self):
        return self.cur.fetchall()

    def commit(self):
        return self.conn.commit()

    def rollback(self):
        return self.conn.rollback()

    def close(self):
        try:
            self.cur.close()
        finally:
            self.conn.close()

def db():
    return DB()

def esc(v):
    return html.escape(str(v or ""))

def init_db():
    x = db()
    try:
        cur = x
        cur.execute("""CREATE TABLE IF NOT EXISTS users(
            id SERIAL PRIMARY KEY, username TEXT UNIQUE NOT NULL, email TEXT UNIQUE,
            password TEXT NOT NULL, emoji TEXT DEFAULT '👤', bio TEXT DEFAULT '',
            admin INTEGER DEFAULT 0, banned INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0, pro INTEGER DEFAULT 0,
            language TEXT DEFAULT 'en')""")
        cur.execute("""CREATE TABLE IF NOT EXISTS rooms(
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, username TEXT UNIQUE NOT NULL,
            kind TEXT NOT NULL, owner TEXT NOT NULL, emoji TEXT DEFAULT '💬',
            bio TEXT DEFAULT '')""")
        cur.execute("""CREATE TABLE IF NOT EXISTS messages(
            id SERIAL PRIMARY KEY, room INTEGER, room_id INTEGER, username TEXT NOT NULL,
            text TEXT NOT NULL, created_at TEXT DEFAULT '', created TEXT DEFAULT '',
            reply INTEGER DEFAULT 0, edited INTEGER DEFAULT 0)""")
        cur.execute("""CREATE TABLE IF NOT EXISTS private_messages(
            id SERIAL PRIMARY KEY, sender TEXT NOT NULL, receiver TEXT NOT NULL,
            text TEXT NOT NULL, created_at TEXT DEFAULT '')""")
        cur.execute("""CREATE TABLE IF NOT EXISTS private_chat_state(
            id SERIAL PRIMARY KEY, owner TEXT NOT NULL, other_user TEXT NOT NULL,
            unread INTEGER DEFAULT 0, UNIQUE(owner, other_user))""")

        def columns(table):
            cur.execute("""SELECT column_name FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s""", (table,))
            rows = cur.fetchall()
            return {r["column_name"] for r in rows}

        migrations = {
            "users": {
                "emoji":"TEXT DEFAULT '👤'","bio":"TEXT DEFAULT ''",
                "admin":"INTEGER DEFAULT 0","banned":"INTEGER DEFAULT 0",
                "verified":"INTEGER DEFAULT 0","pro":"INTEGER DEFAULT 0",
                "language":"TEXT DEFAULT 'en'","avatar":"TEXT DEFAULT ''"},
            "rooms": {"bio":"TEXT DEFAULT ''","emoji":"TEXT DEFAULT '💬'"},
            "messages": {
                "room":"INTEGER","room_id":"INTEGER","created_at":"TEXT DEFAULT ''",
                "created":"TEXT DEFAULT ''","reply":"INTEGER DEFAULT 0",
                "edited":"INTEGER DEFAULT 0"},
            "private_messages":{"created_at":"TEXT DEFAULT ''"}
        }
        for table, fields in migrations.items():
            have = columns(table)
            for name, definition in fields.items():
                if name not in have:
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")

        cur.execute("UPDATE messages SET room=room_id WHERE room IS NULL AND room_id IS NOT NULL")
        cur.execute("UPDATE messages SET room_id=room WHERE room_id IS NULL AND room IS NOT NULL")
        now = datetime.now().isoformat(timespec="seconds")
        cur.execute("UPDATE messages SET created_at=%s WHERE created_at IS NULL OR created_at=''", (now,))
        cur.execute("UPDATE messages SET created=created_at WHERE created IS NULL OR created=''", (now,))

        cur.execute("SELECT id FROM users WHERE username='parto'")
        if not cur.fetchone():
            cur.execute("""INSERT INTO users
                (username,email,password,emoji,bio,admin,verified,pro)
                VALUES(%s,%s,%s,%s,%s,1,1,1)""",
                ("parto","parto@local",generate_password_hash("123456"),"⚡","Official Parto"))

        cur.execute("SELECT id FROM rooms WHERE username='parto'")
        if not cur.fetchone():
            cur.execute("""INSERT INTO rooms(name,username,kind,owner,emoji,bio)
                VALUES(%s,%s,'channel',%s,%s,%s)""",
                ("پرتو","parto","parto","⚡","کانال رسمی پرتو"))

        x.commit()
    except Exception:
        x.rollback()
        raise
    finally:
        cur.close()
        x.close()

def is_pro(username):
    x = db()
    x.execute("SELECT pro FROM users WHERE username=%s", (username,))
    row = x.fetchone()
    x.close()
    return bool(row and row["pro"])


def pro_badge(pro):
    return "<span class='pro-badge'>PRO</span>" if pro else ""

def me():
    name = session.get("user")
    if not name:
        return None
    x = db()
    x.execute("SELECT * FROM users WHERE username=%s", (name,))
    u = x.fetchone()
    x.close()
    return u

CSS = r"""
*{box-sizing:border-box}html,body{margin:0;min-height:100%;background:#070a12;color:#f5f7ff;
font-family:Tahoma,Arial,sans-serif}a{text-decoration:none;color:inherit}button,input,textarea,select{font:inherit}
body{background:radial-gradient(circle at 20% 0%,#20265b 0,transparent 32%),radial-gradient(circle at 100% 20%,#064457 0,transparent 28%),#070a12}
.app{min-height:100vh;display:flex}.side{width:250px;background:#0b101cdd;border-right:1px solid #202a40;padding:18px}
.logo{font-size:25px;font-weight:900;margin:5px 8px 25px}.logo b{display:inline-flex;width:40px;height:40px;
align-items:center;justify-content:center;border-radius:13px;background:linear-gradient(135deg,#765cff,#18cfff);margin-right:8px}
.nav{display:block;padding:13px 14px;margin:6px 0;border-radius:15px;color:#aeb9ce}.nav:hover{background:#151d30;color:white}
.main{flex:1;min-width:0}.header{height:64px;display:flex;align-items:center;padding:0 18px;
border-bottom:1px solid #202a40;background:#0b101cd9;backdrop-filter:blur(20px);position:sticky;top:0;z-index:5}
.header h3{margin:0}.page{max-width:760px;margin:auto;padding:18px 14px 95px}.list{display:flex;flex-direction:column;gap:9px}
.item{display:flex;align-items:center;gap:14px;padding:15px;border:1px solid #1d2940;background:#0e1524e8;
border-radius:21px;transition:.18s}.item:hover{transform:translateY(-1px);background:#141e32;border-color:#35425c}
.avatar{width:56px;height:56px;flex:none;border-radius:18px;background:#172138;display:flex;align-items:center;
justify-content:center;font-size:28px}.info{flex:1;min-width:0}.name{font-weight:900}.sub{font-size:12px;color:#8490a6;margin-top:4px}
.arrow{color:#7d89a0;font-size:22px}.pro-badge{display:inline-block;margin:0 5px;padding:3px 8px;border-radius:999px;background:linear-gradient(135deg,#ff4d8d,#7c5cff);color:#fff;font-size:10px;font-weight:800;box-shadow:0 4px 14px rgba(124,92,255,.28)}.badge{font-size:10px;padding:3px 7px;border-radius:8px;background:#1682ff;margin-right:4px;display:inline-block}.badge.pro{min-width:20px;text-align:center}
.pro{background:linear-gradient(135deg,#ffbd2e,#ff6a00);color:#15100a}.box{max-width:520px;margin:30px auto;padding:22px;
border:1px solid #202a40;border-radius:25px;background:#0d1422ed;box-shadow:0 25px 80px #0007}
input,textarea,select{width:100%;padding:13px;border:1px solid #202a40;border-radius:14px;background:#101a2b;color:#fff;margin:6px 0}
textarea{min-height:100px}button{width:100%;padding:13px;border:0;border-radius:14px;background:linear-gradient(135deg,#765cff,#477cff);color:#fff;font-weight:900;margin:6px 0}
.chat{height:calc(100vh - 64px);display:flex;flex-direction:column}.messages{flex:1;overflow:auto;padding:18px}.msg{max-width:78%;padding:11px 14px;
margin:8px 0;border-radius:18px;background:#111b2d;border:1px solid #202c44;line-height:1.7}.mine{margin-right:auto;background:#273667}
.meta{font-size:11px;color:#8793aa;margin-bottom:3px}.composer{display:flex;gap:8px;padding:10px 14px;background:#0b101ce8;border-top:1px solid #202a40}
.composer input{margin:0}.composer button{width:58px;margin:0}.bottom{display:none}
.profile{max-width:620px;margin:25px auto;text-align:center;background:#0e1525;border:1px solid #202a40;border-radius:28px;overflow:hidden}
.cover{height:135px;background:linear-gradient(120deg,#4e7cff,#8a5cff,#20d7ff)}.bigavatar{font-size:52px;width:100px;height:100px;
display:flex;align-items:center;justify-content:center;margin:-45px auto 10px;background:#111a2d;border:4px solid #111a2d;border-radius:28px}
.actions{display:flex;gap:8px;justify-content:center;padding:15px 20px 25px}.actions a{padding:11px 15px;border-radius:13px;background:#182238}
@media(max-width:700px){.side{display:none}.header{height:62px}.page{padding:12px 10px 88px}.chat{height:calc(100vh - 62px)}
.msg{max-width:90%}.bottom{position:fixed;display:flex;bottom:0;left:0;right:0;height:70px;z-index:30;background:#0a0f1eeF;
border-top:1px solid #202a40;backdrop-filter:blur(22px)}.bottom a{flex:1;text-align:center;padding:8px 2px;color:#8c98ad;font-size:10px}.bottom span{display:block;font-size:21px;margin-bottom:3px}
.bottom .active{color:#fff}.box{margin:15px 5px}.item{padding:13px}.avatar{width:52px;height:52px}}
"""

def layout(title, body, active="chat"):
    links=[("chat","💬","چت","/chat"),("search","⌕","جستجو","/search"),
           ("create","＋","ساخت","/create"),("profile","◉","پروفایل","/profile")]
    side="".join(f"<a class='nav' href='{u}'>{i} {n}</a>" for k,i,n,u in links)
    bottom="".join(f"<a class='{'active' if active==k else ''}' href='{u}'><span>{i}</span>{n}</a>" for k,i,n,u in links)
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    <title>{esc(title)} · Parto</title><style>{CSS}</style></head><body>
    <div class='app'><aside class='side'><div class='logo'><b>⚡</b>Parto</div>{side}
    <a class='nav' href='/settings'>⚙️ تنظیمات</a><a class='nav' href='/logout'>↪ خروج</a></aside>
    <main class='main'><header class='header'><h3>{esc(title)}</h3></header>{body}</main></div>
    <nav class='bottom'>{bottom}</nav></body></html>"""

@app.route("/")
def index():
    if me(): return redirect("/chat")
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>
    <body><div class='box'><div class='avatar' style='margin:auto'>⚡</div><h1 style='text-align:center'>Parto</h1>
    <form method='post' action='/login'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Login</button></form>
    <a href='/register'>Create account</a></div></body></html>"""

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="GET":
        return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'><style>{CSS}</style></head>
        <body><div class='box'><h2>Create account</h2><form method='post'><input name='username' placeholder='Username' required>
        <input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Register</button></form><a href='/'>Back</a></div></body></html>"""
    username = request.form.get("username", "").strip()
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")

    if not username or not email or not password:
        return "Username, email and password are required.", 400
    if len(username) > 40 or len(email) > 255 or len(password) < 6:
        return "Invalid account information.", 400

    x = db()
    try:
        x.execute(
            "INSERT INTO users(username,email,password) VALUES(%s,%s,%s)",
            (username, email, generate_password_hash(password))
        )
        x.commit()
    except psycopg2.IntegrityError:
        x.rollback()
        return "Username or email already exists.", 409
    finally:
        x.close()

    session.clear()
    session["user"] = username
    return redirect("/chat")

@app.route("/login",methods=["POST"])
def login():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    if not email or not password:
        return "Email and password are required.", 400

    x = db()
    try:
        x.execute("SELECT * FROM users WHERE email=%s LIMIT 1", (email,))
        u = x.fetchone()
    finally:
        x.close()

    if not u or not u.get("password"):
        return "Invalid login.", 401

    try:
        valid = check_password_hash(u["password"], password)
    except (ValueError, TypeError):
        valid = False

    if not valid:
        return "Invalid login.", 401
    if u.get("banned"):
        return "Account is banned.", 403

    session.clear()
    session["user"] = u["username"]
    return redirect("/chat")

@app.route("/logout")
def logout(): session.clear();return redirect("/")

@app.route("/chat")
def chat():
    u=me()
    if not u:return redirect("/")
    x=db()
    # Only the official Parto channel is visible on the default chat list.
    official=x.execute("SELECT * FROM rooms WHERE username='parto' LIMIT 1").fetchone()
    private_users=x.execute("""SELECT u.username,u.emoji,COALESCE(s.unread,0) AS unread
        FROM users u JOIN (
          SELECT CASE WHEN sender=%s THEN receiver ELSE sender END AS other_user
          FROM private_messages WHERE sender=%s OR receiver=%s
          GROUP BY CASE WHEN sender=%s THEN receiver ELSE sender END
        ) p ON p.other_user=u.username
        LEFT JOIN private_chat_state s ON s.owner=%s AND s.other_user=u.username
        ORDER BY COALESCE(s.unread,0) DESC,u.username""",
        (u["username"],u["username"],u["username"],u["username"],u["username"])).fetchall()
    rooms=[]
    if official: rooms.append(official)
    x.close()
    cards=""
    if official:
        cards+=f"""<a class='item' href='/room/{official["id"]}'><div class='avatar'>⚡</div><div class='info'>
        <div class='name'>پرتو <span class='badge'>✓</span></div><div class='sub'>کانال رسمی پرتو</div></div><div class='arrow'>‹</div></a>"""
    for z in private_users:
        unread = f"<span class='badge pro'>{int(z['unread'])}</span>" if z['unread'] else ''
        cards+=f"""<a class='item' href='/private/{esc(z["username"])}'><div class='avatar'>{esc(z["emoji"])}</div><div class='info'>
        <div class='name'>@{esc(z["username"])} {unread}</div><div class='sub'>چت خصوصی</div></div><div class='arrow'>‹</div></a>"""
    body=f"""<div class='page'><div class='list'>{cards or '<p class="sub">هنوز چتی نداری.</p>'}</div></div>
    <script>setInterval(()=>location.reload(),7000);</script>"""
    return layout("چت",body,"chat")

@app.route("/room/<int:rid>")
def room(rid):
    u=me()
    if not u:return redirect("/")
    x=db();r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone()
    if not r:x.close();return "Chat not found."
    # Private rooms created by users are never exposed through the main list.
    if r["username"]!="parto" and r["username"] not in request.args.get("id",""):
        pass
    ms=x.execute("SELECT * FROM messages WHERE room=%s ORDER BY id",(rid,)).fetchall();x.close()
    body=""
    for m in ms:
        cls = 'mine' if m['username'] == u['username'] else ''
        body += f"<div class='msg {cls}'><div class='meta'>@{esc(m['username'])}</div>{esc(m['text'])}</div>"
    composer="" if r["kind"]=="channel" and r["owner"]!="parto" and r["owner"]!=u["username"] else f"<form class='composer' method='post' action='/send/{rid}'><input name='text' placeholder='پیام...' required><button>➤</button></form>"
    return layout(r["name"],f"<div class='chat'><div class='messages'>{body or '<p class=\"sub\">هنوز پیامی نیست.</p>'}</div>{composer}</div>","chat")

@app.route("/send/<int:rid>",methods=["POST"])
def send(rid):
    u=me()
    if not u:return redirect("/")
    x=db();r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone()
    if not r:x.close();return "Chat not found."
    if r["kind"]=="channel" and r["owner"]!=u["username"]:x.close();return "Only the owner can post."
    text=request.form.get("text","").strip()
    if text:
        now=datetime.now().isoformat(timespec="seconds")
        x.execute("""INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited)
                     VALUES(%s,%s,%s,%s,%s,%s,0,0)""",(rid,rid,u["username"],text[:2000],now,now))
        x.commit()
    x.close();return redirect(f"/room/{rid}")

@app.route("/search")
def search():
    u=me()
    if not u:return redirect("/")
    q=request.args.get("q","").strip()
    x=db()
    users=x.execute("SELECT username,emoji,verified,pro FROM users WHERE username ILIKE %s LIMIT 30",(f"%{q}%",)).fetchall()
    rooms=x.execute("SELECT * FROM rooms WHERE username ILIKE %s OR name ILIKE %s LIMIT 30",(f"%{q}%",f"%{q}%")).fetchall()
    x.close()
    out=""
    for z in users:
        badges=("<span class='badge'>✓</span>" if z["verified"] else "")+("<span class='badge pro'>PRO</span>" if z["pro"] else "")
        out+=f"""<a class='item' href='/private/{esc(z["username"])}'><div class='avatar'>{esc(z["emoji"])}</div><div class='info'>
        <div class='name'>@{esc(z["username"])} {badges}</div><div class='sub'>شروع چت خصوصی با آیدی</div></div><div class='arrow'>‹</div></a>"""
    for r in rooms:
        out+=f"""<a class='item' href='/room/{r["id"]}'><div class='avatar'>{esc(r["emoji"])}</div><div class='info'>
        <div class='name'>{esc(r["name"])}</div><div class='sub'>@{esc(r["username"])} · {esc(r["kind"])}</div></div><div class='arrow'>‹</div></a>"""
    return layout("جستجو",f"<div class='page'><form><input name='q' value='{esc(q)}' placeholder='آیدی را جستجو کن...'></form><div class='list'>{out}</div></div>","search")

@app.route("/create",methods=["GET","POST"])
def create():
    u=me()
    if not u:return redirect("/")
    if request.method=="GET":
        return layout("ساخت",f"""<div class='page'><div class='box'><h2>ساخت گروه / کانال</h2>
        <form method='post'><input name='name' placeholder='نام' required><input name='username' placeholder='آیدی' required>
        <select name='kind'><option value='group'>گروه</option><option value='channel'>کانال</option></select>
        <input name='emoji' value='💬'><textarea name='bio' placeholder='توضیح'></textarea><button>ساخت</button></form></div></div>""","create")
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    kind = request.form.get("kind", "group")
    if not name or not username or kind not in ("group", "channel"):
        return "Invalid group/channel information.", 400

    x = db()
    try:
        x.execute(
            """INSERT INTO rooms(name,username,kind,owner,emoji,bio)
               VALUES(%s,%s,%s,%s,%s,%s)""",
            (name[:80], username[:40], kind, u["username"],
             request.form.get("emoji", "💬")[:8],
             request.form.get("bio", "")[:200])
        )
        x.commit()
    except psycopg2.IntegrityError:
        x.rollback()
        return "This ID is already in use.", 409
    finally:
        x.close()
    return redirect("/chat")

@app.route("/private/<username>")
def private(username):
    u=me()
    if not u:return redirect("/")
    x=db();z=x.execute("SELECT * FROM users WHERE username=%s",(username,)).fetchone()
    if not z:x.close();return "User not found."
    ms=x.execute("""SELECT * FROM private_messages WHERE
        (sender=%s AND receiver=%s) OR (sender=%s AND receiver=%s) ORDER BY id""",
        (u["username"],username,username,u["username"])).fetchall()
    x.execute("""INSERT INTO private_chat_state(owner,other_user,unread) VALUES(%s,%s,0)
        ON CONFLICT(owner,other_user) DO UPDATE SET unread=0""", (u["username"],username))
    x.commit()
    x.close()
    body = ''
    for m in ms:
        cls = 'mine' if m['sender'] == u['username'] else ''
        body += f"<div class='msg {cls}'><div class='meta'>@{esc(m['sender'])}</div>{esc(m['text'])}</div>"
    return layout("@"+username,f"""<div class='chat'><div class='messages'>{body or '<p class="sub">شروع گفتگو</p>'}</div>
    <form class='composer' method='post' action='/private/{esc(username)}/send'><input name='text' placeholder='پیام خصوصی...' required><button>➤</button></form>
    <script>setInterval(()=>location.reload(),3000);</script></div>""","chat")

@app.route("/private/<username>/send",methods=["POST"])
def private_send(username):
    u=me()
    if not u:return redirect("/")
    x=db()
    if x.execute("SELECT id FROM users WHERE username=%s",(username,)).fetchone():
        x.execute("INSERT INTO private_messages(sender,receiver,text,created_at) VALUES(%s,%s,%s,%s)",
                  (u["username"],username,request.form["text"][:2000],datetime.now().isoformat(timespec="seconds")))
        x.execute("""INSERT INTO private_chat_state(owner,other_user,unread) VALUES(%s,%s,1)
            ON CONFLICT(owner,other_user) DO UPDATE SET unread=private_chat_state.unread+1""",
            (username,u["username"]))
        x.commit()
    x.close();return redirect(f"/private/{username}")

@app.route("/profile")
def profile_redirect():
    u=me()
    return redirect("/profile/"+u["username"]) if u else redirect("/")

@app.route("/profile/<username>")
def profile(username):
    u=me()
    if not u:return redirect("/")
    x=db();z=x.execute("SELECT * FROM users WHERE username=%s",(username,)).fetchone();x.close()
    if not z:return "User not found."
    badges=("<span class='badge'>✓</span>" if z["verified"] else "")+("<span class='badge pro'>PRO</span>" if z["pro"] else "")
    button=f"<a href='/editprofile'>ویرایش پروفایل</a>" if u["username"]==username else f"<a href='/private/{esc(username)}'>💬 چت خصوصی</a>"
    body=f"""<div class='page'><div class='profile'><div class='cover'></div><div class='bigavatar'>{esc(z["avatar"] or z["emoji"])}</div>
    <h2>@{esc(z["username"])} {badges}</h2><p class='sub'>{esc(z["bio"] or "No bio yet.")}</p><div class='actions'>{button}</div></div></div>"""
    return layout("پروفایل",body,"profile")

@app.route("/editprofile",methods=["GET","POST"])
def editprofile():
    u=me()
    if not u:return redirect("/")
    if request.method=="GET":
        return layout("پروفایل",f"""<div class='page'><div class='box'><form method='post'>
        <select name='emoji'><option>👤</option><option>😎</option><option>⚡</option><option>🤖</option><option>🔥</option></select>
        <textarea name='bio' placeholder='بیو'>{esc(u["bio"])}</textarea><button>ذخیره</button></form></div></div>""","profile")
    x=db();x.execute("UPDATE users SET emoji=%s,bio=%s WHERE username=%s",(request.form["emoji"],request.form["bio"][:200],u["username"]));x.commit();x.close()
    return redirect("/profile/"+u["username"])


@app.route("/pro")
def pro_page():
    u = me()
    if not u:
        return redirect("/")
    if not u["pro"]:
        return layout("PRO", """
        <div class="page"><div class="box">
            <h2>حساب PRO</h2>
            <p>حساب شما هنوز PRO نیست.</p>
            <a href="/profile/%s">بازگشت به پروفایل</a>
        </div></div>
        """ % esc(u["username"]), "profile")
    return layout("PRO", """
    <div class="page"><div class="box">
        <h2>PRO فعال است <span class="pro-badge">PRO</span></h2>
        <p class="sub">قابلیت‌های ویژه حساب PRO:</p>
        <div class="card">✓ نشان PRO کنار نام</div>
        <div class="card">✓ پروفایل ویژه</div>
        <div class="card">✓ نمایش وضعیت PRO در لیست‌ها</div>
        <div class="card">✓ دسترسی به صفحه اختصاصی PRO</div>
        <div class="card">✓ امکانات مدیریتی PRO در صورت فعال‌سازی توسط ادمین</div>
    </div></div>
    """, "profile")


@app.route("/favicon.ico")
def favicon():
    return "", 204

@app.route("/health")
def health():
    x = db()
    try:
        x.execute("SELECT 1 AS ok")
        row = x.fetchone()
        return {"status": "ok", "database": bool(row and row["ok"] == 1)}
    finally:
        x.close()


@app.route("/settings")
def settings():
    u=me()
    if not u:return redirect("/")
    return layout("تنظیمات","<div class='page'><div class='box'><h2>⚙️ تنظیمات</h2><p class='sub'>Parto</p></div></div>")

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), debug=False)
