import telebot
from telebot import types
import requests
import json
import time
import logging
import os
import re
import unicodedata
import html
import threading

# ==========================================
# ⚙️ الإعدادات
# ==========================================
BOT_TOKEN = "9257044358:AAF0j2NBcuEZbaAQHMZp4byPZw5wF6WAW0g"
BOT_USERNAME = "@QureoAssistantBot"
OWNER_ID = 7778015097
OWNER_USERNAME = f'<a href="tg://user?id={OWNER_ID}">المالك</a>'
OWNER_LINK = f"tg://user?id={OWNER_ID}"  # رابط التوجيه للشراء

CHANNEL_USERNAME = "@mr0xz404"

BASE = "https://egy.app.spx-learning-square.com"
SUBJECT = 7
QUREO_BASE = "https://me-tp.qureo.education"
QUREO_PORTAL = "https://me-portal.qureo.education"

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
USERS = {}

# ==========================================
# 💾 حفظ وتحميل المستخدمين والإحصائيات والفرص والحظر
# ==========================================
USERS_FILE = "users_db.json"

def load_db():
    try:
        if os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f: 
                data = json.load(f)
                if "users" not in data: data["users"] = []
                if "success" not in data: data["success"] = 0
                if "failed" not in data: data["failed"] = 0
                if "credits" not in data: data["credits"] = {}
                if "banned" not in data: data["banned"] = {}
                return data
    except: pass
    return {"users": [], "success": 0, "failed": 0, "credits": {}, "banned": {}}

def save_db(data):
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f: 
            json.dump(data, f, ensure_ascii=False, indent=2)
    except: pass

DB = load_db()

# ==========================================
# 🛡️ التحقق من الاشتراك
# ==========================================
def check_subscription(user_id):
    try:
        member = bot.get_chat_member(CHANNEL_USERNAME, user_id)
        if member.status in ['creator', 'administrator', 'member']:
            return True
    except Exception as e:
        print(f"Sub Check Error: {e}")
    return False

def send_subscribe_msg(cid):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("📢 اشترك في القناة", url="https://t.me/mr0xz404"))
    markup.add(types.InlineKeyboardButton("✅ تحقق من الاشتراك", callback_data="check_sub"))
    try:
        bot.send_message(cid, "⚠️ <b>عذراً عزيزي،</b>\n\nللاستفادة من البوت، يجب عليك الاشتراك في قناتنا أولاً.\n\n👇 اضغط على اشترك ثم تحقق:", reply_markup=markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending subscribe msg: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "check_sub")
def callback_check_sub(call):
    cid = call.message.chat.id
    if check_subscription(cid):
        bot.answer_callback_query(call.id, "✅ تم التحقق بنجاح!")
        bot.delete_message(cid, call.message.message_id)
        cmd_start(call.message)
    else:
        bot.answer_callback_query(call.id, "❌ أنت لم تشترك في القناة بعد!", show_alert=True)

# ==========================================
# 🧹 دوال المطابقة (SPX)
# ==========================================
def canon(t):
    if not t: return ""
    t = html.unescape(str(t))
    t = re.sub(r'\[\[.*?\]\]', '', t)
    return re.sub(r'\s+', ' ', unicodedata.normalize('NFKC', t)).strip()

def norm(t):
    return canon(t).replace(' ', '').replace('"', '').replace("'", '').replace('`', '').lower()

def find_spx_answer(question_text):
    q_clean = canon(question_text)
    if 'levels' in STUDY_DATA:
        for lvl in STUDY_DATA['levels'].values():
            for q in lvl.get('questions', []):
                if canon(q.get('question', '')) == q_clean: return q.get('answer', '')
    for level, qs in ANSWERS_LEVEL.items():
        if isinstance(qs, list):
            for item in qs:
                if isinstance(item, dict) and item.get('answer'):
                    if len(q_clean) > 20 and canon(item['answer'])[:30] in q_clean: return item['answer']
    return None

def match_option(options, answer_text, is_spx=True):
    if not answer_text: return None
    ans_clean = norm(answer_text)
    for opt in options:
        txt = opt.get('text', '') if is_spx else opt.get('content', '')
        if norm(txt) == ans_clean: return opt['id']
    for opt in options:
        txt = opt.get('text', '') if is_spx else opt.get('content', '')
        if ans_clean in norm(txt): return opt['id']
    return None

# ==========================================
# 📂 تحميل الملفات
# ==========================================
def load_json(path):
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f: return json.load(f)
    except Exception: pass
    return {}

