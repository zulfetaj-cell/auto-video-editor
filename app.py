import os
import re
import random
import tempfile
import asyncio
import subprocess
import requests
import streamlit as st
import edge_tts
import imageio_ffmpeg

st.set_page_config(page_title="Fast AI Video Engine", layout="wide")

st.title("🎬 Fast AI Script-to-Video Engine")
st.write("Lightweight & non-blocking automated video pipeline.")

# Sidebar Settings
st.sidebar.header("🔑 API Setup")
pexels_api_key = st.sidebar.text_input("Pexels API Key", type="password")

st.sidebar.header("🎙️ AI Voice Selection")
voice_library = {
    "Urdu - Asad (Male Narrative)": "ur-PK-AsadNeural",
    "Urdu - Uzma (Female News/Doc)": "ur-PK-UzmaNeural",
    "Hindi - Madhur (Male Deep)": "hi-IN-MadhurNeural",
    "Hindi - Swara (Female Warm)": "hi-IN-SwaraNeural",
    "English (US) - Christopher (Male)": "en-US-ChristopherNeural",
    "English (US) - Guy (Male)": "en-US-GuyNeural",
    "English (US) - Jenny (Female)": "en-US-JennyNeural"
}

selected_voice_label = st.sidebar.selectbox("Voice Actor:", list(voice_library.keys()), index=0)
selected_voice = voice_library[selected_voice_label]

# Main Input
script_text = st.text_area(
    "Apni Script Yahan Paste Karein:",
    height=200,
    placeholder="Technology har roz badal rahi hai.\nArtificial intelligence hamari zindagi ko asan bana rahi hai."
)

STOP_WORDS = {
    "is", "are", "the", "a", "an", "and", "or", "in", "on", "at", "to", "for", "with", 
    "about", "that", "this", "it", "of", "by", "from", "be", "as", "you", "your", "we",
    "they", "he", "she", "kya", "hai", "hain", "ko", "ki", "ka", "ke", "par", "se", 
    "aur", "bhi", "kar", "karna", "raha", "rahe", "hota", "hote", "wale", "kuch"
}

def extract_smart_query(sentence):
    words = re.findall(r'\b[a-zA-Z]{3,}\b', sentence.lower())
    meaningful = [w for w in words if w not in STOP_WORDS]
    if len(meaningful) >= 2:
        return f"{meaningful[0]} {meaningful[1]}"
    elif len(meaningful) == 1:
        return f"{meaningful[0]} technology"
    return "technology business motion"

