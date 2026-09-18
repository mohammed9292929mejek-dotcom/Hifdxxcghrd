from flask import Flask, request, redirect, session, send_from_directory
import os
import html
import uuid
import psycopg2
from psycopg2.extras import RealDictCursor
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.exceptions import RequestEntityTooLarge
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "PARTO_2026")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Upload configuration (secure image uploads for PRO avatars & chat images)
# ---------------------------------------------------------------------------
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
AVATAR_DIR = "avatars"
CHAT_DIR = "chat"
ALLOWED_UPLOAD_SUBDIRS = {AVATAR_DIR, CHAT_DIR}
MAX_IMAGE_BYTES = 5 * 1024 * 1024  # 5 MB per image
# Overall request body cap (a little above MAX_IMAGE_BYTES to allow for form fields).
app.config["MAX_CONTENT_LENGTH"] = 6 * 1024 * 1024

for _d in ALLOWED_UPLOAD_SUBDIRS:
    try:
        os.makedirs(os.path.join(UPLOAD_ROOT, _d), exist_ok=True)
    except Exception:
        pass


class DB:
    def __init__(self):
        if not DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not configured.")
        self.conn = psycopg2.connect(DATABASE_URL)
        self.cur = self.conn.cursor(cursor_factory=RealDictCursor)

    def execute(self, *args, **kwargs):
        self.cur.execute(*args, **kwargs)
        return self.cur

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

        # Safe, additive-only migrations. Nothing here ever drops a table,
        # column or row, so existing production data is always preserved.
        migrations = {
            "users": {
                "emoji":"TEXT DEFAULT '👤'","bio":"TEXT DEFAULT ''",
                "admin":"INTEGER DEFAULT 0","banned":"INTEGER DEFAULT 0",
                "verified":"INTEGER DEFAULT 0","pro":"INTEGER DEFAULT 0",
                "language":"TEXT DEFAULT 'en'",
                # Stores the safe, server-generated filename of a PRO user's
                # uploaded profile picture. Empty string = no picture (emoji avatar).
                "avatar":"TEXT DEFAULT ''"},
            "rooms": {
                "bio":"TEXT DEFAULT ''","emoji":"TEXT DEFAULT '💬'",
                # Admin-controlled blue verification badge for groups/channels.
                "verified":"INTEGER DEFAULT 0",
                # Safe, server-generated filename of a group/channel profile
                # picture. Only the owner may set this, and only if PRO.
                "avatar":"TEXT DEFAULT ''"},
            "messages": {
                "room":"INTEGER","room_id":"INTEGER","created_at":"TEXT DEFAULT ''",
                "created":"TEXT DEFAULT ''","reply":"INTEGER DEFAULT 0",
                "edited":"INTEGER DEFAULT 0",
                # Safe, server-generated filename of an image attached to a message
                # (PRO-only feature, enforced server-side on every send route).
                "image":"TEXT DEFAULT ''"},
            "private_messages":{
                "created_at":"TEXT DEFAULT ''",
                "image":"TEXT DEFAULT ''"}
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
                ("parto","PRATO@B",generate_password_hash("M123"),"⚡","Official Parto"))
        else:
            # Row already exists: never delete it, just make sure the official
            # login (email/password) and admin flag are the requested ones.
            cur.execute(
                "UPDATE users SET email=%s, password=%s, admin=1 WHERE username='parto'",
                ("PRATO@B", generate_password_hash("M123"))
            )

        cur.execute("SELECT id FROM rooms WHERE username='parto'")
        if not cur.fetchone():
            cur.execute("""INSERT INTO rooms(name,username,kind,owner,emoji,bio)
                VALUES(%s,%s,'channel',%s,%s,%s)""",
                ("پرتو","parto","parto","⚡","کانال رسمی پرتو"))
        else:
            # Row already exists: never delete it, just make sure kind/owner are correct.
            cur.execute("UPDATE rooms SET kind='channel', owner='parto' WHERE username='parto'")
        # Official Parto channel is always shown as verified.
        cur.execute("UPDATE rooms SET verified=1 WHERE username='parto'")

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

def is_admin(u):
    return bool(u and int(u["admin"] or 0) == 1)

# ---------------------------------------------------------------------------
# Secure image upload helpers
#   - MIME/type validated from real file bytes (not trusted filename/header)
#   - size-limited
#   - filenames are always server-generated (uuid4) -> no path traversal,
#     no collisions, no reliance on user-supplied names
# ---------------------------------------------------------------------------
def detect_image_type(data):
    """Detect a safe image type from raw file bytes (magic-byte sniffing)."""
    if not data:
        return None, None
    if data[:3] == b"\xff\xd8\xff":
        return "jpg", "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png", "image/png"
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return "gif", "image/gif"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", "image/webp"
    return None, None

def save_uploaded_image(file_storage, subdir):
    """Validate and save an uploaded image. Returns (filename, mime) or (None, None)
    when no file was supplied. Raises ValueError with a user-safe message on any
    validation failure. Never trusts the client-supplied filename or content-type."""
    if subdir not in ALLOWED_UPLOAD_SUBDIRS:
        raise ValueError("Invalid upload target.")
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None, None

    data = file_storage.read()
    if not data:
        return None, None
    if len(data) > MAX_IMAGE_BYTES:
        raise ValueError("Image is too large (max 5MB).")

    ext, mime = detect_image_type(data)
    if not ext:
        raise ValueError("Unsupported image type. Use JPG, PNG, GIF or WEBP.")

    folder = os.path.join(UPLOAD_ROOT, subdir)
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    full_path = os.path.abspath(os.path.join(folder, filename))

    # Defense in depth against path traversal, even though the filename is
    # always server-generated and never derived from user input.
    if not full_path.startswith(os.path.abspath(folder) + os.sep):
        raise ValueError("Invalid file path.")

    with open(full_path, "wb") as f:
        f.write(data)
    return filename, mime

