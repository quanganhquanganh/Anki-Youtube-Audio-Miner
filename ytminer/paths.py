import os

home = os.path.dirname(os.path.abspath(__file__))
root = os.path.dirname(home)
user_files_dir = os.path.join(root, 'user_files')
storage_path = os.path.join(user_files_dir, 'storage.db')
dl_dir = os.path.join(user_files_dir, 'downloads')
audio_dir = os.path.join(user_files_dir, 'audio')
downloaded_ffmpeg = os.path.join(user_files_dir, 'ffmpeg.exe') if os.name == 'nt' else os.path.join(user_files_dir, 'ffmpeg')