from __future__ import (absolute_import, division,
						print_function, unicode_literals)

import os, sys
from typing import List

from gui import initializeQtResources

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip, getFile

from anki.hooks import addHook
from anki.lang import _
from anki import version as anki_version

from PyQt5 import QtCore, QtWidgets
from mwui import MineWindow
from constants import *

import codecs
import re
import random
import string
import glob
import subprocess
import glob
import fileinput
import imghdr
import yt_dlp as youtube_dl
import datetime
import json
import itertools
from storage import Storage
from setfields import SetFields
from storagewindow import StorageWindow

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

sys.stderr.isatty = lambda : True

initializeQtResources()

home = os.path.dirname(os.path.abspath(__file__))
storage_path = os.path.join(home, "storage.db")

#def get_ffmpeg():
#	op_s = os.name
#	return os.path.normpath(os.path.join(home, "ffmpeg", "ffmpeg.exe")) if op_s == "nt" else os.path.normpath(os.path.join(home, "ffmpeg", "ffmpeg"))

def error_message(text,title="Error has occured"):
	dialog = QtWidgets.QMessageBox()
	dialog.setWindowTitle(title)
	dialog.setText(text)
	dialog.setIcon(QtWidgets.QMessageBox.Warning)
	dialog.exec_()

# class Sequence:
# 	def __init__(self, begin, end, sentence):
# 		self._begin = begin
# 		self._end = end
# 		self._sentence = sentence
# 	def begin(self):
# 		return self._begin
# 	def end(self):
# 		return self._end
# 	def sentence(self):
# 		return self._sentence

# class AudioSequence:
# 	def __init__(self, sequence, loc):
# 		self._sequence = sequence
# 		self._loc = loc
# 	def seq(self):
# 		return self._sequence
# 	def loc(self):
# 		return self._loc

class Dl_thread(QtCore.QThread):
	done_info = QtCore.pyqtSignal(dict)
	percent = QtCore.pyqtSignal(float)
	amount = QtCore.pyqtSignal(str)

	def __init__(self, 
				hrefs,
				only_info = False, 
				lang = None, 
				download_path = None):
		super().__init__()
		self.hrefs = hrefs
		self.lang = lang
		self.download_path = download_path
		self.only_info = only_info
		self._current = 0

	def _download_hook(self, d):
		if d['status'] == 'finished':
			self.percent.emit(100)
			filename = os.path.basename(d['filename'])
			url = filename.split(".")[0]
			_info = youtube_dl.YoutubeDL().extract_info(url, download=False)
			_info['filename'] = d['filename']
			self.done_info.emit(_info)
			self._current = self._current + 1
			self.amount.emit(str(self._current))

		if d['status'] == 'downloading':
			p = d['_percent_str']
			p = p.replace('%','')
			#Check if p is convertible to float
			try:
				p = float(p) if float(p) >= 1 else 1
			except:
				p = 0
			self.percent.emit(p)

	def _download_info(self):
		ydl_opts = {"subtitleslangs": [self.lang], 
					"progress_hooks": [self._download_hook],
					"skip_download": True, 
					"writeautomaticsub": True, 
					"writesubtitles": True, 
					"subtitlesformat": 'vtt',
					"outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
					"quiet":True, "no_warnings":True}
		urls = []
		for href in self.hrefs:
			ydl = youtube_dl.YoutubeDL({
				'extract_flat': True,
			})
			info = ydl.extract_info(href, download=False)
			if 'entries' in info:
				# Can be a playlist or a list of videos
				entries = info['entries']
				urls.extend([entry['url'] for entry in entries])
			else:
				# Just a video
				urls.append(info['id'])
		ydl = youtube_dl.YoutubeDL(ydl_opts)
		ydl.download(urls)

	def _download_audio(self):
		error_message("Working!")
		audio_opts = {'format': 'bestaudio/best',
					'progress_hooks': [self._download_hook],
					# 'postprocessors': [{
					# 'key': 'FFmpegExtractAudio',
					# 'preferredcodec': self.audio_format,
					# 'preferredquality': '192',
					# }], 
					"outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
					"quiet":True, "no_warnings":True}

		urls = []
		for href in self.hrefs:
			ydl = youtube_dl.YoutubeDL({
				'extract_flat': True,
			})
			info = ydl.extract_info(href, download=False)
			if 'entries' in info:
				# Can be a playlist or a list of videos
				entries = info['entries']
				urls.extend([entry['url'] for entry in entries])
			else:
				# Just a video
				urls.append(info['id'])
		
		ydl = youtube_dl.YoutubeDL(audio_opts)
		ydl.download(urls)

	def run(self):
		if self.only_info:
			self._download_info()
		else:
			self._download_audio()