def delete_uploaded_file(subdir, filename):
    """Best-effort delete of a previously stored upload. Never raises."""
    if subdir not in ALLOWED_UPLOAD_SUBDIRS or not filename:
        return
    try:
        safe_name = os.path.basename(filename)
        folder = os.path.join(UPLOAD_ROOT, subdir)
        full_path = os.path.abspath(os.path.join(folder, safe_name))
        if not full_path.startswith(os.path.abspath(folder) + os.sep):
            return
        if os.path.isfile(full_path):
            os.remove(full_path)
    except Exception:
        pass

def avatar_html(row, cls="avatar"):
    """Renders a user's or a group/channel's avatar: an uploaded picture for
    PRO accounts/owners who set one, otherwise the emoji avatar every
    user/room has by default. Works for both `users` and `rooms` rows since
    both tables now have an `avatar` and an `emoji` column."""
    avatar_file = None
    try:
        avatar_file = row["avatar"] if row and "avatar" in row.keys() else None
    except Exception:
        avatar_file = row.get("avatar") if row else None
    if avatar_file:
        return f"<div class='{cls} img'><img src='/uploads/avatars/{esc(avatar_file)}' alt=''></div>"
    emoji = (row["emoji"] if row else "👤") or "👤"
    return f"<div class='{cls}'>{esc(emoji)}</div>"

