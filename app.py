import os
import random
import tempfile
import asyncio
import subprocess
import requests
import streamlit as st
import edge_tts
import imageio_ffmpeg

st.set_page_config(page_title="1-Click AI Video Creator (ElevenLabs)", layout="wide")

st.title("🎬 1-Click Script-to-Video AI Creator")
st.write("Script likhein, ElevenLabs ki kisi bhi voice ka preview sunein aur video generate karein.")

# Sidebar Settings
st.sidebar.header("🔑 API Keys Setup")
pexels_api_key = st.sidebar.text_input("Pexels API Key", type="password")
elevenlabs_api_key = st.sidebar.text_input("ElevenLabs API Key (Optional)", type="password")

# --- ElevenLabs Voices Fetching & Selection ---
st.sidebar.header("🎙️ Voiceover Character")

voice_engine = st.sidebar.radio("Voice Engine:", ["ElevenLabs (Hyper Realistic)", "Edge-TTS (Free)"])

selected_voice_id = None
selected_edge_voice = None

if voice_engine == "ElevenLabs (Hyper Realistic)":
    if not elevenlabs_api_key:
        st.sidebar.warning("Sidebar me apni ElevenLabs API Key enter karein.")
    else:
        try:
            # Fetch all voices from ElevenLabs account
            headers = {"xi-api-key": elevenlabs_api_key}
            res = requests.get("https://api.elevenlabs.io/v1/voices", headers=headers, timeout=10)
            if res.status_code == 200:
                voices_data = res.json().get("voices", [])
                
                # Map name with metadata
                voice_dict = {}
                for v in voices_data:
                    label = f"{v['name']} ({v.get('labels', {}).get('accent', 'Global')} - {v.get('labels', {}).get('gender', '')})"
                    voice_dict[label] = {
                        "id": v["voice_id"],
                        "preview_url": v.get("preview_url")
                    }
                
                selected_label = st.sidebar.selectbox("Voice Select Karein:", list(voice_dict.keys()))
                selected_voice_id = voice_dict[selected_label]["id"]
                preview_audio_url = voice_dict[selected_label]["preview_url"]
                
                # Voice Audio Preview Player
                if preview_audio_url:
                    st.sidebar.write("🔊 **Voice Preview:**")
                    st.sidebar.audio(preview_audio_url)
                else:
                    st.sidebar.info("Is voice ka preview sample available nahi hai.")
            else:
                st.sidebar.error("Invalid ElevenLabs API Key!")
        except Exception as e:
            st.sidebar.error(f"Voice load error: {e}")
else:
    # Free Fallback Voices
    edge_voices = {
        "Urdu - Asad (Male)": "ur-PK-AsadNeural",
        "Urdu - Uzma (Female)": "ur-PK-UzmaNeural",
        "Hindi - Madhur (Male)": "hi-IN-MadhurNeural",
        "Hindi - Swara (Female)": "hi-IN-SwaraNeural",
        "English (US) - Guy (Male)": "en-US-GuyNeural",
        "English (US) - Jenny (Female)": "en-US-JennyNeural"
    }
    selected_edge_label = st.sidebar.selectbox("Edge Voice Select Karein:", list(edge_voices.keys()))
    selected_edge_voice = edge_voices[selected_edge_label]

# Main Script Input
script_text = st.text_area(
    "Apni Script Yahan Paste Karein:",
    height=230,
    placeholder="Technology har roz badal rahi hai.\nArtificial intelligence hamari zindagi ko asan bana rahi hai.\nAane wala waqt automated tools ka hai."
)

# Helpers
async def generate_edge_voice(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def generate_elevenlabs_voice(text, voice_id, api_key, output_path):
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "xi-api-key": api_key,
        "Content-Type": "application/json"
    }
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.5,
            "similarity_boost": 0.75
        }
    }
    r = requests.post(url, json=payload, headers=headers, timeout=60)
    if r.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(r.content)
        return True
    else:
        raise Exception(f"ElevenLabs Error: {r.text}")

