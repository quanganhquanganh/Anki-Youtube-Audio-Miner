import os
from aqt.utils import tooltip

from PyQt5 import QtCore
import subprocess

from ytminer.messages import error_message

from . import yt_dlp as youtube_dl

class SearchThread(QtCore.QThread):
  matchings = QtCore.pyqtSignal(dict)

  def __init__(self, db, notes):
    super().__init__()
    self._db = db
    self._notes = notes

  def run(self):
    matchings = self._db.get_matchings(self._notes)
    self.matchings.emit(matchings)

class AddThread(QtCore.QThread):
  percent = QtCore.pyqtSignal(int)
  done = QtCore.pyqtSignal()

  def __init__(self, mappings, browser):
    super().__init__()
    self.mappings = mappings
    self.browser = browser
    # self.abort = False

  def run(self):
    mw = self.browser.mw
    mw.checkpoint("Add audio")
    mw.progress.start()
    self.browser.model.beginReset()
    cnt = 0
    seqs = []
    for video in self.mappings.values():
      seqs.extend(list(video.values()))
    total = len(seqs)
    for seq in seqs:
      nid = seq['note']['nid']
      audio_fld = seq['note']['audio_flds'][seq['pos']] if seq['pos'] in seq['note']['audio_flds'] else None
      sentence_fld = seq['note']['sentence_flds'][seq['pos']] if seq['pos'] in seq['note']['sentence_flds'] else None
      url_fld = seq['note']['url_flds'][seq['pos']] if seq['pos'] in seq['note']['url_flds'] else None
      screenshot_fld = seq['note']['screenshot_flds'][seq['pos']] if seq['pos'] in seq['note']['screenshot_flds'] else None

      note = mw.col.getNote(nid)
      if audio_fld and audio_fld in note:
        if 'a_filepath' not in seq:
          continue
        filepath = seq['a_filepath']
        audiofname = mw.col.media.addFile(filepath)
        note[audio_fld] = "[sound:" + audiofname + "]"
      if sentence_fld and sentence_fld in note:
        note[sentence_fld] = seq['line']
      # Get the Youtube URL from the video's id and start time
      if url_fld and url_fld in note:
        url = "https://www.youtube.com/embed/" + seq['video_id'] + "?start=" + str(int(float(seq['start_time'])))
        embedded_html = "<iframe width=\"560\" height=\"315\" src=\"" + url + "\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>"
        note[url_fld] = embedded_html
      if screenshot_fld and screenshot_fld in note:
        if 'i_filepath' not in seq:
          continue
        filepath = seq['i_filepath']
        screenshotfname = mw.col.media.addFile(filepath)
        note[screenshot_fld] = "<img src=\"" + screenshotfname + "\">"
      cnt += 1
      note.flush()
      self.percent.emit(int(cnt * 100 / total))
    self.browser.model.endReset()
    mw.requireReset()
    mw.progress.finish()
    mw.reset()
    tooltip("<b>Updated</b> {0} notes.".format(cnt), parent = self.browser)
    self.done.emit()

