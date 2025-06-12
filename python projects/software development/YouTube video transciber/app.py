import streamlit as st
from pytube import YouTube
import os
import requests
from zipfile import ZipFile
from pytube.exceptions import PytubeError
from urllib.error import HTTPError

# Title and progress bar
st.markdown('# 📝 **Transcriber App**')
bar = st.progress(0)

# 1. Read API from text file / secrets
api_key = st.secrets['api_key']

# Sidebar input
st.sidebar.header('Input parameter')

with st.sidebar.form(key='my_form'):
    URL = st.text_input('Enter URL of YouTube video:')
    submit_button = st.form_submit_button(label='Go')

# --- Function Definitions ---

# 2. Download audio from YouTube
def get_yt(URL):
    try:
        video = YouTube(URL)
        yt_stream = video.streams.get_audio_only()
        yt_stream.download(filename="yt_audio.mp4")
        bar.progress(10)
        return "yt_audio.mp4"
    except HTTPError as e:
        st.error(f"HTTP Error: {e.code} - {e.reason}")
    except PytubeError as e:
        st.error(f"Pytube Error: {str(e)}")
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
    return None

# 3. Transcribe audio file using AssemblyAI
def transcribe_yt(filename):
    if not filename or not os.path.exists(filename):
        st.error("Audio file not found.")
        return

    bar.progress(20)

    def read_file(filename, chunk_size=5242880):
        with open(filename, 'rb') as _file:
            while True:
                data = _file.read(chunk_size)
                if not data:
                    break
                yield data

    headers = {'authorization': api_key}
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             data=read_file(filename))

    if response.status_code != 200:
        st.error("Failed to upload audio to AssemblyAI.")
        return

    audio_url = response.json().get('upload_url')
    bar.progress(30)

    # Transcribe audio
    transcript_request = {
        "audio_url": audio_url
    }
    headers.update({"content-type": "application/json"})
    transcript_response = requests.post("https://api.assemblyai.com/v2/transcript",
                                        json=transcript_request,
                                        headers=headers)

    if transcript_response.status_code != 200:
        st.error("Transcription request failed.")
        return

    transcript_id = transcript_response.json()["id"]
    bar.progress(50)

    # Poll for completion
    status_endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    while True:
        result = requests.get(status_endpoint, headers=headers).json()
        if result['status'] == 'completed':
            break
        elif result['status'] == 'error':
            st.error("Transcription failed.")
            return
        st.warning("Transcription in progress...")
        time.sleep(5)

    bar.progress(100)

    # Show and save transcription
    st.header('Output')
    transcript_text = result.get("text", "")
    st.success(transcript_text)

    with open("yt.txt", "w") as f:
        f.write(transcript_text)

    srt_response = requests.get(status_endpoint + "/srt", headers=headers)
    with open("yt.srt", "w") as f:
        f.write(srt_response.text)

    with ZipFile('transcription.zip', 'w') as zipf:
        zipf.write('yt.txt')
        zipf.write('yt.srt')

# --- Main Execution ---

if submit_button:
    audio_file = get_yt(URL)
    if audio_file:
        transcribe_yt(audio_file)

        with open("transcription.zip", "rb") as zip_download:
            st.download_button(
                label="Download ZIP",
                data=zip_download,
                file_name="transcription.zip",
                mime="application/zip"
            )
