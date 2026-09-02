import os
import random
import tempfile
import asyncio
import requests
import streamlit as st
import edge_tts
from moviepy import AudioFileClip, VideoFileClip, concatenate_videoclips, vfx

st.set_page_config(page_title="One-Click AI Video Creator", layout="wide")

st.title("🎬 1-Click Script-to-Video AI Creator")
st.write("Sirf script likhein aur Voice Actor select karein — Tool AI Voiceover banayega, relevant clips uthayega aur final video generate karega.")

# Sidebar Settings
st.sidebar.header("🔑 API Setup")
pexels_api_key = st.sidebar.text_input("Pexels API Key", type="password")
pixabay_api_key = st.sidebar.text_input("Pixabay API Key (Optional)", type="password")

st.sidebar.header("🎙️ Voiceover Character")
voice_options = {
    "Urdu - Asad (Male)": "ur-PK-AsadNeural",
    "Urdu - Uzma (Female)": "ur-PK-UzmaNeural",
    "Hindi - Madhur (Male)": "hi-IN-MadhurNeural",
    "Hindi - Swara (Female)": "hi-IN-SwaraNeural",
    "English (US) - Guy (Male)": "en-US-GuyNeural",
    "English (US) - Jenny (Female)": "en-US-JennyNeural",
    "English (UK) - Ryan (Male)": "en-GB-RyanNeural"
}

selected_voice_label = st.sidebar.selectbox("Voice Actor Chunein:", list(voice_options.keys()), index=0)
selected_voice = voice_options[selected_voice_label]

# Main Interface
script_text = st.text_area(
    "Apni Script Yahan Paste Karein:",
    height=250,
    placeholder="Misal ke tor par:\nTechnology har roz badal rahi hai.\nArtificial Intelligence hamari zindagi ko asan bana rahi hai.\nAane wala waqt automated tools ka hai."
)

async def generate_edge_voice(text, voice, output_path):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)

def fetch_pexels_video(query, api_key):
    headers = {"Authorization": api_key}
    url = f"https://api.pexels.com/videos/search?query={query}&per_page=5&orientation=landscape"
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("videos"):
                video = random.choice(data["videos"])
                for f in video.get("video_files", []):
                    if f.get("width", 0) >= 1280:
                        return f.get("link")
                return video["video_files"][0]["link"]
    except Exception:
        pass
    return None

def fetch_pixabay_video(query, api_key):
    url = f"https://pixabay.com/api/videos/?key={api_key}&q={query}&per_page=5"
    try:
        r = requests.get(url, timeout=15)
        if r.status_code == 200:
            data = r.json()
            if data.get("hits"):
                video = random.choice(data["hits"])
                videos_dict = video.get("videos", {})
                for quality in ["large", "medium", "small"]:
                    if quality in videos_dict and videos_dict[quality].get("url"):
                        return videos_dict[quality]["url"]
    except Exception:
        pass
    return None

# Render Process
if st.button("🚀 Generate Full Video Now", type="primary", use_container_width=True):
    if not pexels_api_key and not pixabay_api_key:
        st.error("Sidebar me Pexels API Key zaroor enter karein!")
    elif not script_text.strip():
        st.error("Pehle script likhein!")
    else:
        status_box = st.status("Video generation pipeline active...", expanded=True)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # 1. Natural AI Voiceover Generation
                status_box.write(f"Realistic AI Voiceover generate ho raha hai ({selected_voice_label})...")
                audio_path = os.path.join(temp_dir, "voiceover.mp3")
                asyncio.run(generate_edge_voice(script_text, selected_voice, audio_path))

                audio_clip = AudioFileClip(audio_path)
                target_duration = audio_clip.duration
                status_box.write(f"Voiceover tayyar! Total Duration: {round(target_duration, 1)} seconds")

                # 2. Extract Keywords & Download Matching Clips
                lines = [line.strip() for line in script_text.split("\n") if line.strip()]
                if not lines:
                    lines = ["technology future", "business growth", "cinematic abstract"]

                downloaded_clips = []
                status_box.write("Stock video footage download ho rahi hai...")

                for idx, line in enumerate(lines):
                    query = line.replace(":", " ").replace(".", " ")[:40].strip()
                    video_url = None

                    if pexels_api_key:
                        video_url = fetch_pexels_video(query, pexels_api_key)
                    if not video_url and pixabay_api_key:
                        video_url = fetch_pixabay_video(query, pixabay_api_key)

                    # Generic fallback if no result found
                    if not video_url and pexels_api_key:
                        video_url = fetch_pexels_video("abstract technology motion", pexels_api_key)

                    if video_url:
                        clip_file = os.path.join(temp_dir, f"clip_{idx}.mp4")
                        resp = requests.get(video_url, stream=True, timeout=25)
                        with open(clip_file, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=1024 * 1024):
                                if chunk:
                                    f.write(chunk)
                        downloaded_clips.append(clip_file)

                if not downloaded_clips:
                    st.error("Video clips nahi mil sakin. API Key ya internet check karein.")
                    st.stop()

                # 3. Trim, Transition & Match Duration
                status_box.write("Clips ko voiceover ke sath auto-sync aur edit kiya ja raha hai...")
                video_clips = []
                accumulated_duration = 0
                file_idx = 0

                while accumulated_duration < target_duration:
                    curr_file = downloaded_clips[file_idx % len(downloaded_clips)]
                    clip = VideoFileClip(curr_file).resized(height=1080)

                    needed_duration = target_duration - accumulated_duration
                    if clip.duration > needed_duration:
                        clip = clip.subclipped(0, needed_duration)
                        accumulated_duration += needed_duration
                    else:
                        accumulated_duration += clip.duration

                    clip = clip.with_effects([vfx.FadeIn(0.3), vfx.FadeOut(0.3)])
                    video_clips.append(clip)
                    file_idx += 1

                # 4. Final Video Render
                status_box.write("Final video render ho rahi hai...")
                final_video = concatenate_videoclips(video_clips, method="compose").with_audio(audio_clip)

                output_path = os.path.join(temp_dir, "final_ai_video.mp4")
                final_video.write_videofile(
                    output_path,
                    codec="libx264",
                    audio_codec="aac",
                    fps=30,
                    threads=4,
                    preset="ultrafast"
                )

                audio_clip.close()
                final_video.close()
                for c in video_clips:
                    c.close()

                status_box.update(label="Video complete!", state="complete", expanded=False)
                st.success("✅ Aapki mukammal video tayyar hai!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()

                st.video(video_bytes)
                st.download_button(
                    label="📥 Download Video",
                    data=video_bytes,
                    file_name="complete_ai_video.mp4",
                    mime="video/mp4"
                )

            except Exception as e:
                status_box.update(label="Error aya!", state="error")
                st.error(f"Processing error: {str(e)}")
