import streamlit as st
import streamlit.components.v1 as components
import html as html_lib
import asyncio
import os
import re
import json
import requests
from bs4 import BeautifulSoup
import subprocess
import shutil
import edge_tts
import time
from datetime import datetime
HISTORY_FILE = "processed_urls.json"
GITHUB_REPO = "danielnguyen241/tatinta-audio-tool"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{HISTORY_FILE}"
def _get_github_token():
    try:
        return st.secrets.get("GITHUB_TOKEN", "")
    except:
        return os.environ.get("GITHUB_TOKEN", "")
def load_history():
    gh_token = _get_github_token()
    try:
        headers = {"Accept": "application/vnd.github.v3+json"}
        if gh_token:
            headers["Authorization"] = f"token {gh_token}"
        resp = requests.get(GITHUB_API_URL, headers=headers, timeout=5)
        if resp.status_code == 200:
            import base64
            content = base64.b64decode(resp.json()["content"]).decode("utf-8")
            return json.loads(content)
    except:
        pass
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}
def save_to_history(dest_id, title, audio_vi=None, audio_en=None):
    history = load_history()
    history[dest_id] = {
        "title": title,
        "ran_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "audio_vi": audio_vi,
        "audio_en": audio_en
    }
    json_str = json.dumps(history, ensure_ascii=False, indent=2)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        f.write(json_str)
    gh_token = _get_github_token()
    if gh_token:
        try:
            import base64
            headers = {
                "Authorization": f"token {gh_token}",
                "Accept": "application/vnd.github.v3+json"
            }
            get_resp = requests.get(GITHUB_API_URL, headers=headers, timeout=5)
            sha = get_resp.json().get("sha") if get_resp.status_code == 200 else None
            payload = {
                "message": f"Update history: {dest_id} - {title[:30]}",
                "content": base64.b64encode(json_str.encode("utf-8")).decode("utf-8"),
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha
            requests.put(GITHUB_API_URL, headers=headers, json=payload, timeout=10)
        except:
            pass
st.set_page_config(page_title="Tatinta Audio Automator", page_icon="🎙️", layout="wide")
st.title("🎙️ Hệ Thống Tự Động Thu Âm & Ghép Nhạc Tatinta CMS")
# ================= TABS =================
tab_auto, tab_manual = st.tabs(["🚀 Tự Động Theo URL (Batch)", "✍️ Tạo Audio Tay"])
# ================= STATS =================
@st.fragment(run_every=30)
def show_stats():
    _hist = load_history()
    _total = len(_hist)
    _has_vi = sum(1 for v in _hist.values() if v.get("audio_vi"))
    _has_en = sum(1 for v in _hist.values() if v.get("audio_en"))
    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    col_s1.metric("🎤 Tổng URL đã có Audio", _total)
    col_s2.metric("🇻🇳 Có Audio Tiếng Việt", _has_vi)
    col_s3.metric("🇺🇸 Có Audio Tiếng Anh", _has_en)
    col_s4.metric("📋 Chưa xử lý", "?", help="Dán URL vào để xem")
show_stats()
st.markdown("---")
# ================= XÁC THỰC (dùng chung 2 tab) =================
st.subheader("🔑 1. Xác thực (Bearer Token)")
TOKEN_FILE = "saved_token.txt"
if os.path.exists(TOKEN_FILE):
    with open(TOKEN_FILE, "r") as f:
        default_token = f.read().strip()
else:
    default_token = ""
token = st.text_input("Dán chuỗi Token (bắt đầu bằng eyJ) vào đây:", value=default_token, type="password")
if token and token != default_token and len(token) > 50:
    with open(TOKEN_FILE, "w") as f:
        f.write(token.strip())
    st.success("✅ Đã tự động Trữ đông Token dùng chung cho toàn bộ Team rồi nha Sếp!")
with st.expander("Cách lấy Token (F12)"):
    st.markdown("""
    1. Vào trang cms.tatinta.com.
    2. Ấn **F12** (hoặc chuột phải -> Inspect).
    3. Sang tab **Console**.
    4. Dán nguyên lệnh này vào và Ấn Enter:
    ```javascript
    (function(){const r=/eyJ[a-zA-Z0-9\\-_]+\\.[a-zA-Z0-9\\-_]+\\.[a-zA-Z0-9\\-_]+/; let t=document.cookie.match(r); if(!t){for(let cur of [localStorage, sessionStorage]){for(let i=0; i<cur.length; i++){let k=cur.key(i); let v=cur.getItem(k); if(v && r.test(v)){t=v.match(r); break;}} if(t) break;}} if(t){prompt("Copy Token bên dưới để dán vào Tool:", t[0]);} else{alert("Không tìm thấy Token!");}})();
    ```
    """)
# ================= CẤU HÌNH VOICE (dùng chung) =================
st.subheader("⚙️ 2. Cấu hình Giọng Đọc (TTS) & Ngôn ngữ")
col1, col2 = st.columns(2)
with col1:
    run_vi = st.checkbox("✅ Tạo Tiếng Việt", value=True)
    voice_vi = st.selectbox("Giọng Tiếng Việt", ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"])
    rate_vi = st.slider("Tốc độ VI (%)", -50, 50, 5)
    pitch_vi = st.slider("Độ trầm (Hz)", -20, 20, -10)
with col2:
    run_en = st.checkbox("✅ Tạo Tiếng Anh", value=True)
    voice_en = st.selectbox("Giọng Tiếng Anh", ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-AriaNeural"])
    rate_en = st.slider("Tốc độ EN (%)", -50, 50, 0)
    pitch_en = st.slider("Độ trầm EN (Hz)", -20, 20, -2)
# ================= CẤU HÌNH NHẠC NỀN (dùng chung) =================
st.subheader("🎵 3. Cấu hình Nhạc Nền (BGM)")
bgm_upload = st.file_uploader("Upload file nhạc nền (.mp3) - Không bắt buộc", type=["mp3"])
bgm_volume_db = st.slider("Giảm Volume Nhạc Nền (dB)", -50, 0, -20)
use_bgm = True
bgm_path = "bgm_default.mp3"
if bgm_upload:
    with open("temp_bgm.mp3", "wb") as f:
        f.write(bgm_upload.getbuffer())
    bgm_path = "temp_bgm.mp3"
else:
    if not os.path.exists("bgm_default.mp3") and not os.path.exists("Hovering Thoughts - Spence.mp3"):
        st.warning("⚠️ Không tìm thấy file nhạc mặc định. Hãy upload file MP3 nếu muốn có nhạc nền.")
        use_bgm = False
    elif os.path.exists("Hovering Thoughts - Spence.mp3"):
        bgm_path = "Hovering Thoughts - Spence.mp3"
st.markdown("---")
# ================= HÀM TIỆN ÍCH =================
def fix_text_for_tts(title, raw_html):
    if not title and not raw_html: return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup.find_all(['strong', 'b', 'em', 'i', 'u', 'span', 'a', 'mark', 'small', 'sub', 'sup']):
        tag.unwrap()
    clean_content = soup.get_text(separator="\n").strip()
    text = f"{title}...\n\n{clean_content}"
    text = re.sub(r'(\d{1,2}:\d{2})\s*[–—-]\s*(\d{1,2}:\d{2})', r'\1 đến \2', text)
    ROMAN_CENTURY = {
        'XXI': 21, 'XXII': 22, 'XX': 20, 'XIX': 19, 'XVIII': 18,
        'XVII': 17, 'XVI': 16, 'XV': 15, 'XIV': 14, 'XIII': 13,
        'XII': 12, 'XI': 11, 'X': 10, 'IX': 9, 'VIII': 8,
        'VII': 7, 'VI': 6, 'V': 5, 'IV': 4, 'III': 3, 'II': 2, 'I': 1
    }
    def replace_roman_century(m):
        roman = m.group(1)
        return f"thế kỷ {ROMAN_CENTURY.get(roman, roman)}"
    text = re.sub(
        r'(?:thế kỷ\s+)?(X{0,3}(?:IX|IV|V?I{0,3}))\b',
        lambda m: replace_roman_century(m) if m.group(1) in ROMAN_CENTURY else m.group(0),
        text
    )
    text = re.sub(r'\$\s*(\d[\d\.]*)', r'\1 đô la', text)
    text = re.sub(r'€\s*(\d[\d\.]*)', r'\1 euro', text)
    text = re.sub(r'(\d[\d\.]*)\s*€', r'\1 euro', text)
    text = re.sub(r'(\d[\d\.]*)\s*\$', r'\1 đô la', text)
    text = re.sub(r'(\d+)\s*%', r'\1 phần trăm', text)
    for _ in range(3):
        text = re.sub(r'(?<=\d)\.(?=\d{3}(?:\D|$))', '', text)
    text = re.sub(r'(?<=\d)\s*km\b',    ' ki-lô-mét', text)
    text = re.sub(r'(?<=\d)\s*m²\b',    ' mét vuông', text)
    text = re.sub(r'(?<=\d)\s*m\b',     ' mét', text)
    text = re.sub(r'(?<=\d)\s*kg\b',    ' ki-lô-gam', text)
    text = re.sub(r'(?<=\d)\s*ha\b',    ' héc-ta', text)
    text = re.sub(r'(?<=\d)\s*cm\b',    ' xen-ti-mét', text)
    text = re.sub(r'(?m)^\s*\d+(?:\.\d+)*\.?\s+', '', text)
    text = re.sub(r'\s*[\u2013\u2014]\s*', ', ', text)
    text = re.sub(r'(?m)^\s*[-•·]\s+', '', text)
    text = re.sub(r' - ', ', ', text)
    for q in ['"', '\u201c', '\u201d', '\u201e', '\u201b', '\u201a',
              '«', '»', '‹', '›', "'", '\u2018', '\u2019', '`']:
        text = text.replace(q, '')
    text = re.sub(r'[*#_~`<>{}|\\\\]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'\b[A-Z]{2,}\b', lambda m: m.group(0).capitalize(), text)
    text = text.replace('<', '').replace('>', '').replace('&', ' và ')
    return text.strip()
def fix_plain_text_for_tts(title, plain_text):
    """Dùng cho tab Tạo Audio Tay — input là plain text, không có HTML"""
    if not title and not plain_text: return ""
    text = f"{title}...\n\n{plain_text.strip()}"
    text = re.sub(r'(\d{1,2}:\d{2})\s*[–—-]\s*(\d{1,2}:\d{2})', r'\1 đến \2', text)
    text = re.sub(r'\$\s*(\d[\d\.]*)', r'\1 đô la', text)
    text = re.sub(r'(\d+)\s*%', r'\1 phần trăm', text)
    for _ in range(3):
        text = re.sub(r'(?<=\d)\.(?=\d{3}(?:\D|$))', '', text)
    text = re.sub(r'(?<=\d)\s*km\b', ' ki-lô-mét', text)
    text = re.sub(r'(?<=\d)\s*m²\b', ' mét vuông', text)
    text = re.sub(r'(?<=\d)\s*m\b',  ' mét', text)
    text = re.sub(r'(?<=\d)\s*kg\b', ' ki-lô-gam', text)
    text = re.sub(r'(?<=\d)\s*ha\b', ' héc-ta', text)
    text = re.sub(r'(?<=\d)\s*cm\b', ' xen-ti-mét', text)
    text = re.sub(r'\s*[\u2013\u2014]\s*', ', ', text)
    text = re.sub(r'(?m)^\s*[-•·]\s+', '', text)
    text = re.sub(r' - ', ', ', text)
    for q in ['"', '\u201c', '\u201d', "'", '\u2018', '\u2019', '`', '«', '»']:
        text = text.replace(q, '')
    text = re.sub(r'[*#_~`<>{}|\\\\]', '', text)
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.replace('<', '').replace('>', '').replace('&', ' và ')
    return text.strip()
def upload_audio_to_storage(file_path, tok):
    url = 'https://api.tatinta.com/v1/extra/upload/audio'
    tok_clean = tok.strip().strip('"').strip("'")
    tok_clean = tok_clean.encode('ascii', 'ignore').decode('ascii')
    headers = {
        'Origin': 'https://cms.tatinta.com',
        'Referer': 'https://cms.tatinta.com/',
        'Accept': 'application/json, text/plain, */*',
        'Authorization': f'Bearer {tok_clean}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    with open(file_path, 'rb') as f:
        resp = requests.post(url, headers=headers, files={'faudio': (os.path.basename(file_path), f, 'audio/mpeg')})
    if resp.status_code in [200, 201]:
        return resp.json().get('data', {}).get('filename')
    raise Exception(f"Upload API lỗi HTTP {resp.status_code}: {resp.text[:200]}")
def save_file_to_permanent(tmp_filename, tok):
    url = 'https://api.tatinta.com/v1/extra/upload/save-file'
    tok_clean = tok.strip().strip('"').strip("'")
    tok_clean = tok_clean.encode('ascii', 'ignore').decode('ascii')
    headers = {
        'Origin': 'https://cms.tatinta.com',
        'Referer': 'https://cms.tatinta.com/',
        'Accept': 'application/json, text/plain, */*',
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {tok_clean}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }
    payload = {"filename": tmp_filename, "type": "audio"}
    resp = requests.post(url, headers=headers, json=payload)
    if resp.status_code in [200, 201]:
        return resp.json().get('data', {}).get('url')
    return tmp_filename
def mix_audio(tts_file, bgm_file, output_file, db_reduce):
    if bgm_file and os.path.exists(bgm_file):
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", tts_file,
                "-stream_loop", "-1", "-i", bgm_file,
                "-filter_complex", f"[1:a]volume={-abs(db_reduce)}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2",
                "-c:a", "libmp3lame", "-b:a", "128k",
                output_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    shutil.copy2(tts_file, output_file)
# ================= SESSION STATE =================
if "app_state" not in st.session_state:
    st.session_state.app_state = {"waiting": [], "ok": [], "fail": []}
if "_fail_btn_counter" not in st.session_state:
    st.session_state._fail_btn_counter = 0
if "popup_visible" not in st.session_state:
    st.session_state.popup_visible = True
# ================= SIDEBAR =================
with st.sidebar:
    st.markdown("## 📊 Theo Dõi Tiến Độ")
    sidebar_status = st.empty()
    sidebar_bar = st.progress(0)
    sidebar_pct = st.empty()
    sidebar_detail = st.empty()
    sidebar_ok_count = st.empty()
    sidebar_fail_count = st.empty()
    sidebar_status.info("🗣️ Chưa chạy - Nhấn nút bên phải!")
    st.markdown("---")
    st.markdown("## 📋 Lịch Sử Đã Xử Lý")
    _h = load_history()
    if _h:
        st.markdown(f"✅ **{len(_h)} URL** đã có audio")
        preview = list(_h.keys())[:5]
        for did in preview:
            title_h = _h[did].get('title','?')[:20]
            st.caption(f"• {title_h}... `{did[-8:]}`")
        if len(_h) > 5:
            st.caption(f"_...và {len(_h)-5} URL khác_")
        with st.expander("📋 Xem tất cả & copy"):
            url_lines = "\n".join(
                f"https://cms.tatinta.com/destination/action/{did}"
                for did in _h.keys()
            )
            st.code(url_lines, language=None)
    else:
        st.info("Chưa có lịch sử nào!")
# ================= HÀM CLIPBOARD =================
def clipboard_copy_button(text: str, label: str, btn_id: str):
    safe_text = html_lib.escape(text)
    label_escaped = html_lib.escape(label)
    components.html(f"""
    <pre id="data_{btn_id}" style="display:none;white-space:pre-wrap">{safe_text}</pre>
    <button id="{btn_id}" onclick="
        var txt = document.getElementById('data_{btn_id}').textContent;
        var btn = document.getElementById('{btn_id}');
        function setOK() {{
            btn.innerHTML = '&#10003; Đã copy vào clipboard!';
            btn.style.background = '#00c853';
            setTimeout(function() {{
                btn.innerHTML = '{label_escaped}';
                btn.style.background = '#ff4b4b';
            }}, 2500);
        }}
        if (navigator.clipboard && navigator.clipboard.writeText) {{
            navigator.clipboard.writeText(txt).then(setOK).catch(function() {{ fallback(txt); }});
        }} else {{ fallback(txt); }}
        function fallback(t) {{
            var ta = document.createElement('textarea');
            ta.value = t; ta.style.cssText = 'position:fixed;opacity:0;top:0;left:0';
            document.body.appendChild(ta); ta.focus(); ta.select();
            try {{ document.execCommand('copy'); setOK(); }} catch(e) {{}}
            document.body.removeChild(ta);
        }}
    " style="background:#ff4b4b;color:white;border:none;border-radius:8px;padding:9px 16px;cursor:pointer;font-size:14px;font-weight:600;width:100%;transition:background 0.3s;font-family:sans-serif;">{label_escaped}</button>
    """, height=48)
# ==========================================
# TAB 1: TỰ ĐỘNG BATCH
# ==========================================
with tab_auto:
    st.subheader("🔗 4. Nhập danh sách URLs (Tatinta CMS)")
    if "urls_input" not in st.session_state:
        st.session_state.urls_input = ""
    col_url_btn1, col_url_btn2 = st.columns([4, 1])
    with col_url_btn2:
        if st.button("🧹 Xóa URL đã xong", use_container_width=True, help="Xóa khỏi ô nhập những URL đã chạy thành công"):
            _hist_now = load_history()
            raw_lines = st.session_state.urls_input.strip().split("\n")
            filtered = []
            for line in raw_lines:
                line = line.strip()
                if not line: continue
                m = re.search(r'([a-f0-9]{24})', line)
                if m and m.group(1) in _hist_now:
                    continue
                filtered.append(line)
            st.session_state.urls_input = "\n".join(filtered)
            st.rerun()
    urls_text = st.text_area("Mỗi dòng 1 URL:", height=200,
        placeholder="https://cms.tatinta.com/destination/action/698afc6c1b29cd1e8cc1b826",
        key="urls_input")
    # Bảng theo dõi
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        title_run = st.empty(); area_run = st.empty(); copy_run = st.empty()
    with c2:
        title_ok = st.empty(); area_ok = st.empty(); copy_ok = st.empty()
    with c3:
        title_fail = st.empty(); area_fail = st.empty(); copy_fail = st.empty()
    fail_copy_area = st.empty()
    progress_text = st.empty()
    progress_bar = st.progress(0)
    status_text = st.empty()
    def render_fail_copy():
        lfail = st.session_state.app_state.get("fail", [])
        fail_urls = []
        for item in lfail:
            raw = item.get("URL", "")
            if raw.startswith("http"):
                fail_urls.append(raw)
            elif re.match(r'^[a-f0-9]{24}$', raw):
                fail_urls.append(f"https://cms.tatinta.com/destination/action/{raw}")
        st.session_state._fail_btn_counter += 1
        _btn_key = f"fail_rerun_btn_{st.session_state._fail_btn_counter}"
        with fail_copy_area.container():
            st.markdown(f"### 📋 Link thất bại ({len(fail_urls)} link)")
            if fail_urls:
                st.code("\n".join(fail_urls), language=None)
                if st.button("🔁 Dán lại vào ô URL để chạy lại", use_container_width=True, key=_btn_key):
                    st.session_state.urls_input = "\n".join(fail_urls)
                    st.rerun()
            else:
                st.info("✅ Chưa có link thất bại nào!")
    def refresh_tables():
        lw = st.session_state.app_state["waiting"]
        lok = st.session_state.app_state["ok"]
        lfail = st.session_state.app_state["fail"]
        title_run.markdown(f"🏃 **ĐANG CHẠY ({len(lw)})**")
        title_ok.markdown(f"✅ **THÀNH CÔNG ({len(lok)})**")
        title_fail.markdown(f"❌ **THẤT BẠI ({len(lfail)})**")
        col_cfg = {
            "URL": st.column_config.LinkColumn("Đường Dẫn URL Gốc"),
            "URL CMS": st.column_config.LinkColumn("Link Đi Đích CMS")
        }
        area_run.dataframe(lw, use_container_width=True, hide_index=True, column_config=col_cfg)
        area_ok.dataframe(lok if lok else [{"Trống": "Chưa có"}], use_container_width=True, hide_index=True, column_config=col_cfg)
        area_fail.dataframe(lfail if lfail else [{"Trống": "Chưa có lỗi"}], use_container_width=True, hide_index=True, column_config=col_cfg)
        ctr = st.session_state._fail_btn_counter
        run_urls = []
        for item in lw:
            raw = item.get("URL", "")
            if raw.startswith("http"): run_urls.append(raw)
            elif re.match(r'^[a-f0-9]{24}$', raw): run_urls.append(f"https://cms.tatinta.com/destination/action/{raw}")
        with copy_run.container():
            if run_urls:
                st.text_area("🏃 URLs đang chạy:", value="\n".join(run_urls), height=80, key=f"ta_run_{ctr}", disabled=False)
                clipboard_copy_button("\n".join(run_urls), label=f"📋 Copy {len(run_urls)} URL đang chạy", btn_id=f"btn_run_{ctr}")
        ok_urls = [item.get("URL CMS","") for item in lok if item.get("URL CMS","").startswith("http")]
        with copy_ok.container():
            if ok_urls:
                st.text_area("✅ URLs thành công:", value="\n".join(ok_urls), height=80, key=f"ta_ok_{ctr}", disabled=False)
                clipboard_copy_button("\n".join(ok_urls), label=f"📋 Copy {len(ok_urls)} URL thành công", btn_id=f"btn_ok_{ctr}")
        fail_urls_copy = []
        for item in lfail:
            raw = item.get("URL","")
            if raw.startswith("http"): fail_urls_copy.append(raw)
            elif re.match(r'^[a-f0-9]{24}$', raw): fail_urls_copy.append(f"https://cms.tatinta.com/destination/action/{raw}")
        with copy_fail.container():
            if fail_urls_copy:
                st.text_area("❌ URLs thất bại:", value="\n".join(fail_urls_copy), height=80, key=f"ta_fail_{ctr}", disabled=False)
                clipboard_copy_button("\n".join(fail_urls_copy), label=f"📋 Copy {len(fail_urls_copy)} URL thất bại", btn_id=f"btn_fail_{ctr}")
        render_fail_copy()
    refresh_tables()
    async def process_urls(urls_list):
        valid_urls = [u.strip() for u in urls_list if u.strip()]
        if not valid_urls:
            st.warning("Danh sách link rỗng!")
            return
        sidebar_status.info("♥️ Đang khởi động...")
        sidebar_pct.markdown(""); sidebar_detail.markdown(""); sidebar_ok_count.markdown(""); sidebar_fail_count.markdown("")
        sidebar_bar.progress(0)
        st.session_state.app_state["waiting"] = [{"URL": u, "Trạng thái": "⏳ Đang chờ"} for u in valid_urls]
        st.session_state.app_state["ok"] = []
        st.session_state.app_state["fail"] = []
        refresh_tables()
        os.makedirs("tmp_audios", exist_ok=True)
        clean_token = token.strip().strip('"').strip("'")
        clean_token = clean_token.encode('ascii', 'ignore').decode('ascii')
        headers = {
            'Origin': 'https://cms.tatinta.com', 'Referer': 'https://cms.tatinta.com/',
            'Accept': 'application/json, text/plain, */*',
            'Authorization': f'Bearer {clean_token}',
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        }
        for idx, url in enumerate(valid_urls):
            lw = st.session_state.app_state["waiting"]
            lok = st.session_state.app_state["ok"]
            lfail = st.session_state.app_state["fail"]
            if len(lw) > 0:
                lw[0]["Trạng thái"] = "▶️ Đang xử lý..."
                refresh_tables()
            match = re.search(r'([a-f0-9]{24})', url)
            if not match:
                if lw: lw.pop(0)
                lfail.append({"URL": url, "Lỗi": "Sai format URL CMS"})
                refresh_tables(); continue
            dest_id = match.group(1)
            api_url = f'https://api.tatinta.com/v1/destination/destination/{dest_id}'
            status_text.text(f"⏳ Đang xử lý: {dest_id} (Fetch Data)...")
            try:
                get_resp = requests.get(api_url, headers=headers)
            except Exception as e:
                if lw: lw.pop(0)
                lfail.append({"URL": dest_id, "Lỗi": f"Lệnh Fetch đứt: {e}"})
                refresh_tables(); continue
            if get_resp.status_code in [401, 403]:
                if lw: lw.pop(0)
                lfail.append({"URL": dest_id, "Lỗi": "BỊ CHẶN: TOKEN ĐẾT HẠN!"})
                refresh_tables()
                st.error("🚨 TOKEN ĐÃ HẾT HẠN - SYSTEM PAUSED 🚨")
                break
            data = get_resp.json().get('data', {})
            t_vi = data.get('name', '')
            c_vi = data.get('content', '')
            translations_dict = data.get('translations', {})
            t_en = translations_dict.get('en', {}).get('name', t_vi)
            c_en = translations_dict.get('en', {}).get('content', '')
            filename_vi = None; filename_en = None
            async def process_lang_task(lang_code, title, content, voice, rate, pitch):
                text_tts = fix_text_for_tts(title, content)
                if not text_tts:
                    text_tts = f"{title}...\n\nInformation about this destination will be updated soon." if lang_code == "en" else f"{title}... Chưa có nội dung."
                raw_f = f"tmp_audios/{dest_id}_raw_{lang_code}.mp3"
                mix_f = f"tmp_audios/{dest_id}_mix_{lang_code}.mp3"
                status_text.text(f"Đang sinh EdgeTTS {lang_code.upper()} cho: {title}...")
                await edge_tts.Communicate(text_tts, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz").save(raw_f)
                raw_size = os.path.getsize(raw_f) if os.path.exists(raw_f) else 0
                if raw_size == 0:
                    raise Exception(f"EdgeTTS tạo file rỗng (0 bytes) cho {lang_code.upper()}!")
                status_text.text(f"TTS {lang_code.upper()} OK ({raw_size//1024}KB). Đang mix nhạc...")
                await asyncio.to_thread(mix_audio, raw_f, bgm_path if use_bgm else None, mix_f, bgm_volume_db)
                mix_size = os.path.getsize(mix_f) if os.path.exists(mix_f) else 0
                if mix_size == 0:
                    raise Exception(f"Mix audio thất bại - file rỗng (0 bytes) cho {lang_code.upper()}!")
                status_text.text(f"Mix {lang_code.upper()} OK ({mix_size//1024}KB). Đang upload...")
                fname = await asyncio.to_thread(upload_audio_to_storage, mix_f, clean_token)
                if not fname:
                    raise Exception(f"Upload thất bại - server không trả về filename cho {lang_code.upper()}!")
                status_text.text(f"Lưu vĩnh viễn {lang_code.upper()}...")
                permanent_url = await asyncio.to_thread(save_file_to_permanent, fname, clean_token)
                status_text.text(f"{lang_code.upper()} OK → {permanent_url}")
                if os.path.exists(raw_f): os.remove(raw_f)
                if os.path.exists(mix_f): os.remove(mix_f)
                return permanent_url
            try:
                tasks = []
                if run_vi: tasks.append(process_lang_task("vi", t_vi, c_vi, voice_vi, rate_vi, pitch_vi))
                if run_en: tasks.append(process_lang_task("en", t_en, c_en, voice_en, rate_en, pitch_en))
                results = await asyncio.gather(*tasks)
                if run_vi and run_en: filename_vi, filename_en = results
                elif run_vi: filename_vi = results[0]
                elif run_en: filename_en = results[0]
            except Exception as e:
                if lw: lw.pop(0)
                lfail.append({"URL": dest_id, "Lỗi": f"Lỗi tạo TTS: {e}"})
                refresh_tables(); continue
            status_text.text("Cắm Link Audio vào Bài viết CMS (PUT)...")
            payload = {"translations": translations_dict}
            if filename_vi: payload["audio"] = filename_vi
            if filename_en:
                if 'en' not in payload["translations"]: payload["translations"]["en"] = {}
                payload["translations"]["en"]["audio"] = filename_en
            if filename_vi or filename_en:
                patch_resp = requests.patch(api_url, headers=headers, json=payload)
                if lw: lw.pop(0)
                if patch_resp.status_code == 200:
                    lok.append({"Tên Bài": t_vi, "URL CMS": url})
                    save_to_history(dest_id, t_vi, audio_vi=filename_vi, audio_en=filename_en)
                else:
                    lfail.append({"URL": dest_id, "Lỗi": f"PATCH THẤT BẠI: {patch_resp.text}"})
            else:
                if lw: lw.pop(0)
                lfail.append({"URL": dest_id, "Lỗi": "Không thể up Audio"})
            refresh_tables()
            curr_percent = int(((idx + 1) / len(valid_urls)) * 100)
            lok2 = st.session_state.app_state["ok"]
            lfail2 = st.session_state.app_state["fail"]
            lw2 = st.session_state.app_state["waiting"]
            sidebar_bar.progress((idx + 1) / len(valid_urls))
            sidebar_pct.markdown(f"<h1 style='color:#ff4b4b;margin:0;font-size:64px;'>{curr_percent}<span style='font-size:28px;'>%</span></h1>", unsafe_allow_html=True)
            sidebar_detail.markdown(f"📌 **Bài {idx+1}** / {len(valid_urls)} đang xử lý")
            sidebar_ok_count.markdown(f"✅ **{len(lok2)}** thành công | ❌ **{len(lfail2)}** lỗi | ⏳ {len(lw2)} chờ")
            sidebar_status.info(f"⏳ Đang xử lý bài {idx+1}...")
            progress_bar.progress((idx + 1) / len(valid_urls))
            await asyncio.sleep(0.2)
        status_text.text("🎉 HOÀN TẤT TOÀN BỘ QUÁ TRÌNH!")
        lok_final = st.session_state.app_state["ok"]
        lfail_final = st.session_state.app_state["fail"]
        sidebar_bar.progress(1.0)
        sidebar_pct.markdown("<h1 style='color:#00c853;margin:0;font-size:64px;'>100<span style='font-size:28px;'>%</span></h1>", unsafe_allow_html=True)
        sidebar_detail.markdown(f"🎉 **Hoàn Tất!** {len(valid_urls)} bài viết")
        sidebar_ok_count.markdown(f"✅ **{len(lok_final)}** thành công | ❌ **{len(lfail_final)}** thất bại")
        sidebar_status.success("🎉 Cày DATA XONG!")
        progress_text.markdown("")
    # Nhập URL & nút chạy
    history = load_history()
    urls_list_raw = urls_text.strip().split("\n") if urls_text.strip() else []
    urls_list_raw = [u.strip() for u in urls_list_raw if len(u.strip()) > 5]
    if urls_list_raw:
        already_done = []
        not_yet = []
        for u in urls_list_raw:
            m = re.search(r'([a-f0-9]{24})', u)
            if m and m.group(1) in history:
                already_done.append((u, history[m.group(1)]))
            else:
                not_yet.append(u)
        if already_done:
            with st.expander(f"⚠️ {len(already_done)} URL đã chạy thành công trước đó — nhấn để xem", expanded=True):
                for url, info in already_done:
                    st.markdown(f"✅ **{info.get('title','?')}** — Chạy lúc: `{info.get('ran_at','?')}` — [Link]({url})")
            skip_done = st.checkbox("🔄 Bỏ qua các URL đã chạy thành công", value=True)
        else:
            skip_done = False
    else:
        skip_done = False
        already_done = []
        not_yet = urls_list_raw
    if st.button("🚀 BẮT ĐẦU XỬ LÝ (RUN THE BATCH)", type="primary"):
        if not token:
            st.error("🚨 Sếp chưa nhập Bearer Token!")
        elif len(urls_list_raw) == 0:
            st.error("🚨 Sếp chưa nhập Danh sách URLs!")
        elif not run_vi and not run_en:
            st.error("🚨 Phải tick chọn ít nhất 1 ngôn ngữ chạy chứ sếp!")
        else:
            if skip_done:
                run_list = not_yet
                if already_done:
                    st.info(f"⏭️ Bỏ qua {len(already_done)} URL đã chạy. Chạy {len(run_list)} URL mới.")
            else:
                run_list = urls_list_raw
            if not run_list:
                st.warning("⚠️ Tất cả URL đã được xử lý rồi! Bỏ tick 'Bỏ qua' nếu muốn chạy lại.")
            else:
                st.session_state.popup_visible = True
                asyncio.run(process_urls(run_list))
# ==========================================
# TAB 2: TẠO AUDIO TAY
# ==========================================
with tab_manual:
    st.subheader("✍️ Tạo Audio Thủ Công")
    st.info("💡 Nhập nội dung plain text (không cần format), nhấn nút để tạo audio. Có thể nghe preview, download hoặc upload thẳng lên CMS.")
    # --- Input nội dung ---
    col_vi_m, col_en_m = st.columns(2)
    with col_vi_m:
        st.markdown("#### 🇻🇳 Tiếng Việt")
        manual_run_vi = st.checkbox("Tạo audio Tiếng Việt", value=True, key="manual_run_vi")
        manual_title_vi = st.text_input("Tiêu đề (VI):", placeholder="VD: Hồ Xuân Hương - Đà Lạt", key="manual_title_vi")
        manual_content_vi = st.text_area(
            "Nội dung plain text (VI):",
            height=250,
            placeholder="Dán nội dung tiếng Việt vào đây, không cần format gì hết. App sẽ tự dọn dẹp và đọc...",
            key="manual_content_vi"
        )
    with col_en_m:
        st.markdown("#### 🇺🇸 Tiếng Anh")
        manual_run_en = st.checkbox("Tạo audio Tiếng Anh", value=True, key="manual_run_en")
        manual_title_en = st.text_input("Tiêu đề (EN):", placeholder="VD: Xuan Huong Lake - Da Lat", key="manual_title_en")
        manual_content_en = st.text_area(
            "Nội dung plain text (EN):",
            height=250,
            placeholder="Paste English content here, no formatting needed...",
            key="manual_content_en"
        )
    st.markdown("---")
    # --- Upload lên CMS (tùy chọn) ---
    manual_cms_url = st.text_input(
        "🔗 URL bài viết CMS để upload audio lên (tùy chọn):",
        placeholder="https://cms.tatinta.com/destination/action/698afc6c1b29cd1e8cc1b826",
        key="manual_cms_url"
    )
    # --- Nút tạo audio ---
    if st.button("🎙️ TẠO AUDIO", type="primary", use_container_width=True, key="manual_gen_btn"):
        if not manual_run_vi and not manual_run_en:
            st.error("🚨 Phải chọn ít nhất 1 ngôn ngữ!")
        elif manual_run_vi and not manual_title_vi.strip():
            st.error("🚨 Chưa nhập tiêu đề Tiếng Việt!")
        elif manual_run_en and not manual_title_en.strip():
            st.error("🚨 Chưa nhập tiêu đề Tiếng Anh!")
        else:
            # Dùng /tmp để tránh sandbox macOS block ghi file trong project folder
            import tempfile
            _tmp_dir = tempfile.gettempdir()
            manual_status = st.empty()
            async def run_manual():
                results = {}
                async def gen_one(lang_code, title, content, voice, rate, pitch):
                    text_tts = fix_plain_text_for_tts(title, content)
                    if not text_tts:
                        text_tts = f"{title}..."
                    raw_f = os.path.join(_tmp_dir, f"tatinta_manual_raw_{lang_code}.mp3")
                    mix_f = os.path.join(_tmp_dir, f"tatinta_manual_mix_{lang_code}.mp3")
                    manual_status.info(f"⏳ Đang tạo TTS {lang_code.upper()}...")
                    await edge_tts.Communicate(text_tts, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz").save(raw_f)
                    raw_size = os.path.getsize(raw_f) if os.path.exists(raw_f) else 0
                    if raw_size == 0:
                        raise Exception(f"EdgeTTS tạo file rỗng cho {lang_code.upper()}!")
                    manual_status.info(f"✅ TTS {lang_code.upper()} xong ({raw_size//1024}KB). Đang mix nhạc...")
                    await asyncio.to_thread(mix_audio, raw_f, bgm_path if use_bgm else None, mix_f, bgm_volume_db)
                    mix_size = os.path.getsize(mix_f) if os.path.exists(mix_f) else 0
                    if mix_size == 0:
                        raise Exception(f"Mix audio thất bại cho {lang_code.upper()}!")
                    if os.path.exists(raw_f): os.remove(raw_f)
                    return mix_f
                tasks = {}
                if manual_run_vi:
                    tasks["vi"] = gen_one("vi", manual_title_vi, manual_content_vi, voice_vi, rate_vi, pitch_vi)
                if manual_run_en:
                    tasks["en"] = gen_one("en", manual_title_en, manual_content_en, voice_en, rate_en, pitch_en)
                for lang, coro in tasks.items():
                    try:
                        results[lang] = await coro
                    except Exception as e:
                        results[lang] = None
                        st.error(f"❌ Lỗi tạo audio {lang.upper()}: {e}")
                return results
            with st.spinner("Đang tạo audio..."):
                audio_results = asyncio.run(run_manual())
            manual_status.empty()
            # --- Hiển thị preview & download ---
            if audio_results:
                st.success("🎉 Tạo audio xong!")
                col_prev_vi, col_prev_en = st.columns(2)
                vi_path = audio_results.get("vi")
                en_path = audio_results.get("en")
                with col_prev_vi:
                    if vi_path and os.path.exists(vi_path):
                        st.markdown("**🇻🇳 Preview Audio Tiếng Việt:**")
                        with open(vi_path, "rb") as f:
                            audio_bytes_vi = f.read()
                        st.audio(audio_bytes_vi, format="audio/mp3")
                        st.download_button(
                            label="⬇️ Tải về (VI)",
                            data=audio_bytes_vi,
                            file_name=f"audio_vi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                            mime="audio/mpeg",
                            use_container_width=True,
                            key="dl_vi"
                        )
                with col_prev_en:
                    if en_path and os.path.exists(en_path):
                        st.markdown("**🇺🇸 Preview Audio Tiếng Anh:**")
                        with open(en_path, "rb") as f:
                            audio_bytes_en = f.read()
                        st.audio(audio_bytes_en, format="audio/mp3")
                        st.download_button(
                            label="⬇️ Tải về (EN)",
                            data=audio_bytes_en,
                            file_name=f"audio_en_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                            mime="audio/mpeg",
                            use_container_width=True,
                            key="dl_en"
                        )
                # --- Upload lên CMS nếu có URL ---
                if manual_cms_url.strip():
                    st.markdown("---")
                    if st.button("🚀 Upload Audio lên CMS", type="secondary", use_container_width=True, key="manual_upload_btn"):
                        if not token:
                            st.error("🚨 Chưa nhập Bearer Token ở trên!")
                        else:
                            match_cms = re.search(r'([a-f0-9]{24})', manual_cms_url)
                            if not match_cms:
                                st.error("🚨 URL CMS không hợp lệ!")
                            else:
                                dest_id_m = match_cms.group(1)
                                api_url_m = f'https://api.tatinta.com/v1/destination/destination/{dest_id_m}'
                                clean_tok = token.strip().strip('"').strip("'")
                                clean_tok = clean_tok.encode('ascii', 'ignore').decode('ascii')
                                headers_m = {
                                    'Origin': 'https://cms.tatinta.com',
                                    'Referer': 'https://cms.tatinta.com/',
                                    'Accept': 'application/json, text/plain, */*',
                                    'Authorization': f'Bearer {clean_tok}',
                                    'User-Agent': 'Mozilla/5.0'
                                }
                                with st.spinner("Đang upload lên CMS..."):
                                    uploaded_vi = None
                                    uploaded_en = None
                                    if vi_path and os.path.exists(vi_path):
                                        try:
                                            fname_vi = upload_audio_to_storage(vi_path, clean_tok)
                                            uploaded_vi = save_file_to_permanent(fname_vi, clean_tok)
                                            st.success(f"✅ Upload VI xong: `{uploaded_vi}`")
                                        except Exception as e:
                                            st.error(f"❌ Upload VI thất bại: {e}")
                                    if en_path and os.path.exists(en_path):
                                        try:
                                            fname_en = upload_audio_to_storage(en_path, clean_tok)
                                            uploaded_en = save_file_to_permanent(fname_en, clean_tok)
                                            st.success(f"✅ Upload EN xong: `{uploaded_en}`")
                                        except Exception as e:
                                            st.error(f"❌ Upload EN thất bại: {e}")
                                    if uploaded_vi or uploaded_en:
                                        # Lấy translations hiện tại của bài
                                        try:
                                            get_r = requests.get(api_url_m, headers=headers_m)
                                            existing_trans = get_r.json().get('data', {}).get('translations', {}) if get_r.status_code == 200 else {}
                                        except:
                                            existing_trans = {}
                                        payload_m = {"translations": existing_trans}
                                        if uploaded_vi:
                                            payload_m["audio"] = uploaded_vi
                                        if uploaded_en:
                                            if 'en' not in payload_m["translations"]:
                                                payload_m["translations"]["en"] = {}
                                            payload_m["translations"]["en"]["audio"] = uploaded_en
                                        patch_r = requests.patch(api_url_m, headers=headers_m, json=payload_m)
                                        if patch_r.status_code == 200:
                                            st.success("🎉 Đã cắm audio vào bài CMS thành công!")
                                            save_to_history(dest_id_m, manual_title_vi or manual_title_en, audio_vi=uploaded_vi, audio_en=uploaded_en)
                                        else:
                                            st.error(f"❌ PATCH thất bại: {patch_r.text[:200]}")
