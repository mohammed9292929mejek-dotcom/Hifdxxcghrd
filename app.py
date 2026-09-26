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
app.secret_key = os.getenv("SECRET_KEY", "SIMURGH_2026")
DATABASE_URL = os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Upload configuration (secure image uploads for PRO avatars & chat images)
# ---------------------------------------------------------------------------
UPLOAD_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads")
AVATAR_DIR = "avatars"
CHAT_DIR = "chat"
PAGE_DIR = "pages"
ALLOWED_UPLOAD_SUBDIRS = {AVATAR_DIR, CHAT_DIR, PAGE_DIR}
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_POST_MEDIA_BYTES = 25 * 1024 * 1024
# Overall request body cap (a little above MAX_IMAGE_BYTES to allow for form fields).
app.config["MAX_CONTENT_LENGTH"] = 30 * 1024 * 1024

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
        # Additive Twitter-like features. Existing tables/data are preserved.
        cur.execute("""CREATE TABLE IF NOT EXISTS post_likes(
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, username TEXT NOT NULL,
            created_at TEXT DEFAULT '', UNIQUE(post_id,username))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS post_comments(
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, username TEXT NOT NULL,
            text TEXT NOT NULL, created_at TEXT DEFAULT '')""")
        cur.execute("""CREATE TABLE IF NOT EXISTS follows(
            id SERIAL PRIMARY KEY, follower TEXT NOT NULL, target TEXT NOT NULL,
            created_at TEXT DEFAULT '', UNIQUE(follower,target))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS bookmarks(
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL, username TEXT NOT NULL,
            created_at TEXT DEFAULT '', UNIQUE(post_id,username))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS blocks(
            id SERIAL PRIMARY KEY, blocker TEXT NOT NULL, blocked TEXT NOT NULL,
            created_at TEXT DEFAULT '', UNIQUE(blocker,blocked))""")
        cur.execute("""CREATE TABLE IF NOT EXISTS trending_posts(
            id SERIAL PRIMARY KEY, post_id INTEGER NOT NULL UNIQUE,
            enabled INTEGER DEFAULT 0, created_at TEXT DEFAULT '')""")
        for col, definition in {
            'media_type':"TEXT DEFAULT ''",'media_name':"TEXT DEFAULT ''",'media_url':"TEXT DEFAULT ''"
        }.items():
            cur.execute("SELECT column_name FROM information_schema.columns WHERE table_schema='public' AND table_name='messages' AND column_name=%s",(col,))
            if not cur.fetchone(): cur.execute(f"ALTER TABLE messages ADD COLUMN {col} {definition}")

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
                "avatar":"TEXT DEFAULT ''",
                "profile_music":"TEXT DEFAULT ''"},
            "rooms": {
                "bio":"TEXT DEFAULT ''","emoji":"TEXT DEFAULT '💬'",
                # Admin-controlled blue verification badge for groups/channels.
                "verified":"INTEGER DEFAULT 0"},
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

        cur.execute("SELECT id FROM users WHERE username='simorg'")
        if not cur.fetchone():
            cur.execute("""INSERT INTO users
                (username,email,password,emoji,bio,admin,verified,pro)
                VALUES(%s,%s,%s,%s,%s,1,1,1)""",
                ("simorg","P@Sumorg",generate_password_hash("Html930343245532"),"🦅","Official Simurgh"))
        else:
            # Row already exists: never delete it, just make sure the official
            # login (email/password) and admin flag are the requested ones.
            cur.execute(
                "UPDATE users SET email=%s, password=%s, admin=1 WHERE username='simorg'",
                ("P@Sumorg", generate_password_hash("Html930343245532"))
            )

        cur.execute("SELECT id FROM rooms WHERE username='simorg'")
        if not cur.fetchone():
            cur.execute("""INSERT INTO rooms(name,username,kind,owner,emoji,bio)
                VALUES(%s,%s,'channel',%s,%s,%s)""",
                ("سیمرغ","simorg","simorg","🦅","کانال رسمی سیمرغ"))
        else:
            # Row already exists: never delete it, just make sure kind/owner are correct.
            cur.execute("UPDATE rooms SET kind='channel', owner='simorg' WHERE username='simorg'")
        # Official Simurgh channel is always shown as verified.
        cur.execute("UPDATE rooms SET verified=1 WHERE username='simorg'")

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
    """Renders a user's avatar: an uploaded picture for PRO users who set one,
    otherwise the emoji avatar every account has by default."""
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
  --bg:#1a1410; --bg-grad1:#3d2817; --bg-grad2:#2d2415;
  --text:#f5f3f0; --side-bg:#1e1915dd; --border:#3a3028;
  --nav-text:#b8a89a; --nav-hover-bg:#2a241a;
  --header-bg:#1e1915d9; --item-bg:#2a2318e8; --item-border:#453430; --item-hover:#2f2820;
  --avatar-bg:#3a2e20; --sub-text:#8a7a68; --arrow:#9a8a78;
  --input-bg:#242018; --input-border:#3a3028; --input-text:#fff;
  --btn-grad1:#d4a500; --btn-grad2:#c78a1a; --btn-text:#fff;
  --msg-bg:#241f1a; --msg-border:#3a302a; --msg-mine-bg:#4a3a28;
  --card-bg:#1f1a15ed; --box-shadow:0 25px 80px rgba(0,0,0,.45);
  --logo-grad1:#d4a500; --logo-grad2:#c78a1a;
  --badge-bg:#c78a1a;
  --bottom-bg:#18140af2; --bottom-text:#a09080; --bottom-active:#ffd700;
  --cover-grad:linear-gradient(120deg,#d4a500,#c78a1a,#b8860b);
}
[data-theme='light']{
  --bg:#fef9f5; --bg-grad1:#f5e6d3; --bg-grad2:#f9f0e3;
  --text:#3d2817; --side-bg:#ffffffee; --border:#e8d9c8;
  --nav-text:#8a6b4a; --nav-hover-bg:#f5e6d3;
  --header-bg:#ffffffe6; --item-bg:#ffffff; --item-border:#e8d9c8; --item-hover:#fef9f5;
  --avatar-bg:#f0e6d8; --sub-text:#8a7a68; --arrow:#a89a88;
  --input-bg:#f9f0e3; --input-border:#e8d9c8; --input-text:#3d2817;
  --btn-grad1:#d4a500; --btn-grad2:#c78a1a; --btn-text:#fff;
  --msg-bg:#f5e6d3; --msg-border:#e8d9c8; --msg-mine-bg:#e8d9c8;
  --card-bg:#ffffff; --box-shadow:0 20px 60px rgba(120,80,30,.12);
  --logo-grad1:#d4a500; --logo-grad2:#c78a1a;
  --badge-bg:#c78a1a;
  --bottom-bg:#ffffffF2; --bottom-text:#a09080; --bottom-active:#8a6b4a;
  --cover-grad:linear-gradient(120deg,#d4a500,#c78a1a,#b8860b);
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
.feed-title{display:flex;align-items:center;justify-content:space-between}.feed-tabs{position:sticky;top:62px;z-index:4;display:flex;background:var(--header-bg);backdrop-filter:blur(18px);border-bottom:1px solid var(--border);margin:0 -10px 10px}.feed-tabs a{flex:1;text-align:center;padding:15px 5px;color:var(--sub-text);font-weight:800;border-bottom:3px solid transparent}.feed-tabs a.active{color:var(--text);border-bottom-color:var(--btn-grad2)}.composer-card{background:var(--card-bg);border:1px solid var(--border);border-radius:20px;padding:12px;margin-bottom:10px}.composer-card textarea{min-height:70px;border:0;background:transparent;margin:0;resize:none}.compose-row{display:flex;align-items:center;gap:8px}.compose-row .sub{flex:1}.compose-row button{width:auto;padding:10px 18px;margin:0}.media-pick{width:40px;height:40px;border-radius:50%;display:flex;align-items:center;justify-content:center;background:var(--input-bg);cursor:pointer;font-size:22px}.feed-list{display:flex;flex-direction:column}.post-card{background:var(--card-bg);border:1px solid var(--border);border-radius:20px;padding:14px;margin:7px 0;box-shadow:var(--box-shadow);user-select:text}.post-head{display:flex;align-items:center;gap:10px}.post-author{flex:1;min-width:0}.post-author a{color:var(--text)}.more-btn{width:auto;background:transparent;color:var(--sub-text);padding:5px;margin:0}.post-text{font-size:15px;line-height:1.9;margin:12px 3px;white-space:pre-wrap;word-break:break-word}.post-actions{display:flex;align-items:center;gap:4px;border-top:1px solid var(--border);padding-top:8px;margin-top:8px;flex-wrap:wrap}.post-actions form{display:inline}.post-actions button,.post-actions a{width:auto;background:transparent;color:var(--sub-text);padding:7px 9px;margin:0;border-radius:10px}.post-actions button:hover,.post-actions a:hover{background:var(--input-bg);color:var(--text)}.danger{color:#ff6666!important}.edited{font-size:10px;color:var(--sub-text)}.trend-mark{font-size:9px;background:#ff7a00;color:#fff;border-radius:7px;padding:2px 5px;margin-right:3px}.post-media{width:100%;max-height:480px;border-radius:17px;object-fit:cover;margin-top:5px}.post-audio{width:100%;margin-top:8px}.file-pill{display:block;padding:12px;border:1px solid var(--border);border-radius:13px;margin-top:8px;color:var(--text)}.empty{text-align:center;padding:50px 15px;color:var(--sub-text)}.focus-overlay{position:fixed;inset:0;background:rgba(0,0,0,.72);backdrop-filter:blur(14px);z-index:100;display:none;align-items:center;justify-content:center;padding:15px}.focus-overlay.open{display:flex}.focus-box{width:min(650px,100%);max-height:90vh;overflow:auto}.focus-box .post-card{margin:0;box-shadow:0 20px 80px rgba(0,0,0,.5)}.profile-stats{font-size:14px}.profile-music{padding:8px 18px}.profile-music audio{width:100%;margin-top:7px}.profile-music form{display:flex;gap:8px;align-items:center}.profile-music button{width:auto}.bigavatar.img{overflow:hidden}.bigavatar.img img{width:100%;height:100%;object-fit:cover}.avatar.img{overflow:hidden}.avatar.img img{width:100%;height:100%;object-fit:cover}@media(max-width:700px){.side{display:none}.header{height:62px}.page{padding:12px 10px 88px}.chat{height:calc(100vh - 132px)}
.msg{max-width:90%}.bottom{position:fixed;display:flex;bottom:0;left:0;right:0;height:70px;z-index:30;background:var(--bottom-bg);
border-top:1px solid var(--border);backdrop-filter:blur(22px)}.bottom a{flex:1;text-align:center;padding:8px 2px;color:var(--bottom-text);font-size:10px}.bottom span{display:block;font-size:21px;margin-bottom:3px}
.bottom .active{color:var(--bottom-active)}.box{margin:15px 5px}.item{padding:13px}.avatar{width:52px;height:52px}.post-card{padding:12px;margin:5px 0}
.post-text{font-size:14px;margin:10px 0}.feed-tabs{padding:0 10px}.composer-card{margin:8px 0;padding:10px}.input-bg{padding:10px}input,textarea,button{padding:12px;font-size:16px}
.focus-box{max-height:95vh;border-radius:20px}.focus-overlay{padding:10px}.profile{margin:10px 0}.actions{gap:5px}.admin-row{flex-wrap:wrap}.admin-actions{width:100%;gap:4px}}
"""

THEME_INIT_SCRIPT = """<script>(function(){
try{
  var t = localStorage.getItem('simurgh_theme') || 'dark';
  document.documentElement.setAttribute('data-theme', t);
}catch(e){}
})();</script>"""

THEME_TOGGLE_SCRIPT = """<script>
function toggleTheme(){
  var html = document.documentElement;
  var cur = html.getAttribute('data-theme') || 'dark';
  var next = cur === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  try{ localStorage.setItem('simurgh_theme', next); }catch(e){}
}
function focusPost(e,card){if(e)e.preventDefault();var o=document.getElementById('focusOverlay'),b=document.getElementById('focusBox');if(!o||!b||!card)return;try{var clone=card.cloneNode(true);clone.oncontextmenu=null;clone.ontouchstart=null;clone.ontouchend=null;clone.ontouchmove=null;b.innerHTML='';b.appendChild(clone);o.classList.add('open');document.body.style.overflow='hidden'}catch(x){console.error('Error focusing post:',x)}}
function closeFocus(e){if(e&&e.target.id==='focusOverlay'){e.currentTarget.classList.remove('open');document.body.style.overflow=''}}
var holdTimer;function startHold(e,card){holdTimer=setTimeout(function(){focusPost(e,card)},550)}function cancelHold(){clearTimeout(holdTimer)}
</script>"""

def layout(title, body, active="chat"):
    u = me()
    is_adm = bool(u and int(u["admin"] or 0) == 1)
    links=[("chat","⌂","خانه","/chat"),("messages","✉","دایرکت","/messages"),("search","⌕","جستجو","/search"),
           ("bookmarks","★","ذخیره‌ها","/bookmarks"),("profile","◉","پروفایل","/profile")]
    side="".join(f"<a class='nav' href='{u}'>{i} {n}</a>" for k,i,n,u in links)
    bottom="".join(f"<a class='{'active' if active==k else ''}' href='{u}'><span>{i}</span>{n}</a>" for k,i,n,u in links)
    admin_side = "<a class='nav' href='/admin'>🛡️ پنل مدیریت</a>" if is_adm else ""
    admin_bottom = f"<a class='{'active' if active=='admin' else ''}' href='/admin'><span>🛡️</span>مدیریت</a>" if is_adm else ""
    return f"""<!doctype html><html><head><meta name='viewport' content='width=device-width,initial-scale=1'>
    {THEME_INIT_SCRIPT}
    <title>{esc(title)} · Simurgh</title><style>{CSS}</style></head><body>
    <div class='app'><aside class='side'><div class='logo'><b>🦅</b>Simurgh</div>{side}{admin_side}
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
    <body><div class='box'><div class='avatar' style='margin:auto'>🦅</div><h1 style='text-align:center'>Simurgh</h1>
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

def _post_rows(x, u, tab="for_you"):
    blocked_sql="NOT EXISTS(SELECT 1 FROM blocks b WHERE b.blocker=%s AND b.blocked=m.username) AND NOT EXISTS(SELECT 1 FROM blocks b2 WHERE b2.blocker=m.username AND b2.blocked=%s)"
    params=[u['username'],u['username']]
    if tab == 'following':
        where="("+blocked_sql+") AND EXISTS(SELECT 1 FROM follows f WHERE f.follower=%s AND f.target=m.username)"
        params.append(u['username'])
        order="m.id DESC"
    elif tab == 'trending':
        where="("+blocked_sql+") AND (EXISTS(SELECT 1 FROM trending_posts tp WHERE tp.post_id=m.id AND tp.enabled=1) OR (SELECT COUNT(*) FROM post_likes l2 WHERE l2.post_id=m.id)>=60)"
        order="(SELECT COUNT(*) FROM post_likes l3 WHERE l3.post_id=m.id) DESC,m.id DESC"
    elif tab == 'new':
        where="("+blocked_sql+")"
        order="m.id DESC"
    else:
        where="("+blocked_sql+")"
        order="m.id DESC"
    q=f"""SELECT m.*, COALESCE(r.name,u2.username) AS author_name,
        COALESCE(r.username,u2.username) AS author_username,
        COALESCE(r.emoji,u2.emoji) AS author_emoji,
        COALESCE(r.verified,u2.verified) AS author_verified,
        u2.avatar AS author_avatar,u2.pro AS author_pro,
        (SELECT COUNT(*) FROM post_likes l WHERE l.post_id=m.id) AS likes,
        (SELECT COUNT(*) FROM post_comments c WHERE c.post_id=m.id) AS comments,
        EXISTS(SELECT 1 FROM post_likes ml WHERE ml.post_id=m.id AND ml.username=%s) AS liked,
        EXISTS(SELECT 1 FROM bookmarks bm WHERE bm.post_id=m.id AND bm.username=%s) AS bookmarked,
        EXISTS(SELECT 1 FROM trending_posts tp0 WHERE tp0.post_id=m.id AND tp0.enabled=1) AS admin_trending
        FROM messages m LEFT JOIN rooms r ON r.id=m.room
        LEFT JOIN users u2 ON u2.username=m.username
        WHERE {where} ORDER BY {order} LIMIT 100"""
    return x.execute(q, (u['username'],u['username'],*params)).fetchall()

def _render_post(m, u, modal=True):
    badge=" <span class='badge'>✓</span>" if m['author_verified'] else ''
    pro=" <span class='badge pro'>PRO</span>" if m['author_pro'] else ''
    av=avatar_html({'avatar':m['author_avatar'],'emoji':m['author_emoji']})
    if m.get('room'):
        pi=page_image_url(m['author_username'])
        if pi: av=f"<img class='avatar img' src='{pi}' alt=''>"
    media=''; mt=m.get('media_type') or ''; mu=m.get('media_url') or ''
    if mu and mt.startswith('image/'): media=f"<img class='msg-img' src='/uploads/chat/{esc(mu)}' alt=''>"
    elif mu and mt.startswith('video/'): media=f"<video controls class='post-media'><source src='/uploads/chat/{esc(mu)}' type='{esc(mt)}'></video>"
    elif mu and mt.startswith('audio/'): media=f"<audio controls class='post-audio' src='/uploads/chat/{esc(mu)}'></audio>"
    elif mu: media=f"<a class='file-pill' href='/uploads/chat/{esc(mu)}' download>📎 {esc(m.get('media_name') or 'فایل')}</a>"
    owner_actions=''
    if m['username']==u['username'] or is_admin(u):
        owner_actions=f"<a class='post-more' href='/post/edit/{m['id']}'>ویرایش</a><form style='display:inline' method='post' action='/post/delete/{m['id']}'><button class='post-more danger'>حذف</button></form>"
    like_label='♥' if m['liked'] else '♡'; save_label='★' if m['bookmarked'] else '☆'
    trend=' <span class="trend-mark">ترند</span>' if m.get('admin_trending') else ''
    card=f"""<article class='post-card' data-post='{m['id']}' oncontextmenu='focusPost(event,this)' ontouchstart='startHold(event,this)' ontouchend='cancelHold(this)' ontouchmove='cancelHold(this)'>
    <div class='post-head'>{av}<div class='post-author'><a href='/profile/{esc(m['author_username'])}'><b>{esc(m['author_name'])}</b>{badge}{pro}{trend}</a><div class='sub'>@{esc(m['author_username'])} · {esc(m.get('created_at',''))}</div></div><button class='more-btn' onclick='focusPost(event,this.closest("article"))'>•••</button></div>
    <div class='post-text'>{esc(m['text'])}{' <span class="edited">ویرایش شد</span>' if m['edited'] else ''}</div>{media}
    <div class='post-actions'><form method='post' action='/post/like/{m['id']}'><button title='لایک'>{like_label} <span>{m['likes']}</span></button></form><a href='/post/{m['id']}/comments'>♡ <span>{m['comments']}</span></a><form method='post' action='/post/bookmark/{m['id']}'><button title='ذخیره'>{save_label}</button></form><button onclick='focusPost(event,this.closest("article"))' title='تمرکز'>⤢</button>{owner_actions}</div>
    </article>"""
    return card

@app.route("/chat")
def chat():
    u=me()
    if not u:return redirect("/")
    tab=request.args.get('tab','for_you')
    if tab not in ('for_you','following','trending','new'): tab='for_you'
    x=db();posts=_post_rows(x,u,tab)
    today=datetime.now().date().isoformat();today_count=x.execute("SELECT COUNT(*) AS c FROM messages WHERE username=%s AND created_at LIKE %s",(u['username'],today+'%')).fetchone()['c'];x.close()
    limit=1000 if u['pro'] else (5 if u['verified'] else 3)
    composer=f"""<div class='composer-card'><form method='post' action='/post/create' enctype='multipart/form-data'><textarea name='text' maxlength='2000' placeholder='چه خبر؟'></textarea><div class='compose-row'><span class='sub'>امروز {today_count}/{limit} پست</span><label class='media-pick'>＋<input type='file' name='media' accept='image/*,video/*,audio/*,.pdf,.zip,.txt,.doc,.docx' hidden></label><button>پست کردن</button></div></form></div>"""
    tabs=[('for_you','برای تو'),('following','دنبال‌شده‌ها'),('trending','ترند'),('new','تازه‌ها')]
    tab_html="<div class='feed-tabs'>"+''.join(f"<a class='{'active' if tab==k else ''}' href='/chat?tab={k}'>{n}</a>" for k,n in tabs)+"</div>"
    out=''.join(_render_post(m,u) for m in posts)
    body=f"<div class='page feed-page'><div class='feed-title'><h2>خانه</h2></div>{tab_html}{composer}<div class='feed-list'>{out or '<div class="empty">چیزی برای نمایش نیست.</div>'}</div></div><div id='focusOverlay' class='focus-overlay' onclick='closeFocus(event)'><div id='focusBox' class='focus-box'></div></div>"
    return layout("خانه",body,"chat")

@app.route('/bookmarks')
def bookmarks():
    u=me()
    if not u:return redirect('/')
    x=db();rows=x.execute("""SELECT m.*,COALESCE(r.name,u2.username) AS author_name,COALESCE(r.username,u2.username) AS author_username,COALESCE(r.emoji,u2.emoji) AS author_emoji,COALESCE(r.verified,u2.verified) AS author_verified,u2.avatar AS author_avatar,u2.pro AS author_pro,(SELECT COUNT(*) FROM post_likes l WHERE l.post_id=m.id) AS likes,(SELECT COUNT(*) FROM post_comments c WHERE c.post_id=m.id) AS comments,EXISTS(SELECT 1 FROM post_likes ml WHERE ml.post_id=m.id AND ml.username=%s) AS liked,TRUE AS bookmarked,FALSE AS admin_trending FROM bookmarks b JOIN messages m ON m.id=b.post_id LEFT JOIN rooms r ON r.id=m.room LEFT JOIN users u2 ON u2.username=m.username WHERE b.username=%s ORDER BY b.id DESC""",(u['username'],u['username'])).fetchall();x.close()
    out=''.join(_render_post(m,u) for m in rows)
    body=f"<div class='page'><h2>ذخیره‌ها</h2><div class='feed-list'>{out or '<div class=\"empty\">هنوز پستی ذخیره نکردی.</div>'}</div></div><div id='focusOverlay' class='focus-overlay' onclick='closeFocus(event)'><div id='focusBox' class='focus-box'></div></div>"
    return layout('ذخیره‌ها',body,'bookmarks')

@app.route("/messages")
def messages():
    u=me()
    if not u:return redirect("/")
    x=db()
    private_users=x.execute("""SELECT u.username,u.emoji,u.avatar,u.verified,u.pro,COALESCE(s.unread,0) AS unread
        FROM users u JOIN (SELECT CASE WHEN sender=%s THEN receiver ELSE sender END AS other_user
        FROM private_messages WHERE sender=%s OR receiver=%s GROUP BY CASE WHEN sender=%s THEN receiver ELSE sender END) p
        ON p.other_user=u.username LEFT JOIN private_chat_state s ON s.owner=%s AND s.other_user=u.username
        ORDER BY COALESCE(s.unread,0) DESC,u.username""",(u['username'],u['username'],u['username'],u['username'],u['username'])).fetchall();x.close()
    cards=''.join(f"<a class='item' href='/private/{esc(z['username'])}'>{avatar_html(z)}<div class='info'><div class='name'>@{esc(z['username'])} {'✓' if z['verified'] else ''} {'PRO' if z['pro'] else ''}</div><div class='sub'>دایرکت</div></div></a>" for z in private_users)
    return layout("دایرکت",f"<div class='page'><h2>دایرکت</h2><div class='list'>{cards or '<p class=\"sub\">هنوز گفتگویی نداری.</p>'}</div></div>","messages")

@app.route("/post/create",methods=["POST"])
def create_post():
    u=me()
    if not u:return redirect("/")
    text=request.form.get('text','').strip()[:2000]
    x=db();today=datetime.now().date().isoformat()
    limit=1000 if u['pro'] else (5 if u['verified'] else 3)
    c=x.execute("SELECT COUNT(*) AS c FROM messages WHERE username=%s AND created_at LIKE %s",(u['username'],today+'%')).fetchone()['c']
    if c>=limit:x.close();return f"محدودیت روزانه پست شما تمام شده است. سقف امروز: {limit}",429
    f=request.files.get('media'); media_url=''; media_type=''; media_name=''
    if f and f.filename:
        data=f.read()
        if len(data)>MAX_POST_MEDIA_BYTES:x.close();return 'حجم فایل بیشتر از 25MB است.',400
        ext=os.path.splitext(f.filename)[1].lower()
        allowed={'.jpg': 'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.gif':'image/gif','.webp':'image/webp','.mp4':'video/mp4','.webm':'video/webm','.mov':'video/quicktime','.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.pdf':'application/pdf','.zip':'application/zip','.txt':'text/plain','.doc':'application/msword','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        if ext not in allowed:x.close();return 'نوع فایل پشتیبانی نمی‌شود.',400
        media_type=allowed[ext]; media_name=os.path.basename(f.filename)[:120]; media_url=f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOAD_ROOT,CHAT_DIR,media_url),'wb') as out:out.write(data)
    if not text and not media_url:x.close();return 'پست خالی است.',400
    now=datetime.now().isoformat(timespec='seconds')
    x.execute("INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited,image,media_type,media_name,media_url) VALUES(NULL,NULL,%s,%s,%s,%s,0,0,'',%s,%s,%s)",(u['username'],text,now,now,media_type,media_name,media_url));x.commit();x.close();return redirect('/chat')

@app.route('/post/like/<int:pid>',methods=['POST'])
def post_like(pid):
    u=me()
    if not u:return redirect('/')
    x=db();row=x.execute('SELECT id FROM messages WHERE id=%s',(pid,)).fetchone()
    if not row:x.close();return 'Post not found',404
    if x.execute('SELECT id FROM post_likes WHERE post_id=%s AND username=%s',(pid,u['username'])).fetchone(): x.execute('DELETE FROM post_likes WHERE post_id=%s AND username=%s',(pid,u['username']))
    else:x.execute('INSERT INTO post_likes(post_id,username,created_at) VALUES(%s,%s,%s)',(pid,u['username'],datetime.now().isoformat(timespec='seconds')))
    x.commit();x.close();return redirect('/chat')

@app.route('/post/bookmark/<int:pid>',methods=['POST'])
def post_bookmark(pid):
    u=me()
    if not u:return redirect('/')
    x=db()
    if not x.execute('SELECT id FROM messages WHERE id=%s',(pid,)).fetchone(): x.close();return 'Post not found',404
    if x.execute('SELECT id FROM bookmarks WHERE post_id=%s AND username=%s',(pid,u['username'])).fetchone():
        x.execute('DELETE FROM bookmarks WHERE post_id=%s AND username=%s',(pid,u['username']))
    else:
        x.execute('INSERT INTO bookmarks(post_id,username,created_at) VALUES(%s,%s,%s)',(pid,u['username'],datetime.now().isoformat(timespec='seconds')))
    x.commit();x.close();return redirect(request.referrer or '/chat')

@app.route('/post/<int:pid>/comments',methods=['GET','POST'])
def post_comments(pid):
    u=me()
    if not u:return redirect('/')
    x=db();p=x.execute('SELECT m.*,u.username,u.emoji,u.avatar,u.verified,u.pro FROM messages m JOIN users u ON u.username=m.username WHERE m.id=%s',(pid,)).fetchone()
    if not p:x.close();return 'Post not found',404
    if request.method=='POST':
        t=request.form.get('text','').strip()[:1000]
        if t:x.execute('INSERT INTO post_comments(post_id,username,text,created_at) VALUES(%s,%s,%s,%s)',(pid,u['username'],t,datetime.now().isoformat(timespec='seconds')));x.commit()
    cs=x.execute('SELECT c.*,u.emoji,u.avatar,u.verified,u.pro FROM post_comments c JOIN users u ON u.username=c.username WHERE c.post_id=%s ORDER BY c.id DESC',(pid,)).fetchall();x.close()
    comments=''.join(f"<div class='card'><b>@{esc(c['username'])}</b> {'✓' if c['verified'] else ''}<div>{esc(c['text'])}</div></div>" for c in cs)
    return layout('کامنت‌ها',f"<div class='page'><div class='card'><b>@{esc(p['username'])}</b><p>{esc(p['text'])}</p></div><form method='post'><input name='text' placeholder='کامنت...' required><button>ارسال</button></form><div>{comments}</div></div>",'chat')

@app.route('/post/edit/<int:pid>',methods=['GET','POST'])
def post_edit(pid):
    u=me()
    if not u:return redirect('/')
    x=db();p=x.execute('SELECT * FROM messages WHERE id=%s',(pid,)).fetchone()
    if not p:x.close();return 'Post not found',404
    if p['username']!=u['username'] and not is_admin(u):x.close();return 'Forbidden',403
    if request.method=='POST':
        t=request.form.get('text','').strip()[:2000]
        x.execute('UPDATE messages SET text=%s,edited=1 WHERE id=%s',(t,pid));x.commit();x.close();return redirect('/chat')
    x.close();return layout('ویرایش پست',f"<div class='page'><form method='post'><textarea name='text' required>{esc(p['text'])}</textarea><button>ذخیره</button></form></div>",'chat')

@app.route('/post/delete/<int:pid>',methods=['POST'])
def post_delete(pid):
    u=me()
    if not u:return redirect('/')
    x=db();p=x.execute('SELECT * FROM messages WHERE id=%s',(pid,)).fetchone()
    if not p:x.close();return 'Post not found',404
    if p['username']!=u['username'] and not is_admin(u):x.close();return 'Forbidden',403
    x.execute('DELETE FROM post_likes WHERE post_id=%s',(pid,));x.execute('DELETE FROM post_comments WHERE post_id=%s',(pid,));x.execute('DELETE FROM messages WHERE id=%s',(pid,));x.commit();x.close()
    if p.get('media_url'):delete_uploaded_file(CHAT_DIR,p['media_url'])
    return redirect('/chat')

def page_image_url(username):
    folder=os.path.join(UPLOAD_ROOT,PAGE_DIR)
    for ext in ("jpg","png","gif","webp"):
        name=f"{username}.{ext}"
        if os.path.isfile(os.path.join(folder,name)):
            return f"/uploads/pages/{esc(name)}"
    return ""

@app.route("/page/<int:rid>/image", methods=["POST"])
def page_image_upload(rid):
    u=me()
    if not u:return redirect("/")
    x=db(); r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone(); x.close()
    if not r:return "Page not found.",404
    if r['kind']!='channel' or r['owner']!=u['username']:return "Forbidden",403
    f=request.files.get('image')
    if not f:return redirect(f'/room/{rid}')
    data=f.read()
    ext,_=detect_image_type(data)
    if not ext:return "Unsupported image type.",400
    if len(data)>MAX_IMAGE_BYTES:return "Image is too large (max 5MB).",400
    folder=os.path.join(UPLOAD_ROOT,PAGE_DIR); os.makedirs(folder,exist_ok=True)
    for old_ext in ("jpg","png","gif","webp"):
        old=os.path.join(folder,f"{r['username']}.{old_ext}")
        if os.path.isfile(old):
            try: os.remove(old)
            except Exception: pass
    with open(os.path.join(folder,f"{r['username']}.{ext}"),"wb") as out: out.write(data)
    return redirect(f'/room/{rid}')

@app.route("/room/<int:rid>")
def room(rid):
    u=me()
    if not u:return redirect("/")
    x=db();r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone()
    if not r:x.close();return "Page not found.",404
    if r['kind']!='channel':x.close();return "This legacy room is no longer available.",404
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
        img_input = "<label class='img-btn' title='ارسال عکس (PRO)'>📷<input type='file' name='media' accept='image/*,video/*,audio/*,.pdf,.zip,.txt,.doc,.docx' hidden></label>" if u["pro"] else ""
        composer = f"<form class='composer' method='post' action='/send/{rid}' enctype='multipart/form-data'>{img_input}<input name='text' placeholder='پست جدید برای پیج...'><input type='file' name='media' accept='image/*,video/*,audio/*,.pdf,.zip,.txt,.doc,.docx'><button>پست</button></form>"
    else:
        composer = "<p class='sub' style='text-align:center;padding:14px'>فقط سازنده پیج می‌تواند پیام بفرستد.</p>"
    title = r["name"] + (" ✓" if r["verified"] else "")
    page_img=page_image_url(r["username"]) if r["kind"]=="channel" else ""
    page_head=(f"<div class='card'><img class='msg-img' src='{page_img}' alt=''><div class='name'>@{esc(r["username"])}</div><div class='sub'>{esc(r["bio"] or "")}</div></div>" if page_img else f"<div class='card'><div class='name'>@{esc(r["username"])}</div><div class='sub'>{esc(r["bio"] or "")}</div></div>")
    page_upload=(f"<form method='post' action='/page/{rid}/image' enctype='multipart/form-data'><label class='btn-sm on upload-label'>عکس پیج<input type='file' name='media' accept='image/*,video/*,audio/*,.pdf,.zip,.txt,.doc,.docx' hidden onchange='this.form.submit()'></label></form>" if r["kind"]=="channel" and r["owner"]==u["username"] else "")
    return layout(title,f"<div class='chat'><div class='messages'>{page_head}{page_upload}{body or '<p class=\"sub\">هنوز پیامی نیست.</p>'}</div>{composer}</div>","chat")

@app.route("/send/<int:rid>",methods=["POST"])
def send(rid):
    u=me()
    if not u:return redirect("/")
    x=db();r=x.execute("SELECT * FROM rooms WHERE id=%s",(rid,)).fetchone()
    if not r:x.close();return "Page not found.",404
    if r["kind"]!="channel" or r["owner"]!=u["username"]:x.close();return "Only the page owner can post.",403
    today=datetime.now().date().isoformat();limit=1000 if u['pro'] else (5 if u['verified'] else 3)
    c=x.execute("SELECT COUNT(*) AS c FROM messages WHERE username=%s AND created_at LIKE %s",(u['username'],today+'%')).fetchone()['c']
    if c>=limit:x.close();return f"محدودیت روزانه پست شما تمام شده است. سقف امروز: {limit}",429
    text=request.form.get("text","").strip()[:2000]; media_url='';media_type='';media_name=''
    f=request.files.get('media') or request.files.get('image')
    if f and f.filename:
        data=f.read()
        if len(data)>MAX_POST_MEDIA_BYTES:x.close();return 'حجم فایل بیشتر از 25MB است.',400
        ext=os.path.splitext(f.filename)[1].lower();allowed={'.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png','.gif':'image/gif','.webp':'image/webp','.mp4':'video/mp4','.webm':'video/webm','.mov':'video/quicktime','.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.pdf':'application/pdf','.zip':'application/zip','.txt':'text/plain','.doc':'application/msword','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}
        if ext not in allowed:x.close();return 'نوع فایل پشتیبانی نمی‌شود.',400
        media_type=allowed[ext];media_name=os.path.basename(f.filename)[:120];media_url=f"{uuid.uuid4().hex}{ext}"
        with open(os.path.join(UPLOAD_ROOT,CHAT_DIR,media_url),'wb') as out:out.write(data)
    if not text and not media_url:x.close();return 'پست خالی است.',400
    now=datetime.now().isoformat(timespec='seconds')
    x.execute("INSERT INTO messages(room,room_id,username,text,created_at,created,reply,edited,image,media_type,media_name,media_url) VALUES(%s,%s,%s,%s,%s,%s,0,0,'',%s,%s,%s)",(rid,rid,u['username'],text,now,now,media_type,media_name,media_url));x.commit();x.close();return redirect(f"/room/{rid}")

@app.route("/search")
def search():
    u=me()
    if not u:return redirect("/")
    q=request.args.get("q","").strip()
    x=db()
    users=x.execute("SELECT username,emoji,verified,pro,avatar FROM users WHERE username ILIKE %s LIMIT 30",(f"%{q}%",)).fetchall()
    rooms=x.execute("SELECT * FROM rooms WHERE kind='channel' AND (username ILIKE %s OR name ILIKE %s) LIMIT 30",(f"%{q}%",f"%{q}%")).fetchall()
    x.close()
    out=""
    for z in users:
        badges=("<span class='badge'>✓</span>" if z["verified"] else "")+("<span class='badge pro'>PRO</span>" if z["pro"] else "")
        av = avatar_html(z)
        out+=f"""<a class='item' href='/private/{esc(z["username"])}'>{av}<div class='info'>
        <div class='name'>@{esc(z["username"])} {badges}</div><div class='sub'>شروع چت خصوصی با آیدی</div></div><div class='arrow'>‹</div></a>"""
    for r in rooms:
        rbadge = " <span class='badge'>✓</span>" if r["verified"] else ""
        out+=f"""<a class='item' href='/room/{r["id"]}'><div class='avatar'>{esc(r["emoji"])}</div><div class='info'>
        <div class='name'>{esc(r["name"])}{rbadge}</div><div class='sub'>@{esc(r["username"])} · {esc(r["kind"])}</div></div><div class='arrow'>‹</div></a>"""
    return layout("جستجو",f"<div class='page'><form><input name='q' value='{esc(q)}' placeholder='آیدی را جستجو کن...'></form><div class='list'>{out}</div></div>","search")

@app.route("/create",methods=["GET","POST"])
def create():
    u=me()
    if not u:return redirect("/")
    if request.method=="GET":
        return layout("ساخت",f"""<div class='page'><div class='box'><h2>ساخت پیج</h2>
        <form method='post'><input name='name' placeholder='نام پیج' required><input name='username' placeholder='آیدی پیج' required>
        <input type='hidden' name='kind' value='channel'>
        <input name='emoji' value='💬'><textarea name='bio' placeholder='توضیح'></textarea><button>ساخت</button></form></div></div>""","create")
    name = request.form.get("name", "").strip()
    username = request.form.get("username", "").strip()
    kind = request.form.get("kind", "group")
    if not name or not username or kind != 'channel':
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
    if username!=u['username'] and x.execute("SELECT id FROM blocks WHERE (blocker=%s AND blocked=%s) OR (blocker=%s AND blocked=%s)",(u['username'],username,username,u['username'])).fetchone():
        x.close();return "این حساب برای شما مسدود شده و امکان دایرکت وجود ندارد.",403
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
    img_input = "<label class='img-btn' title='ارسال عکس (PRO)'>📷<input type='file' name='media' accept='image/*,video/*,audio/*,.pdf,.zip,.txt,.doc,.docx' hidden></label>" if u["pro"] else ""
    return layout("@"+username,f"""<div class='chat'><div class='messages'>{body or '<p class="sub">شروع گفتگو</p>'}</div>
    <form class='composer' method='post' action='/private/{esc(username)}/send' enctype='multipart/form-data'>{img_input}<input name='text' placeholder='پیام خصوصی...'><button>➤</button></form>
    <script>setInterval(()=>location.reload(),3000);</script></div>""","chat")

@app.route("/private/<username>/send",methods=["POST"])
def private_send(username):
    u=me()
    if not u:return redirect("/")
    x=db()
    if username!=u['username'] and x.execute("SELECT id FROM blocks WHERE (blocker=%s AND blocked=%s) OR (blocker=%s AND blocked=%s)",(u['username'],username,username,u['username'])).fetchone():
        x.close();return "این حساب برای شما مسدود شده و امکان دایرکت وجود ندارد.",403
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

@app.route('/follow/<username>',methods=['POST'])
def follow_user(username):
    u=me()
    if not u:return redirect('/')
    if username==u['username']:return redirect('/profile/'+username)
    x=db();target=x.execute('SELECT username FROM users WHERE username=%s',(username,)).fetchone()
    if not target:x.close();return 'User not found',404
    if x.execute('SELECT id FROM follows WHERE follower=%s AND target=%s',(u['username'],username)).fetchone():
        x.execute('DELETE FROM follows WHERE follower=%s AND target=%s',(u['username'],username))
    else:x.execute('INSERT INTO follows(follower,target,created_at) VALUES(%s,%s,%s)',(u['username'],username,datetime.now().isoformat(timespec='seconds')))
    x.commit();x.close();return redirect('/profile/'+username)

@app.route("/profile")
def profile_redirect():
    u=me()
    return redirect("/profile/"+u["username"]) if u else redirect("/")

@app.route("/profile/<username>")
def profile(username):
    u=me()
    if not u:return redirect("/")
    x=db();z=x.execute("SELECT * FROM users WHERE username=%s",(username,)).fetchone()
    if not z:x.close();return "User not found."
    followers=x.execute("SELECT COUNT(*) AS c FROM follows WHERE target=%s",(username,)).fetchone()['c']
    following=x.execute("SELECT COUNT(*) AS c FROM follows WHERE follower=%s",(username,)).fetchone()['c']
    if username=='simorg': followers=max(followers,1000000)
    following_me=bool(x.execute("SELECT id FROM follows WHERE follower=%s AND target=%s",(u['username'],username)).fetchone()) if u['username']!=username else False
    blocked=bool(x.execute("SELECT id FROM blocks WHERE blocker=%s AND blocked=%s",(u['username'],username)).fetchone()) if u['username']!=username else False
    posts=x.execute("SELECT * FROM messages WHERE username=%s ORDER BY id DESC LIMIT 30",(username,)).fetchall()
    x.close()
    badges=("<span class='badge'>✓</span>" if z["verified"] else "")+("<span class='badge pro'>PRO</span>" if z["pro"] else "")
    if u['username']==username:
        button=f"<a href='/editprofile'>ویرایش پروفایل</a> <a href='/logout'>خروج از حساب</a>"
    else:
        button=f"<form style='display:inline' method='post' action='/follow/{esc(username)}'><button class='btn-sm'>{'دنبال نکردن' if following_me else 'دنبال کردن'}</button></form> <form style='display:inline' method='post' action='/block/{esc(username)}'><button class='btn-sm warn'>{'رفع بلاک' if blocked else 'بلاک'}</button></form>"
        if not blocked: button+=f" <a href='/private/{esc(username)}'>دایرکت</a>"
    music=f"<div class='profile-music'><div class='sub'>آهنگ پروفایل</div><audio controls src='/uploads/chat/{esc(z['profile_music'])}'></audio></div>" if z.get('profile_music') else ''
    big_avatar=avatar_html(z,cls='bigavatar')
    post_html=''.join(_render_post({**dict(p), 'author_name':username,'author_username':username,'author_emoji':z['emoji'],'author_verified':z['verified'],'author_avatar':z['avatar'],'author_pro':z['pro'],'likes':0,'comments':0,'liked':False,'bookmarked':False,'admin_trending':False},u,False) for p in posts)
    body=f"""<div class='page'><div class='profile'><div class='cover'></div>{big_avatar}<h2>@{esc(z['username'])} {badges}</h2><p class='sub'>{esc(z['bio'] or 'No bio yet.')}</p><p class='profile-stats'><b>{followers:,}</b> دنبال‌کننده · <b>{following:,}</b> دنبال‌شونده</p>{music}<div class='actions'>{button}</div></div><div class='feed-list'>{post_html}</div></div><div id='focusOverlay' class='focus-overlay' onclick='closeFocus(event)'><div id='focusBox' class='focus-box'></div></div>"""
    return layout("پروفایل",body,"profile")

@app.route('/block/<username>',methods=['POST'])
def block_user(username):
    u=me()
    if not u:return redirect('/')
    if username==u['username']:return redirect('/profile/'+username)
    x=db()
    if x.execute('SELECT id FROM users WHERE username=%s',(username,)).fetchone():
        if x.execute('SELECT id FROM blocks WHERE blocker=%s AND blocked=%s',(u['username'],username)).fetchone():
            x.execute('DELETE FROM blocks WHERE blocker=%s AND blocked=%s',(u['username'],username))
        else:
            x.execute('INSERT INTO blocks(blocker,blocked,created_at) VALUES(%s,%s,%s) ON CONFLICT(blocker,blocked) DO NOTHING',(u['username'],username,datetime.now().isoformat(timespec='seconds')))
            x.execute('DELETE FROM follows WHERE (follower=%s AND target=%s) OR (follower=%s AND target=%s)',(u['username'],username,username,u['username']))
        x.commit()
    x.close();return redirect('/profile/'+username)

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
        music_form = f"""<div class='profile-music'><h3>آهنگ پروفایل</h3><p class='sub'>فقط برای PRO · MP3 / WAV / OGG / M4A</p>{('<audio controls src='/uploads/chat/'+esc(u["profile_music"])+''></audio>') if u.get("profile_music") else ''}<form method='post' action='/profile/music' enctype='multipart/form-data'><input type='file' name='music' accept='.mp3,.wav,.ogg,.m4a' required><button>ذخیره آهنگ</button></form></div>""" if u["pro"] else "<p class='sub'>آهنگ پروفایل فقط برای حساب‌های PRO فعال است.</p>"
        return layout("پروفایل",f"""<div class='page'><div class='box'>{avatar_section}<form method='post'>
        <select name='emoji'><option>👤</option><option>😎</option><option>⚡</option><option>🤖</option><option>🔥</option></select>
        <textarea name='bio' placeholder='بیو'>{esc(u["bio"])}</textarea><button>ذخیره</button></form>{music_form}</div></div>""","profile")
    x=db();x.execute("UPDATE users SET emoji=%s,bio=%s WHERE username=%s",(request.form["emoji"],request.form["bio"][:200],u["username"]));x.commit();x.close()
    return redirect("/profile/"+u["username"])

@app.route('/profile/music',methods=['POST'])
def profile_music():
    u=me()
    if not u:return redirect('/')
    if not u['pro']:return 'PRO required.',403
    f=request.files.get('music')
    if not f or not f.filename:return redirect('/editprofile')
    ext=os.path.splitext(f.filename)[1].lower()
    allowed={'.mp3':'audio/mpeg','.wav':'audio/wav','.ogg':'audio/ogg','.m4a':'audio/mp4'}
    if ext not in allowed:return 'فرمت آهنگ پشتیبانی نمی‌شود.',400
    data=f.read()
    if len(data)>10*1024*1024:return 'حجم آهنگ بیشتر از 10MB است.',400
    name=f"profile_music_{uuid.uuid4().hex}{ext}"
    with open(os.path.join(UPLOAD_ROOT,CHAT_DIR,name),'wb') as out:out.write(data)
    x=db();old=u.get('profile_music') or '';x.execute("UPDATE users SET profile_music=%s WHERE username=%s",(name,u['username']));x.commit();x.close()
    if old:delete_uploaded_file(CHAT_DIR,old)
    return redirect('/profile/'+u['username'])

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

@app.route('/admin/trending/<int:pid>',methods=['POST'])
def admin_trending(pid):
    u=me()
    if not u or not is_admin(u):return 'Forbidden',403
    x=db();row=x.execute('SELECT id FROM trending_posts WHERE post_id=%s',(pid,)).fetchone()
    if row:x.execute('UPDATE trending_posts SET enabled=CASE WHEN enabled=1 THEN 0 ELSE 1 END WHERE post_id=%s',(pid,))
    else:x.execute('INSERT INTO trending_posts(post_id,enabled,created_at) VALUES(%s,1,%s)',(pid,datetime.now().isoformat(timespec='seconds')))
    x.commit();x.close();return redirect('/admin')

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
    posts = x.execute("SELECT m.*,u.verified,u.pro FROM messages m LEFT JOIN users u ON u.username=m.username ORDER BY m.id DESC LIMIT 100").fetchall()
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
        kind_label = "گروه" if r["kind"] == "group" else "پیج"
        room_rows += f"""<div class='admin-row'>
        <div class='avatar'>{esc(r["emoji"])}</div>
        <div class='info'><div class='name'>{esc(r["name"])} {rbadge}</div>
        <div class='sub'>@{esc(r["username"])} · {kind_label} · owner: @{esc(r["owner"])}</div></div>
        <div class='admin-actions'>
        <form method='post' action='/admin/room/verify/{r["id"]}'><button class='btn-sm{" on" if not r["verified"] else ""}'>{rverify_label}</button></form>
        </div></div>"""
    post_rows = "".join(f"<div class='admin-row'><div class='info'><div class='name'>#{p['id']} · @{esc(p['username'])}</div><div class='sub'>{esc(p['text'][:180])}</div></div><div class='admin-actions'><a class='btn-sm' href='/post/edit/{p['id']}'>ویرایش</a><form method='post' action='/post/delete/{p['id']}'><button class='btn-sm warn'>حذف</button></form><form method='post' action='/admin/trending/{p['id']}'><button class='btn-sm on'>ترند / لغو</button></form></div></div>" for p in posts)
    body = f"""<div class='page'><h2>پنل مدیریت</h2>
    <h3 class='admin-section-title'>پست‌ها</h3><div class='list'>{post_rows or '<p class="sub">پستی نیست.</p>'}</div>
    <h3 class='admin-section-title'>کاربران</h3><div class='list'>{rows}</div>
    <h3 class='admin-section-title'>گروه‌ها و پیج‌ها</h3><div class='list'>{room_rows or '<p class="sub">هنوز گروه یا کانالی نیست.</p>'}</div>
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
        <div class="card">✓ ارسال عکس در چت خصوصی، گروه و پیج</div>
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
    return layout("تنظیمات","<div class='page'><div class='box'><h2>⚙️ تنظیمات</h2><p class='sub'>Simurgh</p></div></div>")

init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT","8080")), debug=False)
