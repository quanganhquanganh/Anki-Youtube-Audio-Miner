from __future__ import (absolute_import, division,
            print_function, unicode_literals)
import os, sys
import codecs
import re
import glob
import subprocess
import glob
import datetime
import itertools
import time

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip, getFile

from .gui import initializeQtResources

from .threads import SearchThread, DownloadThread, AddThread, ProcessThread
from .paths import dl_dir, audio_dir, user_files_dir
from .messages import error_message #, info_message
from .get_ffmpeg import get_ffmpeg_latest_url, extract_ffmpeg_zip

sys.stderr.isatty = lambda : True

initializeQtResources()

class SubCutter():
  def __init__(self,
        browser,
        db,
        lang: str = "en",
        audio_format = 'mp3',
        image_format = 'jpg',
        ffmpeg = 'ffmpeg',
        set_dl_bar = None,
        set_ext_bar = None,
        set_add_bar = None,
        set_dl_status = None,
        set_ext_status = None,
        set_add_status = None,):
    
    self._db = db
    self._browser = browser
    self.audio_format = audio_format
    self.image_format = image_format
    self.lang = lang
    self.extract_path = os.path.normpath(audio_dir)
    self.download_path = os.path.normpath(dl_dir)
    self._set_dl_bar = set_dl_bar
    self._set_proc_bar = set_ext_bar
    self._set_add_bar = set_add_bar
    self._set_dl_status = set_dl_status
    self._set_proc_status = set_ext_status
    self._set_add_status = set_add_status
    self.ffmpeg = ffmpeg

    #Threads related
    self._dl_thread = None
    self._proc_thread = None
    self._add_thread = None
    self._search_thread = None
    self._matchings = {}
    self._downloaded_videos = []
    self._finish_download = False
    self.running = False

  def update_options(self, **kwargs):
    for key, value in kwargs.items():
      setattr(self, key, value)

  def _create_dl_thread(self,
      hrefs,
      info_callback = None,
      finish_callback = None):
    self._set_dl_bar(0)
    dl_thread = DownloadThread(hrefs = hrefs,
      lang = self.lang, 
      download_path = self.download_path)
    dl_thread.done_info.connect(info_callback)
    dl_thread.percent.connect(self._set_dl_bar)
    dl_thread.amount.connect(self._set_dl_status)
    dl_thread.done.connect(finish_callback)
    return dl_thread

  def _create_proc_thread(self, video_path, sequences, finish_callback = None):
    proc_thread = ProcessThread(video_path,
                    extract_path=self.extract_path, 
                    sequences=sequences,
                    audio_format=self.audio_format,
                    ffmpeg=self.ffmpeg,
                    image_format=self.image_format)
    proc_thread.done_files.connect(finish_callback)
    proc_thread.percent.connect(self._set_proc_bar)
    return proc_thread

  def _download_info(self, hrefs, info_callback = None, finish_dl_thread = None):
    #Get vtt filename then convert it to srt
    def default_finish_dl():
      self._finish_download = True
      self._set_dl_status("Finished downloading subtitles!")
      self.running = False
    hrefs = [{'url': href, 'type': 'info'} for href in hrefs]
    self._dl_thread = self._create_dl_thread(hrefs, 
      info_callback = info_callback,
      finish_callback = finish_dl_thread or default_finish_dl)
    self._dl_thread.start()

  def _store_subtitle(self, info):
    video_id = info['id']
    filename = info['filename']
    srt_filepath = None
    try:
      srt_filepath = self._convert_to_srt(filename)
      sequences = []
      for s in self._make_list(srt_filepath):
        s[2] = s[2].replace("\n", "")
        sequences.append(s)
      self._db.insert_video(info['title'], video_id, self.lang, datetime.datetime.now())
      self._db.insert_sequences(video_id, sequences)
    except Exception as e:
      self._db.delete_video_by_id(video_id)
      error_message("Error while processing video {0}".format(e))
    if os.path.exists(filename):
      os.remove(filename)
    if srt_filepath and os.path.exists(srt_filepath):
      os.remove(srt_filepath)

  def _add_downloaded(self, done_info):
      if 'id' in done_info and 'filename' in done_info:
        id = done_info['id']
        filename = done_info['filename']
        filetype = done_info['type']
        filepath = os.path.join(self.download_path, filename)
        self._db.path_update_video(id, filepath)
        self._db.type_update_video(id, filetype)
        video = self._db.get_video(id)
        video['type'] = done_info['type']
        self._downloaded_videos = itertools.chain(self._downloaded_videos, [video])
      if self._proc_thread is None:
        self._process_next()

  def _process_next(self, files = []):
    # Add filepath to _matchings
    for f in files:
      if f['type'] == 'audio':
        self._matchings[f['video_id']][f['sequence_id']]['a_filepath'] = f['filepath']
      elif f['type'] == 'image':
        self._matchings[f['video_id']][f['sequence_id']]['i_filepath'] = f['filepath']
    video = None
    try:
      video = next(self._downloaded_videos)
    except StopIteration:
      if self._finish_download:
        self._set_proc_status("Finished")
        self._add_thread = AddThread(self._matchings, self._browser)
        self._add_thread.percent.connect(self._set_add_bar)
        self._add_thread.done.connect(self.close)
        self._add_thread.start()
      else:
        self._set_proc_status("Waiting for download...")
      return

    sequences = self._matchings[video['id']]
    # Convert sequences to list
    sequences = list(sequences.values())
    self._proc_thread = self._create_proc_thread(video['path'], sequences, self._process_next)
    self._proc_thread.start()
    self._set_proc_status("Extracting {}...".format(video['title']))

  def _process(self, matchings: dict):
    self._set_dl_bar(0)
    self._set_proc_bar(0)
    self._set_add_bar(0)

    self._finish_download = False
    self._matchings = matchings
    if len(self._matchings) == 0:
      self._set_dl_status("No match found")
      self.running = False
      return

    audio_hrefs = []
    vid_hrefs = []
    to_be_extracted = []
    for vid in self._matchings:
      dl_vid = False # Download video
      dl_audio = False # Download audio
      for seq in self._matchings[vid].values():
        seq['type'] = []
        if seq['pos'] in seq['note']['screenshot_flds']:
          seq['type'].append('image')
          dl_vid = True
        if seq['pos'] in seq['note']['audio_flds']:
          seq['type'].append('audio')
          dl_audio = not dl_vid
      if dl_vid:
        vid_hrefs.append(vid)
      if dl_audio:
        audio_hrefs.append(vid)

    download_folder = os.path.join(dl_dir, "*")
    files = glob.glob(download_folder.replace("\\", "/"))
    for f in files:
      # Check if file name is in audio_hrefs
      basename = os.path.basename(f)
      video_id = basename.split(".")[0]
      video = self._db.get_video(video_id)

      if video_id not in vid_hrefs and video_id not in audio_hrefs:
        os.remove(f)
        continue
      # If video already existed, no need to download either it or the audio
      # If only audio found, and you need to extract images, keep the video href
      if not basename.endswith(".part") and video['type'] == 'image':
        if video_id in vid_hrefs:
          vid_hrefs.remove(video_id)
          to_be_extracted.append(video)
        if video_id in audio_hrefs:
          audio_hrefs.remove(video_id)
          to_be_extracted.append(video)
      elif not basename.endswith(".part") and video['type'] == 'audio':
        if video_id in vid_hrefs:
          os.remove(f)
        elif video_id in audio_hrefs:
          to_be_extracted.append(video)
          audio_hrefs.remove(video_id)

    audio_folder = os.path.join(audio_dir, "*")
    files = glob.glob(audio_folder.replace("\\", "/"))
    for f in files:
      basename = os.path.basename(f)
      video_id = '_'.join(basename.split(".")[0].split("_")[0:-1])
      if video_id not in audio_hrefs and video_id not in vid_hrefs and video_id not in [v['id'] for v in to_be_extracted]:
        os.remove(f)
        continue

    self._downloaded_videos = iter(to_be_extracted)
    hrefs = [{'url': href, 'type': 'image'} for href in vid_hrefs]
    hrefs.extend([{'url': href, 'type': 'audio'} for href in audio_hrefs])
    if len(hrefs) == 0:
      self._finish_download = True
    else:
      self._set_dl_status("Downloading {0} files".format(len(hrefs)))

      def finish_dl_all():
        self._finish_download = True

      self._dl_thread = self._create_dl_thread(hrefs,
        self._add_downloaded,
        finish_dl_all)
      self._dl_thread.start()

    self._process_next()

  def _convert_to_srt(self, filename):
    filepath = os.path.join(self.download_path, filename)
    srt_filepath = os.path.join(self.download_path, filename.replace(".vtt", ".srt"))
    command = self.ffmpeg + ' ' + '-i' + ' ' + filepath + ' ' + srt_filepath + ' -loglevel quiet'
    use_shell = True
    try:
      output = subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
    except Exception as e:
      error_message("Error: Couldn't convert .vtt subtitle to .srt!\n{}".format(e))
      return
    return srt_filepath
    
  def _make_list(self, sub_path):
    have_sub = os.path.exists(sub_path)
    
    if have_sub is False:
      error_message("Error: No .srt subtitle found.")
      return
    
    content = codecs.open((sub_path).replace("\\", "/"), 'r', 'UTF-8').readlines()
    
    time_pat = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})\n")
    empty_pat = re.compile(r"\s+")
    num_pat = re.compile(r"\d+\n")
    begin_time = 0
    end_time = 0

    ms_per_sec = 1000
    ms_per_min = 1000 * 60
    ms_per_hour = 1000 * 60 * 60
  
    sequences = []
    prev_seq = [0, 0, '']
    prev_s = ""
    
    for s in content:
      s = re.sub('\r', '', s)
      if (not s) or (empty_pat.match(s)) or (num_pat.match(s)):
        continue
      matches = time_pat.match(s)
      if(matches):
        begin_time = int(matches[4]) + int(matches[3]) * ms_per_sec + int(matches[2]) * ms_per_min + int(matches[1]) * ms_per_hour
        end_time = int(matches[8]) + int(matches[7]) * ms_per_sec + int(matches[6]) * ms_per_min + int(matches[5]) * ms_per_hour
      elif (s == prev_s):
        prev_seq[1] = end_time / 1000
      elif (s != prev_s):
        prev_seq[2] = prev_s
        sequences.append(prev_seq)
        prev_seq = [begin_time/1000, end_time/1000, ""]
        prev_s = s
    
    prev_seq[2] = prev_s
    sequences.append(prev_seq)
    return sequences[1:]

  def _clean_audio(self):
    audio_folder = os.path.join(audio_dir, "*")
    files = glob.glob(audio_folder.replace("\\", "/"))
    for f in files:
      os.remove(f)
  
  def _clean_downloads(self):
    download_folder = os.path.join(dl_dir, "*")
    files = glob.glob(download_folder.replace("\\", "/"))
    for f in files:
      os.remove(f)

  def run_store(self, hrefs):
    if self.running:
      return
    self.running = True
    self._download_info(hrefs, self._store_subtitle)

  def _store_info(self, info, fields):
    video_id = info['id']
    self._store_subtitle(info)
    matchings = self._db.get_matchings_from_video(video_id)
    for seq in [s for v in matchings.values() for s in v.values()]:
      seq['note'] = {}
      seq['pos'] = 0
      seq['deck_name'] = info['title']
      for f in fields:
        seq['note'][f] = {}
        for i, v in enumerate(fields[f]):
          seq['note'][f][i] = v
    self._matchings.update(matchings)

  def run_create_decks(self, hrefs, fields):
    if self.running:
      return
    self.running = True
    self._matchings = {}
    
    if 'match_fld' in fields:
      fields.pop('match_fld')
    if sum([len(fields[f]) for f in fields]) == 0:
      self._set_dl_status("No fields for creating decks.")
      self.running = False
      return

    def finish_getting_info():
      self._set_dl_status("Finished getting info.")
      self._process(self._matchings)
    def store_info(info):
      self._store_info(info, fields)
    self._download_info(hrefs, store_info, finish_getting_info)

  def download_ffmpeg(self):
    if self.running:
      return
    self.running = True
    # Get platform
    plat = sys.platform
    if plat == 'win64' or plat == 'win32':
      plat = 'Windows'
    else:
      plat = 'Linux'

    url = get_ffmpeg_latest_url(plat)
    url = {'url': url, 'type': 'file'}
    self._dl_thread = DownloadThread(hrefs = [url],
                                  download_path = user_files_dir)

    def extract_ffmpeg(zip_file):
      self._set_dl_status("Extracting ffmpeg...")
      extract_ffmpeg_zip(plat, zip_file['path'], user_files_dir)
      self._set_dl_status("Finished installing ffmpeg!")
      self.running = False

    self._dl_thread.percent.connect(self._set_dl_bar)
    self._dl_thread.amount.connect(self._set_dl_status)
    self._dl_thread.done_info.connect(extract_ffmpeg)
    self._dl_thread.start()

  def run(self, notes):
    # self._clean_downloads()
    if self.running:
      return
    self.running = True
    self._search_thread = SearchThread(self._db, notes)
    self._search_thread.matchings.connect(self._process)
    self._search_thread.start()
    self._set_dl_status("Searching videos for %d " % len(notes)
      + ("cards..." if len(notes) > 1 else "card..."))

  def close(self):
    # Exit all threads
    if self._search_thread:
      self._search_thread.terminate()
      self._search_thread = None
    if self._dl_thread:
      self._dl_thread.terminate()
      self._dl_thread = None
    if self._proc_thread:
      self._proc_thread.terminate()
      self._proc_thread = None
    self.running = False