STUDY_DATA = load_json("study_data.json")
ANSWERS_LEVEL = load_json("answers_by_level.json")

# ==========================================
# 🤖 محرك SPX (الثقافة المالية)
# ==========================================
class SPXSolver:
    def __init__(self, login_id, password):
        self.login_id = login_id
        self.password = password
        self.s = requests.Session()
        self.s.headers.update({
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": BASE,
            "referer": f"{BASE}/subjects/{SUBJECT}/curriculum",
            "user-agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 Chrome/139.0.0.0 Mobile Safari/537.36",
        })
        self.token = None

    def _req(self, method, path, **kw):
        url = path if path.startswith("http") else f"{BASE}{path}"
        try: return self.s.request(method, url, timeout=10, **kw)
        except Exception: return None

    def _get(self, path):
        r = self._req("GET", path)
        if r and r.status_code == 200:
            try: return r.json()
            except: return None
        return None

    def _post(self, path, payload=None): return self._req("POST", path, json=payload or {})
    def _put(self, path, payload=None): return self._req("PUT", path, json=payload or {})

    def login(self):
        r = self._post("/api/v1/auth/login", {"login_id": self.login_id, "password": self.password})
        if not r or r.status_code != 200: return False
        try: body = r.json()
        except: return False
        self.token = body.get("token") or (body.get("data") or {}).get("token")
        if not self.token:
            for c in self.s.cookies:
                if c.name == "learning_token":
                    self.token = c.value
                    break
        if not self.token: return False
        self.s.headers["authorization"] = f"Bearer {self.token}"
        return True

    def find_next(self):
        cur = self._get(f"/api/v1/subjects/{SUBJECT}/curriculum")
        if not cur or 'data' not in cur: return None, 0, 0
        total, completed, next_item = 0, 0, None
        for unit in cur['data']:
            for item in unit.get('items', []):
                total += 1
                if item.get('is_completed'): completed += 1
                elif not next_item: next_item = item
        return ("DONE", completed, total) if not next_item else (next_item, completed, total)

    def solve_chapter(self, chapter_id):
        d = self._get(f"/api/v1/chapters/{chapter_id}/blocks")
        if not d or 'data' not in d: return {"ok": False, "total": 0, "solved": 0}
        blocks = d['data'].get('blocks', [])
        cleared = set(d['data'].get('chapter', {}).get('cleared_block_ids', []))
        questions = [b for b in blocks if b.get('type') == 'question']
        
        solved = 0
        for q in questions:
            if q['id'] in cleared:
                solved += 1; continue
            for opt in q.get('options', []):
                r = self._post(f"/api/v1/chapters/{chapter_id}/answer", {"block_id": q['id'], "selected_option_id": opt['id'], "hint_used": 0})
                if r and r.status_code == 200:
                    try:
                        ans = r.json().get('data', {})
                        if ans.get('is_correct'): solved += 1; break
                        if ans.get('correct_option_id'):
                            self._post(f"/api/v1/chapters/{chapter_id}/answer", {"block_id": q['id'], "selected_option_id": ans['correct_option_id'], "hint_used": 0})
                            solved += 1; break
                    except: pass
        self._post(f"/api/v1/chapters/{chapter_id}/complete")
        return {"ok": True, "solved": solved, "total": len(questions)}

    def solve_review(self, review_id):
        r = self._post(f"/api/v1/reviews/{review_id}/complete")
        return {"ok": r and r.status_code == 200, "solved": 1, "total": 1}

    def solve_test(self, test_id):
        r = self._post(f"/api/v1/tests/{test_id}/start")
        if not r or r.status_code != 200: return {"ok": False, "solved": 0, "total": 0}
        try:
            data = r.json()['data']
            questions_map = data.get('questions', {})
            options_map = data.get('options', {})
            test_questions = data.get('test_questions', [])
        except: return {"ok": False, "solved": 0, "total": 0}
        
        solved = 0
        answers_batch = []
        for tq in test_questions:
            t_id = tq['id']
            q_id = str(tq['question_id'])
            q_text = questions_map.get(q_id, {}).get('question_text', '')
            options = options_map.get(q_id, [])
            if not q_text or not options: continue
            
            ans_text = find_spx_answer(q_text)
            chosen_id = match_option(options, ans_text, True) if ans_text else options[0]['id']
            answers_batch.append((t_id, chosen_id))
            if chosen_id: solved += 1
        
        for t_id, chosen_id in answers_batch:
            self._put(f"/api/v1/tests/{test_id}/questions/{t_id}/answer", {"selected_option_id": chosen_id})
        
        time.sleep(0.5)
        self._post(f"/api/v1/tests/{test_id}/submit")
        time.sleep(1)
        h = self._get(f"/api/v1/tests/{test_id}/history")
        passed, score = False, 0
        if h and 'data' in h:
            for e in h['data']:
                if e.get('status') == 'completed':
                    passed, score = e.get('passed'), e.get('correct_count', 0); break
        return {"ok": passed, "solved": score, "total": len(test_questions)}