CSS = r"""
*{box-sizing:border-box}
html{transition:background-color .2s ease}
:root{
  --bg:#070a12; --bg-grad1:#20265b; --bg-grad2:#064457;
  --text:#f5f7ff; --side-bg:#0b101cdd; --border:#202a40;
  --nav-text:#aeb9ce; --nav-hover-bg:#151d30;
  --header-bg:#0b101cd9; --item-bg:#0e1524e8; --item-border:#1d2940; --item-hover:#141e32;
  --avatar-bg:#172138; --sub-text:#8490a6; --arrow:#7d89a0;
  --input-bg:#101a2b; --input-border:#202a40; --input-text:#fff;
  --btn-grad1:#765cff; --btn-grad2:#477cff; --btn-text:#fff;
  --msg-bg:#111b2d; --msg-border:#202c44; --msg-mine-bg:#273667;
  --card-bg:#0d1422ed; --box-shadow:0 25px 80px rgba(0,0,0,.45);
  --logo-grad1:#765cff; --logo-grad2:#18cfff;
  --badge-bg:#1682ff;
  --bottom-bg:#0a0f1ef2; --bottom-text:#8c98ad; --bottom-active:#fff;
  --cover-grad:linear-gradient(120deg,#4e7cff,#8a5cff,#20d7ff);
}
[data-theme='light']{
  --bg:#f3f7ff; --bg-grad1:#dfe9ff; --bg-grad2:#e2f4ff;
  --text:#0d1830; --side-bg:#ffffffee; --border:#dde6f7;
  --nav-text:#5c6d8f; --nav-hover-bg:#eaf1ff;
  --header-bg:#ffffffe6; --item-bg:#ffffff; --item-border:#e1e8f7; --item-hover:#f2f6ff;
  --avatar-bg:#e8f0ff; --sub-text:#66759a; --arrow:#93a2c2;
  --input-bg:#f0f4fb; --input-border:#d8e2f3; --input-text:#0d1830;
  --btn-grad1:#2f6bff; --btn-grad2:#3f8cff; --btn-text:#fff;
  --msg-bg:#eef3fc; --msg-border:#dde7f8; --msg-mine-bg:#d7e6ff;
  --card-bg:#ffffff; --box-shadow:0 20px 60px rgba(30,60,120,.12);
  --logo-grad1:#2f6bff; --logo-grad2:#39c1ff;
  --badge-bg:#2f6bff;
  --bottom-bg:#ffffffF2; --bottom-text:#7c8aa8; --bottom-active:#0d1830;
  --cover-grad:linear-gradient(120deg,#2f6bff,#5b8dff,#39c1ff);
}
html,body{margin:0;min-height:100%;background:var(--bg);color:var(--text);
font-family:Tahoma,Arial,sans-serif}a{text-decoration:none;color:inherit}button,input,textarea,select{font:inherit}
body{background:radial-gradient(circle at 20% 0%,var(--bg-grad1) 0,transparent 32%),radial-gradient(circle at 100% 20%,var(--bg-grad2) 0,transparent 28%),var(--bg);
transition:background-color .2s ease,color .2s ease}
.app{min-height:100vh;display:flex}.side{width:250px;background:var(--side-bg);border-right:1px solid var(--border);padding:18px}
.logo{font-size:25px;font-weight:900;margin:5px 8px 25px;color:var(--text)}.logo b{display:inline-flex;width:40px;height:40px;
align-items:center;justify-content:center;border-radius:13px;background:linear-gradient(135deg,var(--logo-grad1),var(--logo-grad2));margin-right:8px;color:#fff}
.nav{display:block;padding:13px 14px;margin:6px 0;border-radius:15px;color:var(--nav-text)}.nav:hover{background:var(--nav-hover-bg);color:var(--text)}
.main{flex:1;min-width:0}.header{height:64px;display:flex;align-items:center;gap:10px;padding:0 18px;
border-bottom:1px solid var(--border);background:var(--header-bg);backdrop-filter:blur(20px);position:sticky;top:0;z-index:5}
.header h3{margin:0;flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--text)}
.theme-toggle{flex:none;width:40px;height:40px;border-radius:12px;border:1px solid var(--border);background:var(--input-bg);
color:var(--text);display:flex;align-items:center;justify-content:center;cursor:pointer;font-size:18px;padding:0}
.page{max-width:760px;margin:auto;padding:18px 14px 95px}.list{display:flex;flex-direction:column;gap:9px}
.item{display:flex;align-items:center;gap:14px;padding:15px;border:1px solid var(--item-border);background:var(--item-bg);
border-radius:21px;transition:.18s}.item:hover{transform:translateY(-1px);background:var(--item-hover);border-color:var(--btn-grad2)}
.avatar{width:56px;height:56px;flex:none;border-radius:18px;background:var(--avatar-bg);display:flex;align-items:center;
justify-content:center;font-size:28px;color:var(--text)}
.avatar.img,.bigavatar.img{padding:0;overflow:hidden}
.avatar.img img,.bigavatar.img img{width:100%;height:100%;object-fit:cover;border-radius:inherit;display:block}
.info{flex:1;min-width:0}.name{font-weight:900;color:var(--text)}.sub{font-size:12px;color:var(--sub-text);margin-top:4px}
.arrow{color:var(--arrow);font-size:22px}
.pro-badge{display:inline-block;margin:0 5px;padding:3px 8px;border-radius:999px;background:linear-gradient(135deg,#ff4d8d,#7c5cff);color:#fff;font-size:10px;font-weight:800;box-shadow:0 4px 14px rgba(124,92,255,.28)}
.badge{font-size:10px;padding:3px 7px;border-radius:8px;background:var(--badge-bg);margin-right:4px;display:inline-block;color:#fff}.badge.pro{min-width:20px;text-align:center}
.pro{background:linear-gradient(135deg,#ffbd2e,#ff6a00);color:#15100a}
.box{max-width:520px;margin:30px auto;padding:22px;
border:1px solid var(--border);border-radius:25px;background:var(--card-bg);box-shadow:var(--box-shadow)}
input,textarea,select{width:100%;padding:13px;border:1px solid var(--input-border);border-radius:14px;background:var(--input-bg);color:var(--input-text);margin:6px 0}
textarea{min-height:100px}
button{width:100%;padding:13px;border:0;border-radius:14px;background:linear-gradient(135deg,var(--btn-grad1),var(--btn-grad2));color:var(--btn-text);font-weight:900;margin:6px 0;cursor:pointer}
.chat{height:calc(100vh - 64px);display:flex;flex-direction:column}.messages{flex:1;overflow:auto;padding:18px}.msg{max-width:78%;padding:11px 14px;
margin:8px 0;border-radius:18px;background:var(--msg-bg);border:1px solid var(--msg-border);line-height:1.7;color:var(--text)}.mine{margin-right:auto;background:var(--msg-mine-bg)}
.msg-img{max-width:100%;max-height:320px;object-fit:cover;border-radius:14px;display:block;margin-bottom:6px}
.meta{font-size:11px;color:var(--sub-text);margin-bottom:3px}.composer{display:flex;gap:8px;padding:10px 14px;background:var(--header-bg);border-top:1px solid var(--border)}
.composer input{margin:0}.composer button{width:58px;margin:0;flex:none}.bottom{display:none}
.img-btn{flex:none;width:44px;height:44px;display:flex;align-items:center;justify-content:center;background:var(--input-bg);
border:1px solid var(--input-border);border-radius:14px;cursor:pointer;font-size:18px}
.profile{max-width:620px;margin:25px auto;text-align:center;background:var(--card-bg);border:1px solid var(--border);border-radius:28px;overflow:hidden}
.cover{height:135px;background:var(--cover-grad)}.bigavatar{font-size:52px;width:100px;height:100px;
display:flex;align-items:center;justify-content:center;margin:-45px auto 10px;background:var(--avatar-bg);border:4px solid var(--card-bg);border-radius:28px;color:var(--text)}
.actions{display:flex;gap:8px;justify-content:center;padding:15px 20px 25px}.actions a{padding:11px 15px;border-radius:13px;background:var(--input-bg);color:var(--text)}
.avatar-upload{text-align:center;margin-bottom:10px}
.upload-label{display:inline-block;cursor:pointer;text-align:center}
.admin-row{display:flex;align-items:center;gap:14px;padding:15px;border:1px solid var(--item-border);background:var(--item-bg);border-radius:21px;flex-wrap:wrap}
.admin-row .info{flex:1;min-width:140px}.admin-actions{display:flex;gap:6px;flex-wrap:wrap}
.btn-sm{width:auto;padding:8px 12px;margin:0;font-size:12px;border-radius:10px;background:var(--input-bg);color:var(--text)}
.btn-sm.warn{background:linear-gradient(135deg,#ff4d4d,#c92a2a);color:#fff}.btn-sm.on{background:linear-gradient(135deg,var(--btn-grad1),var(--btn-grad2));color:#fff}
.admin-section-title{margin:22px 0 10px}
.card{padding:12px 14px;border:1px solid var(--item-border);background:var(--item-bg);border-radius:14px;margin:8px 0;color:var(--text)}
@media(max-width:700px){.side{display:none}.header{height:62px}.page{padding:12px 10px 88px}.chat{height:calc(100vh - 132px)}
.msg{max-width:90%}.bottom{position:fixed;display:flex;bottom:0;left:0;right:0;height:70px;z-index:30;background:var(--bottom-bg);
border-top:1px solid var(--border);backdrop-filter:blur(22px)}.bottom a{flex:1;text-align:center;padding:8px 2px;color:var(--bottom-text);font-size:10px}.bottom span{display:block;font-size:21px;margin-bottom:3px}
.bottom .active{color:var(--bottom-active)}.box{margin:15px 5px}.item{padding:13px}.avatar{width:52px;height:52px}}
"""

