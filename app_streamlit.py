import streamlit as st
import asyncio
import os
import re
import requests
from bs4 import BeautifulSoup
import subprocess
import shutil
import edge_tts
import time

st.set_page_config(page_title="Tatinta Audio Automator", page_icon="🎙️", layout="wide")

# ================= KHOÁ BẢO MẬT (LOGIN) =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔒 CỔNG BẢO MẬT TATINTA</h2>", unsafe_allow_html=True)
        pwd_input = st.text_input("🔐 Nhập Mật khẩu Truy Cập Hệ Thống:", type="password")
        if st.button("🚀 Đăng Nhập", use_container_width=True):
            if pwd_input == "Tatintavietnam1#":
                st.session_state.authenticated = True
                st.rerun()
            elif pwd_input:
                st.error("❌ Mật khẩu không chính xác! Vui lòng kiểm tra lại.")
    st.stop() # Chặn đứng mọi thứ ở dưới nếu chưa nhập đúng Pass

# ================= GIAO DIỆN CHÍNH =================
st.title("🎙️ Hệ Thống Tự Động Thu Âm & Ghép Nhạc Tatinta CMS")
st.markdown("Xây dựng bởi Antigravity Agent. Dán danh sách URL là có Full Audio 2 Ngôn Ngữ.")

# ================= KHOẢNG XÁC THỰC =================
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
    (function(){const r=/eyJ[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+\.[a-zA-Z0-9\-_]+/; let t=document.cookie.match(r); if(!t){for(let cur of [localStorage, sessionStorage]){for(let i=0; i<cur.length; i++){let k=cur.key(i); let v=cur.getItem(k); if(v && r.test(v)){t=v.match(r); break;}} if(t) break;}} if(t){prompt("Copy Token bên dưới để dán vào Tool:", t[0]);} else{alert("Không tìm thấy Token!");}})();
    ```
    """)

# ================= KHOẢNG CẤU HÌNH VOICE =================
st.subheader("⚙️ 2. Cấu hình Giọng Đọc (TTS) & Ngôn ngữ")
col1, col2 = st.columns(2)

with col1:
    run_vi = st.checkbox("✅ Tạo Tiếng Việt", value=True)
    voice_vi = st.selectbox("Giọng Tiếng Việt", ["vi-VN-NamMinhNeural", "vi-VN-HoaiMyNeural"])
    rate_vi = st.slider("Tốc độ VI (%)", -50, 50, 5)
    pitch_vi = st.slider("Độ trầm (Hz)", -20, 20, -5)

with col2:
    run_en = st.checkbox("✅ Tạo Tiếng Anh", value=True)
    voice_en = st.selectbox("Giọng Tiếng Anh", ["en-US-GuyNeural", "en-US-ChristopherNeural", "en-US-AriaNeural"])
    rate_en = st.slider("Tốc độ EN (%)", -50, 50, 0)
    pitch_en = st.slider("Độ trầm EN (Hz)", -20, 20, -2)

# ================= KHOẢNG CẤU HÌNH NHẠC NỀN =================
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

# ================= KHU VỰC URLs VÀ KHỞI CHẠY =================
st.subheader("🔗 4. Nhập danh sách URLs (Tatinta CMS)")
urls_text = st.text_area("Mỗi dòng 1 URL:", height=200, placeholder="https://cms.tatinta.com/destination/action/698afc6c1b29cd1e8cc1b826")

def fix_text_for_tts(title, raw_html):
    if not title and not raw_html: return ""
    clean_content = BeautifulSoup(raw_html, "html.parser").get_text(separator="\n").strip()
    clean_content = re.sub(r'([,\.])(?!\d)', r'\1...', clean_content)
    return f"{title}...\n\n{clean_content}"

def upload_audio_to_storage(file_path, tok):
    url = 'https://api.tatinta.com/v1/extra/upload/audio'
    tok_clean = tok.strip().strip('"').strip("'")
    tok_clean = tok_clean.encode('ascii', 'ignore').decode('ascii') # Ép sạch ký tự ẩn unicode
    headers = {
        'Origin': 'https://cms.tatinta.com', 
        'Referer': 'https://cms.tatinta.com/',
        'Accept': 'application/json, text/plain, */*',
        'Authorization': f'Bearer {tok_clean}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    with open(file_path, 'rb') as f:
        resp = requests.post(url, headers=headers, files={'faudio': (os.path.basename(file_path), f, 'audio/mpeg')})
    if resp.status_code in [200, 201]:
        return resp.json().get('data', {}).get('filename')
    return None

def mix_audio(tts_file, bgm_file, output_file, db_reduce):
    if bgm_file and os.path.exists(bgm_file):
        try:
            # Dùng trực tiếp FFmpeg bằng subprocess thay cho pydub (Mạnh hơn, tránh lỗi audioop)
            cmd = [
                "ffmpeg", "-y",
                "-i", tts_file,
                "-stream_loop", "-1", "-i", bgm_file,
                "-filter_complex", f"[1:a]volume={-abs(db_reduce)}dB[bgm];[0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2",
                "-c:a", "libmp3lame",
                "-b:a", "128k",
                output_file
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        except Exception:
            pass
    # Nếu ko có nhạc hoặc lỗi (copy thẳng tts file sang)
    shutil.copy2(tts_file, output_file)

async def process_urls(urls_list):
    valid_urls = [u.strip() for u in urls_list if u.strip()]
    if not valid_urls:
        st.warning("Danh sách link rỗng!")
        return
        
    progress_text = st.empty()
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    list_waiting = [{"URL": u, "Trạng thái": "⏳ Đang chờ"} for u in valid_urls]
    list_ok = []
    list_fail = []

    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    with c1:
        title_run = st.empty()
        area_run = st.empty()
    with c2:
        title_ok = st.empty()
        area_ok = st.empty()
    with c3:
        title_fail = st.empty()
        area_fail = st.empty()
        
    def refresh_tables():
        title_run.markdown(f"🏃 **ĐANG CHẠY / CHỜ ({len(list_waiting)})**")
        title_ok.markdown(f"✅ **THÀNH CÔNG ({len(list_ok)})**")
        title_fail.markdown(f"❌ **THẤT BẠI ({len(list_fail)})**")
        
        col_cfg = {
            "URL": st.column_config.LinkColumn("Đường Dẫn (Click Mở)", display_text="🔗 Xem link"),
            "URL CMS": st.column_config.LinkColumn("Link Đi Đích (Click Mở)", display_text="🔗 Tới CMS")
        }
        area_run.dataframe(list_waiting, use_container_width=True, hide_index=True, column_config=col_cfg)
        area_ok.dataframe(list_ok if list_ok else [{"Trống": "Chưa có"}], use_container_width=True, hide_index=True, column_config=col_cfg)
        area_fail.dataframe(list_fail if list_fail else [{"Trống": "Chưa có lỗi"}], use_container_width=True, hide_index=True, column_config=col_cfg)
        
    refresh_tables()
    
    os.makedirs("tmp_audios", exist_ok=True)
    clean_token = token.strip().strip('"').strip("'")
    clean_token = clean_token.encode('ascii', 'ignore').decode('ascii') # Cạo sạch ký tự tàng hình
    headers = {
        'Origin': 'https://cms.tatinta.com', 
        'Referer': 'https://cms.tatinta.com/',
        'Accept': 'application/json, text/plain, */*',
        'Authorization': f'Bearer {clean_token}',
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
    }
    
    for idx, url in enumerate(valid_urls):
        if len(list_waiting) > 0:
            list_waiting[0]["Trạng thái"] = "▶️ Đang xử lý..."
            refresh_tables()
            
        match = re.search(r'([a-f0-9]{24})', url)
        if not match:
            if list_waiting: list_waiting.pop(0)
            list_fail.insert(0, {"URL": url, "Lỗi": "Sai format URL CMS"})
            refresh_tables()
            continue
            
        dest_id = match.group(1)
        api_url = f'https://api.tatinta.com/v1/destination/destination/{dest_id}'
        
        status_text.text(f"⏳ Đang xử lý: {dest_id} (Fetch Data)...")
        
        try:
            get_resp = requests.get(api_url, headers=headers)
        except Exception as e:
            if list_waiting: list_waiting.pop(0)
            list_fail.insert(0, {"URL": dest_id, "Lỗi": f"Lệnh Fetch đứt: {e}"})
            refresh_tables(); continue
            
        if get_resp.status_code in [401, 403]:
            if list_waiting: list_waiting.pop(0)
            list_fail.insert(0, {"URL": dest_id, "Lỗi": f"BỊ CHẶN: TOKEN ĐẾT HẠN!"})
            refresh_tables()
            st.error("🚨 TOKEN ĐÃ HẾT HẠN - SYSTEM PAUSED 🚨")
            break
            
        data = get_resp.json().get('data', {})
        t_vi = data.get('name', '')
        c_vi = data.get('content', '')
        
        translations_dict = data.get('translations', {})
        t_en = translations_dict.get('en', {}).get('name', t_vi)
        c_en = translations_dict.get('en', {}).get('content', '')
        
        filename_vi = None
        filename_en = None
        
        async def process_lang_task(lang_code, title, content, voice, rate, pitch):
            text_tts = fix_text_for_tts(title, content)
            if not text_tts: 
                text_tts = f"{title}...\n\nInformation about this destination will be updated soon." if lang_code == "en" else f"{title}... Chưa có nội dung."
            
            raw_f = f"tmp_audios/{dest_id}_raw_{lang_code}.mp3"
            mix_f = f"tmp_audios/{dest_id}_mix_{lang_code}.mp3"
            
            status_text.text(f"Đang sinh EdgeTTS {lang_code.upper()} cho: {title}...")
            await edge_tts.Communicate(text_tts, voice, rate=f"{rate:+d}%", pitch=f"{pitch:+d}Hz").save(raw_f)
            
            status_text.text(f"Mix nhạc {lang_code.upper()}...")
            await asyncio.to_thread(mix_audio, raw_f, bgm_path if use_bgm else None, mix_f, bgm_volume_db)
            
            status_text.text(f"Upload kho lưu trữ {lang_code.upper()}...")
            fname = await asyncio.to_thread(upload_audio_to_storage, mix_f, clean_token)
            
            if os.path.exists(raw_f): os.remove(raw_f)
            if os.path.exists(mix_f): os.remove(mix_f)
            return fname

        try:
            tasks = []
            if run_vi:
                tasks.append(process_lang_task("vi", t_vi, c_vi, voice_vi, rate_vi, pitch_vi))
            if run_en:
                tasks.append(process_lang_task("en", t_en, c_en, voice_en, rate_en, pitch_en))
                
            results = await asyncio.gather(*tasks)
            
            if run_vi and run_en:
                filename_vi, filename_en = results
            elif run_vi:
                filename_vi = results[0]
            elif run_en:
                filename_en = results[0]
                
        except Exception as e:
            if list_waiting: list_waiting.pop(0)
            list_fail.insert(0, {"URL": dest_id, "Lỗi": f"Lỗi tạo TTS: {e}"})
            refresh_tables()
            continue
                
        # PATCH LÊN CMS
        status_text.text(f"Cắm Link Audio vào Bài viết CMS (Patch)...")
        payload = {"translations": translations_dict}
        if filename_vi:
            payload["audio"] = f"tmp/{filename_vi}"
        if filename_en:
            if 'en' not in payload["translations"]: payload["translations"]["en"] = {}
            payload["translations"]["en"]["audio"] = f"tmp/{filename_en}"
            
        if filename_vi or filename_en:
            patch_resp = requests.patch(api_url, headers=headers, json=payload)
            if list_waiting: list_waiting.pop(0)
            if patch_resp.status_code == 200:
                list_ok.insert(0, {"Tên Bài": t_vi, "URL CMS": url})
            else:
                list_fail.insert(0, {"URL": dest_id, "Lỗi": f"PATCH THẤT BẠI: {patch_resp.text}"})
        else:
            if list_waiting: list_waiting.pop(0)
            list_fail.insert(0, {"URL": dest_id, "Lỗi": "Không thể up Audio"})
            
        refresh_tables()
        curr_percent = int(((idx + 1) / len(valid_urls)) * 100)
        progress_text.markdown(f"**🎯 Tiến độ xử lý: {curr_percent}%** ({idx+1}/{len(valid_urls)} Bài viết)")
        progress_bar.progress((idx + 1) / len(valid_urls))
        await asyncio.sleep(0.2) # Chống spam - thay cho time.sleep(1)

    status_text.text("🎉 HOÀN TẤT TOÀN BỘ QUÁ TRÌNH!")

if st.button("🚀 BẮT ĐẦU XỬ LÝ (RUN THE BATCH)", type="primary"):
    urls_list = urls_text.strip().split("\n")
    urls_list = [u for u in urls_list if len(u) > 5]
    
    if not token:
        st.error("🚨 Sếp chưa nhập Bearer Token!")
    elif len(urls_list) == 0:
        st.error("🚨 Sếp chưa nhập Danh sách URLs!")
    elif not run_vi and not run_en:
        st.error("🚨 Phải tick chọn ít nhất 1 ngôn ngữ chạy chứ sếp!")
    else:
        asyncio.run(process_urls(urls_list))