# ==========================================
# 🐍 محرك Qureo (بايثون + JavaScript)
# ==========================================
def run_qureo_tool(cid_tg, message_id, STUDENT_ID, PASSWORD, content_id, json_file, platform_name):
    def load_json_tool(p):
        if not os.path.exists(p): return {}
        try:
            with open(p, encoding="utf-8") as f: return json.load(f)
        except: return {}

    max_data = load_json_tool(json_file)
    if not max_data:
        try: bot.edit_message_text(f"❌ ملف {json_file} مش موجود!", cid_tg, message_id)
        except: pass
        return

    try: bot.edit_message_text(f"⏳ جاري تسجيل الدخول لـ {platform_name}...", cid_tg, message_id)
    except: pass

    s = requests.Session()
    s.headers.update({
        "authority": "me-tp.qureo.education",
        "content-type": "application/json",
        "origin": QUREO_BASE,
        "referer": f"{QUREO_BASE}/",
        "user-agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/139.0.0.0 Safari/537.36"
    })
    lh = s.headers.copy()
    lh["origin"] = QUREO_PORTAL
    lh["referer"] = f"{QUREO_PORTAL}/"
    
    r = s.post(f"{QUREO_PORTAL}/oauth2/password-login", json={"student_id": STUDENT_ID, "password": PASSWORD}, headers=lh)
    token = s.cookies.get("egy_student_access_token")
    
    if not token: 
        try: bot.edit_message_text(f"❌ فشل الدخول! رد السيرفر: {r.status_code}.", cid_tg, message_id)
        except: pass
        DB["failed"] += 1
        save_db(DB)
        return
    
    s.headers["authorization"] = f"Bearer {token}"
    s.cookies.set("student_selected_content_id", content_id, domain="me-tp.qureo.education")

    def fix_indentation(code):
        if not code or not isinstance(code, str): return code
        lines = code.split('\n')
        fixed_lines = []
        for line in lines:
            stripped = line.strip()
            if not stripped:
                fixed_lines.append("")
            elif stripped.startswith("//") or stripped.startswith("console.log") or stripped.startswith("let ") or stripped.startswith("if ") or stripped.startswith("for ") or stripped.startswith("function ") or stripped.startswith("while "):
                if not line.startswith("  "):
                    fixed_lines.append("  " + stripped)
                else:
                    fixed_lines.append(line)
            else:
                fixed_lines.append(line)
        return '\n'.join(fixed_lines)

    def check_status(cid):
        s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
        try:
            res = s.get(f"{QUREO_BASE}/api/study/students/chapters/{cid}")
            if res.status_code == 200:
                data = res.json()
                return data.get('best_correct_count', 0), data.get('completed_at') is not None
        except: pass
        return 0, False

    def solve_lectures(cid):
        s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
        try:
            r = s.get(f"{QUREO_BASE}/api/study/chapters/{cid}")
            if r.status_code == 200:
                lectures = r.json().get('lectures', [])
                for lec in lectures:
                    s.put(f"{QUREO_BASE}/api/study/students/lectures/{lec['id']}", json={})
                    s.put(f"{QUREO_BASE}/api/study/students/lectures/{lec['id']}/complete", json={})
        except: pass

    def solve_chapter(cid):
        s.cookies.set("_cf_s_path", f"/contents/chapter/{cid}", domain="me-tp.qureo.education")
        
        best, is_completed = check_status(cid)
        if is_completed and best > 0: return True, best, best
        
        try: r = s.get(f"{QUREO_BASE}/api/study/chapters/{cid}/test")
        except: return False, 0, 0
        
        if r.status_code == 403: return False, 0, -1
        if r.status_code != 200: return False, 0, 0
        
        try: qs_data = r.json()
        except: return False, 0, 0
        
        s.put(f"{QUREO_BASE}/api/study/students/chapters/{cid}/test", json={})
        s.put(f"{QUREO_BASE}/api/study/students/chapters/{cid}/test", json={})
        
        solved = 0
        chapter_answers = max_data.get('chapters', {}).get(str(cid), {}).get('answers', {})
        if not chapter_answers:
            chapter_answers = max_data.get('chapters', {}).get(str(cid), {}).get('questions', {})
        
        for i, q in enumerate(qs_data):
            q_info = q['question']
            q_id = str(q_info['id'])
            q_type = q_info['type']
            
            item = chapter_answers.get(q_id, {})
            if isinstance(item, dict): ans = item.get('answer')
            elif isinstance(item, (tuple, list)): ans = item[1]
            else: ans = item
            
            if ans is None:
                if q_type == 'choice' and q.get('choices'):
                    ans = q['choices'][0]['id']
                else:
                    continue
            
            if q_type == 'description' and isinstance(ans, str):
                if content_id == "javascript_ar":
                    ans = fix_indentation(ans)
                
            if q_type == 'description':
                url = f"{QUREO_BASE}/api/study/students/test-questions/{q_id}/answer/description"
                payload = {"answer_code": str(ans)}
            else:
                url = f"{QUREO_BASE}/api/study/students/test-questions/{q_id}/answer/choice"
                payload = {"choice_id": int(ans)}
            
            res = s.put(url, json=payload)
            
            if res.status_code != 200 and q_type == 'choice' and q.get('choices'):
                for ch in q['choices']:
                    res2 = s.put(url, json={"choice_id": int(ch['id'])})
                    if res2.status_code == 200:
                        res = res2
                        break
            
            if res.status_code in (200, 400):
                solved += 1
            else:
                if q_type == 'description': url_rev = f"{QUREO_BASE}/api/study/students/review-questions/{q_id}/answer/description"
                else: url_rev = f"{QUREO_BASE}/api/study/students/review-questions/{q_id}/answer/choice"
                if s.put(url_rev, json=payload).status_code == 200: solved += 1
                
            time.sleep(0.1)
        
        time.sleep(0.5)
        best, is_completed = check_status(cid)
        if is_completed and best >= len(qs_data): return True, best, len(qs_data)
        return solved == len(qs_data), solved, len(qs_data)

    total_chapters = 54 if content_id == "javascript_ar" else 25
    start_cid = 90001 if content_id == "javascript_ar" else 511001
    
    activities = ["🚀 بدء..."]
    last_update_time = 0
    fail_count = 0
    
    for chap_idx in range(total_chapters):
        if not USERS.get(cid_tg, {}).get('running'): break
        cid = start_cid + chap_idx
        
        if time.time() - last_update_time > 2:
            percent = int(((chap_idx + 1) / total_chapters) * 100)
            progress_bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            status_text = (
                f"⏳ <b>جاري الحل ({platform_name})...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 كود: <code>{STUDENT_ID}</code>\n"
                f"📊 التقدم: <code>[{progress_bar}] {percent}%</code>\n"
                f"🎯 العنصر: <code>فصل {chap_idx + 1} من {total_chapters}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>آخر النشاطات:</b>\n"
            )
            for act in activities[-4:]: status_text += f"• {act}\n"
            try: bot.edit_message_text(status_text, cid_tg, message_id)
            except: pass
            last_update_time = time.time()
        
        solve_lectures(cid)
        ok, solved, total = solve_chapter(cid)
        
        if total == -1: 
            activities.append(f"🔒 فصل {chap_idx + 1} (مقفول)")
            fail_count += 1
        elif total == 0: 
            activities.append(f"⚠️ فصل {chap_idx + 1} (خطأ)")
            fail_count += 1
        elif ok: activities.append(f"✅ فصل {chap_idx + 1} (PERFECT)")
        else: 
            activities.append(f"❌ فصل {chap_idx + 1} ({solved}/{total})")
            fail_count += 1

    if fail_count == total_chapters:
        DB["failed"] += 1
    else:
        DB["success"] += 1
    
    # خصم الفرصة بعد المحاولة (باستثناء الـ VIP)
    user_credit = DB.get("credits", {}).get(str(cid_tg))
    if user_credit != "max":
        if user_credit is not None and isinstance(user_credit, int) and user_credit > 0:
            DB["credits"][str(cid_tg)] -= 1
        elif user_credit is None:
            DB["credits"][str(cid_tg)] = 0

    save_db(DB)

    final_text = (
        f"🎉 <b>تم إنهاء {platform_name}!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 كود: <code>{STUDENT_ID}</code>\n"
        f"📸 <b>أرسل صورة النتيجة لـ</b> {OWNER_USERNAME}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📝 <b>ملخص النشاط:</b>\n"
    )
    for act in activities[-10:]: final_text += f"• {act}\n"
    try: bot.edit_message_text(final_text, cid_tg, message_id)
    except: pass