class Process_thread(QtCore.QThread):
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
				files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id']})
				continue
			command = command_format.format(s['start_time'], self.audio_path, float(s['end_time']) - float(s['start_time']), filepath)
			try:
				subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
				files.append({'filename': filename, 'filepath': filepath, 'sequence_id': s['id']})
			except:
				continue

		self.done_files.emit(files)

class SubCutter:
	def __init__(self, 
				db: Storage,
				lang: str = "en", 
				vid_format = 'mp4', 
				audio_format = 'mp3',
				sub_format = 'srt',
				begin = -1, 
				end = 999999,
				dl_bar: QtWidgets.QProgressBar = None,
				ext_bar: QtWidgets.QProgressBar = None,
				dl_status: QtWidgets.QLabel = None,
				ext_status: QtWidgets.QLabel = None):
		
		self.vid_format = vid_format
		self.audio_format = audio_format
		self.lang = lang
		self.sub_format = sub_format
		self.begin = begin
		self.end = end
		self.extract_path = os.path.normpath(os.path.join(home, "audio"))
		self.download_path = os.path.normpath(os.path.join(home, "downloads"))
		self._dl_bar = dl_bar
		self._ext_bar = ext_bar
		self._dl_status = dl_status
		self._ext_status = ext_status
		self._ffmpeg = "ffmpeg"
		self._db = db

		#Threads related
		self._dl_thread = None
		self._ext_thread = None
		self._downloaded_videos = None
		self._current = 0

	def _download_info(self, hrefs):
		self._dl_bar.setValue(0)
		if self._dl_thread is not None:
			self._dl_thread.terminate()
		self._dl_thread = Dl_thread(hrefs = hrefs, lang = self.lang, 
								download_path = self.download_path,
								only_info = True)
		#Get vtt filename then convert it to srt
		self._dl_thread.done_info.connect(self._store_subtitle)
		self._dl_thread.percent.connect(self._dl_bar.setValue)
		self._dl_thread.amount.connect(self._dl_status.setText)
		self._dl_thread.start()

	def _store_subtitle(self, info):
		video_id = info['id']
		filename = info['filename']
		srt_filepath = None
		try:
			srt_filepath = self._convert_to_srt(filename)
			sequences = self._make_list(srt_filepath)
			self._db.insert_video(info['title'], video_id, self.lang, 'Unavailable', datetime.datetime.now())
			self._db.insert_sequences(video_id, sequences)
		except Exception as e:
			self._db.delete_video_by_id(video_id)
			error_message("Error while processing video {0}".format(e))
		if(os.path.exists(filename)):
			os.remove(filename)
		if(srt_filepath and os.path.exists(srt_filepath)):
			os.remove(srt_filepath)
		

	def _process(self, exprs):
		self._dl_bar.setValue(0)
		self._ext_bar.setValue(0)
		
		if self._dl_thread is not None:
			self._dl_thread.terminate()
		if self._ext_thread is not None:
			self._ext_thread.terminate()

		# available = self._db.get_matched_videos(exprs)
		# #For loop from 1 to len(available)
		# for v in available:
		# 	#Check if path is still available
		# 	if not os.path.exists(v['path']):
		# 		available.remove(v)

		self._downloaded_videos = iter([])

		def add_downloaded(done_info):
			id = done_info['id']
			filename = done_info['filename']
			filepath = os.path.join(self.download_path, filename)
			self._db.path_update_video(id, filepath)
			self._downloaded_videos = itertools.chain(self._downloaded_videos, [self._db.get_video(id)])
			if self._ext_thread is None:
				process_next()
		
		def process_next(files = []):
			for file in files:
				self._db.insert_file(file['filename'], file['filepath'], file['sequence_id'])
			video = None
			try:
				video = next(self._downloaded_videos)
			except StopIteration:
				self._ext_thread = None
				return
			if self._ext_thread is not None:
				self._ext_thread.terminate()

			sequences = self._db.get_matched_sequences(exprs, video['id'])
			self._ext_thread = Process_thread(video['path'], 
											extract_path=self.extract_path, 
											sequences=sequences, 
											audio_format=self.audio_format)
			self._ext_thread.done_files.connect(process_next)
			self._ext_thread.percent.connect(self._ext_bar.setValue)
			self._ext_thread.start()
			self._current += 1
			self._ext_status.setText(str(self._current))

		hrefs = [v['id'] for v in self._db.get_matched_videos(exprs)]
		error_message("Downloading {0} videos".format(len(hrefs)))
		error_message(str(hrefs))
		self._dl_thread = Dl_thread(hrefs = hrefs, lang = self.lang, 
								download_path = self.download_path,
								only_info = False)
		self._dl_thread.done_info.connect(add_downloaded)
		self._dl_thread.percent.connect(self._dl_bar.setValue)
		self._dl_thread.start()
		process_next()

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

		mili_per_sec = 1000
		mili_per_min = 1000 * 60
		mili_per_hour = 1000 * 60 * 60
	
		sequences = []
		prev_seq = [0, 0, '']
		prev_s = ""
		
		for s in content:
			s = re.sub('\r', '', s)
			if (not s) or (empty_pat.match(s)) or (num_pat.match(s)):
				continue
			matches = time_pat.match(s)
			if(matches):
				begin_time = int(matches[4]) + int(matches[3]) * mili_per_sec + int(matches[2]) * mili_per_min + int(matches[1]) * mili_per_hour
				end_time = int(matches[8]) + int(matches[7]) * mili_per_sec + int(matches[6]) * mili_per_min + int(matches[5]) * mili_per_hour
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
		audio_folder = os.path.join(home, "audio/*")
		files = glob.glob(audio_folder.replace("\\", "/"))
		for f in files:
			os.remove(f)
		self._db.delete_all_files()
	
	def _clean_downloads(self):
		download_folder = os.path.join(home, "downloads/*")
		files = glob.glob(download_folder.replace("\\", "/"))
		for f in files:
			os.remove(f)

	def run_store(self, hrefs):
		try:	
			self._download_info(hrefs)
		except Exception as e:
			error_message("Error: Couldn't download video info!\n{}".format(e))
			return

	def run_create_deck(self):
		try:
			self._process(self.exprs)
		except Exception as e:
			error_message("Error: Couldn't create deck!\n{}".format(e))
			return
	# 	try:
	# 		self._cleanDownloads()
	# 		self._download()
	# 	except Exception as e:
	# 		error_message("Error:  Something went wrong with the downloading process: \n{}".format(e))
	# 		return

	# def run_extract(self, exprs):
	# 	try:	
	# 		self._make_list()
	# 		self._cleanAudio()
	# 		self._process(exprs)
	# 	except Exception as e:
	# 		error_message("Error:  Something went wrong with the extracting process: \n{}".format(e))
	# 		return
	
	def run(self, exprs):
		try:
			self._clean_downloads()
			self._process(exprs)
		except Exception as e:
			error_message("Error:  Something went wrong with the extracting process: \n{}".format(e))
			return