def get_audio_duration(ffmpeg_path, file_path):
    cmd = [ffmpeg_path, "-i", file_path, "-f", "null", "-"]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    for line in result.stderr.split("\n"):
        if "Duration" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = time_str.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    return 10.0

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

# Main Trigger
if st.button("🚀 Generate Full Video Now", type="primary", use_container_width=True):
    if not pexels_api_key:
        st.error("Sidebar me Pexels API Key enter karein!")
    elif not script_text.strip():
        st.error("Pehle script likhein!")
    elif voice_engine == "ElevenLabs (Hyper Realistic)" and not selected_voice_id:
        st.error("ElevenLabs API Key aur Voice zaroor select karein!")
    else:
        status_box = st.status("Video generation pipeline active...", expanded=True)
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()

        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Voiceover Generation
                audio_path = os.path.join(temp_dir, "voiceover.mp3")
                
                if voice_engine == "ElevenLabs (Hyper Realistic)":
                    status_box.write("ElevenLabs AI Voiceover generate ho raha hai...")
                    generate_elevenlabs_voice(script_text, selected_voice_id, elevenlabs_api_key, audio_path)
                else:
                    status_box.write("Edge-TTS Voiceover generate ho raha hai...")
                    asyncio.run(generate_edge_voice(script_text, selected_edge_voice, audio_path))

                target_duration = get_audio_duration(ffmpeg_bin, audio_path)
                status_box.write(f"Voiceover mukammal! Duration: {round(target_duration, 1)}s")

                # 2. Clips Search & Download
                raw_lines = [line.strip() for line in script_text.split("\n") if line.strip()]
                lines = []
                for l in raw_lines:
                    sentences = [s.strip() for s in l.replace(".", "\n").replace(";", "\n").split("\n") if len(s.strip()) > 3]
                    lines.extend(sentences)

                if not lines:
                    lines = ["technology background", "business modern", "city life", "abstract motion"]

                downloaded_clips = []
                status_box.write("Relevant stock video footage download ho rahi hai...")

                for idx, line in enumerate(lines):
                    query = line[:35].strip()
                    urls = fetch_pexels_video_urls(query, pexels_api_key)
                    if not urls:
                        urls = fetch_pexels_video_urls("cinematic modern background", pexels_api_key)

                    for candidate_url in urls:
                        clip_file = os.path.join(temp_dir, f"raw_{idx}_{random.randint(100, 999)}.mp4")
                        if download_video_file(candidate_url, clip_file):
                            clean_clip = os.path.join(temp_dir, f"clean_{idx}_{random.randint(100, 999)}.mp4")
                            norm_cmd = [
                                ffmpeg_bin, "-y", "-i", clip_file,
                                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30",
                                "-c:v", "libx264", "-preset", "ultrafast", "-an", clean_clip
                            ]
                            subprocess.run(norm_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            if os.path.exists(clean_clip):
                                downloaded_clips.append(clean_clip)
                                break

                if not downloaded_clips:
                    st.error("Video clips download nahi huin. Pexels key check karein.")
                    st.stop()

                # 3. Concat & Final Render
                status_box.write("Clips merge aur final video render ho rahi hai...")
                concat_file = os.path.join(temp_dir, "concat_list.txt")
                with open(concat_file, "w") as f:
                    for _ in range(6):
                        random.shuffle(downloaded_clips)
                        for c in downloaded_clips:
                            f.write(f"file '{c}'\n")

                output_path = os.path.join(temp_dir, "final_video.mp4")
                render_cmd = [
                    ffmpeg_bin, "-y", "-f", "concat", "-safe", "0", "-i", concat_file,
                    "-i", audio_path,
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-c:a", "aac", "-b:a", "192k",
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-t", str(target_duration),
                    "-pix_fmt", "yuv420p",
                    output_path
                ]
                subprocess.run(render_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

                status_box.update(label="Complete!", state="complete", expanded=False)
                st.success("✅ ElevenLabs Voiceover ke sath video tayyar hai!")

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
