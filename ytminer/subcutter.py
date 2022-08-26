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
from .paths import dl_dir, audio_dir
from .messages import error_message #, info_message

sys.stderr.isatty = lambda : True

initializeQtResources()

class SubCutter():
  def __init__(self,
        browser,
        db,
        lang: str = "en",
        audio_format = 'mp3',
        image_format = 'jpg',
        dl_bar = None,
        ext_bar = None,
        add_bar = None,
        dl_status = None,
        ext_status = None,
        add_status = None,):
    
    self._db = db
    self._browser = browser
    self.audio_format = audio_format
    self.image_format = image_format
    self.lang = lang
    self.extract_path = os.path.normpath(audio_dir)
    self.download_path = os.path.normpath(dl_dir)
    self._dl_bar = dl_bar
    self._proc_bar = ext_bar
    self._add_bar = add_bar
    self._dl_status = dl_status
    self._proc_status = ext_status
    self._add_status = add_status
    self._ffmpeg = "ffmpeg"

    #Threads related
    self._dl_thread = None
    self._proc_thread = None
    self._add_thread = None
    self._search_thread = None
    self._matchings = None
    self._downloaded_videos = None
    self._finish_download = False
    self.done_flag = False

  def update_options(self, **kwargs):
    for key, value in kwargs.items():
      setattr(self, key, value)

  def _create_dl_thread(self, hrefs, type, finish_callback = None):
    dl_thread = DownloadThread(hrefs = hrefs,
                                  lang = self.lang, 
                                  download_path = self.download_path,
                                  type = type)
    dl_thread.done_info.connect(self._add_downloaded)
    dl_thread.percent.connect(self._dl_bar.setValue)
    dl_thread.amount.connect(self._dl_status.setText)
    dl_thread.done.connect(finish_callback)
    # self._dl_thread.start()
    # Wait for the thread to start-up
    # if self._dl_thread.isRunning():
    #   time.sleep(0.1) # if type == "audio" else 20)
    return dl_thread

  def _create_proc_thread(self, video_path, sequences, finish_callback = None):
    proc_thread = ProcessThread(video_path, 
                    extract_path=self.extract_path, 
                    sequences=sequences,
                    audio_format=self.audio_format,
                    image_format=self.image_format)
    proc_thread.done_files.connect(finish_callback)
    proc_thread.percent.connect(self._proc_bar.setValue)
    # self._proc_thread.start()
    # Wait for the thread to start-up
    # if self._proc_thread.isRunning():
    #   time.sleep(0.1)
    return proc_thread

  def _download_info(self, hrefs, finished_callback = None):
    self._dl_bar.setValue(0)
    # if self._dl_thread is not None:
    #   self._dl_thread.terminate()
    self._dl_thread = DownloadThread(hrefs = hrefs,
                                  lang = self.lang, 
                                  download_path = self.download_path,
                                  type = "info")
    #Get vtt filename then convert it to srt
    def finish_dl_thread():
      self._finish_download = True
      self._dl_thread.terminate()
      self._dl_thread = None
      self._dl_status.setText("Finished downloading subtitles!")
    self._dl_thread.done_info.connect(finished_callback)
    self._dl_thread.percent.connect(self._dl_bar.setValue)
    self._dl_thread.amount.connect(self._dl_status.setText)
    self._dl_thread.done.connect(finish_dl_thread)
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

  # def _create_deck(self, info):
  #   video_id = info['id']
  #   filename = info['filename']
  #   if not self._matchings:
  #     self._matchings = {}
  #   self._matchings[video_id] = {}

  #   srt_filepath = None
  #   try:
  #     srt_filepath = self._convert_to_srt(filename)
  #     sequences = []
  #     for s in self._make_list(srt_filepath):
  #       s[2] = s[2].replace("\n", "")
  #       sequences.append(s)
  #     for s in sequences:
  #       self._matchings[video_id][s[0]] = s[1]

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
        self._proc_status.setText("Finished")
        self._add_thread = AddThread(self._matchings, self._browser)
        self._add_thread.percent.connect(self._add_bar.setValue)
        self._add_thread.done.connect(self.close)
        self._add_thread.start()
      else:
        self._proc_status.setText("Waiting for download...")
      self._proc_thread = None
      return

    sequences = self._matchings[video['id']]
    # Convert sequences to list
    sequences = list(sequences.values())
    self._proc_thread = self._create_proc_thread(video['path'], sequences, self._process_next)
    self._proc_thread.start()
    self._proc_status.setText("Extracting {}...".format(video['title']))

  def _process(self, matchings: dict):
    self._dl_bar.setValue(0)
    self._proc_bar.setValue(0)
    self._add_bar.setValue(0)

    self._finish_download = False
    self._matchings = matchings
    if len(self._matchings) == 0:
      self._dl_status.setText("No match found")
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

      # If video already existed, no need to download either it or the audio
      # If only audio found, and you need to extract images, keep the video href
      if not basename.endswith(".part") and video['type'] == 'image':
        to_be_extracted.append(video)
        if video_id in vid_hrefs:
          vid_hrefs.remove(video_id)
        if video_id in audio_hrefs:
          audio_hrefs.remove(video_id)
      elif video_id in audio_hrefs and not basename.endswith(".part") and video['type'] == 'audio':
        to_be_extracted.append(video)
        audio_hrefs.remove(video_id)
      else:
        os.remove(f)

    self._downloaded_videos = iter(to_be_extracted)
    if len(audio_hrefs) == 0 and len(vid_hrefs) == 0:
      self._finish_download = True
    else:
      self._dl_status.setText("Downloading {0} files".format(len(audio_hrefs) + len(vid_hrefs)))

      def finish_dl_all():
        self._finish_download = True
      def finish_dl_video():
        self._dl_thread = self._create_dl_thread(audio_hrefs, "audio", finish_dl_all)
        self._dl_thread.start()

      if len(vid_hrefs) > 0:
        self._dl_thread = self._create_dl_thread(vid_hrefs, "image", finish_dl_video
          if len(audio_hrefs) > 0 else finish_dl_all)
      else:
        self._dl_thread = self._create_dl_thread(audio_hrefs, "audio", finish_dl_all)
      
      self._dl_thread.start()
    self._process_next()


  def _convert_to_srt(self, filename):
    filepath = os.path.join(self.download_path, filename)
    srt_filepath = os.path.join(self.download_path, filename.replace(".vtt", ".srt"))
    command = self._ffmpeg + ' ' + '-i' + ' ' + filepath + ' ' + srt_filepath + ' -loglevel quiet'
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
    self._download_info(hrefs, self._store_subtitle)

  def run_create_deck(self, hrefs):
    if self.done_flag is True:
      return
    self.done_flag = True
    self._download_info(hrefs)
    self._process()

  def run(self, notes):
    # self._clean_downloads()
    if self.done_flag is True:
      return
    self.done_flag = True
    self._search_thread = SearchThread(self._db, notes)
    self._search_thread.matchings.connect(self._process)
    self._search_thread.start()
    self._dl_status.setText("Searching videos for %d " % len(notes)
      + ("cards..." if len(notes) > 1 else "card..."))

  def close(self):
    # Exit all threads
    if self._search_thread is not None:
      self._search_thread.terminate()
      self._search_thread = None
    if self._dl_thread is not None:
      self._dl_thread.terminate()
      self._dl_thread = None
    if self._proc_thread is not None:
      self._proc_thread.terminate()
      self._proc_thread = None
    self.done_flag = False
