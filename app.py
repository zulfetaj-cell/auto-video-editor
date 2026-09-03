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

st.set_page_config(page_title="Pro AI Video Engine", layout="wide")

st.title("🎬 Professional AI Script-to-Video Engine")
st.write("Smart Visual Search, Animated Subtitles aur Dynamic Transitions ke sath automated video generator.")

# Sidebar Settings
st.sidebar.header("🔑 API Setup")
pexels_api_key = st.sidebar.text_input("Pexels API Key", type="password")

st.sidebar.header("🎙️ AI Voice Selection")
voice_library = {
    "Urdu - Asad (Male Narrative)": "ur-PK-AsadNeural",
    "Urdu - Uzma (Female News/Doc)": "ur-PK-UzmaNeural",
    "Hindi - Madhur (Male Deep)": "hi-IN-MadhurNeural",
    "Hindi - Swara (Female Warm)": "hi-IN-SwaraNeural",
    "English (US) - Christopher (Documentary Male)": "en-US-ChristopherNeural",
    "English (US) - Guy (YouTube Male)": "en-US-GuyNeural",
    "English (US) - Jenny (Professional Female)": "en-US-JennyNeural"
}

selected_voice_label = st.sidebar.selectbox("Voice Actor:", list(voice_library.keys()), index=0)
selected_voice = voice_library[selected_voice_label]

# Subtitle Styling Option
st.sidebar.header("📝 Subtitle Style")
font_size = st.sidebar.slider("Subtitle Font Size", min_value=18, max_value=32, value=24)
sub_color = st.sidebar.selectbox("Subtitle Color", ["Yellow (&H0000FFFF)", "White (&H00FFFFFF)", "Cyan (&H00FFFF00)"])
color_hex = sub_color.split("(")[-1].replace(")", "")

# Main Input
script_text = st.text_area(
    "Apni Script Yahan Paste Karein:",
    height=220,
    placeholder="Technology har roz badal rahi hai.\nArtificial intelligence hamari zindagi ko asan bana rahi hai.\nAane wala waqt automated machine systems ka hai."
)

# --- Visual Keyword Extraction ---
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
        return f"{meaningful[0]} footage"
    return "cinematic business technology"

# --- Edge-TTS with Subtitle Timings ---
async def generate_voice_and_subtitles(text, voice, audio_path, srt_path):
    communicate = edge_tts.Communicate(text, voice)
    submaker = edge_tts.SubMaker()
    with open(audio_path, "wb") as file:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                file.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                submaker.create_sub((chunk["offset"], chunk["duration"]), chunk["text"])
    with open(srt_path, "w", encoding="utf-8") as file:
        file.write(submaker.generate_subs())

