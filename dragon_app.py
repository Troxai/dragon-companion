import sys, math, random, ctypes, sqlite3, os, json, threading, urllib.request, time, winsound
from ctypes import wintypes
from datetime import datetime, date
from PyQt6.QtWidgets import QApplication, QWidget, QLineEdit, QSystemTrayIcon, QMenu
from PyQt6.QtCore import Qt, QTimer, QPoint, QPointF, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QPixmap, QIcon, QCursor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(SCRIPT_DIR, "image")
APP_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~/.config")), "DragonCompanion")
os.makedirs(APP_DIR, exist_ok=True)
DB_PATH = os.path.join(APP_DIR, "dragon.db")

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

db = sqlite3.connect(DB_PATH, check_same_thread=False)
db.row_factory = sqlite3.Row
db.executescript("""
    CREATE TABLE IF NOT EXISTS dragon(id INTEGER PRIMARY KEY, stage TEXT DEFAULT 'egg', xp INTEGER DEFAULT 0, level INTEGER DEFAULT 1, mood REAL DEFAULT 0.6, hp REAL DEFAULT 1.0, element TEXT DEFAULT 'fire', name TEXT DEFAULT 'Spyro');
    CREATE TABLE IF NOT EXISTS goals(id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, text TEXT, done INTEGER DEFAULT 0);
    CREATE TABLE IF NOT EXISTS streaks(type TEXT PRIMARY KEY, count INTEGER DEFAULT 0, best INTEGER DEFAULT 0, last_date TEXT);
    CREATE TABLE IF NOT EXISTS achievements(id TEXT PRIMARY KEY, name TEXT, desc TEXT, unlocked_at TEXT);
    CREATE TABLE IF NOT EXISTS daily_stats(date TEXT PRIMARY KEY, focus_min INTEGER DEFAULT 0, pomodoros INTEGER DEFAULT 0, goals_done INTEGER DEFAULT 0);
""")
db.execute("INSERT OR IGNORE INTO dragon(id,stage,xp,level,mood,hp,element,name) VALUES(1,'egg',0,1,0.6,1.0,'fire','Spyro')")
db.commit()

STAGES = ["egg","hatchling","juvenile","adult","ancient","legendary"]
STAGE_XP = {"egg":0,"hatchling":100,"juvenile":350,"adult":800,"ancient":1800,"legendary":4000}
STAGE_W = {"egg":80,"hatchling":100,"juvenile":140,"adult":180,"ancient":220,"legendary":260}
STAGE_NAMES = {"egg":"Trứng","hatchling":"Rồng con","juvenile":"Rồng vị thành niên","adult":"Rồng trưởng thành","ancient":"Rồng cổ đại","legendary":"Rồng huyền thoại"}
STAGE_FILES = {"egg":"trung.png","hatchling":"Rồng-con.png","juvenile":"Rồng-vị-thành-niên.png","adult":"Rồng-trưởng-thành.png","ancient":"Rồng-cổ-đại.png","legendary":"rồng-huyền-thoại.png"}
ELEMENTS = {"fire":"Lửa","ice":"Băng","gold":"Vàng","shadow":"Bóng tối"}
ACHIEVEMENTS = {
    "first_word":"Lời đầu tiên","first_goal":"Mục tiêu đầu","first_evo":"Tiến hoá đầu","pomo_5":"5 Pomodoro","pomo_20":"20 Pomodoro",
    "streak_3":"3 ngày liên tiếp","streak_7":"7 ngày liên tiếp","level_5":"Level 5","level_10":"Level 10","legend":"Huyền thoại"
}

SPRITES = {}
for stage, fname in STAGE_FILES.items():
    path = os.path.join(IMAGE_DIR, fname)
    if os.path.exists(path):
        px = QPixmap(path)
        if px.width() > 0:
            w = STAGE_W[stage]
            ratio = px.height() / px.width()
            SPRITES[stage] = px.scaled(w, int(w * ratio), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)

def get_dragon():
    return dict(db.execute("SELECT * FROM dragon WHERE id=1").fetchone())

def save_dragon(**kw):
    db.execute(f"UPDATE dragon SET {', '.join(f'{k}=?' for k in kw)} WHERE id=1", list(kw.values()))
    db.commit()

def add_xp(n):
    d = get_dragon()
    nx = d["xp"] + n
    cs, ns = d["stage"], d["stage"]
    for s in STAGES:
        if nx >= STAGE_XP[s]: ns = s
    nl = d["level"]
    if ns != cs: nl += 1
    save_dragon(xp=nx, stage=ns, level=nl)
    return ns != cs, ns, nl

def update_mood(delta):
    d = get_dragon()
    save_dragon(mood=max(0.0, min(1.0, d["mood"] + delta)))

def update_streak(stype, ok):
    today = date.today().isoformat()
    row = db.execute("SELECT * FROM streaks WHERE type=?", (stype,)).fetchone()
    if not row:
        db.execute("INSERT INTO streaks(type,count,best,last_date) VALUES(?,0,0,?)", (stype, today))
        row = db.execute("SELECT * FROM streaks WHERE type=?", (stype,)).fetchone()
    r = dict(row)
    ld = r["last_date"]
    if ok:
        if ld == today: pass
        elif ld and (date.today() - date.fromisoformat(ld)).days == 1:
            r["count"] += 1
        else:
            r["count"] = 1
        r["best"] = max(r["count"], r["best"])
        r["last_date"] = today
    else:
        if ld != today: r["count"] = 0; r["last_date"] = today
    db.execute("UPDATE streaks SET count=?, best=?, last_date=? WHERE type=?", (r["count"], r["best"], r["last_date"], stype))
    db.commit()


