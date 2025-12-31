import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
import io
import pytz 

# MENGGUNAKAN LIBSQL (TURSO)
import libsql_experimental as sqlite3 

# ==========================================
# 1. KONFIGURASI HALAMAN & CSS
# ==========================================
st.set_page_config(
    page_title="Lulusin", 
    page_icon="🎓", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- HELPER TIMEZONE (WIB / GMT+7) ---
def get_wib_now():
    return datetime.now(pytz.timezone('Asia/Jakarta')).replace(tzinfo=None)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* 1. Global Font */
    html, body, [class*="css"] { font-family: 'Segoe UI', Roboto, sans-serif; }

    /* 2. Card Containers */
    [data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] > div {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }

    /* 3. Question Card */
    .question-container {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-left: 5px solid #ff4b4b;
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
        background-color: var(--bg-card);
    }

    /* 4. NAVIGASI SIDEBAR BULAT (DOTS) */
    [data-testid="stSidebar"] button {
        border-radius: 50% !important;
        width: 45px !important;
        height: 45px !important;
        padding: 0 !important;
        font-weight: bold !important;
        font-size: 14px !important;
        margin: 2px !important;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border: 1px solid rgba(0,0,0,0.1);
    }
    
    /* 5. General Buttons */
    .exam-card-header { font-size: 1.2rem; font-weight: 700; margin-bottom: 5px; }
    .exam-card-info { font-size: 0.9rem; opacity: 0.8; margin-bottom: 15px; }
    
    /* Admin & Logout Buttons (Normal) */
    .main button:has(p:contains("✏️")), .main button:has(p:contains("🗑️")), 
    div[data-testid="stSidebar"] button:has(p:contains("🚪")) {
        padding: 0px 15px !important;
        border-radius: 4px !important;
        width: auto !important;
        height: auto !important;
        border: 1px solid rgba(128,128,128,0.2) !important;
    }

    .stTabs [data-baseweb="tab-list"] { gap: 15px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    .stButton > button[kind="primary"] { font-weight: 600; border-radius: 8px; }
    
    :root { --btn-edit-bg: #FFC107; --btn-delete-bg: #E53935; }
    @media (prefers-color-scheme: dark) { :root { --btn-edit-bg: #FFD54F; --btn-delete-bg: #EF5350; } }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE MANAGER (TURSO + CACHE)
# ==========================================

@st.cache_resource(ttl=3600)
def get_db_connection():
    try:
        url = st.secrets["turso"]["db_url"]
        token = st.secrets["turso"]["auth_token"]
        conn = sqlite3.connect(url, auth_token=token)
        return conn
    except Exception as e:
        st.error(f"Koneksi Database Gagal: {e}")
        return None

def run_query(query, params=()):
    conn = get_db_connection()
    if not conn: return None
    c = conn.cursor()
    try:
        c.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            cols = [description[0] for description in c.description]
            data = c.fetchall()
            result = [dict(zip(cols, row)) for row in data]
            return result
        else:
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Query Error: {e}")
        return []

def init_db():
    queries = [
        '''CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, role TEXT, name TEXT)''',
        '''CREATE TABLE IF NOT EXISTS materials (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, title TEXT, content TEXT, youtube_url TEXT, file_name TEXT, file_data BLOB, file_type TEXT)''',
        '''CREATE TABLE IF NOT EXISTS exams (id INTEGER PRIMARY KEY AUTOINCREMENT, category TEXT, sub_category TEXT, question TEXT, q_image BLOB, opt_a TEXT, opt_a_img BLOB, opt_b TEXT, opt_b_img BLOB, opt_c TEXT, opt_c_img BLOB, opt_d TEXT, opt_d_img BLOB, opt_e TEXT, opt_e_img BLOB, answer TEXT)''',
        '''CREATE TABLE IF NOT EXISTS results (id INTEGER PRIMARY KEY AUTOINCREMENT, student_name TEXT, category TEXT, score REAL, total_questions INTEGER, date TEXT)''',
        '''CREATE TABLE IF NOT EXISTS exam_schedules (category TEXT PRIMARY KEY, open_time TEXT, close_time TEXT, duration_minutes INTEGER, max_attempts INTEGER)''',
        '''CREATE TABLE IF NOT EXISTS student_exam_attempts (student_name TEXT, category TEXT, start_time TEXT, PRIMARY KEY (student_name, category))''',
        '''CREATE TABLE IF NOT EXISTS student_answers_temp (student_name TEXT, category TEXT, question_id INTEGER, answer TEXT, is_doubtful INTEGER DEFAULT 0, PRIMARY KEY (student_name, category, question_id))''',
        '''CREATE TABLE IF NOT EXISTS banners (id INTEGER PRIMARY KEY AUTOINCREMENT, type TEXT, content TEXT, image_data BLOB, created_at TEXT)'''
    ]
    conn = get_db_connection()
    if conn:
        c = conn.cursor()
        for q in queries: c.execute(q)
        conn.commit()
        res = run_query("SELECT count(*) as cnt FROM users")
        if res and res[0]['cnt'] == 0:
            run_query("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '123', 'admin', 'Administrator'))
            run_query("INSERT INTO users VALUES (?, ?, ?, ?)", ('siswa1', '123', 'student', 'Budi Santoso'))

init_db()

# --- DATABASE HELPERS ---

@st.cache_data(ttl=600)
def get_exams():
    rows = run_query("SELECT * FROM exams")
    formatted = []
    for r in rows:
        raw_opsi = [r['opt_a'], r['opt_b'], r['opt_c'], r['opt_d'], r['opt_e']]
        raw_imgs = [r['opt_a_img'], r['opt_b_img'], r['opt_c_img'], r['opt_d_img'], r['opt_e_img']]
        valid_opsi, valid_imgs = [], []
        for i in range(len(raw_opsi)):
            if raw_opsi[i] and str(raw_opsi[i]).strip() != "":
                valid_opsi.append(raw_opsi[i]); valid_imgs.append(raw_imgs[i])
        formatted.append({"id": r['id'], "category": r['category'], "sub_category": r['sub_category'] if 'sub_category' in r else "Umum", "tanya": r['question'], "q_img": r['q_image'], "opsi": valid_opsi, "opsi_img": valid_imgs, "jawaban": r['answer']})
    return formatted

@st.cache_data(ttl=600)
def get_materials(): return pd.DataFrame(run_query("SELECT * FROM materials"))

def clear_cache():
    get_exams.clear()
    get_materials.clear()

def get_user(u): 
    res = run_query("SELECT * FROM users WHERE username = ?", (u,))
    return res[0] if res else None
def get_all_users(): return pd.DataFrame(run_query("SELECT username, role, name FROM users"))
def add_user(u, p, r, n): run_query("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, r, n)); return True
def update_user_data(u, n, r, np=None):
    if np: run_query("UPDATE users SET name=?, role=?, password=? WHERE username=?", (n, r, np, u))
    else: run_query("UPDATE users SET name=?, role=? WHERE username=?", (n, r, u))
def delete_user(u): run_query("DELETE FROM users WHERE username=?", (u,))
def update_user_password(u, np): run_query("UPDATE users SET password = ? WHERE username = ?", (np, u))

def get_material_by_id(mid): res=run_query("SELECT * FROM materials WHERE id = ?", (mid,)); return res[0] if res else None
def add_material(cat, tit, con, yt, fn, fd, ft): 
    run_query("INSERT INTO materials (category, title, content, youtube_url, file_name, file_data, file_type) VALUES (?,?,?,?,?,?,?)", (cat, tit, con, yt, fn, fd, ft))
    clear_cache()
def update_material(mid, cat, tit, con, yt, fn, fd, ft):
    if fd: run_query("UPDATE materials SET category=?, title=?, content=?, youtube_url=?, file_name=?, file_data=?, file_type=? WHERE id=?", (cat, tit, con, yt, fn, fd, ft, mid))
    else: run_query("UPDATE materials SET category=?, title=?, content=?, youtube_url=? WHERE id=?", (cat, tit, con, yt, mid))
    clear_cache()
def delete_material(mid): 
    run_query("DELETE FROM materials WHERE id=?", (mid,))
    clear_cache()

def get_exam_by_id(eid): res=run_query("SELECT * FROM exams WHERE id = ?", (eid,)); return res[0] if res else None
def add_exam(cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans):
    od=None if not od or str(od).strip()=="" else od; oe=None if not oe or str(oe).strip()=="" else oe
    run_query('''INSERT INTO exams (category, sub_category, question, q_image, opt_a, opt_a_img, opt_b, opt_b_img, opt_c, opt_c_img, opt_d, opt_d_img, opt_e, opt_e_img, answer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', (cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans))
    clear_cache()
def update_exam_data(eid, cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans):
    od=None if not od or str(od).strip()=="" else od; oe=None if not oe or str(oe).strip()=="" else oe
    run_query("""UPDATE exams SET category=?, sub_category=?, question=?, q_image=?, opt_a=?, opt_a_img=?, opt_b=?, opt_b_img=?, opt_c=?, opt_c_img=?, opt_d=?, opt_d_img=?, opt_e=?, opt_e_img=?, answer=? WHERE id=?""", (cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans, eid))
    clear_cache()
def delete_exam_data(eid): 
    run_query("DELETE FROM exams WHERE id=?", (eid,))
    clear_cache()
def delete_all_exams_in_category(cat): 
    run_query("DELETE FROM exams WHERE category=?", (cat,))
    clear_cache()

def set_schedule(cat, op, cl, dur, mx): run_query("REPLACE INTO exam_schedules (category, open_time, close_time, duration_minutes, max_attempts) VALUES (?, ?, ?, ?, ?)", (cat, op, cl, dur, mx))
def get_schedule(cat): res=run_query("SELECT * FROM exam_schedules WHERE category = ?", (cat,)); return res[0] if res else None

def start_student_exam(name, cat): 
    run_query("INSERT INTO student_exam_attempts (student_name, category, start_time) VALUES (?, ?, ?)", (name, cat, get_wib_now().strftime("%Y-%m-%d %H:%M:%S")))
def get_student_attempt(name, cat): res=run_query("SELECT start_time FROM student_exam_attempts WHERE student_name=? AND category=?", (name, cat)); return res[0] if res else None
def get_all_student_attempts(name): return run_query("SELECT category, start_time FROM student_exam_attempts WHERE student_name=?", (name,))
def clear_student_attempt(name, cat):
    run_query("DELETE FROM student_exam_attempts WHERE student_name=? AND category=?", (name, cat))
    run_query("DELETE FROM student_answers_temp WHERE student_name=? AND category=?", (name, cat))

def save_single_answer(name, cat, q_id, ans, doubt):
    """Menyimpan satu jawaban (digunakan saat next/prev)"""
    doubt_val = 1 if doubt else 0
    run_query("REPLACE INTO student_answers_temp (student_name, category, question_id, answer, is_doubtful) VALUES (?, ?, ?, ?, ?)", (name, cat, q_id, ans, doubt_val))

def save_bulk_answers(name, cat, answers_dict):
    """Menyimpan banyak jawaban sekaligus (Batch)"""
    conn = get_db_connection()
    if not conn: return
    c = conn.cursor()
    try:
        c.execute("BEGIN TRANSACTION")
        for qid, val in answers_dict.items():
            doubt_val = 1 if val['doubt'] else 0
            ans = val['answer']
            if ans:
                c.execute("REPLACE INTO student_answers_temp (student_name, category, question_id, answer, is_doubtful) VALUES (?, ?, ?, ?, ?)", (name, cat, qid, ans, doubt_val))
        conn.commit()
    except Exception as e:
        st.error(f"Save Error: {e}")

def get_temp_answers_full(name, cat):
    rows = run_query("SELECT question_id, answer, is_doubtful FROM student_answers_temp WHERE student_name=? AND category=?", (name, cat))
    result = {}
    for r in rows: result[r['question_id']] = {'answer': r['answer'], 'doubt': bool(r['is_doubtful'])}
    return result
def get_student_result_count(name, cat): res=run_query("SELECT count(*) as cnt FROM results WHERE student_name=? AND category=?", (name, cat)); return res[0]['cnt'] if res else 0
def add_result(name, cat, sc, tot, dt): run_query("INSERT INTO results (student_name, category, score, total_questions, date) VALUES (?, ?, ?, ?, ?)", (name, cat, sc, tot, dt))
def get_results(): return pd.DataFrame(run_query("SELECT * FROM results"))
def get_latest_student_result(name, cat): res=run_query("SELECT * FROM results WHERE student_name=? AND category=? ORDER BY id DESC LIMIT 1", (name, cat)); return res[0] if res else None
def add_banner(typ, cont, img): run_query("INSERT INTO banners (type, content, image_data, created_at) VALUES (?, ?, ?, ?)", (typ, cont, img, get_wib_now().strftime("%Y-%m-%d")))
def get_banners(): return run_query("SELECT * FROM banners ORDER BY id DESC")
def delete_banner(bid): run_query("DELETE FROM banners WHERE id=?", (bid,))

# ==========================================
# 3. AUTH & SESSION
# ==========================================
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
for k in ['admin_active_category','edit_target_user','edit_q_id','selected_exam_cat','edit_material_id']:
    if k not in st.session_state: st.session_state[k] = None

# [STATE BARU UNTUK NAVIGASI PAGINATION & BUFFER]
if 'q_idx' not in st.session_state: st.session_state.q_idx = 0
if 'local_answers' not in st.session_state: st.session_state['local_answers'] = {}

def check_session_persistence():
    if st.session_state['current_user'] is None and "u_id" in st.query_params:
        user_data = get_user(st.query_params["u_id"])
        if user_data: st.session_state['current_user'] = {"username": user_data['username'], "role": user_data['role'], "name": user_data['name']}
    if "cat" in st.query_params: st.session_state['selected_exam_cat'] = st.query_params["cat"]

def login_page():
    st.write(""); st.write(""); st.write("")
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown("""<div style="text-align: center; margin-bottom: 20px;"><div style="font-size: 50px;">🎓</div><h2 style="margin: 0; padding:0;">Lulusin</h2><p style="opacity: 0.7; font-size: 14px; margin-top: 5px;">Silakan masuk untuk melanjutkan</p></div>""", unsafe_allow_html=True)
            user = st.text_input("Username", placeholder="Masukkan username")
            pwd = st.text_input("Password", type="password", placeholder="Masukkan password")
            st.write("")
            if st.form_submit_button("Masuk", type="primary", use_container_width=True):
                data = get_user(user)
                if data and data['password'] == pwd:
                    st.session_state['current_user'] = {"username": data['username'], "role": data['role'], "name": data['name']}
                    st.query_params["u_id"] = user; st.rerun()
                else: st.error("Username atau Password salah")

def logout_button():
    if st.sidebar.button("🚪 Keluar"): 
        st.session_state['current_user'] = None
        st.session_state['local_answers'] = {} 
        st.session_state.q_idx = 0
        for k in ['edit_q_id', 'edit_material_id', 'selected_exam_cat', 'admin_active_category']: st.session_state[k] = None
        st.query_params.clear(); st.rerun()

# ==========================================
# 4. KOMPONEN UI
# ==========================================
def display_timer_js(seconds_left):
    html_code = f"""
    <div style="width:100%; background:#ff4b4b; color:white; text-align:center; padding:10px; border-radius:8px; font-size:18px; font-weight:bold; margin-bottom:10px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">
        ⏱️ <span id="timer">Loading...</span>
    </div>
    <script>
        var timeLeft = {int(seconds_left)};
        var x = setInterval(function() {{
            if (timeLeft <= 0) {{
                clearInterval(x);
                document.getElementById("timer").innerHTML = "0m 0s";
                window.parent.location.reload(); 
            }} else {{
                var m = Math.floor(timeLeft / 60);
                var s = Math.floor(timeLeft % 60);
                document.getElementById("timer").innerHTML = m + "m " + s + "s ";
                timeLeft -= 1;
            }}
        }}, 1000);
    </script>
    """
    components.html(html_code, height=60)

@st.dialog("🎉 Hasil Ujian", width="small")
def show_result_popup(score, correct, total, category):
    st.balloons()
    st.markdown(f"""<div style='text-align: center; padding: 20px;'><h4 style='margin:0; opacity:0.7;'>Hasil Ujian</h4><h2 style='margin:0;'>{category}</h2><h1 style='color: #27ae60; font-size: 72px; margin: 10px 0;'>{score:.1f}</h1><div style='background:rgba(128,128,128,0.1); padding:10px; border-radius:8px;'>✅ Benar: <b>{int(correct)}</b> / {total} Soal</div></div>""", unsafe_allow_html=True)
    if st.button("Tutup & Kembali ke Menu", use_container_width=True, type="primary"):
        st.session_state['selected_exam_cat'] = None
        st.session_state.q_idx = 0
        if "exam_done" in st.query_params: del st.query_params["exam_done"]
        if "cat" in st.query_params: del st.query_params["cat"]
        st.rerun()

def display_banner_carousel():
    banners = get_banners()
    if not banners: return
    slides = ""
    for idx, b in enumerate(banners):
        disp = "block" if idx == 0 else "none"
        if b['type']=='image' and b['image_data']:
            b64 = base64.b64encode(b['image_data']).decode()
            slides += f"""<div class="mySlides fade" style="display:{disp};"><img src="data:image/png;base64,{b64}" style="width:100%;height:300px;object-fit:cover;border-radius:10px;box-shadow:0 4px 6px rgba(0,0,0,0.1);"></div>"""
        else: slides += f"""<div class="mySlides fade" style="display:{disp};">{b['content']}</div>"""
    components.html(f"""<style>.slideshow-container{{max-width:100%;position:relative;margin:auto;}}.fade{{animation-name:fade;animation-duration:1.5s;}}@keyframes fade{{from{{opacity:.4}}to{{opacity:1}}}}</style><div class="slideshow-container">{slides}</div><script>let si=0;show();function show(){{let i;let s=document.getElementsByClassName("mySlides");for(i=0;i<s.length;i++){{s[i].style.display="none";}}si++;if(si>s.length){{si=1}}s[si-1].style.display="block";setTimeout(show,5000);}}</script>""", height=310)

# ==========================================
# 5. DASHBOARD ADMIN
# ==========================================
def admin_dashboard():
    st.title("👨‍🏫 Dashboard Admin")
    c1,c2,c3 = st.columns(3)
    c1.metric("Total Pengguna", len(get_all_users()))
    c2.metric("Total Soal", len(get_exams()))
    c3.metric("Materi Aktif", len(get_materials()))
    st.write("")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📚 Materi", "📝 Bank Soal", "📢 Info & Banner", "📊 Nilai", "👥 User"])
    
    # --- TAB 1: MATERI ---
    with tab1:
        if st.session_state['edit_material_id']:
            md = get_material_by_id(st.session_state['edit_material_id'])
            if md:
                st.info(f"✏️ Edit: {md['title']}")
                with st.form("emf"):
                    c1,c2=st.columns(2)
                    cat=c1.text_input("Kategori", md['category']); tit=c1.text_input("Judul", md['title']); yt=c1.text_input("YouTube", md['youtube_url'])
                    con=c2.text_area("Isi", md['content'], height=150); f=c2.file_uploader("Ganti File")
                    if st.form_submit_button("Simpan"):
                        fn,fd,ft = (f.name,f.getvalue(),f.type) if f else (None,None,None)
                        update_material(md['id'],cat,tit,con,yt,fn,fd,ft); st.session_state['edit_material_id']=None; st.success("OK"); st.rerun()
                    if st.form_submit_button("Batal"): st.session_state['edit_material_id']=None; st.rerun()
        else:
            with st.expander("➕ Tambah Materi"):
                with st.form("amf"):
                    c1,c2=st.columns(2)
                    cat=c1.text_input("Kategori"); tit=c1.text_input("Judul"); yt=c1.text_input("YouTube")
                    con=c2.text_area("Isi"); f=c2.file_uploader("File")
                    if st.form_submit_button("Simpan"):
                        fn,fd,ft = (f.name,f.getvalue(),f.type) if f else (None,None,None)
                        add_material(cat,tit,con,yt,fn,fd,ft); st.success("OK"); st.rerun()
            st.write("### Daftar Materi")
            df = get_materials()
            if not df.empty:
                c1,c2,c3,c4=st.columns([2,4,1,1]); c1.markdown("**Kategori**"); c2.markdown("**Judul**"); st.divider()
                for i,r in df.iterrows():
                    with st.container():
                        c1,c2,c3,c4=st.columns([2,4,1,1]); c1.write(r['category']); c2.write(r['title'])
                        if c3.button("✏️", key=f"em_{r['id']}"): st.session_state['edit_material_id']=r['id']; st.rerun()
                        if c4.button("🗑️", key=f"dm_{r['id']}"): delete_material(r['id']); st.rerun()
            else: st.info("Kosong")

    # --- TAB 2: BANK SOAL ---
    with tab2:
        if not st.session_state['admin_active_category']:
            cats = sorted(list(set([e['category'] for e in get_exams()])))
            c1,c2=st.columns(2); pc=c1.selectbox("Pilih Kategori", ["--"]+cats); ic=c2.text_input("Buat Baru")
            if st.button("Kelola"): st.session_state['admin_active_category']=ic if ic else (pc if pc!="--" else None); st.rerun()
        else:
            ac = st.session_state['admin_active_category']
            c1,c2=st.columns([4,1]); c1.markdown(f"### 📂 {ac}"); 
            if c2.button("⬅️ Kembali"): st.session_state['admin_active_category']=None; st.rerun()
            
            with st.expander("📅 Jadwal Ujian"):
                sch=get_schedule(ac)
                d_def = get_wib_now().date()
                with st.form("schf"):
                    dr=st.date_input("Tanggal", [d_def, d_def])
                    c1,c2=st.columns(2)
                    top=c1.time_input("Buka", get_wib_now().time(), step=60)
                    cl=c2.time_input("Tutup", (get_wib_now()+timedelta(hours=4)).time(), step=60)
                    c3,c4=st.columns(2)
                    du=c3.number_input("Durasi (Menit)", min_value=1, value=60, step=1)
                    mx=c4.number_input("Max Attempt", min_value=1, value=1)
                    if st.form_submit_button("Simpan"):
                        fo = datetime.combine(dr[0],top).strftime("%Y-%m-%d %H:%M:%S")
                        fc = datetime.combine(dr[1] if len(dr)>1 else dr[0], cl).strftime("%Y-%m-%d %H:%M:%S")
                        set_schedule(ac,fo,fc,du,mx); st.success("OK")

            if st.session_state['edit_q_id']:
                qd = get_exam_by_id(st.session_state['edit_q_id'])
                if qd:
                    with st.form("eqf"):
                        sub=st.text_input("Sub", qd['sub_category']); q=st.text_area("Soal", qd['question'])
                        qi=st.file_uploader("Gbr Soal")
                        c1,c2=st.columns(2)
                        oa=c1.text_input("A", qd['opt_a']); ob=c1.text_input("B", qd['opt_b']); oc=c1.text_input("C", qd['opt_c'])
                        od=c2.text_input("D", qd['opt_d']); oe=c2.text_input("E", qd['opt_e']); ans=c2.text_input("Kunci", qd['answer'])
                        if st.form_submit_button("Update"):
                            nqi = qi.getvalue() if qi else qd['q_image']
                            update_exam_data(qd['id'],ac,sub,q,nqi,oa,None,ob,None,oc,None,od,None,oe,None,ans); st.session_state['edit_q_id']=None; st.rerun()
                        if st.form_submit_button("Batal"): st.session_state['edit_q_id']=None; st.rerun()
            else:
                t1,t2=st.tabs(["Tambah Manual", "Import Excel"])
                with t1:
                    with st.form("aqf", clear_on_submit=True):
                        sub=st.text_input("Sub"); q=st.text_area("Soal"); qi=st.file_uploader("Gbr Soal")
                        n=st.radio("Jml Opsi",[3,4,5], horizontal=True)
                        st.caption("Isi teks opsi.")
                        c_ops1, c_ops2 = st.columns(2)
                        with c_ops1: oa=st.text_input("A"); ob=st.text_input("B"); oc=st.text_input("C")
                        with c_ops2: od=st.text_input("D"); oe=st.text_input("E"); ans=st.text_input("Kunci")
                        with st.expander("Gbr Opsi"):
                            c1,c2,c3,c4,c5=st.columns(5)
                            ia=c1.file_uploader("A",key="ia"); ib=c2.file_uploader("B",key="ib"); ic=c3.file_uploader("C",key="ic")
                            id=c4.file_uploader("D",key="id"); ie=c5.file_uploader("E",key="ie")
                        if st.form_submit_button("Simpan"):
                            nqi=qi.getvalue() if qi else None
                            via=ia.getvalue() if ia else None; vib=ib.getvalue() if ib else None; vic=ic.getvalue() if ic else None
                            vid=id.getvalue() if id else None; vie=ie.getvalue() if ie else None
                            add_exam(ac,sub,q,nqi,oa,via,ob,vib,oc,vic,od,vid,oe,vie,ans); st.success("OK"); st.rerun()
                with t2:
                    uf=st.file_uploader("Excel"); 
                    if uf and st.button("Import"):
                        try:
                            df=pd.read_excel(uf)
                            for _,r in df.iterrows():
                                def c(v): return str(v).strip() if pd.notna(v) else None
                                add_exam(ac,c(r["Sub Kategori"]),c(r["Pertanyaan"]),None,c(r["Opsi A"]),None,c(r["Opsi B"]),None,c(r["Opsi C"]),None,c(r["Opsi D"]),None,c(r["Opsi E"]),None,c(r["Jawaban Benar"]))
                            st.success("OK"); st.rerun()
                        except: st.error("Format Salah")

            st.write("### Daftar Soal"); st.divider()
            exams=[e for e in get_exams() if e['category']==ac]
            if exams:
                for ex in exams:
                    with st.container():
                        c_row1, c_row2, c_row3 = st.columns([6, 1, 1])
                        c_row1.markdown(f"**[{ex['sub_category']}]** {ex['tanya'][:80]}...")
                        if c_row2.button("✏️", key=f"eq_{ex['id']}"): st.session_state['edit_q_id']=ex['id']; st.rerun()
                        if c_row3.button("🗑️", key=f"dq_{ex['id']}"): delete_exam_data(ex['id']); st.rerun()
                        st.markdown("---")
            else: st.info("Kosong")

    with tab3:
        t1,t2=st.tabs(["Editor", "Preview"]); 
        with t1:
            bg=st.color_picker("BG", "#1e3c72"); txt=st.text_area("Konten", "Halo!")
            if st.button("Publish"): 
                h=f"""<div style="width:100%;height:300px;background:{bg};color:white;display:flex;align-items:center;justify-content:center;border-radius:10px;">{txt}</div>"""
                add_banner('text',h,None); st.rerun()
        with t2:
            bans=get_banners()
            for b in bans:
                c1,c2=st.columns([4,1]); c1.write(f"ID: {b['id']}"); 
                if c2.button("Hapus", key=f"db_{b['id']}"): delete_banner(b['id']); st.rerun()

    with tab4:
        df = get_results()
        if not df.empty:
            st.dataframe(df, use_container_width=True)
        else:
            st.info("Kosong")

    # --- TAB 5: KELOLA USER ---
    with tab5:
        with st.expander("➕ Tambah User"):
            with st.form("auf"):
                u=st.text_input("User"); p=st.text_input("Pass", type="password"); n=st.text_input("Nama"); r=st.selectbox("Role", ["student","admin"])
                if st.form_submit_button("Simpan"): add_user(u,p,r,n); st.rerun()
        
        st.write("### Daftar User")
        dfu = get_all_users()
        c1,c2,c3,c4,c5 = st.columns([2,3,2,1,1]); c1.markdown("**User**"); c2.markdown("**Nama**"); c3.markdown("**Role**")
        st.divider()
        
        for i, row in dfu.iterrows():
            with st.container():
                c1,c2,c3,c4,c5 = st.columns([2,3,2,1,1])
                c1.write(row['username'])
                c2.write(row['name'])
                c3.markdown(f":red[{row['role']}]" if row['role']=='admin' else f":blue[{row['role']}]")
                if c4.button("✏️", key=f"eu_{row['username']}"): st.session_state['edit_target_user']=row['username']; st.rerun()
                if c5.button("🗑️", key=f"du_{row['username']}"): 
                    if row['username'] != st.session_state['current_user']['username']: delete_user(row['username']); st.rerun()
                st.markdown("---")
        
        if st.session_state['edit_target_user']:
            ud = get_user(st.session_state['edit_target_user'])
            if ud:
                st.info(f"Edit: {ud['username']}")
                with st.form("euf"):
                    en=st.text_input("Nama", value=ud['name'])
                    er=st.selectbox("Role", ["student","admin"], index=0 if ud['role']=="student" else 1)
                    ep=st.text_input("Reset Pass (Isi jika ingin ubah)", type="password")
                    if st.form_submit_button("Simpan"): update_user_data(ud['username'],en,er,ep if ep else None); st.session_state['edit_target_user']=None; st.rerun()
                    if st.form_submit_button("Batal"): st.session_state['edit_target_user']=None; st.rerun()

# ==========================================
# 6. STUDENT DASHBOARD (RAM BUFFER MODE)
# ==========================================
def student_dashboard():
    user = st.session_state['current_user']
    
    # [POP-UP CHECK DI AWAL]
    if "exam_done" in st.query_params:
        tc = st.query_params.get("cat")
        lr = get_latest_student_result(user['name'], tc)
        if lr:
            show_result_popup(lr['score'], (lr['score']/100)*lr['total_questions'] if lr['total_questions']>0 else 0, lr['total_questions'], tc)

    all_qs = get_exams() # Cache
    atts = get_all_student_attempts(user['name'])
    
    # [TIMER LOGIC]
    trigger_submit_final = False
    target_cat_final = None
    
    for att in atts:
        cat = att['category']; sch = get_schedule(cat)
        if sch:
            s_dt = datetime.strptime(att['start_time'], "%Y-%m-%d %H:%M:%S")
            dead = s_dt + timedelta(minutes=sch['duration_minutes'])
            if (dead - get_wib_now()).total_seconds() <= 0:
                trigger_submit_final = True
                target_cat_final = cat

    # [HELPER: COLLECT ALL WIDGET VALUES] (Dipanggil saat Submit/Timeout)
    def collect_all_answers_from_widgets(cat_name):
        current_answers = st.session_state['local_answers'].get(cat_name, {})
        # Loop semua soal di kategori ini
        raw_qs = [e for e in all_qs if e['category']==cat_name]
        for q in raw_qs:
            # Ambil nilai langsung dari Widget jika ada
            w_ans = st.session_state.get(f"rad_{q['id']}")
            w_dbt = st.session_state.get(f"chk_{q['id']}")
            if w_ans is not None:
                current_answers[q['id']] = {'answer': w_ans, 'doubt': w_dbt}
        return current_answers

    # [SUBMIT OTOMATIS (WAKTU HABIS)]
    if trigger_submit_final and target_cat_final:
        # 1. Ambil paksa semua jawaban dari Widget saat ini
        final_answers = collect_all_answers_from_widgets(target_cat_final)
        
        # 2. Simpan Batch ke DB
        save_bulk_answers(user['name'], target_cat_final, final_answers)
        
        # 3. Hitung Nilai dari Data Final
        raw=[e for e in all_qs if e['category']==target_cat_final]
        # Kita pakai data dari RAM final_answers untuk scoring agar akurat 100%
        sc=sum([1 for s in raw if final_answers.get(s['id'],{}).get('answer') == s['jawaban']])
        val=(sc/len(raw))*100 if raw else 0
        
        add_result(user['name'], target_cat_final, val, len(raw), get_wib_now().strftime("%Y-%m-%d %H:%M:%S"))
        clear_student_attempt(user['name'], target_cat_final)
        
        st.session_state['selected_exam_cat'] = None
        st.session_state.q_idx = 0
        st.query_params["exam_done"]="true"; st.query_params["cat"]=target_cat_final; st.query_params["u_id"]=user['username']
        st.rerun()

    st.markdown(f"### 👋 Halo, {user['name']}"); display_banner_carousel(); st.write("")
    tab1, tab2, tab3 = st.tabs(["📚 Materi", "📝 Ujian", "🏆 Nilai"])

    # TAB MATERI
    with tab1:
        df = get_materials()
        if not df.empty:
            cat = st.selectbox("📂 Filter Kategori Materi", sorted(df['category'].unique()))
            st.divider()
            for _, r in df[df['category']==cat].iterrows():
                with st.expander(f"📄 {r['title']}"):
                    st.write(r['content'])
                    if r['youtube_url']: st.video(r['youtube_url'])
                    if r['file_data']:
                        st.download_button(f"⬇️ Download {r['file_name']}", r['file_data'], file_name=r['file_name'])
        else: st.info("Belum ada materi tersedia.")

    # TAB UJIAN (PAGINATION)
    with tab2:
        cats = sorted(list(set([e['category'] for e in all_qs])))
        
        if st.session_state['selected_exam_cat'] is None:
            # GRID VIEW
            if not cats: st.info("Belum ada ujian tersedia.")
            else:
                cols = st.columns(3)
                for i, cat in enumerate(cats):
                    sch = get_schedule(cat)
                    stat_txt = "Tersedia"; stat_col = "#27ae60"
                    
                    if sch:
                        od = datetime.strptime(sch['open_time'], "%Y-%m-%d %H:%M:%S")
                        cd = datetime.strptime(sch['close_time'], "%Y-%m-%d %H:%M:%S")
                        now_wib = get_wib_now()
                        if now_wib < od: stat_txt = "Belum Buka"; stat_col = "#e67e22"
                        elif now_wib > cd: stat_txt = "Ditutup"; stat_col = "#c0392b"
                    
                    with cols[i%3]:
                        with st.container(border=True):
                            st.markdown(f"<div class='exam-card-header'>📚 {cat}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='exam-card-info' style='color:{stat_col}'>{stat_txt}</div>", unsafe_allow_html=True)
                            if st.button(f"Buka Soal", key=f"open_{cat}", use_container_width=True):
                                st.session_state['selected_exam_cat'] = cat; st.session_state.q_idx = 0; st.query_params["cat"] = cat; st.rerun()
        else:
            # PAGINATION QUESTION VIEW
            pcat = st.session_state['selected_exam_cat']
            
            c_back, c_title = st.columns([1, 5])
            with c_back:
                if st.button("⬅️ Kembali"):
                    st.session_state['selected_exam_cat'] = None
                    st.session_state.q_idx = 0
                    if "cat" in st.query_params: del st.query_params["cat"]
                    st.rerun()
            with c_title: st.markdown(f"## 📝 Ujian: {pcat}")
            
            sch = get_schedule(pcat); show_exam = False
            if sch:
                odt = datetime.strptime(sch['open_time'], "%Y-%m-%d %H:%M:%S")
                cdt = datetime.strptime(sch['close_time'], "%Y-%m-%d %H:%M:%S")
                dur = sch['duration_minutes']
                lim = sch['max_attempts']
                cnt = get_student_result_count(user['name'], pcat)
                att = get_student_attempt(user['name'], pcat)
                now_wib = get_wib_now()

                if att:
                    dead = datetime.strptime(att['start_time'], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=dur)
                    if (dead - now_wib).total_seconds() > 0:
                        with st.sidebar:
                            display_timer_js((dead - now_wib).total_seconds())
                        show_exam = True
                else:
                    st.info(f"Riwayat Percobaan: {cnt}/{lim}")
                    if cnt >= lim: st.error("Kesempatan ujian habis.")
                    elif now_wib < odt: st.warning(f"Ujian dibuka pada: {odt}")
                    elif now_wib > cdt: st.error("Ujian sudah ditutup.")
                    else:
                        if st.button("🚀 MULAI UJIAN", type="primary"):
                            start_student_exam(user['name'], pcat); st.rerun()
            else:
                st.info("Mode Latihan (Tanpa Batas Waktu)"); show_exam = True

            if show_exam:
                raw = [e for e in all_qs if e['category']==pcat]
                
                # --- LOAD INITIAL DB DATA TO LOCAL STATE (ONCE) ---
                if pcat not in st.session_state['local_answers']:
                    st.session_state['local_answers'][pcat] = get_temp_answers_full(user['name'], pcat)
                
                local_data = st.session_state['local_answers'][pcat]
                
                # --- CALLBACKS PURE RAM (INSTANT) ---
                def update_ram(qid):
                    # Fungsi ini dipanggil on_change radio/checkbox
                    # HANYA update Session State, JANGAN panggil DB
                    ans = st.session_state.get(f"rad_{qid}")
                    dbt = st.session_state.get(f"chk_{qid}")
                    if ans:
                        local_data[qid] = {'answer': ans, 'doubt': dbt}

                def go_jump(idx): st.session_state.q_idx = idx
                def go_next(): 
                    if st.session_state.q_idx < len(raw)-1: st.session_state.q_idx += 1
                def go_prev(): 
                    if st.session_state.q_idx > 0: st.session_state.q_idx -= 1

                # --- SIDEBAR NAVIGATION (READ FROM RAM) ---
                with st.sidebar:
                    st.write("### 🧭 Navigasi Soal")
                    cols = st.columns(5)
                    for i, q in enumerate(raw):
                        d = local_data.get(q['id'], {})
                        # Color Logic (Baca RAM, jadi instan berubah)
                        if i == st.session_state.q_idx: btn_type = "primary" # Active
                        elif d.get('doubt'): btn_type = "secondary" # Ragu (Kuning via CSS/Emoji)
                        elif d.get('answer'): btn_type = "primary" # Dijawab (Biru/Primary)
                        else: btn_type = "secondary" # Kosong
                        
                        # Emoji Label (Dot Style)
                        label = str(i+1)
                        if d.get('doubt'): label = f"⚠️ {i+1}"
                        elif d.get('answer'): label = f"✅ {i+1}"
                        
                        # Button with Callback
                        if cols[i%5].button(label, key=f"nav_{i}", type=btn_type, on_click=go_jump, args=(i,)):
                            pass

                # --- DISPLAY CURRENT QUESTION ---
                current_q = raw[st.session_state.q_idx]
                q_id = current_q['id']
                
                saved_val = local_data.get(q_id, {})
                idx_sel = current_q['opsi'].index(saved_val.get('answer')) if saved_val.get('answer') in current_q['opsi'] else None

                st.markdown(f"#### Soal No. {st.session_state.q_idx + 1}")
                st.markdown(f"<div class='question-container'>{current_q['tanya']}</div>", unsafe_allow_html=True)
                if current_q['q_img'] and isinstance(current_q['q_img'], bytes): st.image(current_q['q_img'], width=400)
                
                if len(current_q['opsi']) > 0:
                    c_ops = st.columns(len(current_q['opsi']))
                    for i, c in enumerate(c_ops):
                        with c:
                            if current_q['opsi_img'][i] and isinstance(current_q['opsi_img'][i], bytes): st.image(current_q['opsi_img'][i], width=100)

                # --- INPUTS (RAM UPDATE ONLY - ZERO LOADING) ---
                st.radio("Pilih Jawaban:", current_q['opsi'], index=idx_sel, key=f"rad_{q_id}", on_change=update_ram, args=(q_id,))
                st.checkbox("🚩 Ragu-ragu", value=saved_val.get('doubt', False), key=f"chk_{q_id}", on_change=update_ram, args=(q_id,))
                
                st.divider()
                
                # NAVIGASI BUTTONS
                c_prev, c_dbt, c_next = st.columns([1, 2, 1])
                
                # Saat pindah soal, kita BOLEH save ke DB (Background) agar aman jika browser close
                def on_nav_click(direction):
                    # Save current q to DB
                    curr_q_id = raw[st.session_state.q_idx]['id']
                    ans = st.session_state.get(f"rad_{curr_q_id}")
                    dbt = st.session_state.get(f"chk_{curr_q_id}")
                    if ans:
                        save_single_answer(user['name'], pcat, curr_q_id, ans, dbt)
                    
                    if direction == 'next': go_next()
                    elif direction == 'prev': go_prev()

                c_prev.button("⬅️ Sebelumnya", disabled=(st.session_state.q_idx == 0), on_click=on_nav_click, args=('prev',))

                if st.session_state.q_idx < len(raw) - 1:
                    c_next.button("Selanjutnya ➡️", type="primary", on_click=on_nav_click, args=('next',))
                else:
                    if c_next.button("✅ Kirim Selesai", type="primary"):
                        # 1. Collect All Answers from Widgets (RAM)
                        final_answers = collect_all_answers_from_widgets(pcat)
                        
                        # 2. Save Batch to DB
                        save_bulk_answers(user['name'], pcat, final_answers)
                        
                        # 3. Grading
                        raw=[e for e in all_qs if e['category']==pcat]
                        sc=sum([1 for s in raw if final_answers.get(s['id'],{}).get('answer') == s['jawaban']])
                        val=(sc/len(raw))*100 if raw else 0
                        
                        add_result(user['name'], pcat, val, len(raw), get_wib_now().strftime("%Y-%m-%d %H:%M:%S"))
                        clear_student_attempt(user['name'], pcat)
                        
                        st.session_state['selected_exam_cat'] = None
                        st.session_state.q_idx = 0
                        st.query_params["exam_done"]="true"; st.query_params["cat"]=pcat; st.query_params["u_id"]=user['username']
                        st.rerun()

    # TAB NILAI
    with tab3:
        df = get_results()
        if not df.empty:
            my_df = df[df['student_name'] == user['name']]
            if not my_df.empty:
                c1, c2 = st.columns(2)
                c1.metric("Ujian Diikuti", len(my_df))
                c2.metric("Rata-rata Score", f"{my_df['score'].mean():.1f}")
                st.divider()
                st.dataframe(my_df, use_container_width=True)
            else: st.info("Anda belum mengikuti ujian apapun.")
        else: st.info("Belum ada data nilai.")

def main():
    check_session_persistence()
    if not st.session_state['current_user']: login_page()
    else:
        st.sidebar.write(f"👤 {st.session_state['current_user']['name']}")
        with st.sidebar.expander("🔐 Ganti Password"):
            op = st.text_input("Lama", type="password"); np = st.text_input("Baru", type="password")
            if st.button("Simpan"):
                u = st.session_state['current_user']['username']; d = get_user(u)
                if d and d['password']==op: update_user_password(u, np); st.success("OK")
        logout_button()
        if st.session_state['current_user']['role'] == 'admin': admin_dashboard()
        else: student_dashboard()

if __name__ == "__main__": main()
