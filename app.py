import os
import random
import tempfile
import streamlit as st
from moviepy.editor import AudioFileClip, VideoFileClip, concatenate_videoclips, vfx

st.set_page_config(page_title="Auto Video Sync Editor", layout="centered")

st.title("🎬 Automated Voiceover Video Editor")
st.write("Apni audio aur video files upload karein, tool automatically voiceover ke mutabiq edit karke final video download ke liye de dega.")

# 1. Audio Upload Box
st.subheader("1. Audio / Voiceover File")
audio_file = st.file_uploader("Audio upload karein (.mp3, .wav, .m4a)", type=["mp3", "wav", "m4a"])

# 2. Video Upload Box
st.subheader("2. Video Footage")
video_files = st.file_uploader(
    "Single video ya multiple video clips upload karein (.mp4, .mov)", 
    type=["mp4", "mov", "avi"], 
    accept_multiple_files=True
)

# 3. Process & Render
if st.button("🚀 Render & Generate Video", type="primary"):
    if not audio_file:
        st.error("Pehle Audio file upload karein!")
    elif not video_files:
        st.error("Kam az kam ek Video file upload karein!")
    else:
        status_box = st.status("Video process ho rahi hai...", expanded=True)
        
        with tempfile.TemporaryDirectory() as temp_dir:
            try:
                # Save uploaded audio
                audio_path = os.path.join(temp_dir, audio_file.name)
                with open(audio_path, "wb") as f:
                    f.write(audio_file.getbuffer())

                # Save uploaded videos
                saved_video_paths = []
                for vfile in video_files:
                    vpath = os.path.join(temp_dir, vfile.name)
                    with open(vpath, "wb") as f:
                        f.write(vfile.getbuffer())
                    saved_video_paths.append(vpath)

                status_box.write("Audio duration analyze ho rahi hai...")
                audio_clip = AudioFileClip(audio_path)
                target_duration = audio_clip.duration

                status_box.write("Clips sync aur auto-trim ho rahi hain...")
                video_clips = []
                accumulated_duration = 0
                file_idx = 0
                
                random.shuffle(saved_video_paths)

                while accumulated_duration < target_duration:
                    current_path = saved_video_paths[file_idx % len(saved_video_paths)]
                    clip = VideoFileClip(current_path)

                    clip = clip.resize(height=1080)

                    needed_duration = target_duration - accumulated_duration
                    if clip.duration > needed_duration:
                        clip = clip.subclip(0, needed_duration)
                        accumulated_duration += needed_duration
                    else:
                        accumulated_duration += clip.duration

                    clip = clip.fx(vfx.fadein, 0.3).fx(vfx.fadeout, 0.3)
                    video_clips.append(clip)
                    file_idx += 1

                status_box.write("Video concatenate aur voiceover sync ho raha hai...")
                final_video = concatenate_videoclips(video_clips, method="compose")
                final_video = final_video.set_audio(audio_clip)

                output_path = os.path.join(temp_dir, "final_output.mp4")
                status_box.write("Final MP4 export ho rahi hai...")
                
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

                status_box.update(label="Video tayyar hai!", state="complete", expanded=False)
                st.success("✅ Video editing mukammal ho chuki hai!")

                with open(output_path, "rb") as f:
                    video_bytes = f.read()
                    
                st.video(video_bytes)
                st.download_button(
                    label="📥 Download Edited Video",
                    data=video_bytes,
                    file_name="auto_edited_video.mp4",
                    mime="video/mp4"
                )

            except Exception as e:
                status_box.update(label="Error aya hai!", state="error")
                st.error(f"Processing error: {str(e)}")
