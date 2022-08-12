from distutils.log import error
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

			note = mw.col.getNote(nid)
			if audio_fld and audio_fld in note:
				if 'filepath' not in seq:
					continue
				filepath = seq['filepath']
				audiofname = mw.col.media.addFile(filepath)
				note[audio_fld] = "[sound:" + audiofname + "]"
			if sentence_fld and sentence_fld in note:
				note[sentence_fld] = seq['line']
			# Get the Youtube URL from the video's id and start time
			if url_fld and url_fld in note:
				url = "https://www.youtube.com/embed/" + seq['video_id'] + "?start=" + str(int(float(seq['start_time'])))
				embedded_html = "<iframe width=\"560\" height=\"315\" src=\"" + url + "\" frameborder=\"0\" allow=\"accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture\" allowfullscreen></iframe>"
				note[url_fld] = embedded_html
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
				only_info = False, 
				lang = None,
				download_path = None):
		super().__init__()
		self.hrefs = hrefs
		self.lang = lang
		self.download_path = download_path
		self.only_info = only_info
		self._current = 0
		self._total = 0

	def _download_hook(self, d):
		if d['status'] == 'finished':
			self.percent.emit(100)
			self.amount.emit("Download {0}/{1}{2}".
				format(self._current + 1, self._total, ". Inserting subtitles..." if self.only_info else ""))
			filename = os.path.basename(d['filename'])
			url = filename.split(".")[0]
			_info = youtube_dl.YoutubeDL({
        'quiet': True,
        'no_warnings': True,
      }).extract_info(url, download=False)		
			_info['filename'] = d['filename']
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
			if "HTTP Error 429: Too Many Requests" in str(e):
				to_be_downloaded = to_be_downloaded[(self._current - prev_current):]
				return self._download_urls(to_be_downloaded, options, extract_info = False)
			else:
				self.done.emit()
				self.done_info.emit(None)
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

	def run(self):
		if self.only_info:
			self._download_info()
		else:
			self._download_audio()

class ProcessThread(QtCore.QThread):
	done_files = QtCore.pyqtSignal(list)
	percent = QtCore.pyqtSignal(float)

	def __init__(self,
				audio_path,
				extract_path,
				sequences,
				audio_format = "mp3"):
		super().__init__()
		self.audio_path = audio_path
		self.extract_path = extract_path
		self.audio_format = audio_format
		self.sequences = sequences
		self.ffmpeg = "ffmpeg"

	def run(self):
		command_format = self.ffmpeg + " -ss {0} -i \"{1}\" -ss 0 -c copy -t {2} -avoid_negative_ts make_zero -c:a libmp3lame \"{3}\""
		use_shell = True
		
		total = len(self.sequences)
		files = []

		for index, s in enumerate(self.sequences):
			self.percent.emit(round((index + 1) / total * 100, 1))
			filename = s['id'] + '.' + self.audio_format
			filepath = os.path.join(self.extract_path, filename)
			if os.path.exists(filepath):
				files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id']})
				continue
			command = command_format.format(s['start_time'], self.audio_path, float(s['end_time']) - float(s['start_time']), filepath)
			try:
				subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
				files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id'], 'video_id': s['video_id']})
			except Exception as e:
				continue

		self.done_files.emit(files)