def get_media_duration(ffmpeg_path, file_path):
    cmd = [ffmpeg_path, "-i", file_path, "-f", "null", "-"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = time_str.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 6.0

def fetch_pexels_video_urls(query, api_key):
    headers = {"Authorization": api_key, "User-Agent": "Mozilla/5.0"}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=6&orientation=landscape"
    links = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            for v in data.get("videos", []):
                for f in v.get("video_files", []):
                    if f.get("width") in [1280, 1920]:
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
        with requests.get(url, headers=headers, stream=True, timeout=25) as resp:
            resp.raise_for_status()
            with open(save_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 512):
                    if chunk:
                        f.write(chunk)
        if os.path.exists(save_path) and os.path.getsize(save_path) > 10000:
            return True
    except Exception:
        pass
    return False

# Main Render Process
if st.button("🚀 Generate Full Video with Subtitles & VFX", type="primary", use_container_width=True):
    if not pexels_api_key:
        st.error("Sidebar me Pexels API Key zaroor enter karein!")
    elif not script_text.strip():
        st.error("Pehle script likhein!")
    else:
        status_box = st.status("Advanced Video Pipeline running...", expanded=True)
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Voiceover & Subtitles Generation
                status_box.write("Realistic Voiceover aur Subtitles timestamps generate ho rahe hain...")
                audio_path = os.path.join(temp_dir, "voiceover.mp3")
                srt_path = os.path.join(temp_dir, "captions.srt")
                asyncio.run(generate_voice_and_subtitles(script_text, selected_voice, audio_path, srt_path))

                target_duration = get_media_duration(ffmpeg_bin, audio_path)
                status_box.write(f"Voiceover duration: {round(target_duration, 1)}s")

                # 2. Smart Visual Query Splitting
                raw_lines = [l.strip() for l in script_text.replace(".", "\n").replace(";", "\n").split("\n") if len(l.strip()) > 3]
                if not raw_lines:
                    raw_lines = ["modern business technology", "financial growth digital", "futuristic concept"]

                downloaded_clips = []
                status_box.write("Sentence meaning analyze karke relevant stock videos download ki ja rahi hain...")

                for idx, line in enumerate(raw_lines):
                    smart_query = extract_smart_query(line)
                    urls = fetch_pexels_video_urls(smart_query, pexels_api_key)
                    if not urls:
                        urls = fetch_pexels_video_urls("cinematic modern background", pexels_api_key)

                    for candidate_url in urls:
                        clip_file = os.path.join(temp_dir, f"raw_{idx}_{random.randint(100, 999)}.mp4")
                        if download_video_file(candidate_url, clip_file):
                            raw_dur = get_media_duration(ffmpeg_bin, clip_file)
                            clip_target_dur = random.uniform(4.5, 6.5)
                            start_time = 0.0
                            if raw_dur > clip_target_dur + 1:
                                start_time = random.uniform(0, raw_dur - clip_target_dur)

                            clean_clip = os.path.join(temp_dir, f"clean_{idx}_{random.randint(100, 999)}.mp4")
                            
                            # Scale + Dynamic Zoom Motion (Ken Burns Effect) + 720p HD
                            norm_cmd = [
                                ffmpeg_bin, "-y",
                                "-ss", str(start_time),
                                "-t", str(clip_target_dur),
                                "-i", clip_file,
                                "-vf", "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=z='min(zoom+0.0015,1.2)':d=150:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1280x720,fps=30",
                                "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2", "-an",
                                clean_clip
                            ]
                            subprocess.run(norm_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            if os.path.exists(clean_clip):
                                downloaded_clips.append(clean_clip)
                                break

                if not downloaded_clips:
                    st.error("Video clips download nahi huin. Pexels API Key check karein.")
                    st.stop()

                # 3. Merge Footage
                status_box.write("Footage merge aur transitions stitch ho rahi hain...")
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_file, "w") as f:
                    for _ in range(8):
                        random.shuffle(downloaded_clips)
                        for c in downloaded_clips:
                            f.write(f"file '{c}'\n")

                merged_raw = os.path.join(temp_dir, "merged_raw.mp4")
                merge_cmd = [
                    ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
                    "-t", str(target_duration),
                    merged_raw
                ]
                subprocess.run(merge_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                # 4. Burn Subtitles & Audio Sync
                status_box.write("Screen par synchronized subtitles burn aur final video render ho rahi hai...")
                output_path = os.path.join(temp_dir, "final_subtitled_video.mp4")
                
                # Subtitle filter with clean box & styling
                srt_escaped = srt_path.replace("\\", "/").replace(":", "\\:")
                sub_filter = f"subtitles='{srt_escaped}':force_style='FontSize={font_size},PrimaryColour={color_hex},OutlineColour=&H80000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=35'"

                final_render_cmd = [
                    ffmpeg_bin, "-y",
                    "-i", merged_raw,
                    "-i", audio_path,
                    "-vf", sub_filter,
                    "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
                    "-c:a", "aac", "-b:a", "128k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-pix_fmt", "yuv420p",
                    output_path
                ]
                subprocess.run(final_render_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                status_box.update(label="Complete!", state="complete", expanded=False)
                st.success("✅ Professional Video with Subtitles & Visual Effects tayyar hai!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.video(video_bytes)
                st.download_button(
                    label="📥 Download Subtitled Video",
                    data=video_bytes,
                    file_name="pro_ai_video_with_subs.mp4",
                    mime="video/mp4"
                )

            except Exception as e:
                status_box.update(label="Error aya!", state="error")
                st.error(f"Processing error: {str(e)}")
