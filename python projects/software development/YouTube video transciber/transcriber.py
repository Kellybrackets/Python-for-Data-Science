import argparse
import os
import time
import requests
from pytube import YouTube
from pytube.exceptions import PytubeError
from urllib.error import HTTPError
from zipfile import ZipFile

def parse_arguments():
    parser = argparse.ArgumentParser(prog='transcriber', description='YouTube to transcript CLI tool')
    parser.add_argument('-i', required=True, help='Enter the URL of YouTube video')
    return parser.parse_args()

def read_api_key():
    try:
        with open("api.txt", "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        print("❌ Error: api.txt file not found.")
        exit(1)

def download_audio(url):
    try:
        yt = YouTube(url)
        audio_stream = yt.streams.get_audio_only()
        filename = "yt_audio.mp4"
        audio_stream.download(filename=filename)
        print("✅ Audio downloaded as:", filename)
        return filename
    except (PytubeError, HTTPError) as e:
        print(f"❌ Error downloading YouTube video: {e}")
        exit(1)

def upload_audio(filename, api_key):
    def read_file(filename, chunk_size=5242880):
        with open(filename, 'rb') as f:
            while chunk := f.read(chunk_size):
                yield chunk
    headers = {'authorization': api_key}
    response = requests.post('https://api.assemblyai.com/v2/upload',
                             headers=headers,
                             data=read_file(filename))
    if response.status_code != 200:
        print("❌ Error uploading audio.")
        print(response.json())
        exit(1)
    print("✅ Audio uploaded to AssemblyAI")
    return response.json()['upload_url']

def request_transcription(audio_url, api_key):
    endpoint = "https://api.assemblyai.com/v2/transcript"
    json = { "audio_url": audio_url }
    headers = {
        "authorization": api_key,
        "content-type": "application/json"
    }
    response = requests.post(endpoint, json=json, headers=headers)
    if response.status_code != 200:
        print("❌ Error requesting transcription.")
        print(response.json())
        exit(1)
    print("✅ Transcription requested")
    return response.json()["id"]

def poll_transcription(transcript_id, api_key):
    endpoint = f"https://api.assemblyai.com/v2/transcript/{transcript_id}"
    headers = { "authorization": api_key }
    while True:
        response = requests.get(endpoint, headers=headers).json()
        status = response['status']
        if status == 'completed':
            print("✅ Transcription completed")
            return response
        elif status == 'error':
            print("❌ Transcription failed")
            print(response)
            exit(1)
        print("⏳ Transcription in progress...")
        time.sleep(5)

def save_transcripts(response, api_key):
    text = response["text"]
    print("\n📝 Transcript:\n")
    print(text)

    with open("yt.txt", "w") as f:
        f.write(text)
    
    srt_endpoint = f"https://api.assemblyai.com/v2/transcript/{response['id']}/srt"
    headers = { "authorization": api_key }
    srt_response = requests.get(srt_endpoint, headers=headers)

    with open("yt.srt", "w") as f:
        f.write(srt_response.text)

    with ZipFile('transcription.zip', 'w') as zipf:
        zipf.write('yt.txt')
        zipf.write('yt.srt')

    print("✅ Files saved: yt.txt, yt.srt, transcription.zip")

# --- Main Execution ---
if __name__ == "__main__":
    args = parse_arguments()
    api_key = read_api_key()
    audio_file = download_audio(args.i)
    audio_url = upload_audio(audio_file, api_key)
    transcript_id = request_transcription(audio_url, api_key)
    response = poll_transcription(transcript_id, api_key)
    save_transcripts(response, api_key)