THEME_INIT_SCRIPT = """<script>(function(){
try{
  var t = localStorage.getItem('parto_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
}catch(e){}
})();</script>"""

THEME_TOGGLE_SCRIPT = """<script>
function toggleTheme(){
  var html = document.documentElement;
  var cur = html.getAttribute('data-theme') || 'dark';
  var next = cur === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  try{ localStorage.setItem('parto_theme', next); }catch(e){}
}
</script>"""

def layout(title, body, active="chat"):
    u = me()
    is_adm = bool(u and int(u["admin"] or 0) == 1)
    links=[("chat","💬","چت","/chat"),("search","⌕","جستجو","/search"),
           ("create","＋","ساخت","/create"),("profile","◉","پروفایل","/profile")]
    side="".join(f"<a class='nav' href='{u}'>{i} {n}</a>" for k,i,n,u in links)
    bottom="".join(f"<a class='{'active' if active==k else ''}' href='{u}'><span>{i}</span>{n}</a>" for k,i,n,u in links)
    admin_side = "<a class='nav' href='/admin'>🛡️ پنل مدیریت</a>" if is_adm else ""
    admin_bottom = f"<a class='{'active' if active=='admin' else ''}' href='/admin'><span>🛡️</span>مدیریت</a>" if is_adm else ""
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    {THEME_INIT_SCRIPT}
    <title>{esc(title)} · Parto</title><style>{CSS}</style></head><body>
    <div class='app'><aside class='side'><div class='logo'><b>⚡</b>Parto</div>{side}{admin_side}
    <a class='nav' href='/settings'>⚙️ تنظیمات</a><a class='nav' href='/logout'>↪ خروج</a></aside>
    <main class='main'><header class='header'><h3>{esc(title)}</h3>
    <button type='button' class='theme-toggle' onclick='toggleTheme()' title='تغییر پوسته روشن/تاریک'>🌓</button>
    </header>{body}</main></div>
    <nav class='bottom'>{bottom}{admin_bottom}</nav>{THEME_TOGGLE_SCRIPT}</body></html>"""

@app.route("/")
def index():
    if me(): return redirect("/chat")
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    {THEME_INIT_SCRIPT}<style>{CSS}</style></head>
    <body><div class='box'><div class='avatar' style='margin:auto'>⚡</div><h1 style='text-align:center'>Parto</h1>
    <form method='post' action='/login'><input name='email' placeholder='Email' required><input name='password' type='password' placeholder='Password' required><button>Login</button></form>
    <a href='/register'>Create account</a></div></body></html>"""

