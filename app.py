import os
import random
import tempfile
import asyncio
import subprocess
import requests
import streamlit as st
import edge_tts
import imageio_ffmpeg

st.set_page_config(page_title="1-Click AI Video Creator", layout="wide")

st.title("🎬 1-Click Script-to-Video AI Creator")
st.write("Script likhein — Tool AI Voiceover banayega aur 5-7 second ke dynamic clips auto-stitch karke video render karega.")

# Sidebar Settings
st.sidebar.header("🔑 API Setup")
pexels_api_key = st.sidebar.text_input("Pexels API Key", type="password")

# High Quality AI Voices
st.sidebar.header("🎙️ Realistic AI Voices")
voice_library = {
    "Urdu - Asad (Male)": "ur-PK-AsadNeural",
    "Urdu - Uzma (Female)": "ur-PK-UzmaNeural",
    "Hindi - Madhur (Male)": "hi-IN-MadhurNeural",
    "Hindi - Swara (Female)": "hi-IN-SwaraNeural",
    "English (US) - Christopher (Male)": "en-US-ChristopherNeural",
    "English (US) - Guy (Male)": "en-US-GuyNeural",
    "English (US) - Jenny (Female)": "en-US-JennyNeural"
}

selected_voice_label = st.sidebar.selectbox("Voice Actor Select Karein:", list(voice_library.keys()), index=0)
selected_voice = voice_library[selected_voice_label]

st.sidebar.subheader("🔊 Voice Preview")
if st.sidebar.button("Test Voice"):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as preview_tmp:
        test_phrase = "Yeh meri natural voice ka preview sample hai."
        asyncio.run(edge_tts.Communicate(test_phrase, selected_voice).save(preview_tmp.name))
        st.sidebar.audio(preview_tmp.name)

# Main Input
script_text = st.text_area(
    "Apni Script Yahan Paste Karein:",
    height=220,
    placeholder="Script yahan likhein..."
)

async def generate_voice(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

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
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=8&orientation=landscape"
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
if st.button("🚀 Generate Full Video Now", type="primary", use_container_width=True):
    if not pexels_api_key:
        st.error("Sidebar me Pexels API Key zaroor enter karein!")
    elif not script_text.strip():
        st.error("Pehle script likhein!")
    else:
        status_box = st.status("Video generation pipeline active...", expanded=True)
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. AI Voiceover Generation
                status_box.write(f"Voiceover generate ho raha hai ({selected_voice_label})...")
                audio_path = os.path.join(temp_dir, "voiceover.mp3")
                asyncio.run(generate_voice(script_text, selected_voice, audio_path))

                target_duration = get_media_duration(ffmpeg_bin, audio_path)
                status_box.write(f"Voiceover tayyar! Total Duration: {round(target_duration, 1)}s")

                # 2. Extract Keywords & Download
                raw_lines = [line.strip() for line in script_text.split("\n") if line.strip()]
                lines = []
                for l in raw_lines:
                    sentences = [s.strip() for s in l.replace(".", "\n").replace(";", "\n").split("\n") if len(s.strip()) > 3]
                    lines.extend(sentences)

                if not lines:
                    lines = ["technology motion", "business finance", "modern world", "digital data"]

                downloaded_clips = []
                status_box.write("Stock video footage download aur 5-7 second trim ho rahi hai...")

                for idx, line in enumerate(lines):
                    query = line[:35].strip()
                    urls = fetch_pexels_video_urls(query, pexels_api_key)
                    if not urls:
                        urls = fetch_pexels_video_urls("cinematic modern abstract", pexels_api_key)

                    for candidate_url in urls:
                        clip_file = os.path.join(temp_dir, f"raw_{idx}_{random.randint(100, 999)}.mp4")
                        if download_video_file(candidate_url, clip_file):
                            # Clip duration check
                            raw_dur = get_media_duration(ffmpeg_bin, clip_file)
                            
                            # Trim to random 5 to 7 seconds snippet
                            clip_target_dur = random.uniform(5.0, 7.0)
                            start_time = 0.0
                            if raw_dur > clip_target_dur + 1:
                                start_time = random.uniform(0, raw_dur - clip_target_dur)

                            clean_clip = os.path.join(temp_dir, f"clean_{idx}_{random.randint(100, 999)}.mp4")
                            
                            # Optimized 720p render to save CPU & stay fast
                            norm_cmd = [
                                ffmpeg_bin, "-y",
                                "-ss", str(start_time),
                                "-t", str(clip_target_dur),
                                "-i", clip_file,
                                "-vf", "scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,fps=30",
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

                # 3. Clips Merge
                status_box.write("Dynamic short clips merge ho rahi hain...")
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_file, "w") as f:
                    for _ in range(8):
                        random.shuffle(downloaded_clips)
                        for c in downloaded_clips:
                            f.write(f"file '{c}'\n")

                # 4. Final Fast Render
                output_path = os.path.join(temp_dir, "final_video.mp4")
                render_cmd = [
                    ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", audio_path,
                    "-c:v", "libx264", "-preset", "ultrafast", "-threads", "2",
                    "-c:a", "aac", "-b:a", "128k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-t", str(target_duration),
                    "-pix_fmt", "yuv420p",
                    output_path
                ]
                subprocess.run(render_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                status_box.update(label="Complete!", state="complete", expanded=False)
                st.success("✅ Fast 5-7 second pacing ke sath video tayyar hai!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.video(video_bytes)
                st.download_button(
                    label="📥 Download Video",
                    data=video_bytes,
                    file_name="final_ai_video.mp4",
                    mime="video/mp4"
                )

            except Exception as e:
                status_box.update(label="Error aya!", state="error")
                st.error(f"Processing error: {str(e)}")