# ==========================================
# 🧠 محرك SPX (الثالثة) - اللفة الرئيسية
# ==========================================
def run_spx_tool(cid_tg, message_id, login_id, password):
    solver = SPXSolver(login_id, password)
    if not solver.login():
        try: bot.edit_message_text("❌ فشل الدخول للثقافة المالية!", cid_tg, message_id)
        except: pass
        DB["failed"] += 1
        save_db(DB)
        return

    activities = ["🚀 بدء..."]
    last_update_time = 0
    fail_count = 0

    while USERS.get(cid_tg, {}).get('running'):
        item, completed, total = solver.find_next()
        if item == "DONE" or not item: break
        
        item_title = item.get('title', '')
        itype = item.get('item_type')
        item_id = item.get('id')
        
        if itype == "chapter":
            res = solver.solve_chapter(item_id)
        elif itype == "review":
            solver.solve_review(item_id)
            res = {"solved": 1, "total": 1}
        elif itype == "test":
            res = solver.solve_test(item_id)
        else:
            res = {}
        
        activities.append(f"✅ {item_title[:20]}")
        if not res.get('ok', True): fail_count += 1
        
        if time.time() - last_update_time > 2:
            percent = int((completed / total) * 100) if total > 0 else 0
            progress_bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            
            status_text = (
                f"⏳ <b>جاري حل الثقافة المالية...</b>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 كود: <code>{login_id}</code>\n"
                f"📊 التقدم: <code>[{progress_bar}] {percent}%</code>\n"
                f"🎯 العنصر: <code>{item_title[:40]}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"📝 <b>آخر النشاطات:</b>\n"
            )
            for act in activities[-4:]: status_text += f"• {act}\n"
            
            try: bot.edit_message_text(status_text, cid_tg, message_id)
            except: pass
            last_update_time = time.time()

    if fail_count > 0 and completed == 0:
        DB["failed"] += 1
    else:
        DB["success"] += 1
        
    # خصم الفرصة بعد المحاولة (باستثناء الـ VIP)
    user_credit = DB.get("credits", {}).get(str(cid_tg))
    if user_credit != "max":
        if user_credit is not None and isinstance(user_credit, int) and user_credit > 0:
            DB["credits"][str(cid_tg)] -= 1
        elif user_credit is None:
            DB["credits"][str(cid_tg)] = 0
        
    save_db(DB)

    final_text = (
        f"🎉 <b>تم إنهاء الثقافة المالية!</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👤 كود: <code>{login_id}</code>\n"
        f"📸 <b>أرسل صورة النتيجة لـ</b> {OWNER_USERNAME}\n"
    )
    try: bot.edit_message_text(final_text, cid_tg, message_id)
    except: pass

