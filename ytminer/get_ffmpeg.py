import requests
import zipfile
import tarfile
import os
import shutil

def get_ffmpeg_latest_url(plat):
  """
  Get the latest ffmpeg url from the github releases page.
  """
  url = 'https://api.github.com/repos/yt-dlp/FFmpeg-Builds/releases/latest'
  if plat == 'Windows':
    plat = 'win64'
  elif plat == 'Linux':
    plat = 'linux64'
  else:
    raise Exception('Unsupported platform: ' + plat)
  r = requests.get(url)
  if r.status_code != 200:
    raise Exception('Failed to get latest ffmpeg release: ' + r.text)
  data = r.json()
  for asset in data['assets']:
    if asset['name'].startswith('ffmpeg-master-latest-{0}-gpl.'.format(plat)):
      return asset['browser_download_url']

def extract_ffmpeg_zip(plat, zip_src, dest):
  ffmpeg_extract_dir = os.path.join(dest, 'ffmpeg-extract')
  if zip_src.endswith('.zip'):
    with zipfile.ZipFile(zip_src, 'r') as zip_ref:
      zip_ref.extractall(ffmpeg_extract_dir)
  elif zip_src.endswith('.tar.xz'):
    with tarfile.open(zip_src) as tar:
      tar.extractall(ffmpeg_extract_dir)
  os.remove(zip_src)
  # If plat is Windows, move ffmpeg.exe to the root of the extracted directory.
  zip_name = os.path.basename(zip_src).split('.')[0]
  bin_dir = os.path.join(dest, 'ffmpeg-extract', zip_name, 'bin')
  if plat == 'Windows':
    shutil.copyfile(os.path.join(bin_dir, 'ffmpeg.exe'), os.path.join(dest, 'ffmpeg.exe'))
    shutil.copyfile(os.path.join(bin_dir, 'ffprobe.exe'), os.path.join(dest, 'ffprobe.exe'))
  else:
    shutil.copyfile(os.path.join(bin_dir, 'ffmpeg'), os.path.join(dest, 'ffmpeg'))
    shutil.copyfile(os.path.join(bin_dir, 'ffprobe'), os.path.join(dest, 'ffprobe'))
    # chmod +x ffmpeg and ffprobe
    os.chmod(os.path.join(dest, 'ffmpeg'), 0o755)
    os.chmod(os.path.join(dest, 'ffprobe'), 0o755)
  shutil.rmtree(ffmpeg_extract_dir)
