import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
from datetime import datetime, timedelta
import time
import base64
import io

# GANTI IMPORT SQLITE BIASA DENGAN LIBSQL (TURSO)
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

# --- CUSTOM CSS (LAYOUT RAPI & DEFAULT COLOR FRIENDLY) ---
st.markdown("""
<style>
    /* === 1. GLOBAL STYLE === */
    html, body, [class*="css"] { font-family: 'Segoe UI', Roboto, sans-serif; }

    /* === 2. LOGIN & CARD CONTAINER === */
    /* Membuat form login dan container terlihat seperti kartu dengan border halus */
    [data-testid="stForm"], [data-testid="stVerticalBlockBorderWrapper"] > div {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-radius: 12px;
        padding: 25px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
    }

    /* === 3. KARTU SOAL (QUESTION CARD) === */
    .question-container {
        border: 1px solid rgba(128, 128, 128, 0.2);
        border-left: 5px solid #ff4b4b; /* Aksen merah default Streamlit */
        border-radius: 8px;
        padding: 20px;
        margin-bottom: 20px;
    }

    /* === 4. NAVIGASI SIDEBAR === */
    .nav-box {
        display: inline-block; width: 35px; height: 35px;
        line-height: 35px; text-align: center; margin: 3px;
        border-radius: 6px; font-size: 14px; font-weight: bold;
        color: white !important; /* Teks selalu putih agar kontras */
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        box-shadow: 0 2px 4px rgba(0,0,0,0.2);
    }

    /* === 5. GRID CARD UJIAN === */
    .exam-card-header {
        font-size: 1.2rem; font-weight: 700; margin-bottom: 5px;
    }
    .exam-card-info {
        font-size: 0.9rem; opacity: 0.8; margin-bottom: 15px;
    }

    /* === 6. TOMBOL IKON KECIL (EDIT/DELETE) === */
    /* Menggunakan teknik CSS Selector 'has' untuk menargetkan tombol berisi emoji */
    button:has(p:contains("✏️")), button:has(p:contains("🗑️")) {
        padding: 0px 10px !important;
        border-radius: 6px !important;
        min-height: 32px !important; height: 32px !important;
        border: 1px solid rgba(128,128,128,0.2) !important;
        margin: 0px !important;
    }
    /* Hover effect khusus */
    button:has(p:contains("✏️")):hover { border-color: #f1c40f !important; color: #f1c40f !important; }
    button:has(p:contains("🗑️")):hover { border-color: #e74c3c !important; color: #e74c3c !important; }

    /* === 7. GENERAL TWEAKS === */
    .stTabs [data-baseweb="tab-list"] { gap: 15px; }
    [data-testid="stMetricValue"] { font-size: 1.8rem !important; }
    
    /* Tombol Utama (Primary) */
    .stButton > button[kind="primary"] {
        font-weight: 600;
        border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. DATABASE MANAGER (VERSI TURSO / LIBSQL)
# ==========================================

@st.cache_resource
def get_db_connection():
    # Ambil kredensial dari secrets.toml
    try:
        url = st.secrets["turso"]["db_url"]
        token = st.secrets["turso"]["auth_token"]
        conn = sqlite3.connect(url, auth_token=token)
        return conn
    except Exception as e:
        st.error(f"Gagal koneksi ke Database Turso: {e}")
        return None

def run_query(query, params=()):
    """Helper function untuk menjalankan query di Turso/LibSQL"""
    conn = get_db_connection()
    if not conn: return None
    
    c = conn.cursor()
    try:
        c.execute(query, params)
        if query.strip().upper().startswith("SELECT"):
            cols = [description[0] for description in c.description]
            data = c.fetchall()
            # Convert ke list of dict agar kompatibel dengan kode lama (row['key'])
            result = [dict(zip(cols, row)) for row in data]
            return result
        else:
            conn.commit()
            return True
    except Exception as e:
        st.error(f"Query Error: {e}")
        return []

def init_db():
    # Membuat tabel jika belum ada
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
        for q in queries:
            c.execute(q)
        conn.commit()

        # Cek User Default
        res = run_query("SELECT count(*) as cnt FROM users")
        if res and res[0]['cnt'] == 0:
            run_query("INSERT INTO users VALUES (?, ?, ?, ?)", ('admin', '123', 'admin', 'Administrator'))
            run_query("INSERT INTO users VALUES (?, ?, ?, ?)", ('siswa1', '123', 'student', 'Budi Santoso'))

# Jalankan inisialisasi DB
init_db()

# --- DATABASE HELPERS (CRUD MENGGUNAKAN RUN_QUERY) ---

def get_user(u): 
    res = run_query("SELECT * FROM users WHERE username = ?", (u,))
    return res[0] if res else None

def get_all_users(): return pd.DataFrame(run_query("SELECT username, role, name FROM users"))
def add_user(u, p, r, n): run_query("INSERT INTO users VALUES (?, ?, ?, ?)", (u, p, r, n))
def update_user_data(u, n, r, np=None):
    if np: run_query("UPDATE users SET name=?, role=?, password=? WHERE username=?", (n, r, np, u))
    else: run_query("UPDATE users SET name=?, role=? WHERE username=?", (n, r, u))
def delete_user(u): run_query("DELETE FROM users WHERE username=?", (u,))
def update_user_password(u, np): run_query("UPDATE users SET password = ? WHERE username = ?", (np, u))

def get_materials(): return pd.DataFrame(run_query("SELECT * FROM materials"))
def get_material_by_id(mid): 
    res = run_query("SELECT * FROM materials WHERE id = ?", (mid,))
    return res[0] if res else None
def add_material(cat, tit, con, yt, fn, fd, ft): 
    run_query("INSERT INTO materials (category, title, content, youtube_url, file_name, file_data, file_type) VALUES (?,?,?,?,?,?,?)", (cat, tit, con, yt, fn, fd, ft))
def update_material(mid, cat, tit, con, yt, fn, fd, ft):
    if fd: run_query("UPDATE materials SET category=?, title=?, content=?, youtube_url=?, file_name=?, file_data=?, file_type=? WHERE id=?", (cat, tit, con, yt, fn, fd, ft, mid))
    else: run_query("UPDATE materials SET category=?, title=?, content=?, youtube_url=? WHERE id=?", (cat, tit, con, yt, mid))
def delete_material(mid): run_query("DELETE FROM materials WHERE id=?", (mid,))

def get_exams():
    rows = run_query("SELECT * FROM exams")
    formatted = []
    for r in rows:
        # Bersihkan opsi kosong/None
        raw_opsi = [r['opt_a'], r['opt_b'], r['opt_c'], r['opt_d'], r['opt_e']]
        raw_imgs = [r['opt_a_img'], r['opt_b_img'], r['opt_c_img'], r['opt_d_img'], r['opt_e_img']]
        valid_opsi, valid_imgs = [], []
        for i in range(len(raw_opsi)):
            if raw_opsi[i] and str(raw_opsi[i]).strip() != "":
                valid_opsi.append(raw_opsi[i]); valid_imgs.append(raw_imgs[i])
        formatted.append({
            "id": r['id'], "category": r['category'], 
            "sub_category": r['sub_category'] if 'sub_category' in r and r['sub_category'] else "Umum", 
            "tanya": r['question'], "q_img": r['q_image'], 
            "opsi": valid_opsi, "opsi_img": valid_imgs, "jawaban": r['answer']
        })
    return formatted

def get_exam_by_id(eid): 
    res = run_query("SELECT * FROM exams WHERE id = ?", (eid,))
    return res[0] if res else None

def add_exam(cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans):
    # Pastikan None jika string kosong untuk D dan E
    od = None if not od or str(od).strip() == "" else od
    oe = None if not oe or str(oe).strip() == "" else oe
    run_query('''INSERT INTO exams (category, sub_category, question, q_image, opt_a, opt_a_img, opt_b, opt_b_img, opt_c, opt_c_img, opt_d, opt_d_img, opt_e, opt_e_img, answer) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''', 
              (cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans))

def update_exam_data(eid, cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans):
    od = None if not od or str(od).strip() == "" else od
    oe = None if not oe or str(oe).strip() == "" else oe
    run_query("""UPDATE exams SET category=?, sub_category=?, question=?, q_image=?, opt_a=?, opt_a_img=?, opt_b=?, opt_b_img=?, opt_c=?, opt_c_img=?, opt_d=?, opt_d_img=?, opt_e=?, opt_e_img=?, answer=? WHERE id=?""", 
              (cat, sub, q, qi, oa, oai, ob, obi, oc, oci, od, odi, oe, oei, ans, eid))

def delete_exam_data(eid): run_query("DELETE FROM exams WHERE id=?", (eid,))
def delete_all_exams_in_category(cat): run_query("DELETE FROM exams WHERE category=?", (cat,))

def set_schedule(cat, op, cl, dur, mx): run_query("REPLACE INTO exam_schedules (category, open_time, close_time, duration_minutes, max_attempts) VALUES (?, ?, ?, ?, ?)", (cat, op, cl, dur, mx))
def get_schedule(cat): 
    res = run_query("SELECT * FROM exam_schedules WHERE category = ?", (cat,))
    return res[0] if res else None

def start_student_exam(name, cat): run_query("INSERT INTO student_exam_attempts (student_name, category, start_time) VALUES (?, ?, ?)", (name, cat, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
def get_student_attempt(name, cat): 
    res = run_query("SELECT start_time FROM student_exam_attempts WHERE student_name=? AND category=?", (name, cat))
    return res[0] if res else None
def get_all_student_attempts(name): return run_query("SELECT category, start_time FROM student_exam_attempts WHERE student_name=?", (name,))

def clear_student_attempt(name, cat):
    run_query("DELETE FROM student_exam_attempts WHERE student_name=? AND category=?", (name, cat))
    run_query("DELETE FROM student_answers_temp WHERE student_name=? AND category=?", (name, cat))

def save_temp_answer(name, cat, qid, ans, doubt):
    val = 1 if doubt else 0
    run_query("REPLACE INTO student_answers_temp (student_name, category, question_id, answer, is_doubtful) VALUES (?, ?, ?, ?, ?)", (name, cat, qid, ans, val))

def get_temp_answers_full(name, cat):
    rows = run_query("SELECT question_id, answer, is_doubtful FROM student_answers_temp WHERE student_name=? AND category=?", (name, cat))
    result = {}
    for r in rows: result[r['question_id']] = {'answer': r['answer'], 'doubt': bool(r['is_doubtful'])}
    return result

def get_student_result_count(name, cat): 
    res = run_query("SELECT count(*) as cnt FROM results WHERE student_name=? AND category=?", (name, cat))
    return res[0]['cnt'] if res else 0
def add_result(name, cat, sc, tot, dt): run_query("INSERT INTO results (student_name, category, score, total_questions, date) VALUES (?, ?, ?, ?, ?)", (name, cat, sc, tot, dt))
def get_results(): return pd.DataFrame(run_query("SELECT * FROM results"))
def get_latest_student_result(name, cat): 
    res = run_query("SELECT * FROM results WHERE student_name=? AND category=? ORDER BY id DESC LIMIT 1", (name, cat))
    return res[0] if res else None

def add_banner(typ, cont, img): run_query("INSERT INTO banners (type, content, image_data, created_at) VALUES (?, ?, ?, ?)", (typ, cont, img, datetime.now().strftime("%Y-%m-%d")))
def get_banners(): return run_query("SELECT * FROM banners ORDER BY id DESC")
def delete_banner(bid): run_query("DELETE FROM banners WHERE id=?", (bid,))

# ==========================================
# 3. AUTH & SESSION
# ==========================================
if 'current_user' not in st.session_state: st.session_state['current_user'] = None
if 'admin_active_category' not in st.session_state: st.session_state['admin_active_category'] = None
if 'edit_target_user' not in st.session_state: st.session_state['edit_target_user'] = None
if 'edit_q_id' not in st.session_state: st.session_state['edit_q_id'] = None
if 'selected_exam_cat' not in st.session_state: st.session_state['selected_exam_cat'] = None
if 'edit_material_id' not in st.session_state: st.session_state['edit_material_id'] = None

def check_session_persistence():
    if st.session_state['current_user'] is None and "u_id" in st.query_params:
        user_data = get_user(st.query_params["u_id"])
        if user_data: st.session_state['current_user'] = {"username": user_data['username'], "role": user_data['role'], "name": user_data['name']}
    if "cat" in st.query_params:
        st.session_state['selected_exam_cat'] = st.query_params["cat"]

def input_callback(q_id, category):
    user_name = st.session_state['current_user']['name']
    radio_key = f"q_{q_id}"; check_key = f"chk_{q_id}"
    selected_val = st.session_state.get(radio_key); is_doubt = st.session_state.get(check_key, False)
    save_temp_answer(user_name, category, q_id, selected_val, is_doubt)

def login_page():
    st.write("")
    st.write("")
    st.write("")
    c1, c2, c3 = st.columns([1, 1.5, 1])
    with c2:
        with st.form("login_form", clear_on_submit=False):
            st.markdown("""
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="font-size: 50px;">🎓</div>
                <h2 style="margin: 0; padding:0;">Lulusin</h2>
                <p style="opacity: 0.7; font-size: 14px; margin-top: 5px;">Silakan masuk untuk melanjutkan</p>
            </div>
            """, unsafe_allow_html=True)
            user = st.text_input("Username", placeholder="Masukkan username")
            pwd = st.text_input("Password", type="password", placeholder="Masukkan password")
            st.write("")
            submitted = st.form_submit_button("Masuk", type="primary", use_container_width=True)
            if submitted:
                data = get_user(user)
                if data and data['password'] == pwd:
                    st.session_state['current_user'] = {"username": data['username'], "role": data['role'], "name": data['name']}
                    st.query_params["u_id"] = user
                    st.rerun()
                else: st.error("Username atau Password salah")

def logout_button():
    if st.sidebar.button("🚪 Keluar", type="primary"):
        st.session_state['current_user'] = None
        for key in ['edit_q_id', 'edit_material_id', 'selected_exam_cat']:
            st.session_state[key] = None
        st.query_params.clear()
        st.rerun()

# ==========================================
# 4. KOMPONEN UI
# ==========================================

def display_timer_js(end_time_str):
    html_code = f"""
    <div style="position:fixed; top:0; left:0; width:100%; background:#ff4b4b; color:white; text-align:center; padding:12px; font-size:20px; font-weight:bold; z-index:99999; box-shadow: 0 2px 5px rgba(0,0,0,0.2);">
        ⏱️ Sisa Waktu: <span id="timer">Loading...</span>
    </div>
    <script>
        var end = new Date("{end_time_str.replace(" ", "T")}").getTime();
        var x = setInterval(function() {{
            var now = new Date().getTime();
            var dist = end - now;
            var m = Math.floor((dist % (1000 * 60 * 60)) / (1000 * 60));
            var s = Math.floor((dist % (1000 * 60)) / 1000);
            document.getElementById("timer").innerHTML = m + "m " + s + "s ";
            if (dist < 0) {{
                clearInterval(x);
                document.getElementById("timer").innerHTML = "WAKTU HABIS!";
                window.parent.location.reload(); 
            }}
        }}, 1000);
    </script>
    """
    components.html(html_code, height=55)

@st.dialog("🎉 Hasil Ujian", width="small")
def show_result_popup(score, correct, total, category):
    st.balloons()
    st.markdown(f"""
    <div style='text-align: center; padding: 20px;'>
        <h4 style='margin:0; opacity:0.7;'>Hasil Ujian</h4>
        <h2 style='margin:0;'>{category}</h2>
        <h1 style='color: #27ae60; font-size: 72px; margin: 10px 0;'>{score:.1f}</h1>
        <div style='background:rgba(128,128,128,0.1); padding:10px; border-radius:8px;'>
            ✅ Benar: <b>{int(correct)}</b> / {total} Soal
        </div>
    </div>
    """, unsafe_allow_html=True)
    if st.button("Tutup & Kembali ke Menu", use_container_width=True, type="primary"):
        if "exam_done" in st.query_params: del st.query_params["exam_done"]
        if "cat" in st.query_params: del st.query_params["cat"]
        st.session_state['selected_exam_cat'] = None
        st.rerun()

def display_banner_carousel():
    banners = get_banners()
    if not banners: return

    slides_html = ""
    for idx, b in enumerate(banners):
        b_type = b['type']; content = b['content']; img_blob = b['image_data']
        display_style = "block" if idx == 0 else "none"
        if b_type == 'image' and img_blob:
            b64_img = base64.b64encode(img_blob).decode()
            slides_html += f"""<div class="mySlides fade" style="display:{display_style};"><img src="data:image/png;base64,{b64_img}" style="width:100%;height:300px;object-fit:cover;border-radius:10px;box-shadow:0 4px 6px rgba(0,0,0,0.1);"></div>"""
        else:
            slides_html += f"""<div class="mySlides fade" style="display:{display_style};">{content}</div>"""

    carousel_code = f"""
    <style>
    .slideshow-container {{ max-width: 100%; position: relative; margin: auto; }}
    .fade {{ animation-name: fade; animation-duration: 1.5s; }}
    @keyframes fade {{ from {{opacity: .4}} to {{opacity: 1}} }}
    </style>
    <div class="slideshow-container"> {slides_html} </div>
    <script>
    let slideIndex = 0; showSlides();
    function showSlides() {{
      let i; let slides = document.getElementsByClassName("mySlides");
      for (i = 0; i < slides.length; i++) {{ slides[i].style.display = "none"; }}
      slideIndex++;
      if (slideIndex > slides.length) {{slideIndex = 1}}    
      slides[slideIndex-1].style.display = "block";  
      setTimeout(showSlides, 5000); 
    }}
    </script>
    """
    components.html(carousel_code, height=310)

# ==========================================
# 5. DASHBOARD ADMIN
# ==========================================
def admin_dashboard():
    st.title("👨‍🏫 Dashboard Admin")
    
    # METRICS SUMMARY
    users = get_all_users()
    exams = get_exams()
    mats = get_materials()
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Pengguna", len(users))
    c2.metric("Total Soal", len(exams))
    c3.metric("Materi Aktif", len(mats))
    
    st.write("")
    
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📚 Materi", "📝 Bank Soal", "📢 Info & Banner", "📊 Nilai", "👥 User"])
    
    # TAB 1: MATERI
    with tab1:
        if st.session_state['edit_material_id']:
            mat_data = get_material_by_id(st.session_state['edit_material_id'])
            if mat_data:
                st.info(f"✏️ Edit Materi: {mat_data['title']}")
                with st.form("edit_materi_form"):
                    col_a, col_b = st.columns(2)
                    with col_a:
                        e_cat = st.text_input("Kategori", value=mat_data['category'])
                        e_tit = st.text_input("Judul", value=mat_data['title'])
                        e_yt = st.text_input("YouTube URL", value=mat_data['youtube_url'])
                    with col_b:
                        e_con = st.text_area("Isi Materi", value=mat_data['content'], height=150)
                        e_file = st.file_uploader("Ganti File (Opsional)")
                    
                    if st.form_submit_button("💾 Simpan Perubahan", type="primary"):
                        fn, fd, ft = (e_file.name, e_file.getvalue(), e_file.type) if e_file else (None, None, None)
                        update_material(mat_data['id'], e_cat, e_tit, e_con, e_yt, fn, fd, ft)
                        st.session_state['edit_material_id'] = None; st.success("Updated!"); st.rerun()
                    if st.form_submit_button("❌ Batal"):
                        st.session_state['edit_material_id'] = None; st.rerun()
        else:
            with st.expander("➕ Tambah Materi Baru"):
                with st.form("add_mat_form", clear_on_submit=True):
                    ca, cb = st.columns(2)
                    with ca:
                        cat = st.text_input("Kategori")
                        tit = st.text_input("Judul")
                        yt = st.text_input("YouTube URL")
                    with cb:
                        con = st.text_area("Isi Materi")
                        f = st.file_uploader("File Pendukung")
                    if st.form_submit_button("Simpan Materi", type="primary"):
                        fn, fd, ft = (f.name, f.getvalue(), f.type) if f else (None, None, None)
                        add_material(cat, tit, con, yt, fn, fd, ft); st.success("Tersimpan!"); st.rerun()
            
            st.write("### Daftar Materi")
            df_mat = get_materials()
            if not df_mat.empty:
                c1, c2, c3, c4 = st.columns([2, 4, 1, 1])
                c1.markdown("**Kategori**"); c2.markdown("**Judul**")
                st.divider()
                for i, row in df_mat.iterrows():
                    with st.container():
                        c1, c2, c3, c4 = st.columns([2, 4, 1, 1])
                        c1.write(row['category']); c2.write(row['title'])
                        if c3.button("✏️", key=f"edm_{row['id']}"): st.session_state['edit_material_id'] = row['id']; st.rerun()
                        if c4.button("🗑️", key=f"delm_{row['id']}"): delete_material(row['id']); st.success("Deleted"); st.rerun()
            else: st.info("Belum ada materi.")

    # TAB 2: SOAL
    with tab2:
        if not st.session_state['admin_active_category']:
            st.info("Pilih kategori ujian.")
            cats = sorted(list(set([e['category'] for e in get_exams()])))
            c_sel1, c_sel2 = st.columns(2)
            with c_sel1: pc = st.selectbox("Pilih Kategori", ["--"]+cats)
            with c_sel2: ic = st.text_input("Buat Kategori Baru")
            if st.button("Kelola Kategori", type="primary"): 
                st.session_state['admin_active_category'] = ic if ic else (pc if pc!="--" else None); st.rerun()
        else:
            ac = st.session_state['admin_active_category']
            c_head1, c_head2 = st.columns([4, 1])
            c_head1.markdown(f"### 📂 {ac}")
            if c_head2.button("⬅️ Kembali"): st.session_state['admin_active_category']=None; st.rerun()
            
            with st.expander("📅 Pengaturan Jadwal", expanded=False):
                sch = get_schedule(ac)
                d_s, d_e = datetime.now().date(), datetime.now().date()
                t_op, t_cl = datetime.now().time(), (datetime.now()+timedelta(hours=4)).time()
                d_dur, d_max = 60, 1
                if sch:
                    try:
                        od = datetime.strptime(sch['open_time'], "%Y-%m-%d %H:%M:%S")
                        cd = datetime.strptime(sch['close_time'], "%Y-%m-%d %H:%M:%S")
                        d_s, d_e, t_op, t_cl, d_dur, d_max = od.date(), cd.date(), od.time(), cd.time(), sch['duration_minutes'], sch['max_attempts']
                    except: pass
                
                with st.form("sch_form"):
                    c1, c2 = st.columns(2)
                    dr = c1.date_input("Rentang Tanggal", [d_s, d_e])
                    c3, c4 = st.columns(2)
                    top = c3.time_input("Jam Buka", t_op); tcl = c4.time_input("Jam Tutup", t_cl)
                    c5, c6 = st.columns(2)
                    du = c5.number_input("Durasi (Menit)", value=d_dur); mx = c6.number_input("Max Attempt", value=d_max)
                    
                    if st.form_submit_button("Simpan Jadwal"):
                        s_d = dr[0]; e_d = dr[1] if len(dr)>1 else dr[0]
                        fo = datetime.combine(s_d, top).strftime("%Y-%m-%d %H:%M:%S")
                        fc = datetime.combine(e_d, tcl).strftime("%Y-%m-%d %H:%M:%S")
                        if fc <= fo: st.error("Waktu tutup salah!")
                        else: set_schedule(ac, fo, fc, du, mx); st.success("Tersimpan!")

            st.write("")
            
            if st.session_state['edit_q_id']:
                q_data = get_exam_by_id(st.session_state['edit_q_id'])
                if q_data:
                    st.info(f"✏️ Edit Soal ID: {q_data['id']}")
                    with st.form("edit_q_form"):
                        e_sub = st.text_input("Sub Kategori", value=q_data['sub_category'])
                        e_q = st.text_area("Pertanyaan", value=q_data['question'])
                        c_opt1, c_opt2 = st.columns(2)
                        with c_opt1:
                            oa = st.text_input("A", value=q_data['opt_a']); ob = st.text_input("B", value=q_data['opt_b']); oc = st.text_input("C", value=q_data['opt_c'])
                        with c_opt2:
                            od = st.text_input("D", value=q_data['opt_d'] or ""); oe = st.text_input("E", value=q_data['opt_e'] or ""); ans = st.text_input("Kunci", value=q_data['answer'])
                        
                        if st.form_submit_button("Simpan"):
                            update_exam_data(q_data['id'], ac, e_sub, e_q, q_data['q_image'], oa, None, ob, None, oc, None, od, None, oe, None, ans)
                            st.session_state['edit_q_id'] = None; st.rerun()
                        if st.form_submit_button("Batal"): st.session_state['edit_q_id'] = None; st.rerun()
            else:
                t_man, t_imp = st.tabs(["📝 Tambah Manual", "📤 Import Excel"])
                with t_man:
                    with st.form("add_q_form", clear_on_submit=True):
                        sub = st.text_input("Sub Kategori", "Umum"); q = st.text_area("Pertanyaan")
                        c_o1, c_o2 = st.columns(2)
                        with c_o1:
                            oa = st.text_input("Opsi A"); ob = st.text_input("Opsi B"); oc = st.text_input("Opsi C")
                        with c_o2:
                            od = st.text_input("Opsi D"); oe = st.text_input("Opsi E"); ans = st.text_input("Kunci Jawaban")
                        if st.form_submit_button("Simpan Soal"):
                            add_exam(ac, sub, q, None, oa, None, ob, None, oc, None, od, None, oe, None, ans); st.success("OK"); st.rerun()
                
                with t_imp:
                    st.info("Format: Sub Kategori, Pertanyaan, Opsi A, Opsi B, Opsi C, Opsi D, Opsi E, Jawaban Benar")
                    s_data = [{"Sub Kategori": "Logika", "Pertanyaan": "...", "Opsi A": "A", "Opsi B": "B", "Opsi C": "C", "Opsi D": "", "Opsi E": "", "Jawaban Benar": "A"}]
                    df_t = pd.DataFrame(s_data)
                    buf = io.BytesIO(); 
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer: df_t.to_excel(writer, index=False)
                    st.download_button("⬇️ Template Excel", data=buf.getvalue(), file_name="template.xlsx", mime="application/vnd.ms-excel")
                    
                    uf = st.file_uploader("Upload Excel", type=['xlsx'])
                    if uf and st.button("Proses Import"):
                        try:
                            df_u = pd.read_excel(uf)
                            for _, r in df_u.iterrows():
                                def cln(v): return str(v).strip() if pd.notna(v) and str(v).strip()!="" else None
                                add_exam(ac, cln(r["Sub Kategori"]), cln(r["Pertanyaan"]), None, cln(r["Opsi A"]), None, cln(r["Opsi B"]), None, cln(r["Opsi C"]), None, cln(r["Opsi D"]), None, cln(r["Opsi E"]), None, cln(r["Jawaban Benar"]))
                            st.success("Import Berhasil!"); time.sleep(1); st.rerun()
                        except Exception as e: st.error(f"Error: {e}")

            st.divider()
            c_list1, c_list2 = st.columns([4,1])
            c_list1.write("### Daftar Soal")
            if c_list2.button("🗑️ Hapus Semua", type="primary"): delete_all_exams_in_category(ac); st.rerun()
            
            exams = [e for e in get_exams() if e['category']==ac]
            if exams:
                for ex in exams:
                    with st.container():
                        c_row1, c_row2, c_row3 = st.columns([6, 1, 1])
                        c_row1.markdown(f"**[{ex['sub_category']}]** {ex['tanya'][:80]}...")
                        if c_row2.button("✏️", key=f"eq_{ex['id']}"): st.session_state['edit_q_id'] = ex['id']; st.rerun()
                        if c_row3.button("🗑️", key=f"dq_{ex['id']}"): delete_exam_data(ex['id']); st.rerun()
                        st.markdown("---")
            else: st.info("Kosong.")

    # TAB 3: BANNER
    with tab3:
        col_b1, col_b2 = st.columns([1, 1])
        with col_b1:
            st.markdown("#### Preview Banner")
            b_type = st.radio("Tipe", ["Teks Custom", "Gambar"], horizontal=True)
            final_html, final_img = None, None
            
            if b_type == "Teks Custom":
                with st.expander("⚙️ Settings"):
                    bg = st.color_picker("Background", "#1e3c72"); txt = st.color_picker("Text", "#ffffff")
                    sz = st.slider("Size", 10, 50, 24); fm = st.selectbox("Font", ["Arial", "Verdana"])
                raw_txt = st.text_area("Isi Teks", "Info Penting!")
                final_html = f"""<div style="width:100%; height:300px; background-color:{bg}; color:{txt}; font-family:{fm}; font-size:{sz}px; display:flex; align-items:center; justify-content:center; text-align:center; padding:20px; border-radius:10px;"><div>{raw_txt.replace(chr(10), '<br>')}</div></div>"""
                st.markdown(final_html, unsafe_allow_html=True)
            else:
                up = st.file_uploader("Gambar")
                if up: final_img = up.getvalue(); st.image(up)
            
            if st.button("🚀 Publish Banner", type="primary"):
                add_banner('image' if b_type=="Gambar" else 'text', final_html, final_img); st.success("OK"); st.rerun()

        with col_b2:
            st.markdown("#### Banner Aktif")
            bans = get_banners()
            for b in bans:
                with st.container():
                    c1, c2 = st.columns([4, 1])
                    if b['type']=='text': c1.caption("Teks Banner")
                    else: c1.image(b['image_data'], width=100)
                    if c2.button("🗑️", key=f"db_{b['id']}"): delete_banner(b['id']); st.rerun()
                    st.divider()

    # TAB 4: NILAI
    with tab4:
        df = get_results()
        if not df.empty:
            c1, c2 = st.columns(2)
            c1.metric("Total Ujian Masuk", len(df))
            c2.metric("Rata-rata Nilai", f"{df['score'].mean():.1f}")
            st.divider()
            st.dataframe(df, use_container_width=True)
        else: st.info("Belum ada data nilai.")

    # TAB 5: USER
    with tab5:
        dfu = get_all_users()
        c1, c2, c3 = st.columns(3)
        c1.metric("Total User", len(dfu))
        c2.metric("Admin", len(dfu[dfu['role']=='admin']))
        c3.metric("Siswa", len(dfu[dfu['role']=='student']))
        st.write("")
        
        with st.expander("➕ Tambah User Baru"):
            with st.form("add_user"):
                c1, c2 = st.columns(2)
                u = c1.text_input("Username"); p = c2.text_input("Password", type="password")
                n = c1.text_input("Nama Lengkap"); r = c2.selectbox("Role", ["student", "admin"])
                if st.form_submit_button("Tambah"): add_user(u,p,r,n); st.rerun()
        
        st.dataframe(dfu, use_container_width=True)

# ==========================================
# 6. DASHBOARD STUDENT
# ==========================================
def student_dashboard():
    user = st.session_state['current_user']
    
    # Auto Check Time Logic
    attempts = get_all_student_attempts(user['name'])
    all_qs = get_exams()
    for att in attempts:
        cat = att['category']; sch = get_schedule(cat)
        if sch:
            dead = datetime.strptime(att['start_time'], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=sch['duration_minutes'])
            if datetime.now() > dead:
                raw = [e for e in all_qs if e['category'] == cat]
                ans_data = get_temp_answers_full(user['name'], cat)
                score = 0
                for s in raw:
                    if ans_data.get(s['id'], {}).get('answer') == s['jawaban']: score += 1
                val = (score/len(raw))*100 if len(raw) > 0 else 0
                add_result(user['name'], cat, val, len(raw), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                clear_student_attempt(user['name'], cat)
                st.query_params["exam_done"]="true"; st.query_params["cat"]=cat; st.query_params["u_id"]=user['username']; st.rerun()

    st.markdown(f"### 👋 Selamat Datang, **{user['name']}**")
    display_banner_carousel()
    st.write("")

    tab1, tab2, tab3 = st.tabs(["📚 Materi Pelajaran", "📝 Ujian & Kuis", "🏆 Rapor Nilai"])

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

    # TAB UJIAN (GRID)
    with tab2:
        cats = sorted(list(set([e['category'] for e in all_qs])))
        
        if st.session_state['selected_exam_cat'] is None:
            if not cats: st.info("Belum ada ujian aktif.")
            else:
                cols = st.columns(3)
                for i, cat in enumerate(cats):
                    sch = get_schedule(cat)
                    stat_txt = "Tersedia"; stat_col = "#27ae60"
                    if sch:
                        od = datetime.strptime(sch['open_time'], "%Y-%m-%d %H:%M:%S")
                        cd = datetime.strptime(sch['close_time'], "%Y-%m-%d %H:%M:%S")
                        if datetime.now() < od: stat_txt = "Belum Buka"; stat_col = "#e67e22"
                        elif datetime.now() > cd: stat_txt = "Ditutup"; stat_col = "#c0392b"
                    
                    with cols[i%3]:
                        with st.container(border=True):
                            st.markdown(f"<div class='exam-card-header'>📝 {cat}</div>", unsafe_allow_html=True)
                            st.markdown(f"<div class='exam-card-info' style='color:{stat_col}'>{stat_txt}</div>", unsafe_allow_html=True)
                            if st.button("Buka Soal", key=f"op_{cat}", use_container_width=True):
                                st.session_state['selected_exam_cat'] = cat; st.query_params["cat"] = cat; st.rerun()
        else:
            pcat = st.session_state['selected_exam_cat']
            c1, c2 = st.columns([1, 6])
            if c1.button("⬅️ Kembali"): 
                st.session_state['selected_exam_cat'] = None
                if "cat" in st.query_params: del st.query_params["cat"]
                st.rerun()
            c2.markdown(f"### 📝 Pengerjaan: {pcat}")
            
            sch = get_schedule(pcat); show_exam = False; trigger_submit = False
            if sch:
                odt = datetime.strptime(sch['open_time'], "%Y-%m-%d %H:%M:%S")
                cdt = datetime.strptime(sch['close_time'], "%Y-%m-%d %H:%M:%S")
                dur = sch['duration_minutes']
                lim = sch['max_attempts']
                cnt = get_student_result_count(user['name'], pcat)
                att = get_student_attempt(user['name'], pcat)
                now = datetime.now()

                if att:
                    dead = datetime.strptime(att['start_time'], "%Y-%m-%d %H:%M:%S") + timedelta(minutes=dur)
                    if (dead - now).total_seconds() <= 0: trigger_submit = True
                    else:
                        display_timer_js(dead.strftime("%Y-%m-%d %H:%M:%S"))
                        show_exam = True
                else:
                    st.info(f"Riwayat Percobaan: {cnt}/{lim}")
                    if cnt >= lim: st.error("Kesempatan ujian habis.")
                    elif now < odt: st.warning(f"Ujian dibuka pada: {odt}")
                    elif now > cdt: st.error("Ujian sudah ditutup.")
                    else:
                        if st.button("🚀 MULAI UJIAN", type="primary"):
                            start_student_exam(user['name'], pcat); st.rerun()
            else:
                st.info("Mode Latihan (Tanpa Batas Waktu)"); show_exam = True

            if show_exam:
                raw = [e for e in all_qs if e['category']==pcat]
                saved_data = get_temp_answers_full(user['name'], pcat)
                
                with st.sidebar:
                    st.write("### 🧭 Navigasi Soal")
                    grid_html = '<div style="display: grid; grid-template-columns: repeat(5, 1fr); gap: 5px;">'
                    for i, q in enumerate(raw):
                        d = saved_data.get(q['id'], {})
                        bg = "#95a5a6"
                        if d.get('answer'): bg = "#f1c40f" if d.get('doubt') else "#27ae60"
                        grid_html += f'<div class="nav-box" style="background-color:{bg}">{i+1}</div>'
                    grid_html += '</div>'
                    st.markdown(grid_html, unsafe_allow_html=True)
                    st.caption("Hijau: Dijawab | Kuning: Ragu")

                curr_sub = None
                for idx, s in enumerate(raw):
                    if s['sub_category'] != curr_sub:
                        st.markdown(f"#### 📑 {s['sub_category']}"); st.markdown("---"); curr_sub = s['sub_category']
                    
                    st.markdown(f"<div class='question-container'><b>Soal {idx+1}:</b><br>{s['tanya']}</div>", unsafe_allow_html=True)
                    if s['q_img'] and isinstance(s['q_img'], bytes): st.image(s['q_img'], width=400)
                    
                    if len(s['opsi']) > 0:
                        cols = st.columns(len(s['opsi']))
                        for i, c in enumerate(cols):
                            with c: 
                                if s['opsi_img'][i] and isinstance(s['opsi_img'][i], bytes): st.image(s['opsi_img'][i], width=100)
                    
                    cur_d = saved_data.get(s['id'], {})
                    c1, c2 = st.columns([4, 1])
                    with c1: st.radio(f"Jawab {idx+1}", s['opsi'], key=f"q_{s['id']}", index=s['opsi'].index(cur_d.get('answer')) if cur_d.get('answer') in s['opsi'] else None, on_change=input_callback, args=(s['id'], pcat), label_visibility="collapsed")
                    with c2: st.checkbox("Ragu", value=cur_d.get('doubt', False), key=f"chk_{s['id']}", on_change=input_callback, args=(s['id'], pcat))

                st.divider()
                if st.button("✅ KIRIM SEMUA JAWABAN", type="primary", use_container_width=True): trigger_submit = True

            if trigger_submit:
                raw = [e for e in all_qs if e['category']==pcat]
                final = get_temp_answers_full(user['name'], pcat)
                score = 0
                for s in raw:
                    if final.get(s['id'], {}).get('answer') == s['jawaban']: score += 1
                val = (score/len(raw))*100 if len(raw)>0 else 0
                add_result(user['name'], pcat, val, len(raw), datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                clear_student_attempt(user['name'], pcat)
                st.session_state['selected_exam_cat'] = None
                st.query_params["exam_done"]="true"; st.query_params["cat"]=pcat; st.query_params["u_id"]=user['username']; st.rerun()

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