# ==========================================
# 🎨 الواجهة (الأزرار)
# ==========================================
def get_main_keyboard(chat_id):
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(types.InlineKeyboardButton("☕ JavaScript", callback_data="sel_js"))
    markup.add(types.InlineKeyboardButton("🐍 Python", callback_data="sel_python"))
    markup.add(types.InlineKeyboardButton("💼 الثقافة المالية", callback_data="sel_spx"))
    return markup

@bot.message_handler(commands=["start"])
def cmd_start(msg):
    cid = msg.chat.id
    
    # ⭐ التأكد إن الشخص مش محظور
    if DB.get("banned", {}).get(str(cid)):
        try: bot.send_message(cid, "🚫 <b>عذراً، أنت محظور من استخدام البوت.</b>", parse_mode="HTML")
        except: pass
        return
        
    if not check_subscription(cid):
        send_subscribe_msg(cid)
        return

    USERS[cid] = {"running": False}
    if cid not in DB["users"]:
        DB["users"].append(cid)
        save_db(DB)
    name = msg.from_user.first_name
    
    # ⭐ التحقق لو هو VIP
    user_credit = DB.get("credits", {}).get(str(cid))
    is_vip = (user_credit == "max")
    
    if cid == OWNER_ID:
        title_text = f"👑 أهلاً بك يا مالك البوت، <b>{name}</b> Mohmed 🏴‍☠️!"
    elif is_vip:
        title_text = f"💎 أهلاً بك يا <b>{name}</b> في بوت Mohmed 🏴‍☠️!\n(عضو VIP - فرص لا نهائية)"
    else:
        title_text = f"👋 أهلاً بك يا <b>{name}</b> في بوت Mohmed 🏴‍☠️!"
        
    full_caption = f"{title_text}\n\nاختر المادة:"
    
    try: bot.send_message(cid, full_caption, reply_markup=get_main_keyboard(cid), parse_mode="HTML")
    except Exception as e: print(f"Msg Error: {e}")