class DownloadThread(QtCore.QThread):
  done_info = QtCore.pyqtSignal(dict)
  percent = QtCore.pyqtSignal(float)
  amount = QtCore.pyqtSignal(str)
  done = QtCore.pyqtSignal()

  def __init__(self, 
        hrefs: list,
        type = 'image', 
        lang = None,
        download_path = None):
    super().__init__()
    self.hrefs = hrefs
    self.lang = lang
    self.download_path = download_path
    self.type = type
    self._current = 0
    self._total = 0
    self._max_try = 3
    self._try = 0

  def _download_hook(self, d):
    if d['status'] == 'finished':
      self.percent.emit(100)
      filetype = self.type if self.type != 'image' else 'video'
      self.amount.emit('Downloading {0}s: {1}/{2}{3}'.
        format(filetype, self._current + 1, self._total,'. Inserting subtitles...'
        if self.type == 'info' else ''))
      filename = os.path.basename(d['filename'])
      url = filename.split(".")[0]

      _info = youtube_dl.YoutubeDL({
        'quiet': True,
        'no_warnings': True,
      }).extract_info(url, download=False)
      _info['filename'] = d['filename']
      _info['type'] = self.type
      _info['status'] = 'finished'

      self.done_info.emit(_info)
      self._current = self._current + 1
      if self._current == self._total:
        self.done.emit()

    if d['status'] == 'downloading':
      p = d['_percent_str']
      p = p.replace('%','')
      #Check if p is convertible to float
      try:
        p = float(p) if float(p) >= 1 else 1
      except:
        p = 0
      self.percent.emit(p)
      self.amount.emit("Download {0}/{1}".format(self._current + 1, self._total))
      
  def _download_urls(self, urls, options, extract_info = True):
    prev_current = self._current
    to_be_downloaded = []
    if extract_info:
      self.amount.emit("Extracting info...")
      for href in urls:
        ydl = youtube_dl.YoutubeDL({
          'extract_flat': True,
          'quiet': True,
          'no_warnings': True,
        })
        info = ydl.extract_info(href, download=False)
        if 'entries' in info:
          # Can be a playlist or a list of videos
          entries = info['entries']
          # Remove private videos
          entries = [e for e in entries if e['uploader']]
          to_be_downloaded.extend([entry['url'] for entry in entries])
        else:
          # Just a video
          to_be_downloaded.append(info['id'])
      self._total = len(to_be_downloaded)
    else:
      to_be_downloaded = urls
      if self._total == 0:
        self._total = len(to_be_downloaded)
    ydl = youtube_dl.YoutubeDL(options)
    try:
      ydl.download(to_be_downloaded)
    except Exception as e:
      if self._try < self._max_try:
        self._try += 1
        to_be_downloaded = to_be_downloaded[(self._current - prev_current):]
        return self._download_urls(to_be_downloaded, options, extract_info = False)
      else:
        self.done.emit()
        self.done_info.emit({'status': 'error', 'message': str(e)})
        return

  def _download_info(self):
    # Check if hrefs is a list of string pairs
    if len(self.hrefs) != 0 and isinstance(self.hrefs[0], dict):
      languages = list(set([href['lang'] for href in self.hrefs]))
    else:
      self.hrefs = [{'lang': 'ja', 'url': href} for href in self.hrefs]
      languages = [self.lang]
    for lang in languages:
      urls = [href['url'] for href in self.hrefs if href['lang'] == lang]
      ydl_opts = {"subtitleslangs": [lang],
        "progress_hooks": [self._download_hook],
        "skip_download": True, 
        "writeautomaticsub": True, 
        "writesubtitles": True, 
        "subtitlesformat": 'vtt',
        "outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
        "quiet":True, "no_warnings":True}
      self._download_urls(urls, ydl_opts)

  def _download_audio(self):
    # Check if hrefs is a list of string pairs
    if len(self.hrefs) != 0 and isinstance(self.hrefs[0], dict):
      languages = list(set([href['lang'] for href in self.hrefs]))
    else:
      self.hrefs = [{'lang': 'ja', 'url': href} for href in self.hrefs]
      languages = ['ja']
    for lang in languages:
      urls = [href['url'] for href in self.hrefs if href['lang'] == lang]
      audio_opts = {'format': 'bestaudio/best',
            'progress_hooks': [self._download_hook],
            "outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
            "quiet":True, "no_warnings":True}
      self._download_urls(urls, audio_opts, extract_info = False)

  def _download_video(self):
    # Check if hrefs is a list of string pairs
    if len(self.hrefs) != 0 and isinstance(self.hrefs[0], dict):
      languages = list(set([href['lang'] for href in self.hrefs]))
    else:
      self.hrefs = [{'lang': 'ja', 'url': href} for href in self.hrefs]
      languages = ['ja']
    for lang in languages:
      urls = [href['url'] for href in self.hrefs if href['lang'] == lang]
      # Options for an audio-less video
      video_opts = {'format': '22/18/13/worst',
            'progress_hooks': [self._download_hook],
            "outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
            "quiet":True, "no_warnings":True}
      self._download_urls(urls, video_opts, extract_info = False)

  def run(self):
    if self.type == 'info':
      self._download_info()
    elif self.type == 'audio':
      self._download_audio()
    elif self.type == 'image':
      self._download_video()

class ProcessThread(QtCore.QThread):
  done_files = QtCore.pyqtSignal(list)
  percent = QtCore.pyqtSignal(float)

  def __init__(self,
        audio_path,
        extract_path,
        sequences,
        audio_format = "mp3",
        image_format = "jpeg",):
    super().__init__()
    self.audio_path = audio_path
    self.extract_path = extract_path
    self.audio_format = audio_format
    self.image_format = image_format
    self.sequences = sequences
    self.total = sum([len(seq['type']) for seq in sequences])
    self.current = 0
    self.ffmpeg = "ffmpeg"

  def _extract_audio(self):
    command_format = self.ffmpeg + " -ss {0} -i \"{1}\" -ss 0 -c copy -t {2} -avoid_negative_ts make_zero -c:a libmp3lame \"{3}\""
    use_shell = True
    
    files = []

    for s in [s for s in self.sequences if 'audio' in s['type']]:
      self.current += 1
      self.percent.emit(round(self.current / self.total * 100, 1))
      filename = s['id'] + '.' + self.audio_format
      filepath = os.path.join(self.extract_path, filename)
      if os.path.exists(filepath):
        files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id'], 'type': 'audio'})
        continue
      command = command_format.format(s['start_time'], self.audio_path, float(s['end_time']) - float(s['start_time']), filepath)
      try:
        subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
        files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id'], 'type': 'audio'})
      except Exception as e:
        continue
    return files

  def _extract_screenshots(self):
    command_format = self.ffmpeg + " -ss {0} -i \"{1}\" -vframes 1 -q:v 2 -f image2 \"{2}\""
    use_shell = True
    
    files = []

    for s in [s for s in self.sequences if 'image' in s['type']]:
      self.current += 1
      self.percent.emit(round(self.current / self.total * 100, 1))
      filename = s['id'] + '.' + self.image_format
      filepath = os.path.join(self.extract_path, filename)
      if os.path.exists(filepath):
        files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id'], 'type': 'image'})
        continue
      command = command_format.format(s['start_time'], self.audio_path, filepath)
      try:
        subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
        files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id'], 'type': 'image'})
      except Exception as e:
        continue
    return files
  
  def run(self):
    files = []
    files.extend(self._extract_audio())
    files.extend(self._extract_screenshots())
    self.done_files.emit(files)
    # self.done_files.emit(self._extract_audio() if self.type == 'audio' else self._extract_screenshots())