RESPONSES_PATH = os.path.join(APP_DIR, "responses.json")
def load_custom_responses():
    try:
        with open(RESPONSES_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {}
def save_custom_responses(r):
    with open(RESPONSES_PATH, "w", encoding="utf-8") as f:
        json.dump(r, f, ensure_ascii=False, indent=2)
CUSTOM_RESPONSES = load_custom_responses()

# --- LLM Config ---
LLM_CONFIG_PATH = os.path.join(APP_DIR, "llm_config.json")
def load_llm_config():
    try:
        with open(LLM_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except: return {"provider":"ollama","model":"qwen3:4b","api_key":""}
def save_llm_config(cfg):
    with open(LLM_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)
LLM_CONFIG = load_llm_config()
def play_sound(name):
    try:
        if name == "feed": winsound.Beep(600, 100)
        elif name == "evo": winsound.Beep(1000, 200)
        elif name == "achievement": winsound.Beep(1200, 150)
    except: pass

def speak_tts(text):
    try:
        import pythoncom; pythoncom.CoInitialize()
        import win32com.client
        tts = win32com.client.Dispatch("SAPI.SpVoice")
        voices = tts.GetVoices()
        for i in range(voices.Count):
            v = voices.Item(i)
            desc = v.GetDescription()
            if "Vietnamese" in desc or "linh" in desc.lower() or "VN" in desc:
                tts.Voice = v
                break
        tts.Rate = 0
        tts.Speak(text, 1)
    except: pass

def speak_tts_async(text):
    threading.Thread(target=speak_tts, args=(text,), daemon=True).start()


def unlock_ach(ach_id):
    if db.execute("SELECT id FROM achievements WHERE id=?", (ach_id,)).fetchone(): return
    name = ACHIEVEMENTS.get(ach_id, ach_id)
    db.execute("INSERT INTO achievements(id,name,desc,unlocked_at) VALUES(?,?,?,?)", (ach_id, name, "", datetime.now().isoformat()))
    db.commit()
    return name

def strip_border(hwnd):
    try:
        dwm = ctypes.windll.dwmapi
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(33), ctypes.byref(wintypes.DWORD(1)), ctypes.sizeof(wintypes.DWORD))
        dwm.DwmSetWindowAttribute(wintypes.HWND(hwnd), wintypes.DWORD(34), ctypes.byref(wintypes.DWORD(0)), ctypes.sizeof(wintypes.DWORD))
    except: pass

def get_active_window():
    try:
        import psutil
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd: return "", ""
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0 or length > 256: return "", ""
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        title = buf.value or ""
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if pid.value <= 0: return "", title
        try:
            exe = psutil.Process(pid.value).name().lower()
        except:
            exe = ""
        return exe, title
    except:
        return "", ""

class LLM:
    def __init__(self):
        cfg = LLM_CONFIG
        self.provider = cfg.get("provider", "ollama")
        self.url = cfg.get("url", "http://localhost:11434/api/chat")
        self.model = cfg.get("model", "qwen3:4b")
        self.api_key = cfg.get("api_key", "")

    def ask(self, system_prompt, msg, callback):
        if self.provider == "gemini":
            self._ask_gemini(system_prompt, msg, callback)
        elif self.provider == "ollama":
            self._ask_ollama(system_prompt, msg, callback)
        else:
            callback(None)

    def _ask_ollama(self, sys_pmt, msg, cb):
        def go():
            try:
                data = json.dumps({"model":self.model,"messages":[{"role":"system","content":sys_pmt},{"role":"user","content":msg}],"stream":False,"options":{"temperature":0.8,"num_predict":60}}).encode()
                req = urllib.request.Request(self.url, data=data, headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=8) as r:
                    text = json.loads(r.read())["message"]["content"].strip()
                    cb(text[:250] if text else None)
            except: cb(None)
        threading.Thread(target=go, daemon=True).start()

    def _ask_gemini(self, sys_pmt, msg, cb):
        def go():
            try:
                full_prompt = f"{sys_pmt}\n\nUser: {msg}"
                data = json.dumps({"contents":[{"parts":[{"text":full_prompt}]}]}).encode()
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
                req = urllib.request.Request(url, data=data, headers={"Content-Type":"application/json"})
                with urllib.request.urlopen(req, timeout=10) as r:
                    resp = json.loads(r.read())
                    text = resp["candidates"][0]["content"]["parts"][0]["text"].strip()
                    cb(text[:250] if text else None)
            except: cb(None)
        threading.Thread(target=go, daemon=True).start()

class Dragon:
    def __init__(self):
        self.frame = 0; self.blink_timer = 0; self.blinking = False
        self.speech_text = ""; self.speech_timer = 0; self.sleeping = False; self.evo_flash = 0
        self.hp_bar = 1.0; self.mood_icon = ""
        self.particles = []
        self.breath_phase = random.random() * math.pi * 2
        self.mouse_x = 0; self.mouse_y = 0
        self.hover_alpha = 0
        self.combo = 0; self.combo_timer = 0

    def speak(self, txt):
        self.speech_text = txt; self.speech_timer = 150

    def tick(self):
        self.frame += 1
        if self.evo_flash > 0: self.evo_flash -= 1
        if self.blink_timer > 0: self.blink_timer -= 1
        elif random.random() < 0.02: self.blinking = True; self.blink_timer = 4
        else: self.blinking = False
        if self.speech_timer > 0:
            self.speech_timer -= 1
            if self.speech_timer == 0: self.speech_text = ""
        if self.combo_timer > 0:
            self.combo_timer -= 1
            if self.combo_timer == 0: self.combo = 0
        for i in range(len(self.particles)-1, -1, -1):
            px, py, vx, vy, life, color, size = self.particles[i]
            px += vx; py += vy; life -= 1
            if life <= 0: self.particles.pop(i)
            else: self.particles[i] = (px, py, vx, vy, life, color, size)

    def add_sparkles(self, count=8):
        for _ in range(count):
            self.particles.append((0, random.randint(-30, 10), random.uniform(-1.5, 1.5), random.uniform(-2, -0.5), random.randint(20, 50), "#FFD700", random.uniform(2, 5)))

    def add_hearts(self, count=5):
        for _ in range(count):
            self.particles.append((random.randint(-15, 15), -10, random.uniform(-0.5, 0.5), random.uniform(-2.5, -1), random.randint(25, 55), "#FF4081", random.uniform(3, 6)))

    def add_fire(self, count=6):
        for _ in range(count):
            self.particles.append((random.randint(-10, 10), 15, random.uniform(-1, 1), random.uniform(-2, -0.3), random.randint(15, 35), random.choice(["#FF4500", "#FF6600", "#FFD700"]), random.uniform(3, 7)))

    def draw(self, p, w, h, stage, mood, hp, drag_name=""):
        self.tick()
        self.breath_phase += 0.05
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        px_img = SPRITES.get(stage)
        if px_img is None: return
        cx, cy = w / 2, h * 0.55
        bob = math.sin(self.frame * 0.07) * 2.5 if not self.sleeping else math.sin(self.frame * 0.04) * 1.5
        cy += bob
        breath = 1.0 + math.sin(self.breath_phase) * 0.03
        pw, ph = px_img.width() * breath, px_img.height() * breath
        x, y = int(cx - pw / 2), int(cy - ph / 2)

        if self.sleeping: p.setOpacity(0.6)
        # Draw image with breathing scale
        target = QRectF(x, y, pw, ph)
        source = QRectF(0, 0, px_img.width(), px_img.height())
        p.drawPixmap(target, px_img, source)
        p.setOpacity(1.0)

        # HP bar
        bar_w, bar_h = pw, 4
        bx, by_bar = x, y + ph + 2
        p.setBrush(QBrush(QColor("#333333"))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(QRectF(bx, by_bar, bar_w, bar_h), 2, 2)
        hp_color = QColor("#4CAF50") if hp > 0.5 else QColor("#FF9800") if hp > 0.25 else QColor("#F44336")
        p.setBrush(QBrush(hp_color))
        p.drawRoundedRect(QRectF(bx, by_bar, bar_w * hp, bar_h), 2, 2)

        # Mouse tracking eyes (shift pupils)
        dx = (self.mouse_x - cx) * 0.03; dy = (self.mouse_y - cy) * 0.03
        dx = max(-2, min(2, dx)); dy = max(-2, min(2, dy))

        # Mood icon
        mood_icons = {range(0, 25): "(╥_╥)", range(25, 50): "(｡•́︿•̀｡)", range(50, 75): "(◕‿◕)", range(75, 101): "(ﾉ◕ヮ◕)ﾉ"}
        mi = "(◕‿◕)"
        for r, icon in mood_icons.items():
            if int(mood * 100) in r: mi = icon
        fnt = QFont("Segoe UI", 9); p.setFont(fnt)
        p.setPen(QPen(QColor("#666"), 1))
        p.drawText(QPointF(cx - 22, y - 6), mi)

        # Tooltip on hover
        if self.hover_alpha > 0 and drag_name:
            fnt2 = QFont("Segoe UI", 8); p.setFont(fnt2)
            tip = f"{drag_name}"
            tw = p.fontMetrics().horizontalAdvance(tip)
            tip_bg = QColor("#333333"); tip_bg.setAlpha(int(self.hover_alpha * 200))
            p.setBrush(QBrush(tip_bg)); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(QRectF(cx - tw/2 - 8, y - 20, tw + 16, 18), 6, 6)
            p.setPen(QPen(QColor("#FFF"))); p.drawText(QPointF(cx - tw/2, y - 6), tip)

        # Combo display
        if self.combo >= 3 and self.combo_timer > 0:
            combo_alpha = int(min(255, self.combo_timer * 8))
            combo_color = QColor("#FFD700"); combo_color.setAlpha(combo_alpha)
            fnt3 = QFont("Segoe UI", 14, QFont.Weight.Bold); p.setFont(fnt3)
            p.setPen(QPen(combo_color))
            p.drawText(QPointF(cx - 20, y + ph + 20), f"x{self.combo}!")

        # Particles (sparkles, hearts, fire)
        for px_p, py_p, vx, vy, life, color, size in self.particles:
            alpha = int(255 * (life / 55))
            clr = QColor(color); clr.setAlpha(alpha)
            p.setBrush(QBrush(clr)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(cx + px_p, cy + py_p), size * (life/55), size * (life/55))

        # Evo flash
        if self.evo_flash > 0:
            alpha = int(100 * (self.evo_flash / 60))
            flash = QColor("#FFD700"); flash.setAlpha(alpha)
            p.setBrush(QBrush(flash)); p.setPen(Qt.PenStyle.NoPen)
            p.drawEllipse(QPointF(int(cx), int(cy)), 60, 60)

        if self.speech_text:
            self._draw_bubble(p, w, cx, cy, bob, y)

    def _draw_bubble(self, p, w, cx, cy, bob, dragon_top):
        fnt = QFont("Segoe UI", 10); p.setFont(fnt)
        fm = p.fontMetrics(); mw = min(320, w - 20)
        lines, cur = [], ""
        for word in self.speech_text.split(" "):
            test = cur + (" " if cur else "") + word
            if fm.horizontalAdvance(test) < mw - 24: cur = test
            else:
                if cur: lines.append(cur)
                cur = word
        if cur: lines.append(cur)
        if not lines: lines = [self.speech_text]
        lh = fm.height() + 2
        bw = max(max((fm.horizontalAdvance(l) for l in lines), default=0) + 24, 60)
        bw = min(bw, mw); bh = len(lines) * lh + 20
        bx = cx - bw / 2; by2 = max(5, dragon_top - bh - 4)
        br = QRectF(bx, by2, bw, bh)
        bg = QColor("#FFFFFF"); bg.setAlpha(240)
        p.setBrush(QBrush(bg)); p.setPen(QPen(QColor("#AAAAAA"), 1))
        p.drawRoundedRect(br, 12, 12)
        p.setPen(QPen(QColor("#333333"), 1))
        for i, line in enumerate(lines):
            p.drawText(QPointF(bx + 12, by2 + lh * (i + 1) + 2), line)

class Pet(QWidget):
    def __init__(self):
        super().__init__()
        self.dragon = Dragon(); self.llm = LLM()
        self._drag = False; self._off = QPoint(); self._idle_c = 0; self._last_mp = None
        self._pomo_active = False; self._pomo_sec = 0; self._pomo_timer = None; self._pomo_count = 0
        self._session_start = time.time(); self._last_eye = time.time(); self._burnout_warned = False; self._sleep_warned = False
        self._mood_warned = 0
        self._last_water = time.time(); self._last_posture = time.time()
        self._multitask_count = 0; self._last_multitask_warn = 0
        self._last_app = ""; self._last_switch = time.time(); self._last_title = ""
        d = get_dragon(); self._stage = d["stage"]
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.Tool)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setStyleSheet("background: transparent;")
        pw = STAGE_W.get(self._stage, 80)
        self.resize(max(pw + 60, 280), pw + 110)
        scr = app.primaryScreen().availableGeometry()
        self.move(scr.center().x() - self.width() // 2, scr.center().y() - self.height() // 2)

        self.chat = QLineEdit(self)
        self.chat.setPlaceholderText("Chat với rồng..."); self.chat.setFixedHeight(36)
        self.chat.setStyleSheet("QLineEdit{background:rgba(255,255,255,248);border:1px solid #bbb;border-radius:8px;padding:4px 14px;font-size:14px;color:#333}")
        self.chat.returnPressed.connect(self._send); self.chat.hide()

        self.tray = QSystemTrayIcon(self)
        pm = QPixmap(32,32); pm.fill(Qt.GlobalColor.transparent)
        tp = QPainter(pm); tp.setRenderHint(QPainter.RenderHint.Antialiasing)
        tp.setBrush(QBrush(QColor("#FF6B35"))); tp.setPen(QPen(QColor("#E55A2B"),1))
        tp.drawEllipse(QPointF(16,18), 10.0, 9.0)
        tp.setBrush(QBrush(QColor("#FFF"))); tp.setPen(QPen(QColor("#E55A2B"),0.5))
        tp.drawEllipse(QPointF(11,10), 3.0, 3.5); tp.drawEllipse(QPointF(21,10), 3.0, 3.5)
        tp.setBrush(QBrush(QColor("#222"))); tp.setPen(Qt.PenStyle.NoPen)
        tp.drawEllipse(QPointF(10,9), 1.5, 1.5); tp.drawEllipse(QPointF(20,9), 1.5, 1.5)
        tp.setPen(QPen(QColor("#FF4500"), 2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        tp.drawLine(9,3,5,-2); tp.drawLine(23,3,27,-2); tp.end()
        self.tray.setIcon(QIcon(pm)); self.tray.setToolTip("Dragon Companion")
        m = QMenu()
        m.addAction("Show/Hide").triggered.connect(lambda: self.hide() if self.isVisible() else self.show())
        m.addAction("Feed (+10 XP)").triggered.connect(self._feed)
        self._pomo_action = m.addAction("Start Pomodoro (25m)")
        self._pomo_action.triggered.connect(self._toggle_pomo)
        m.addAction("Goals").triggered.connect(self._show_goals)
        m.addSeparator(); m.addAction("Exit").triggered.connect(app.quit)
        self.tray.setContextMenu(m); self.tray.show()

        self._at = QTimer(self); self._at.timeout.connect(self._anim_tick); self._at.start(33)
        self._it = QTimer(self); self._it.timeout.connect(self._check_idle); self._it.start(15000)

    def _anim_tick(self):
        if self.dragon.hover_alpha > 0 and not self._drag:
            self.dragon.hover_alpha = max(0, self.dragon.hover_alpha - 0.02)
        self.update()
        self._rt = QTimer(self); self._rt.timeout.connect(self._check_reminders); self._rt.start(60000)
        self._tt = QTimer(self); self._tt.timeout.connect(self._track_window); self._tt.start(5000)
        update_streak("daily_login", True)
        self._check_reminders()
        self._evening_review_setup()

    def _evening_review_setup(self):
        self._review_done = False
        self._review_timer = QTimer(self)
        self._review_timer.timeout.connect(self._check_evening)
        self._review_timer.start(300000)

    def _check_evening(self):
        h = datetime.now().hour
        if h >= 21 and not self._review_done:
            self._review_done = True
            goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
            done = sum(1 for g in goals if g["done"])
            total = len(goals)
            if total > 0:
                pct = done * 100 // total
                self.dragon.speak(f"Tối rồi! Hôm nay anh đạt {done}/{total} mục tiêu ({pct}%). Ngày mai cố gắng hơn nhé!")
                if pct >= 80: update_streak("goal_streak", True)
                else: update_streak("goal_streak", False)

    def _check_idle(self):
        if not self.dragon.sleeping:
            self._idle_c += 15
            if self._idle_c > 300: self.dragon.sleeping = True; self._idle_c = 0
        else:
            cp = QCursor.pos()
            if self._last_mp is not None and self._last_mp != cp:
                self.dragon.sleeping = False; self._idle_c = 0
            self._last_mp = cp

    def _check_reminders(self):
        now = time.time(); h = datetime.now().hour
        # Eye rest (every 20 min)
        if now - self._last_eye > 1200:
            self._last_eye = now
            if not self.dragon.sleeping:
                self.dragon.speak("20-20-20! Nhìn xa 20 feet trong 20 giây đi anh!")
        # Burnout (>10h session)
        hours = (now - self._session_start) / 3600
        if hours > 10 and not self._burnout_warned:
            self._burnout_warned = True
            self.dragon.speak(f"Cảnh báo! Anh đã làm việc {int(hours)} tiếng liên tục. Nghỉ ngơi đi!")
        
        if now - self._last_water > 3600:
            self._last_water = now
            if not self.dragon.sleeping:
                self.dragon.speak("Uống miếng nước đi anh! Cơ thể cần nước nè!")
        if now - self._last_posture > 2400:
            self._last_posture = now
            if not self.dragon.sleeping:
                self.dragon.speak("Ngồi thẳng lưng lên nào! Đừng gù đấy!")
        # Sleep guard
        if h >= 23 and not self._sleep_warned:
            self._sleep_warned = True
            self.dragon.speak("Khuya rồi anh ơi! Đi ngủ đi mai còn sức!")
        if h >= 1 and not self.dragon.sleeping:
            self.dragon.sleeping = True
        # HP decay (slower)
        if not self.dragon.sleeping: update_mood(-0.001)
        d = get_dragon()
        now_ts = time.time()
        if d["mood"] < 0.2 and now_ts - self._mood_warned > 600:
            self._mood_warned = now_ts
            self.dragon.speak("Em thấy hơi buồn... anh nói chuyện với em đi!")

    def _track_window(self):
        exe, title = get_active_window()
        if not exe: return
        now = time.time()
        if self._last_app and exe != self._last_app:
            if now - self._last_switch < 30:
                self._multitask_count += 1
                if self._multitask_count >= 5 and now - self._last_multitask_warn > 300:
                    self._last_multitask_warn = now
                    self.dragon.add_fire(5)
                    self.dragon.speak("Anh đang nhảy qua lại giữa các app quá nhanh! Tập trung 1 việc thôi!")
            else:
                self._multitask_count = 0
            self._last_switch = now
        if now - getattr(self, '_drift_checked', 0) > 600 and title and title != getattr(self, '_last_title', ''):
            self._drift_checked = now
            goals = db.execute("SELECT * FROM goals WHERE date=? AND done=0", (date.today().isoformat(),)).fetchall()
            if goals and len(goals) > 0:
                goal_texts = "; ".join([g["text"] for g in goals[:3]])
                d = get_dragon()
                prompt = f"User goals: {goal_texts}. Current window title: '{title}'. Does this window seem related to any goal? Reply ONLY YES or NO."
                self.llm.ask("Reply only YES or NO.", prompt,
                    lambda r: self.dragon.speak(f"Anh bảo '{goal_texts[:40]}...' nhưng đang '{title[:30]}'! Quay lại focus đi!") if r and "NO" in r.upper() and "YES" not in r.upper() else None)
        self._last_app = exe; self._last_title = title

    def _toggle_pomo(self):
        if self._pomo_active:
            self._pomo_active = False
            if self._pomo_timer: self._pomo_timer.stop(); self._pomo_timer = None
            self._pomo_action.setText("Start Pomodoro (25m)")
            self.dragon.speak("Pomodoro đã dừng. Lần sau cố nhé!")
        else:
            self._pomo_active = True; self._pomo_sec = 25 * 60
            self._pomo_action.setText(f"Pomodoro: {self._pomo_sec//60}m left")
            self._pomo_timer = QTimer(self); self._pomo_timer.timeout.connect(self._pomo_tick); self._pomo_timer.start(1000)
            self.dragon.speak("Pomodoro 25 phút bắt đầu! Tập trung nhé anh!")

    def _pomo_tick(self):
        self._pomo_sec -= 1
        self._pomo_action.setText(f"Pomodoro: {self._pomo_sec//60}m left")
        if self._pomo_sec <= 0:
            self._pomo_active = False
            if self._pomo_timer: self._pomo_timer.stop(); self._pomo_timer = None
            self._pomo_action.setText("Start Pomodoro (25m)")
            self._pomo_count += 1; add_xp(5); update_mood(0.08)
            self.dragon.evo_flash = 30
            self.dragon.speak(f"Pomodoro xong! Nghỉ 5 phút đi anh. Tổng: {self._pomo_count} pomo.")
            if self._pomo_count == 5: self._try_unlock("pomo_5")
            if self._pomo_count == 20: self._try_unlock("pomo_20")
        elif self._pomo_sec in (60, 120, 300, 600):
            self.dragon.speak(f"Còn {self._pomo_sec//60} phút nữa! Cố lên!")

    def _feed(self):
        play_sound("feed")
        evolved, ns, nl = add_xp(10)
        update_mood(0.05)
        d = get_dragon()
        self.dragon.add_hearts(6)
        self.dragon.combo += 1; self.dragon.combo_timer = 60
        if evolved:
            self._stage = ns
            pw = STAGE_W.get(ns, 80); self.resize(max(pw + 60, 280), pw + 110)
            self.dragon.evo_flash = 60
            ename = STAGE_NAMES.get(ns, ns)
            play_sound("evo")
            self.dragon.speak(f"TIẾN HOÁ! {ename} - LV.{nl}!")
            self._try_unlock("first_evo")
            if ns == "legendary": self._try_unlock("legend")
            if nl >= 5: self._try_unlock("level_5")
            if nl >= 10: self._try_unlock("level_10")
            # Suggest element
            if nl == 3 and d["element"] == "fire":
                self.dragon.speak("Gợi ý: Anh có vẻ hợp hệ Băng (kỷ luật) hoặc Vàng (mục tiêu lớn). Muốn đổi không?")
        else:
            self.dragon.speak(f"Ngon quá! +10 XP (Tổng: {d['xp']} XP) | Mood: {int(d['mood']*100)}%")

    def _show_goals(self):
        goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
        if not goals:
            self.dragon.speak("Hôm nay chưa có mục tiêu nào. Dùng /goal <text> để thêm!")
        else:
            done = sum(1 for g in goals if g["done"])
            lines = [f"Mục tiêu ({done}/{len(goals)}):"]
            for g in goals:
                st = "[x]" if g["done"] else "[ ]"
                lines.append(f"{st} {g['text']}")
            self.dragon.speak(" | ".join(lines))

    def _try_unlock(self, ach_id):
        name = unlock_ach(ach_id)
        if name:
            play_sound("achievement")
            self.dragon.speak(f"Thành tựu mới: {name}!")

    def _send(self):
        t = self.chat.text().strip(); self.chat.clear(); self.chat.hide()
        if not t: return
        tl = t.lower()
        d = get_dragon()

        if tl.startswith("/goal "):
            goal_text = t[6:].strip()
            db.execute("INSERT INTO goals(date,text) VALUES(?,?)", (date.today().isoformat(), goal_text))
            db.commit(); add_xp(5); update_mood(0.03)
            self.dragon.speak(f"Đã thêm mục tiêu: {goal_text}")
            self._try_unlock("first_goal")
        elif tl.startswith("/name "):
            new_name = t[6:].strip()
            if 1 <= len(new_name) <= 20:
                try: db.execute("ALTER TABLE dragon ADD COLUMN name TEXT DEFAULT 'Spyro'")
                except: pass
                db.execute("UPDATE dragon SET name=?", (new_name,)); db.commit()
                self.dragon.add_sparkles(12)
                self.dragon.speak(f"Đã đổi tên thành {new_name}! Dễ thương quá!")
            else:
                self.dragon.speak("Tên phải từ 1-20 ký tự nhé!")
        elif tl.startswith("/done "):
            try:
                gid = int(t.split()[1])
                db.execute("UPDATE goals SET done=1 WHERE id=?", (gid,))
                db.commit(); add_xp(25); update_mood(0.1)
                self.dragon.speak("Mục tiêu hoàn thành! +25 XP")
            except: self.dragon.speak("Dùng: /done <id>")
        elif tl.startswith("/element "):
            el = t.split()[1].lower()
            if el in ELEMENTS:
                save_dragon(element=el)
                self.dragon.speak(f"Đã đổi sang hệ {ELEMENTS[el]}!")
            else: self.dragon.speak(f"Hệ: {', '.join(ELEMENTS.keys())}")
        elif tl.startswith("/stats"):
            st = db.execute("SELECT * FROM streaks").fetchall()
            ach = db.execute("SELECT COUNT(*) as c FROM achievements").fetchone()["c"]
            self.dragon.speak(f"LV.{d['level']} {STAGE_NAMES.get(self._stage,'?')} | XP:{d['xp']} | Mood:{int(d['mood']*100)}% | Pomos:{self._pomo_count} | Achievements:{ach}")
        elif tl.startswith("/teach "):
            parts = t[7:].split("|", 1)
            if len(parts) == 2:
                keyword = parts[0].strip().lower()
                response = parts[1].strip()
                if keyword and response:
                    CUSTOM_RESPONSES[keyword] = response
                    save_custom_responses(CUSTOM_RESPONSES)
                    self.dragon.add_sparkles(10)
                    self.dragon.speak(f"Dạy xong! Khi anh nói '{keyword}' em sẽ trả lời riêng!")
                else:
                    self.dragon.speak("Dùng: /teach <từ khoá> | <câu trả lời>")
            else:
                self.dragon.speak("Dùng: /teach <từ khoá> | <câu trả lời>")
        elif tl.startswith("/forget "):
            keyword = t[8:].strip().lower()
            if keyword in CUSTOM_RESPONSES:
                del CUSTOM_RESPONSES[keyword]
                save_custom_responses(CUSTOM_RESPONSES)
                self.dragon.speak(f"Đã quên '{keyword}'!")
            else:
                self.dragon.speak(f"Chưa được dạy '{keyword}' mà?")
        elif tl.startswith("/list"):
            if CUSTOM_RESPONSES:
                keys = list(CUSTOM_RESPONSES.keys())[:10]
                self.dragon.speak(f"Em biết {len(CUSTOM_RESPONSES)} câu: {', '.join(keys)}")
            else:
                self.dragon.speak("Em chưa được dạy gì! Dùng /teach <keyword> | <response> nha!")
        elif tl.startswith("/llm "):
            parts = t[5:].strip().split()
            if len(parts) >= 1:
                LLM_CONFIG["provider"] = parts[0]
                if len(parts) >= 2: LLM_CONFIG["model"] = parts[1]
                if len(parts) >= 3: LLM_CONFIG["api_key"] = parts[2]
                save_llm_config(LLM_CONFIG)
                self.llm.provider = LLM_CONFIG["provider"]
                self.llm.model = LLM_CONFIG["model"]
                self.llm.api_key = LLM_CONFIG.get("api_key", "")
                self.dragon.add_sparkles(8)
                self.dragon.speak(f"Đã chuyển sang {LLM_CONFIG['provider']} - {LLM_CONFIG['model']}!")
            else:
                self.dragon.speak("Dùng: /llm <gemini|ollama> <model> <api_key>")
        elif any(w in tl for w in ["hello","chào","hi"]):
            self.dragon.speak("Chào anh! Hôm nay anh muốn làm gì nào?")
            self.dragon.add_sparkles(5); add_xp(1)
        elif any(w in tl for w in ["focus","tập trung"]):
            self.dragon.speak("Có em canh chừng rồi, anh cứ tập trung đi!")
            self.dragon.add_sparkles(3); add_xp(2)
        elif any(w in tl for w in ["ngủ","sleep"]):
            self.dragon.sleeping = True; self.dragon.speak("Zzz... em ngủ đây!")
        elif any(w in tl for w in ["pomo"]):
            self._toggle_pomo()
        else:
            # Check custom taught responses first
            for keyword, response in CUSTOM_RESPONSES.items():
                if keyword in tl:
                    self.dragon.speak(response)
                    add_xp(1); update_mood(0.01)
                    return
            # Try LLM with rich context
            self.dragon.speak("Để em nghĩ...")
            d = get_dragon()
            h = datetime.now().hour
            time_ctx = "sáng sớm" if h < 8 else "buổi sáng" if h < 12 else "buổi trưa" if h < 14 else "buổi chiều" if h < 18 else "buổi tối" if h < 22 else "đêm khuya"
            goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
            goal_text = ", ".join([g["text"] for g in goals]) if goals else "chưa có mục tiêu"
            try:
                idx = STAGES.index(self._stage)
                xp_next = STAGE_XP[STAGES[idx + 1]] if idx < len(STAGES) - 1 else "MAX"
            except: xp_next = "?"
            sys_pmt = (
                f"Bạn là {d.get('name','Spyro')}, một chú rồng {STAGE_NAMES.get(self._stage,'?')} LV.{d['level']} hệ {ELEMENTS.get(d['element'],'Lửa')}. "
                f"Tính cách: hài hước, láu cá, nói nhanh gọn (1-2 câu), thân mật kiểu bạn bè. Bạn đang ở cùng chủ nhân vào {time_ctx}. "
                f"Mood của bạn: {int(d['mood']*100)}%. Mục tiêu hôm nay: {goal_text}. "
                f"Trả lời bằng tiếng Việt tự nhiên, đúng chất rồng, ngắn gọn."
            )
            self.llm.ask(sys_pmt, t, lambda r: self.dragon.speak(r[:250]) if r else self._smart_reply(t))
            add_xp(1); update_mood(0.01)

    def _smart_reply(self, msg):
        d = get_dragon()
        tl = msg.lower()
        h = datetime.now().hour
        try:
            idx = STAGES.index(self._stage)
            xp_next = STAGE_XP[STAGES[idx + 1]] if idx < len(STAGES) - 1 else "MAX"
        except: xp_next = "?"

        # Time-aware morning greeting
        if any(w in tl for w in ["sáng","morning","chào buổi sáng","good morning"]):
            goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
            if not goals:
                return self.dragon.speak(f"Chào buổi sáng anh! Hôm nay anh định làm gì? /goal <mục tiêu> để em theo dõi cho!")
            else:
                return self.dragon.speak(f"Chào buổi sáng! Hôm nay có {len(goals)} mục tiêu, mình cùng cố gắng nhé!")

        # Time-aware evening
        if h >= 20 and any(w in tl for w in ["tối","night","ngủ","ngon"]):
            goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
            done = sum(1 for g in goals if g["done"])
            total = len(goals)
            if total > 0:
                return self.dragon.speak(f"Chúc anh ngủ ngon! Hôm nay {done}/{total} mục tiêu {'- xuất sắc!' if done==total else '- mai cố gắng thêm nhé!'}")
            return self.dragon.speak("Chúc anh ngủ ngon! Mai mình lại chiến đấu tiếp!")

        # Sad/mood check
        if any(w in tl for w in ["buồn","sad","chán","mệt mỏi"]):
            return self.dragon.speak(f"Em hiểu mà. Đi uống miếng nước, hít thở sâu 3 lần đi anh. Rồi mình quay lại chiến sau! Bây giờ mood em đang {int(d['mood']*100)}%, anh làm em vui lên tí đi!")

        # Happy
        if any(w in tl for w in ["vui","happy","tuyệt","thích","yêu"]):
            self.dragon.add_hearts(8)
            return self.dragon.speak("Em cũng vui quá! Yêu anh nhất luôn! (ﾉ◕ヮ◕)ﾉ*:･ﾟ✧")

        # Ask about goals
        if any(w in tl for w in ["mục tiêu","goal","kế hoạch","plan","làm gì"]):
            goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
            if not goals:
                return self.dragon.speak("Hôm nay chưa có mục tiêu nào! Gõ /goal <việc cần làm> để em theo dõi cho anh nhé!")
            lines = [f"Mục tiêu hôm nay ({sum(1 for g in goals if g['done'])}/{len(goals)}):"]
            for i, g in enumerate(goals):
                st = "[x]" if g["done"] else "[ ]"
                lines.append(f"{st} {i+1}. {g['text']}")
            return self.dragon.speak(" | ".join(lines))

        # Motivate
        if any(w in tl for w in ["động viên","motivate","cố lên","khó","nản"]):
            quotes = [
                f"Anh làm được mà! Nhìn em nè - từ quả trứng lên {STAGE_NAMES.get(self._stage,'?')} LV.{d['level']} luôn!",
                "Mỗi lần anh focus 25 phút là em được XP đó. Cùng tiến bộ nha!",
                f"Người ta nói rồng {STAGE_NAMES.get(self._stage,'?')} chỉ ở cạnh người chăm chỉ thôi đó!",
                "Thất bại là mẹ thành công. Quan trọng là đứng dậy đi tiếp!",
            ]
            return self.dragon.speak(random.choice(quotes))

        # Ask about dragon
        if any(w in tl for w in ["ai","tên","mày","rồng","dragon","spyro","là gì"]):
            return self.dragon.speak(f"Em là {d.get('name','Spyro')}, {STAGE_NAMES.get(self._stage,'?')} LV.{d['level']} hệ {ELEMENTS.get(d['element'],'Lửa')}. Em sống để canh chừng anh làm việc!")

        # Help
        if any(w in tl for w in ["help","giúp","lệnh","command","hướng dẫn"]):
            return self.dragon.speak("Lệnh: /goal <text> thêm mục tiêu | /done <id> hoàn thành | /stats xem thống kê | /name <tên> đổi tên | /element <hệ> đổi hệ. Chat thường thì em trả lời!")

        # Default smart response
        reply_pool = [
            f"Em đây! {d.get('name','Spyro')} - {STAGE_NAMES.get(self._stage,'?')} LV.{d['level']} | XP: {d['xp']}/{xp_next} | Mood: {int(d['mood']*100)}%",
            f"Anh gọi em à? Hôm nay anh focus được bao nhiêu phút rồi?",
            "Em đang nghe đây! Kể em nghe anh đang làm gì đi!",
        ]
        if h >= 22:
            reply_pool.append("Khuya rồi anh ơi! Mai mình làm tiếp được không?")
        if self._stage == "egg":
            reply_pool.append("Em vẫn còn là trứng... anh feed em để em nở nha!")
        self.dragon.speak(random.choice(reply_pool))

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = True; self._off = e.pos()
            if self.dragon.sleeping: self.dragon.sleeping = False; self._idle_c = 0
        elif e.button() == Qt.MouseButton.RightButton:
            self._show_context_menu(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._drag: self.move(self.mapToParent(e.pos()) - self._off)
        self.dragon.mouse_x = e.pos().x(); self.dragon.mouse_y = e.pos().y()
        self.dragon.hover_alpha = 1.0

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = False
            if (e.pos() - self._off).manhattanLength() < 5:
                self.dragon.combo += 1; self.dragon.combo_timer = 45
                if self.dragon.combo == 5: self.dragon.speak("Combo x5! Anh đang vui mà!")
                if self.dragon.combo == 10: self.dragon.speak("Combo x10!! Đỉnh quá!")
                self.dragon.add_sparkles(3)
                if self.chat.isVisible(): self.chat.hide()
                else: self.chat.setFixedWidth(self.width() - 16); self.chat.move(8, 5); self.chat.show(); self.chat.setFocus()

    def contextMenuEvent(self, e):
        self._show_context_menu(e.globalPos())

    def _show_context_menu(self, pos):
        d = get_dragon()
        m = QMenu(self)
        m.addAction(f"Feed (+10 XP) [XP: {d['xp']}]").triggered.connect(self._feed)
        m.addAction("Add Goal").triggered.connect(lambda: (self.chat.setText("/goal "), self.chat.setFixedWidth(self.width()-16), self.chat.move(8,5), self.chat.show(), self.chat.setFocus()))
        pomo_text = "Stop Pomodoro" if self._pomo_active else "Start Pomodoro (25m)"
        m.addAction(pomo_text).triggered.connect(self._toggle_pomo)
        m.addAction("Show Goals").triggered.connect(self._show_goals)
        m.addAction("Stats").triggered.connect(lambda: self.dragon.speak(f"LV.{d['level']} {STAGE_NAMES.get(self._stage,'?')} | {d['xp']} XP | {self._pomo_count} pomos"))
        m.addSeparator()
        m.addAction("Weekly Letter").triggered.connect(self._weekly_letter)
        m.addAction("Hide 30m").triggered.connect(lambda: (self.hide(), QTimer.singleShot(1800000, self.show)))
        m.addAction("Exit").triggered.connect(app.quit)
        m.exec(pos)

    def _weekly_letter(self):
        d = get_dragon()
        week_ago = (date.today() - timedelta(days=7)).isoformat()
        goals = db.execute("SELECT * FROM goals WHERE date >= ?", (week_ago,)).fetchall()
        total_goals = len(goals); done_goals = sum(1 for g in goals if g["done"])
        streaks = dict(db.execute("SELECT type, best FROM streaks").fetchall())
        ach_count = db.execute("SELECT COUNT(*) as c FROM achievements").fetchone()["c"]
        letter = (
            f"Tuần này anh đã hoàn thành {done_goals}/{total_goals} mục tiêu. "
            f"Streak dài nhất: {streaks.get('goal_streak',0)} ngày. "
            f"Achievements: {ach_count}. "
            f"Rồng đang ở {STAGE_NAMES.get(self._stage,'?')} LV.{d['level']} với {d['xp']} XP. "
            f"Cố gắng tuần sau nhé!"
        )
        self.dragon.speak(letter)
        speak_tts_async(letter)

    def paintEvent(self, e):
        p = QPainter(self)
        d = get_dragon()
        if d["stage"] != self._stage:
            old = self._stage
            self._stage = d["stage"]
            pw = STAGE_W.get(self._stage, 80)
            self.resize(max(pw + 60, 280), pw + 110)
            self.dragon.evo_flash = 60
            play_sound("evo")
            self._try_unlock("first_evo")
            if self._stage == "legendary": self._try_unlock("legend")
            if d["level"] >= 5: self._try_unlock("level_5")
            if d["level"] >= 10: self._try_unlock("level_10")
        self.dragon.draw(p, self.width(), self.height(), self._stage, d["mood"], d["hp"], d.get("name", ""))
        p.end()

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, lambda: strip_border(int(self.winId())))

pet = Pet()
pet.show()
d = get_dragon()
sn = STAGE_NAMES.get(d["stage"], "?")
# Morning ritual
h = datetime.now().hour
if h < 12:
    goals = db.execute("SELECT * FROM goals WHERE date=?", (date.today().isoformat(),)).fetchall()
    if not goals:
        pet.dragon.speak(f"Chào buổi sáng anh! Hôm nay anh định làm gì? /goal <mục tiêu> để em theo dõi cho nha!")
    else:
        pet.dragon.speak(f"Chào buổi sáng! Hôm nay có {len(goals)} mục tiêu: {', '.join([g['text'] for g in goals[:2]])}. Cùng chiến nào!")
else:
    pet.dragon.speak(f"Chào anh! Em là {sn} LV.{d['level']}. Hôm nay anh muốn làm gì? /goal <mục tiêu> để bắt đầu nhé!")
app.exec()