# ==========================================
# 👑 أوامر الأونر
# ==========================================
@bot.message_handler(commands=["cmds"])
def cmd_owner_commands(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    text = (
        f"👑 <b>أوامر المالك</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📊 <code>/cmd</code> - الإحصائيات\n"
        f"➕ <code>/solve [ID] [العدد]</code> - إضافة فرص\n"
        f"💎 <code>/vip [ID]</code> - تفعيل VIP\n"
        f"❌ <code>/unvip [ID]</code> - إزالة VIP\n"
        f"🔄 <code>/reset [ID]</code> - تصفير الفرص\n"
        f"🚫 <code>/ban [ID]</code> - حظر مستخدم\n"
        f"📢 <code>/broadcast [رسالتك]</code> - إذاعة\n"
    )
    bot.send_message(cid, text, parse_mode="HTML")

@bot.message_handler(commands=["vip"])
def cmd_owner_vip(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    try:
        args = msg.text.replace("/vip", "").strip().split()
        if len(args) < 1:
            bot.reply_to(msg, "⚠️ <b>الاستخدام الصحيح:</b>\n<code>/vip 8549348815</code>", parse_mode="HTML")
            return
        target_id = args[0]
        if "credits" not in DB: DB["credits"] = {}
        DB["credits"][target_id] = "max"
        save_db(DB)
        bot.reply_to(msg, f"💎 تم تفعيل <b>العضوية اللانهائية (VIP)</b> للطالب <code>{target_id}</code>.", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=["unvip"])
def cmd_owner_unvip(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    try:
        args = msg.text.replace("/unvip", "").strip().split()
        if len(args) < 1: return
        target_id = args[0]
        if "credits" in DB and target_id in DB["credits"]:
            del DB["credits"][target_id]
            save_db(DB)
            bot.reply_to(msg, f"✅ تم إزالة الـ VIP من الطالب <code>{target_id}</code>.", parse_mode="HTML")
        else:
            bot.reply_to(msg, f"⚠️ هذا الطالب ليس VIP بالفعل.")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=["ban"])
def cmd_owner_ban(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    try:
        args = msg.text.replace("/ban", "").strip().split()
        if len(args) < 1: return
        target_id = args[0]
        if "banned" not in DB: DB["banned"] = {}
        DB["banned"][target_id] = True
        save_db(DB)
        bot.reply_to(msg, f"🚫 تم حظر الطالب <code>{target_id}</code> من استخدام البوت.", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=["reset"])
def cmd_owner_reset(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    try:
        args = msg.text.replace("/reset", "").strip().split()
        if len(args) < 1: return
        target_id = args[0]
        if "credits" not in DB: DB["credits"] = {}
        DB["credits"][target_id] = 0
        save_db(DB)
        bot.reply_to(msg, f"🔄 تم تصفير فرص الطالب <code>{target_id}</code>.", parse_mode="HTML")
    except Exception as e:
        bot.reply_to(msg, f"⚠️ خطأ: {e}")

@bot.message_handler(commands=["solve"])
def cmd_owner_add_credit(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    try:
        args = msg.text.replace("/solve", "").strip().split()
        if len(args) < 2:
            bot.reply_to(msg, "⚠️ <b>الاستخدام الصحيح:</b>\n<code>/solve 8549348815 10</code>", parse_mode="HTML")
            return
        target_id = args[0]
        amount = int(args[1])
        if "credits" not in DB: DB["credits"] = {}
        if DB["credits"].get(target_id) == "max":
            bot.reply_to(msg, f"⚠️ هذا الطالب VIP بالفعل.")
            return
        if target_id not in DB["credits"]: DB["credits"][target_id] = 0
        DB["credits"][target_id] += amount
        save_db(DB)
        bot.reply_to(msg, f"✅ تم إضافة <code>{amount}</code> فرصة للطالب <code>{target_id}</code>.", parse_mode="HTML")
    except ValueError:
        bot.reply_to(msg, "⚠️ <b>الاستخدام الصحيح:</b>\n<code>/solve 8549348815 10</code>", parse_mode="HTML")

@bot.message_handler(commands=["cmd"])
def cmd_owner_stats(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    db = load_db()
    text = (
        f"👑 <b>لوحة تحكم البوت</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"👥 إجمالي المستخدمين: <code>{len(db.get('users', []))}</code>\n"
        f"✅ عمليات ناجحة: <code>{db.get('success', 0)}</code>\n"
        f"❌ عمليات فاشلة: <code>{db.get('failed', 0)}</code>\n"
    )
    bot.send_message(cid, text, parse_mode="HTML")

@bot.message_handler(commands=["broadcast"])
def cmd_owner_broadcast(msg):
    cid = msg.chat.id
    if cid != OWNER_ID: return
    text_to_send = msg.text.replace("/broadcast", "").strip()
    if not text_to_send:
        bot.reply_to(msg, "⚠️ <b>الاستخدام:</b> <code>/broadcast رسالتك هنا</code>", parse_mode="HTML")
        return
    db = load_db()
    users = db.get("users", [])
    if not users:
        bot.reply_to(msg, "⚠️ مفيش مستخدمين مسجلين.")
        return
    sent_count = 0
    failed_count = 0
    status_msg = bot.reply_to(msg, f"⏳ جاري الإرسال لـ {len(users)} مستخدم...")
    for user_id in users:
        try:
            bot.send_message(user_id, f"📢 <b>رسالة إدارية:</b>\n\n{text_to_send}", parse_mode="HTML")
            sent_count += 1
            time.sleep(0.05)
        except: failed_count += 1
    bot.edit_message_text(
        f"✅ <b>تمت الإذاعة!</b>\n\n📤 تم الإرسال لـ: <code>{sent_count}</code>\n🚫 فشل الإرسال لـ: <code>{failed_count}</code>",
        chat_id=cid, message_id=status_msg.message_id, parse_mode="HTML"
    )

# ==========================================
# 🧠 استقبال الأزرار
# ==========================================
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    cid = call.message.chat.id
    if cid not in USERS: USERS[cid] = {"running": False}
    
    if call.data == "sel_js":
        USERS[cid]['platform'] = 'js'
        bot.edit_message_caption(caption="✅ اخترت <b>JavaScript</b>\n\n📝 أرسل كود الطالب:", chat_id=cid, message_id=call.message.message_id, parse_mode="HTML")
    elif call.data == "sel_python":
        USERS[cid]['platform'] = 'python'
        bot.edit_message_caption(caption="✅ اخترت <b>Python</b>\n\n📝 أرسل كود الطالب:", chat_id=cid, message_id=call.message.message_id, parse_mode="HTML")
    elif call.data == "sel_spx":
        USERS[cid]['platform'] = 'spx'
        bot.edit_message_caption(caption="✅ اخترت <b>الثقافة المالية</b>\n\n📝 أرسل كود الطالب:", chat_id=cid, message_id=call.message.message_id, parse_mode="HTML")
        
    elif call.data == "start_solve":
        if cid != OWNER_ID:
            credits = DB.get("credits", {}).get(str(cid), None)
            if credits != "max": 
                if credits is not None and credits <= 0:
                    markup = types.InlineKeyboardMarkup(row_width=1)
                    markup.add(types.InlineKeyboardButton("👨‍💻 OWNER (شراء الأداة)", url=OWNER_LINK))
                    markup.add(types.InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"))
                    text = (
                        f"⚠️ <b>عذراً يا صديقي!</b>\n\n"
                        f"لقد استنفدت فرصة الحل المجانية المتاحة لك.\n"
                        f"<i>(نظام البوت يتيح لك حل مادة واحدة فقط مجاناً)</i>\n\n"
                        f"💳 <b>متاح شراء الأداة وتفعيل المحاولات فوراً:</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"🐍 بايثون (Qureo): <b>50 ج</b>\n"
                        f"💰 الثقافة المالية (SPX): <b>50 ج</b>\n"
                        f"☕ جافا سكريبت (Qureo): <b>50 ج</b>\n\n"
                        f"🔥 <b>عرض خاص:</b> جافا + الثقافة + بايثون معاً بـ <b>100 ج فقط!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━━━\n"
                        f"👇 اضغط على زر <b>OWNER</b> أدناه للتواصل مع المالك وتفعيل حسابك:"
                    )
                    bot.edit_message_caption(caption=text, chat_id=cid, message_id=call.message.message_id, reply_markup=markup, parse_mode="HTML")
                    return

        if "login_id" in USERS.get(cid, {}) and "password" in USERS.get(cid, {}):
            USERS[cid]["running"] = True
            bot.answer_callback_query(call.id, "🚀 بدأ الحل!")
            msg_id = call.message.message_id
            platform = USERS[cid].get('platform')
            
            if platform == 'spx':
                threading.Thread(target=run_spx_tool, args=(cid, msg_id, USERS[cid]['login_id'], USERS[cid]['password'])).start()
            elif platform == 'js':
                threading.Thread(target=run_qureo_tool, args=(cid, msg_id, USERS[cid]['login_id'], USERS[cid]['password'], "javascript_ar", "javascript_final_db.json", "JavaScript")).start()
            elif platform == 'python':
                threading.Thread(target=run_qureo_tool, args=(cid, msg_id, USERS[cid]['login_id'], USERS[cid]['password'], "python_short_ar", "max.json", "Python")).start()
        else:
            bot.answer_callback_query(call.id, "⚠️ البيانات ناقصة.", show_alert=True)

    elif call.data == "my_stats":
        credits = DB.get("credits", {}).get(str(cid), 0)
        if credits == "max":
            bot.answer_callback_query(call.id, f"💎 رصيدك: فرص لا نهائية (VIP)", show_alert=True)
        else:
            bot.answer_callback_query(call.id, f"📊 رصيدك الحالي: {credits} فرصة متبقية.", show_alert=True)

# ==========================================
# 🆔 استقبال الكود والباسورد
# ==========================================
@bot.message_handler(func=lambda msg: msg.chat.id in USERS and "login_id" not in USERS[msg.chat.id])
def step_id(msg):
    cid = msg.chat.id
    USERS[cid]['login_id'] = msg.text.strip()
    m = bot.send_message(cid, "🔑 أرسل كلمة المرور:")
    bot.register_next_step_handler(m, step_pass)

def step_pass(msg):
    cid = msg.chat.id
    pw = msg.text.strip()
    try: bot.delete_message(cid, msg.message_id)
    except: pass
    if cid not in USERS or 'platform' not in USERS[cid]:
        bot.send_message(cid, "⚠️ الجلسة انتهت، يرجى إرسال /start من جديد.")
        return
    USERS[cid]['password'] = pw
    
    credits = DB.get("credits", {}).get(str(cid), None)
    if cid != OWNER_ID and credits != "max" and credits is not None and credits <= 0:
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(types.InlineKeyboardButton("👨‍💻 OWNER (شراء الأداة)", url=OWNER_LINK))
        markup.add(types.InlineKeyboardButton("📊 إحصائياتي", callback_data="my_stats"))
        text = (
            f"⚠️ <b>عذراً يا صديقي!</b>\n\n"
            f"لقد استنفدت فرصة الحل المجانية المتاحة لك.\n"
            f"<i>(نظام البوت يتيح لك حل مادة واحدة فقط مجاناً)</i>\n\n"
            f"💳 <b>متاح شراء الأداة وتفعيل المحاولات فوراً:</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🐍 بايثون (Qureo): <b>50 ج</b>\n"
            f"💰 الثقافة المالية (SPX): <b>50 ج</b>\n"
            f"☕ جافا سكريبت (Qureo): <b>50 ج</b>\n\n"
            f"🔥 <b>عرض خاص:</b> جافا + الثقافة + بايثون معاً بـ <b>100 ج فقط!</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"👇 اضغط على زر <b>OWNER</b> أدناه للتواصل مع المالك وتفعيل حسابك:"
        )
        bot.send_message(cid, text, reply_markup=markup, parse_mode="HTML")
        return

    markup = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("🚀 بدء الحل التلقائي", callback_data="start_solve"))
    bot.send_message(cid, "✅ <b>تم حفظ البيانات!</b>\n\nاضغط لبدء الحل.", reply_markup=markup, parse_mode="HTML")

# ==========================================
# 🚀 تشغيل البوت
# ==========================================
if __name__ == "__main__":
    print("👑 Mohmed X (JS + Python + SPX) Started...")
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            print(f"⚠️ انقطع الاتصال: {e}")
            time.sleep(5)