class MW(MineWindow):
	def __init__(self, browser):
		super().__init__()
		self.browser = browser
		self.exprs = []
		self.nids = []
		self.sub_cutter = None
		#Create storage.db
		self.db = Storage(storage_path)
		self.db.create_table()
		self.setup_ui()

	def setup_ui(self):
		self.language_box.addItems(lang_list)
		self.col = self.browser.mw.col
		# self._set_fields()
		# self.download_button.clicked.connect(self.download)
		# self.extract_button.clicked.connect(self.extract)
		self.store_button.clicked.connect(self.store_video)
		self.set_fields_button.clicked.connect(self.open_set_fields)
		self.open_storage_button.clicked.connect(self.open_storage)
		self.add_button.clicked.connect(self.extract)
		self.create_deck_button.clicked.connect(self.add_audio)
		self.download_bar.setValue(0)
		self.extract_bar.setValue(0)
		self.add_bar.setValue(0)
		# self.time_slider.setDisabled(True)
		# self.begin_box.setDisabled(True)
		# self.end_box.setDisabled(True)
		self.time_len = 1000
		# self.time_slider.startValueChanged.connect(self._update_begin)
		# self.time_slider.endValueChanged.connect(self._update_end)
		self._get_options()
		self.language_box.currentTextChanged.connect(self._save_options)
		# self.phrase_box.currentTextChanged.connect(self._save_options)
		# self.audio_box.currentTextChanged.connect(self._save_options)
		# self.setup_slider()
	
	def get_expressions(self):
		nids = self.browser.selectedNotes()
		self.exprs = []
		self.nids = nids
		expr_fld = 'Front'
		# self.phrase_box.currentText()
		for nid in nids:
			note = self.col.getNote(nid)
			if expr_fld in note:
				self.exprs.append(note[expr_fld])

	def _update_begin(self, value):
		s = str(datetime.timedelta(seconds = int(self.time_len * value / 100)))
		self.begin_box.setText(s)

	def _update_end(self, value):
		s = str(datetime.timedelta(seconds = int(self.time_len * value / 100)))
		self.end_box.setText(s)

	def _set_fields(self):
		fields = []
		notes = self.col.models.allNames()
		for n in notes:
			for x in self.browser.mw.col.models.byName(str(n))['flds']:
				if x['name'] not in fields:
					fields.append(x['name'])
		# self.phrase_box.addItems(fields)
		# self.audio_box.addItems(fields)
	
	def download(self):
		link = str(self.link_box.text())
		try:
			sub_lang = {v:k for k, v in LANGUAGES.items()}[str(self.language_box.currentText())]
		except:
			error_message("Invalid language.")
			return
		if not link.startswith("https://www.youtube.com/watch?v="):
			error_message("Invalid youtube link.")
			return
		self.sub_cutter = SubCutter(db = self.db,
									hrefs = link, 
									lang = sub_lang, 
									dl_bar = self.download_bar, 
									ext_bar = self.extract_bar,
									dl_status=self.download_status,
									ext_status=self.extract_status)
		self.sub_cutter.run_download()
	
	def extract(self):
		# begin = int(self.time_len * self.time_slider.start() / 100)
		# end = int(self.time_len * self.time_slider.end() / 100)
		# if self.sub_cutter is None:
		# 	download_dir = os.path.join(home, "downloads")
		# 	srt_file = None
		# 	mp3_file = None
		# 	srt_file = getFile(self, _("Choose .srt file:"), dir = download_dir.replace("\\", "/"), cb = None, filter = _("*.srt"))
		# 	if srt_file is None:
		# 		return
		# 	mp3_file = getFile(self, _("Choose .mp3 file:"), dir = download_dir.replace("\\", "/"), cb = None, filter = _("*.mp3"))
		# 	if mp3_file is None:
		# 		return
		# 	self.download_bar.setValue(100)
		# 	self.sub_cutter = SubCutter(db = self.db,
		# 								dl_bar = self.download_bar, 
		# 								ext_bar = self.extract_bar)
		# 	self.sub_cutter.sub_path = srt_file
		# 	self.sub_cutter.audio_path = mp3_file
		# else:
		# 	self.sub_cutter.begin = begin
		# 	self.sub_cutter.end = end
		if self.sub_cutter is None:
			self.sub_cutter = SubCutter(db = self.db,
										dl_bar = self.download_bar, 
										ext_bar = self.extract_bar,
										dl_status=self.download_status,
										ext_status=self.extract_status)
		self.get_expressions()
		self.sub_cutter.run(self.exprs)

	def store_video(self):
		link = str(self.link_box.text())
		try:
			sub_lang = {v:k for k, v in LANGUAGES.items()}[str(self.language_box.currentText())]
		except:
			error_message("Invalid language.")
			return
		if not link.startswith("https://www.youtube.com/"):
			error_message("Invalid youtube link.")
			return
		self.sub_cutter = SubCutter(db = self.db, 
									lang = sub_lang, 
									dl_bar = self.download_bar, 
									ext_bar = self.extract_bar,
									dl_status=self.download_status,
									ext_status=self.extract_status)
		self.sub_cutter.run_store([link])

	def open_set_fields(self):
		self.set_fields = SetFields()
		self.set_fields.show()

	def open_storage(self):
		self.storage_window = StorageWindow()
		self.storage_window.show()

	def add_audio(self):
		if self.sub_cutter is None:
			self.download_bar.setValue(100)
			self.extract_bar.setValue(100)
			self.add_bar.setValue(0)
		mw = self.browser.mw
		mw.checkpoint("batch edit")
		mw.progress.start()
		self.browser.model.beginReset()
		cnt = 0
		atype = "mp3"
		expr_fld = 'sentence'
		# self.phrase_box.currentText()
		audio_fld = 'audio'
		# self.audio_box.currentText()

		if not expr_fld:
			error_message("Please choose a type for phrase field.")
			return
		if not audio_fld:
			error_message("Please choose a type for audio field.")
			return

		self.get_expressions()
		total = len(self.nids)
		cur = 0

		for nid in self.nids:
			cur = cur + 1
			self.add_bar.setValue(cur / total * 100)

			note = mw.col.getNote(nid)
			if expr_fld in note and audio_fld in note:
				if not note[expr_fld]:
					continue
				if note[audio_fld]:
					audio_id = note[audio_fld].split(":")[1].split("]")[0].split(".")[0]
					if self.db.get_sequence(audio_id) is not None:
						continue
				# pat = re.compile(r"(.+\." + atype + r")\-(\[.+\]):(.+)")
				# with codecs.open(seq_path.replace("\\", "/"), 'r', 'UTF-8') as seq_map:
				# 	sequences = seq_map.readlines()
				# 	for s in sequences:
				# 		matches = pat.match(s)
				# 		if not matches:
				# 			continue
				# 		if matches[3].find(note[expr_fld]) != -1:
				# 			audiofname = mw.col.media.addFile(matches[1])
				# 			note[audio_fld] = "[sound:" + audiofname + "]"
				sequences = self.db.search_matched_audios_by_line(note[expr_fld])
				if sequences:
					sequence = sequences[0]
					audiofname = mw.col.media.addFile(sequence['path'])
					note[audio_fld] = "[sound:" + audiofname + "]"
					cnt += 1
				note.flush()
		self.browser.model.endReset()
		mw.requireReset()
		mw.progress.finish()
		mw.reset()
		tooltip("<b>Updated</b> {0} notes.".format(cnt), parent = self.browser)

	def create_deck(self):
		return

	def _save_options(self):
		# opts = {}
		# opts['lang'] = self.language_box.currentText()
		# opts['expr_fld'] = self.phrase_box.currentText()
		# opts['audio_fld'] = self.audio_box.currentText()

		# with codecs.open(path, 'w', 'UTF-8') as opt_file:
		# 	opt_file.write(str(opts))
		self.db.insert_setting('lang', self.language_box.currentText())
		# self.db.insert_setting('expr_fld', self.phrase_box.currentText())
		# self.db.insert_setting('audio_fld', self.audio_box.currentText())
	
	def _get_options(self):
		# opts = {}
		# path = opt_path.replace("\\", "/")
		# if os.stat(path).st_size:
		# 	try:
		# 		with codecs.open(path, 'r', 'UTF-8') as opt_file:
		# 			opts = eval(opt_file.read())
		# 		if opts['lang']:
		# 			self.language_box.setCurrentText(opts['lang'])
		# 		if opts['expr_fld']:
		# 			self.phrase_box.setCurrentText(opts['expr_fld'])
		# 		if opts['audio_fld']:
		# 			self.audio_box.setCurrentText(opts['audio_fld'])
		# 	except:
		# 		return
		settings = self.db.get_settings()
		if len(settings) == 0:
			return
		for setting in settings:
			if setting['name'] == 'lang':
				self.language_box.setCurrentText(setting['value'])
			# if setting['name'] == 'expr_fld':
			# 	self.phrase_box.setCurrentText(setting['value'])
			# if setting['name'] == 'audio_fld':
			# 	self.audio_box.setCurrentText(setting['value'])

def onBatchEdit(browser):
	dl_dir = os.path.join(home, 'downloads')
	audio_dir = os.path.join(home, 'audio')
	if not os.path.exists(dl_dir):
		os.makedirs(dl_dir)
	if not os.path.exists(audio_dir):
		os.makedirs(audio_dir)
		
	# nids = browser.selectedNotes()
	# if not nids:
	# 	tooltip("No cards selected.")
	# 	return
	browser.widget = MW(browser)
	browser.widget.show()

def setupMenu(browser):
	menu = browser.form.menuEdit
	menu.addSeparator()
	a = menu.addAction('Mine audio...')
	a.setShortcut(QKeySequence('Ctrl+Alt+M'))
	a.triggered.connect(lambda _, b=browser: onBatchEdit(b))

def addToBrowser():
	addHook("browser.setupMenus", setupMenu)