async def generate_voice_and_vtt(text, voice, audio_path, vtt_path):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    with open(audio_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.feed(chunk)
    
    # Save Subtitles
    srt_text = submaker.get_srt() if hasattr(submaker, 'get_srt') else submaker.generate_subs()
    with open(vtt_path, "w", encoding="utf-8") as file:
        file.write(srt_text)

def get_media_duration(ffmpeg_path, file_path):
    try:
        cmd = [ffmpeg_path, "-i", file_path, "-f", "null", "-"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
        for line in result.stderr.split("\n"):
            if "Duration" in line:
                time_str = line.split("Duration:")[1].split(",")[0].strip()
                h, m, s = time_str.split(":")
                return float(h) * 3600 + float(m) * 60 + float(s)
    except Exception:
        pass
    return 6.0

def fetch_pexels_video_urls(query, api_key):
    headers = {"Authorization": api_key, "User-Agent": "Mozilla/5.0"}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=landscape"
    links = []
    try:
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            data = r.json()
            for v in data.get("videos", []):
                for f in v.get("video_files", []):
                    # Pick lightweight 720p / 540p files for instant processing
                    if f.get("width") in [1280, 960, 640]:
                        links.append(f.get("link"))
                        break
                else:
                    if v.get("video_files"):
                        links.append(v["video_files"][0].get("link"))
    except Exception:
        pass
    return links

def download_video_file(url, save_path):
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        with requests.get(url, headers=headers, stream=True, timeout=12) as resp:
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 5000:
            return True
    except Exception:
        pass
    return False

# Main Render Process
if st.button("🚀 Generate Full Video Now", type="primary", use_container_width=True):
    if not pexels_api_key:
        st.error("Sidebar me Pexels API Key zaroor enter karein!")
    elif not script_text.strip():
        st.error("Pehle script likhein!")
    else:
        status_box = st.status("Fast processing shuru ho rahi hai...", expanded=True)
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Voiceover
                status_box.write("Audio voiceover generate ho raha hai...")
                audio_path = os.path.join(temp_dir, "voiceover.mp3")
                sub_path = os.path.join(temp_dir, "captions.srt")
                asyncio.run(generate_voice_and_vtt(script_text, selected_voice, audio_path, sub_path))

                target_duration = get_media_duration(ffmpeg_bin, audio_path)
                status_box.write(f"Voiceover mukammal: {round(target_duration, 1)}s")

                # 2. Extract Keywords & Download
                raw_lines = [l.strip() for l in script_text.replace(".", "\n").replace(";", "\n").split("\n") if len(l.strip()) > 3]
                if not raw_lines:
                    raw_lines = ["modern technology", "digital business", "abstract motion"]

                downloaded_clips = []
                status_box.write("Video clips download aur standardize ho rahi hain...")

                for idx, line in enumerate(raw_lines[:8]):  # Max 8 scenes to keep speed ultra fast
                    query = extract_smart_query(line)
                    urls = fetch_pexels_video_urls(query, pexels_api_key)
                    if not urls:
                        urls = fetch_pexels_video_urls("cinematic background", pexels_api_key)

                    for candidate_url in urls:
                        clip_file = os.path.join(temp_dir, f"raw_{idx}_{random.randint(100, 999)}.mp4")
                        if download_video_file(candidate_url, clip_file):
                            clean_clip = os.path.join(temp_dir, f"clean_{idx}.mp4")
                            
                            # Fast 720p scaling without complex filters
                            norm_cmd = [
                                ffmpeg_bin, "-y",
                                "-t", "6.0",
                                "-i", clip_file,
                                "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,fps=30",
                                "-c:v", "libx264", "-preset", "ultrafast", "-an",
                                clean_clip
                            ]
                            subprocess.run(norm_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
                            if os.path.exists(clean_clip):
                                downloaded_clips.append(clean_clip)
                                break

                if not downloaded_clips:
                    st.error("Video clips download nahi huin. Pexels API Key verify karein.")
                    st.stop()

                # 3. Fast Concat List
                status_box.write("Clips merge aur audio sync ho raha hai...")
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_file, "w") as f:
                    for _ in range(6):
                        random.shuffle(downloaded_clips)
                        for c in downloaded_clips:
                            f.write(f"file '{c}'\n")

                # 4. Direct Merge without Heavy Filtering (No Stuck/Crash)
                output_path = os.path.join(temp_dir, "final_video.mp4")
                render_cmd = [
                    ffmpeg_bin, "-y",
                    "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", audio_path,
                    "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "128k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-t", str(target_duration),
                    output_path
                ]
                subprocess.run(render_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30)

                status_box.update(label="Complete!", state="complete", expanded=False)
                st.success("✅ Video bina kisi rukawat ke tayyar hai!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.video(video_bytes)
                
                # Subtitles download button
                with open(sub_path, "rb") as sf:
                    sub_bytes = sf.read()

                col_d1, col_d2 = st.columns(2)
                with col_d1:
                    st.download_button("📥 Download Final Video", data=video_bytes, file_name="final_video.mp4", mime="video/mp4")
                with col_d2:
                    st.download_button("📝 Download Captions (.SRT)", data=sub_bytes, file_name="captions.srt", mime="text/plain")

            except subprocess.TimeoutExpired:
                status_box.update(label="Process Timeout!", state="error")
                st.error("Server bohot slow hone ki wajah se timeout hua. Streamlit app ko Reboot karein.")
            except Exception as e:
                status_box.update(label="Error aya!", state="error")
                st.error(f"Processing error: {str(e)}")