@app.route("/register",methods=["GET","POST"])
def register():
    if request.method=="GET":
        return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
        {THEME_INIT_SCRIPT}<style>{CSS}</style></head>
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

    x = None
    try:
        x = db()
        x.execute(
            "SELECT username, password, banned FROM users WHERE LOWER(email)=LOWER(%s) LIMIT 1",
            (email,)
        )
        u = x.fetchone()
        x.close()
        x = None
    except Exception:
        app.logger.exception("LOGIN DATABASE ERROR")
        if x is not None:
            try:
                x.rollback()
                x.close()
            except Exception:
                pass
        return "Login database error. Check Render logs.", 500

    if not u:
        return "Invalid login.", 401

    try:
        if not check_password_hash(u["password"], password):
            return "Invalid login.", 401
    except Exception:
        app.logger.exception("PASSWORD HASH ERROR")
        return "Invalid login.", 500

    if int(u["banned"] or 0) == 1:
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
    # Official Parto channel.
    official=x.execute("SELECT * FROM rooms WHERE username='parto' LIMIT 1").fetchone()
    # Every group and every channel created by any user is visible to everyone.
    other_rooms=x.execute("SELECT * FROM rooms WHERE username!='parto' ORDER BY id DESC").fetchall()
    private_users=x.execute("""SELECT u.username,u.emoji,u.avatar,COALESCE(s.unread,0) AS unread
        FROM users u JOIN (
          SELECT CASE WHEN sender=%s THEN receiver ELSE sender END AS other_user
          FROM private_messages WHERE sender=%s OR receiver=%s
          GROUP BY CASE WHEN sender=%s THEN receiver ELSE sender END
        ) p ON p.other_user=u.username
        LEFT JOIN private_chat_state s ON s.owner=%s AND s.other_user=u.username
        ORDER BY COALESCE(s.unread,0) DESC,u.username""",
        (u["username"],u["username"],u["username"],u["username"],u["username"])).fetchall()
    x.close()
    cards=""
    if official:
        oav = avatar_html(official)
        cards+=f"""<a class='item' href='/room/{official["id"]}'>{oav}<div class='info'>
        <div class='name'>پرتو <span class='badge'>✓</span></div><div class='sub'>کانال رسمی پرتو</div></div><div class='arrow'>‹</div></a>"""
    for r in other_rooms:
        kind_label = "گروه" if r["kind"] == "group" else "کانال"
        rbadge = " <span class='badge'>✓</span>" if r["verified"] else ""
        rav = avatar_html(r)
        cards+=f"""<a class='item' href='/room/{r["id"]}'>{rav}<div class='info'>
        <div class='name'>{esc(r["name"])}{rbadge}</div><div class='sub'>@{esc(r["username"])} · {kind_label}</div></div><div class='arrow'>‹</div></a>"""
    for z in private_users:
        unread = f"<span class='badge pro'>{int(z['unread'])}</span>" if z['unread'] else ''
        av = avatar_html(z)
        cards+=f"""<a class='item' href='/private/{esc(z["username"])}'>{av}<div class='info'>
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
    ms=x.execute("SELECT * FROM messages WHERE room=%s ORDER BY id",(rid,)).fetchall();x.close()
    body=""
    for m in ms:
        cls = 'mine' if m['username'] == u['username'] else ''
        img_tag = f"<img class='msg-img' src='/uploads/chat/{esc(m['image'])}' alt=''>" if m.get('image') else ""
        txt = esc(m['text']) if m['text'] else ""
        body += f"<div class='msg {cls}'><div class='meta'>@{esc(m['username'])}</div>{img_tag}{txt}</div>"
    # Groups: everyone can post. Channels: only the owner can post (enforced again in /send).
    can_send = r["kind"] == "group" or (r["kind"] == "channel" and r["owner"] == u["username"])
    if can_send:
        # Image sending is a PRO-only feature. Server-side enforcement happens
        # again in /send regardless of what is rendered here.
        img_input = "<label class='img-btn' title='ارسال عکس (PRO)'>📷<input type='file' name='image' accept='image/*' hidden></label>" if u["pro"] else ""
        composer = f"<form class='composer' method='post' action='/send/{rid}' enctype='multipart/form-data'>{img_input}<input name='text' placeholder='پیام...'><button>➤</button></form>"
    else:
        composer = "<p class='sub' style='text-align:center;padding:14px'>فقط سازنده کانال می‌تواند پیام بفرستد.</p>"
    title = r["name"] + (" ✓" if r["verified"] else "")
    # Editing the group/channel profile (picture, name, emoji, bio) is a
    # PRO-only feature and only the owner may do it (enforced again server-side).
    edit_bar = ""
    if r["owner"] == u["username"] and u["pro"]:
        edit_bar = f"<div style='padding:10px 14px 0'><a class='btn-sm on' style='display:inline-block;width:auto' href='/room/{rid}/edit'>ویرایش پروفایل گروه/کانال</a></div>"
    return layout(title,f"<div class='chat'>{edit_bar}<div class='messages'>{body or '<p class=\"sub\">هنوز پیامی نیست.</p>'}</div>{composer}</div>","chat")

@app.route("/send/<int:rid>",methods=["POST"])
def send(rid):
    u=me()
    if not u:return redirect("/")
    x=db();r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone()
    if not r:x.close();return "Chat not found."
    if r["kind"]=="channel" and r["owner"]!=u["username"]:x.close();return "Only the channel owner can post.",403
    text=request.form.get("text","").strip()
    image_filename = ""
    # Image attachments are strictly a PRO feature; enforced here regardless
    # of whether the client UI exposed the file input.
    if u["pro"]:
        file_storage = request.files.get("image")
        try:
            fname, _mime = save_uploaded_image(file_storage, CHAT_DIR)
            image_filename = fname or ""
        except ValueError as e:
            x.close()
            return str(e), 400
    if text or image_filename:
        now=datetime.now().isoformat(timespec="seconds")
        x.execute("""INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited,image)
                     VALUES(%s,%s,%s,%s,%s,%s,0,0,%s)""",(rid,rid,u["username"],text[:2000],now,now,image_filename))
        x.commit()
    x.close();return redirect(f"/room/{rid}")

@app.route("/search")
def search():
    u=me()
    if not u:return redirect("/")
    q=request.args.get("q","").strip()
    x=db()
    users=x.execute("SELECT username,emoji,verified,pro,avatar FROM users WHERE username ILIKE %s LIMIT 30",(f"%{q}%",)).fetchall()
    rooms=x.execute("SELECT * FROM rooms WHERE username ILIKE %s OR name ILIKE %s LIMIT 30",(f"%{q}%",f"%{q}%")).fetchall()
    x.close()
    out=""
    for z in users:
        badges=("<span class='badge'>✓</span>" if z["verified"] else "")+("<span class='badge pro'>PRO</span>" if z["pro"] else "")
        av = avatar_html(z)
        out+=f"""<a class='item' href='/private/{esc(z["username"])}'>{av}<div class='info'>
        <div class='name'>@{esc(z["username"])} {badges}</div><div class='sub'>شروع چت خصوصی با آیدی</div></div><div class='arrow'>‹</div></a>"""
    for r in rooms:
        rbadge = " <span class='badge'>✓</span>" if r["verified"] else ""
        rav = avatar_html(r)
        out+=f"""<a class='item' href='/room/{r["id"]}'>{rav}<div class='info'>
        <div class='name'>{esc(r["name"])}{rbadge}</div><div class='sub'>@{esc(r["username"])} · {esc(r["kind"])}</div></div><div class='arrow'>‹</div></a>"""
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

@app.route("/room/<int:rid>/edit", methods=["GET", "POST"])
def room_edit(rid):
    u = me()
    if not u:
        return redirect("/")
    x = db(); r = x.execute("SELECT * FROM rooms WHERE id=%s", (rid,)).fetchone()
    if not r:
        x.close()
        return "Chat not found."
    # Only the group/channel owner may edit its profile, and only if PRO.
    # Both checks are enforced here regardless of what the UI shows.
    if r["owner"] != u["username"]:
        x.close()
        return "Only the owner can edit this profile.", 403
    if not u["pro"]:
        x.close()
        return "PRO required to edit the group/channel profile.", 403

    if request.method == "GET":
        x.close()
        preview = avatar_html(r, cls="bigavatar")
        remove_btn = f"<form method='post' action='/room/{rid}/avatar/remove'><button class='btn-sm warn'>حذف عکس پروفایل</button></form>" if r["avatar"] else ""
        body = f"""<div class='page'><div class='box'>
        <div class='avatar-upload'>{preview}
        <form method='post' action='/room/{rid}/avatar/upload' enctype='multipart/form-data'>
        <label class='btn-sm on upload-label'>آپلود عکس پروفایل
        <input type='file' name='avatar' accept='image/*' hidden onchange='this.form.submit()'></label>
        </form>{remove_btn}</div>
        <form method='post'>
        <input name='name' value='{esc(r["name"])}' placeholder='نام' required maxlength='80'>
        <input name='emoji' value='{esc(r["emoji"])}' placeholder='ایموجی' maxlength='8'>
        <textarea name='bio' placeholder='توضیح' maxlength='200'>{esc(r["bio"])}</textarea>
        <button>ذخیره</button>
        </form></div></div>"""
        return layout("ویرایش پروفایل", body, "chat")

    name = request.form.get("name", "").strip()
    emoji = request.form.get("emoji", "").strip() or "💬"
    bio = request.form.get("bio", "").strip()
    if not name:
        x.close()
        return "Name is required.", 400
    x.execute("UPDATE rooms SET name=%s, emoji=%s, bio=%s WHERE id=%s", (name[:80], emoji[:8], bio[:200], rid))
    x.commit()
    x.close()
    return redirect(f"/room/{rid}")

@app.route("/room/<int:rid>/avatar/upload", methods=["POST"])
def room_avatar_upload(rid):
    u = me()
    if not u:
        return redirect("/")
    x = db(); r = x.execute("SELECT * FROM rooms WHERE id=%s", (rid,)).fetchone()
    if not r:
        x.close()
        return "Chat not found."
    if r["owner"] != u["username"]:
        x.close()
        return "Only the owner can edit this profile.", 403
    if not u["pro"]:
        x.close()
        return "PRO required to edit the group/channel profile.", 403
    file_storage = request.files.get("avatar")
    try:
        filename, _mime = save_uploaded_image(file_storage, AVATAR_DIR)
    except ValueError as e:
        x.close()
        return str(e), 400
    if not filename:
        x.close()
        return redirect(f"/room/{rid}/edit")
    old = r["avatar"]
    x.execute("UPDATE rooms SET avatar=%s WHERE id=%s", (filename, rid))
    x.commit()
    x.close()
    if old:
        delete_uploaded_file(AVATAR_DIR, old)
    return redirect(f"/room/{rid}/edit")

@app.route("/room/<int:rid>/avatar/remove", methods=["POST"])
def room_avatar_remove(rid):
    u = me()
    if not u:
        return redirect("/")
    x = db(); r = x.execute("SELECT * FROM rooms WHERE id=%s", (rid,)).fetchone()
    if not r:
        x.close()
        return "Chat not found."
    if r["owner"] != u["username"]:
        x.close()
        return "Only the owner can edit this profile.", 403
    if not u["pro"]:
        x.close()
        return "PRO required to edit the group/channel profile.", 403
    old = r["avatar"]
    x.execute("UPDATE rooms SET avatar='' WHERE id=%s", (rid,))
    x.commit()
    x.close()
    if old:
        delete_uploaded_file(AVATAR_DIR, old)
    return redirect(f"/room/{rid}/edit")

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
        img_tag = f"<img class='msg-img' src='/uploads/chat/{esc(m['image'])}' alt=''>" if m.get('image') else ""
        txt = esc(m['text']) if m['text'] else ""
        body += f"<div class='msg {cls}'><div class='meta'>@{esc(m['sender'])}</div>{img_tag}{txt}</div>"
    # Image sending in private chats is PRO-only; enforced again in /private/<u>/send.
    img_input = "<label class='img-btn' title='ارسال عکس (PRO)'>📷<input type='file' name='image' accept='image/*' hidden></label>" if u["pro"] else ""
    return layout("@"+username,f"""<div class='chat'><div class='messages'>{body or '<p class="sub">شروع گفتگو</p>'}</div>
    <form class='composer' method='post' action='/private/{esc(username)}/send' enctype='multipart/form-data'>{img_input}<input name='text' placeholder='پیام خصوصی...'><button>➤</button></form>
    <script>setInterval(()=>location.reload(),3000);</script></div>""","chat")

@app.route("/private/<username>/send",methods=["POST"])
def private_send(username):
    u=me()
    if not u:return redirect("/")
    x=db()
    if x.execute("SELECT id FROM users WHERE username=%s",(username,)).fetchone():
        text = request.form.get("text","").strip()[:2000]
        image_filename = ""
        if u["pro"]:
            file_storage = request.files.get("image")
            try:
                fname, _mime = save_uploaded_image(file_storage, CHAT_DIR)
                image_filename = fname or ""
            except ValueError as e:
                x.close()
                return str(e), 400
        if text or image_filename:
            x.execute("INSERT INTO private_messages(sender,receiver,text,created_at,image) VALUES(%s,%s,%s,%s,%s)",
                      (u["username"],username,text,datetime.now().isoformat(timespec="seconds"),image_filename))
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
    big_avatar = avatar_html(z, cls="bigavatar")
    body=f"""<div class='page'><div class='profile'><div class='cover'></div>{big_avatar}
    <h2>@{esc(z["username"])} {badges}</h2><p class='sub'>{esc(z["bio"] or "No bio yet.")}</p><div class='actions'>{button}</div></div></div>"""
    return layout("پروفایل",body,"profile")

@app.route("/editprofile",methods=["GET","POST"])
def editprofile():
    u=me()
    if not u:return redirect("/")
    if request.method=="GET":
        # PRO users may upload/change/remove a profile picture. Normal users
        # keep the emoji-only avatar (enforced server-side in /avatar/upload).
        if u["pro"]:
            preview = avatar_html(u, cls="bigavatar")
            remove_btn = "<form method='post' action='/avatar/remove'><button class='btn-sm warn'>حذف عکس پروفایل</button></form>" if u["avatar"] else ""
            avatar_section = f"""<div class='avatar-upload'>{preview}
            <form method='post' action='/avatar/upload' enctype='multipart/form-data'>
            <label class='btn-sm on upload-label'>آپلود عکس پروفایل
            <input type='file' name='avatar' accept='image/*' hidden onchange='this.form.submit()'></label>
            </form>{remove_btn}</div>"""
        else:
            avatar_section = f"""<div class='avatar-upload'>{avatar_html(u, cls='bigavatar')}
            <p class='sub'>آپلود عکس پروفایل مخصوص کاربران PRO است.</p></div>"""
        return layout("پروفایل",f"""<div class='page'><div class='box'>{avatar_section}<form method='post'>
        <select name='emoji'><option>👤</option><option>😎</option><option>⚡</option><option>🤖</option><option>🔥</option></select>
        <textarea name='bio' placeholder='بیو'>{esc(u["bio"])}</textarea><button>ذخیره</button></form></div></div>""","profile")
    x=db();x.execute("UPDATE users SET emoji=%s,bio=%s WHERE username=%s",(request.form["emoji"],request.form["bio"][:200],u["username"]));x.commit();x.close()
    return redirect("/profile/"+u["username"])

@app.route("/avatar/upload", methods=["POST"])
def avatar_upload():
    u = me()
    if not u:
        return redirect("/")
    # Server-side enforcement: only PRO accounts may upload a profile picture,
    # regardless of what request is sent to this endpoint.
    if not u["pro"]:
        return "PRO required.", 403
    file_storage = request.files.get("avatar")
    try:
        filename, _mime = save_uploaded_image(file_storage, AVATAR_DIR)
    except ValueError as e:
        return str(e), 400
    if not filename:
        return redirect("/editprofile")
    old = u["avatar"]
    x = db()
    x.execute("UPDATE users SET avatar=%s WHERE username=%s", (filename, u["username"]))
    x.commit()
    x.close()
    if old:
        delete_uploaded_file(AVATAR_DIR, old)
    return redirect("/editprofile")

@app.route("/avatar/remove", methods=["POST"])
def avatar_remove():
    u = me()
    if not u:
        return redirect("/")
    if not u["pro"]:
        return "PRO required.", 403
    old = u["avatar"]
    x = db()
    x.execute("UPDATE users SET avatar='' WHERE username=%s", (u["username"],))
    x.commit()
    x.close()
    if old:
        delete_uploaded_file(AVATAR_DIR, old)
    return redirect("/editprofile")

@app.route("/uploads/<subdir>/<filename>")
def serve_upload(subdir, filename):
    # Only ever serve from the two known, whitelisted subfolders, and only a
    # bare filename (no path separators / traversal sequences survive this).
    if subdir not in ALLOWED_UPLOAD_SUBDIRS:
        return "Not found", 404
    safe_name = os.path.basename(filename)
    if not safe_name or safe_name != filename:
        return "Not found", 404
    folder = os.path.join(UPLOAD_ROOT, subdir)
    full_path = os.path.abspath(os.path.join(folder, safe_name))
    if not full_path.startswith(os.path.abspath(folder) + os.sep):
        return "Not found", 404
    if not os.path.isfile(full_path):
        return "Not found", 404
    return send_from_directory(folder, safe_name)

@app.route("/admin")
def admin_panel():
    u = me()
    if not u:
        return redirect("/")
    if not is_admin(u):
        return redirect("/chat")
    x = db()
    users = x.execute("SELECT * FROM users ORDER BY id").fetchall()
    rooms = x.execute("SELECT * FROM rooms ORDER BY id").fetchall()
    x.close()
    rows = ""
    for z in users:
        badges = ("<span class='badge'>✓</span>" if z["verified"] else "") + \
                 ("<span class='badge pro'>PRO</span>" if z["pro"] else "") + \
                 ("<span class='badge' style='background:#ff4d4d'>مدیر</span>" if z["admin"] else "") + \
                 ("<span class='badge' style='background:#555'>بن‌شده</span>" if z["banned"] else "")
        ban_label = "آزاد کردن" if z["banned"] else "بن کردن"
        verify_label = "لغو تایید" if z["verified"] else "تایید کردن"
        pro_label = "لغو PRO" if z["pro"] else "فعال کردن PRO"
        av = avatar_html(z)
        rows += f"""<div class='admin-row'>
        {av}
        <div class='info'><div class='name'>@{esc(z["username"])} {badges}</div>
        <div class='sub'>{esc(z["email"] or "")}</div></div>
        <div class='admin-actions'>
        <form method='post' action='/admin/ban/{esc(z["username"])}'><button class='btn-sm{" warn" if not z["banned"] else ""}'>{ban_label}</button></form>
        <form method='post' action='/admin/verify/{esc(z["username"])}'><button class='btn-sm{" on" if not z["verified"] else ""}'>{verify_label}</button></form>
        <form method='post' action='/admin/pro/{esc(z["username"])}'><button class='btn-sm{" on" if not z["pro"] else ""}'>{pro_label}</button></form>
        </div></div>"""
    room_rows = ""
    for r in rooms:
        rbadge = "<span class='badge'>✓</span>" if r["verified"] else ""
        rverify_label = "لغو تایید" if r["verified"] else "تایید کردن"
        kind_label = "گروه" if r["kind"] == "group" else "کانال"
        rav = avatar_html(r)
        room_rows += f"""<div class='admin-row'>
        {rav}
        <div class='info'><div class='name'>{esc(r["name"])} {rbadge}</div>
        <div class='sub'>@{esc(r["username"])} · {kind_label} · owner: @{esc(r["owner"])}</div></div>
        <div class='admin-actions'>
        <form method='post' action='/admin/room/verify/{r["id"]}'><button class='btn-sm{" on" if not r["verified"] else ""}'>{rverify_label}</button></form>
        </div></div>"""
    body = f"""<div class='page'><h2>پنل مدیریت</h2>
    <h3 class='admin-section-title'>کاربران</h3><div class='list'>{rows}</div>
    <h3 class='admin-section-title'>گروه‌ها و کانال‌ها</h3><div class='list'>{room_rows or '<p class="sub">هنوز گروه یا کانالی نیست.</p>'}</div>
    </div>"""
    return layout("مدیریت", body, "admin")

@app.route("/admin/ban/<username>", methods=["POST"])
def admin_toggle_ban(username):
    u = me()
    if not u or not is_admin(u):
        return "Forbidden", 403
    x = db()
    x.execute("UPDATE users SET banned = CASE WHEN banned=1 THEN 0 ELSE 1 END WHERE username=%s", (username,))
    x.commit()
    x.close()
    return redirect("/admin")

@app.route("/admin/verify/<username>", methods=["POST"])
def admin_toggle_verify(username):
    u = me()
    if not u or not is_admin(u):
        return "Forbidden", 403
    x = db()
    x.execute("UPDATE users SET verified = CASE WHEN verified=1 THEN 0 ELSE 1 END WHERE username=%s", (username,))
    x.commit()
    x.close()
    return redirect("/admin")

@app.route("/admin/pro/<username>", methods=["POST"])
def admin_toggle_pro(username):
    u = me()
    if not u or not is_admin(u):
        return "Forbidden", 403
    x = db()
    x.execute("UPDATE users SET pro = CASE WHEN pro=1 THEN 0 ELSE 1 END WHERE username=%s", (username,))
    x.commit()
    x.close()
    return redirect("/admin")

@app.route("/admin/room/verify/<int:rid>", methods=["POST"])
def admin_toggle_room_verify(rid):
    u = me()
    if not u or not is_admin(u):
        return "Forbidden", 403
    x = db()
    x.execute("UPDATE rooms SET verified = CASE WHEN verified=1 THEN 0 ELSE 1 END WHERE id=%s", (rid,))
    x.commit()
    x.close()
    return redirect("/admin")

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
        <div class="card">✓ آپلود، تغییر و حذف عکس پروفایل</div>
        <div class="card">✓ ارسال عکس در چت خصوصی، گروه و کانال</div>
        <div class="card">✓ امکانات مدیریتی PRO در صورت فعال‌سازی توسط ادمین</div>
    </div></div>
    """, "profile")


@app.errorhandler(RequestEntityTooLarge)
def handle_too_large(error):
    return "Uploaded file is too large.", 413


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("UNHANDLED APPLICATION ERROR")
    return "Internal Server Error. Check Render logs for the traceback.", 500


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
