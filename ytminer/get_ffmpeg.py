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
  print(data)
  for asset in data['assets']:
    if asset['name'].startswith('ffmpeg-master-latest-{0}-gpl.'.format(plat)):
      return asset['browser_download_url']
# plat = 'Linux'
# url = get_ffmpeg_latest_url(plat)
# print(url)
# zip_name = url.split('/')[-1]
# print("Downloading ffmpeg...")
# r = requests.get(url, stream=True)
# with open(zip_name, 'wb') as f:
#   shutil.copyfileobj(r.raw, f)
# print("Extracting ffmpeg...")
# if zip_name.endswith('.zip'):
#   with zipfile.ZipFile(zip_name, 'r') as zip_ref:
#     zip_ref.extractall('ffmpeg-extracted')
# elif zip_name.endswith('.tar.xz'):
#   with tarfile.open(zip_name) as tar:
#     tar.extractall('ffmpeg-extracted')
# os.remove(zip_name)
# print("Done.")
# print("Installing ffmpeg...")
# if plat == 'Windows':
#   shutil.copyfile('ffmpeg-extracted/{0}/bin/ffmpeg.exe'.format(zip_name.split('.')[0]), 'ffmpeg.exe')
#   shutil.copyfile('ffmpeg-extracted/{0}/bin/ffprobe.exe'.format(zip_name.split('.')[0]), 'ffprobe.exe')
# else:
#   shutil.copyfile('ffmpeg-extracted/{0}/bin/ffmpeg'.format(zip_name.split('.')[0]), 'ffmpeg')
#   shutil.copyfile('ffmpeg-extracted/{0}/bin/ffprobe'.format(zip_name.split('.')[0]), 'ffprobe')
# shutil.rmtree('ffmpeg-extracted')