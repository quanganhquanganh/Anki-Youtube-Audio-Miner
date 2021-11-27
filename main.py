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

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

sys.stderr.isatty = lambda : True

initializeQtResources()

home = os.path.dirname(os.path.abspath(__file__))
seq_path = os.path.join(home, "seq_time.txt")
opt_path = os.path.join(home, "options.txt")

#def get_ffmpeg():
#	op_s = os.name
#	return os.path.normpath(os.path.join(home, "ffmpeg", "ffmpeg.exe")) if op_s == "nt" else os.path.normpath(os.path.join(home, "ffmpeg", "ffmpeg"))

def error_message(text,title="Error has occured"):
	dialog = QtWidgets.QMessageBox()
	dialog.setWindowTitle(title)
	dialog.setText(text)
	dialog.setIcon(QtWidgets.QMessageBox.Warning)
	dialog.exec_()

class Sequence:
	def __init__(self, begin, end, sentence):
		self._begin = begin
		self._end = end
		self._sentence = sentence
	def begin(self):
		return self._begin
	def end(self):
		return self._end
	def sentence(self):
		return self._sentence

class AudioSequence:
	def __init__(self, sequence, loc):
		self._sequence = sequence
		self._loc = loc
	def seq(self):
		return self._sequence
	def loc(self):
		return self._loc

class Dl_thread(QtCore.QThread):
	done = QtCore.pyqtSignal(bool)

	def __init__(self, href, lang, general_path, audio_path, vtt_sub_path, audio_format, dl_bar):
		super().__init__()
		self.href = href
		self.lang = lang
		self.general_path = general_path
		self.audio_path = audio_path
		self.vtt_sub_path = vtt_sub_path
		self.audio_format = audio_format
		self.dl_bar = dl_bar
		self.ffmpeg = "ffmpeg"
	
	def __str__(self):
		mem_var = {}
		mem_var['href'] = self.href
		mem_var['lang'] = self.lang
		mem_var['general_path'] = self.general_path
		mem_var['audio_path'] = self.audio_path
		mem_var['vtt_sub_path'] = self.vtt_sub_path
		mem_var['audio_format'] = self.audio_format
		return str(mem_var)

	def _download_hook(self, d):
		if d['status'] == 'finished':
			self.done.emit(True)
		if d['status'] == 'downloading':
			p = d['_percent_str']
			p = p.replace('%','')
			self.dl_bar.setValue(float(p))

	def run(self):
		print(self)
		ydl_opts = {'subtitleslangs': [self.lang], "skip_download": True, "writesubtitles": True, "subtitlesformat": 'vtt',
				"outtmpl": self.general_path, "quiet":True, "no_warnings":True}
		
		opts_no_lang = {'subtitleslangs': [self.lang], "skip_download": True, "writeautomaticsub": True, "writesubtitles": True, "subtitlesformat": 'vtt',
						"outtmpl": self.general_path, "quiet":True, "no_warnings":True}

		vid_opts = {'format': 'bestaudio/best',
					'progress_hooks': [self._download_hook],
					'postprocessors': [{
					'key': 'FFmpegExtractAudio',
					'preferredcodec': self.audio_format,
					'preferredquality': '192',
					}], "outtmpl": self.audio_path, "quiet":True, "no_warnings":True}

		ydl = youtube_dl.YoutubeDL(ydl_opts)
		ydl.download([self.href])
		have_sub = os.path.exists(self.vtt_sub_path)
		if have_sub is False:
			ydl = youtube_dl.YoutubeDL(opts_no_lang)
			ydl.download([self.href])
		
		have_sub = os.path.exists(self.vtt_sub_path)
		
		if have_sub is False:
			error_message("Couldn't download the subtitles for some reason. Try again later.")
			return

		ydl = youtube_dl.YoutubeDL(vid_opts)
		ydl.download([self.href])
		return

class Process_thread(QtCore.QThread):
	percent = QtCore.pyqtSignal(float)

	def __init__(self, sequences: List = None, 
				begin: float = -1.0, 
				end: float = 999999, 
				audio_format = "mp3", 
				audio_path = None):
		super().__init__()
		self.sequences = sequences
		self.begin = begin
		self.end = end
		self.audio_format = audio_format
		self.audio_path = audio_path
		self.ffmpeg = "ffmpeg"

	def run(self):
		str_length = 4
		
		output_sub = seq_path
		
		out = codecs.open(output_sub.replace("\\", "/"), 'w', 'UTF-8')

		command_format = self.ffmpeg + " -ss {0} -i \"{1}\" -ss 0 -c copy -t {2} -avoid_negative_ts make_zero -c:a libmp3lame \"{3}\""
		use_shell = True
		random_prefix = "".join(random.choice(string.ascii_letters) for i in range(str_length))
		
		total = len(self.sequences)
		cur = 0

		for s in self.sequences:
			cur = cur + 1
			self.percent.emit(round(cur / total * 100, 1))
			
			if s.begin() < self.begin:
				continue
			filename = "{0}{1}.".format(random_prefix, int(s.begin() * 1000)) + self.audio_format
			filepath = os.path.join(home, "audio", filename)
			command = command_format.format(s.begin(), self.audio_path, s.end() - s.begin(), filepath)
			try:
				subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
			except:
				continue
			str = "{0}-[{1}-{2}]:{3}".format(filepath, s.begin(), s.end(), s.sentence())
			out.write(str)
			if s.end() > self.end:
				self.percent.emit(100.0)
				return

class SubCutter:
	def __init__(self, href = None, 
				vid_format = 'mp4', 
				audio_format = 'mp3', 
				lang = 'ja', 
				sub_format = 'srt',
				begin = -1, 
				end = 999999,
				dl_bar: QtWidgets.QProgressBar = None,
				ext_bar: QtWidgets.QProgressBar = None,
				setup_range = None):
		
		self.href = href
		self.vid_format = vid_format
		self.audio_format = audio_format
		self.lang = lang
		self.sub_format = sub_format
		self.begin = begin
		self.end = end
		self.general_path = os.path.normpath(os.path.join(home, "downloads", "SC"))
		self.vid_path = self.general_path + "." + vid_format
		self.audio_path = self.general_path + "." + audio_format
		self.vtt_sub_path = self.general_path + "." + lang + ".vtt"
		self.sub_path = self.general_path + "." + lang + "." + sub_format
		self.dl_bar = dl_bar
		self.ext_bar = ext_bar
		self.ffmpeg = "ffmpeg"
		self.setup_range = setup_range

	def _download(self):
		self.dl_bar.setValue(0)
		#app = QtCore.QCoreApplication([])
		self.thread = Dl_thread(href = self.href, 
								lang = self.lang, 
								general_path = self.general_path, 
								audio_path = self.audio_path, 
								vtt_sub_path = self.vtt_sub_path, 
								audio_format = self.audio_format, 
								dl_bar = self.dl_bar)
		self.thread.done.connect(self._convert_to_srt)
		self.thread.start()
		#app.exec_()

	def _convert_to_srt(self):
		command = self.ffmpeg + ' ' + '-i' + ' ' + self.vtt_sub_path + ' ' + self.sub_path + ' -loglevel quiet'
		use_shell = True
		try:
			output = subprocess.check_output(command.replace("\\", "/"), shell=use_shell)
			self.setup_range()	
		except Exception as e:
			error_message("Error: Couldn't convert .vtt subtitle to .srt!\n{}".format(e))
			return
		
	def _make_list(self):
		have_sub = os.path.exists(self.sub_path)
		
		if have_sub is False:
			error_message("Error: No .srt subtitle found.")
			return
		
		content = codecs.open((self.sub_path).replace("\\", "/"), 'r', 'UTF-8').readlines()
		
		time_pat = re.compile(r"(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})\n")
		empty_pat = re.compile(r"\s+")
		num_pat = re.compile(r"\d+\n")
		begin_time = 0
		end_time = 0

		mili_per_sec = 1000
		mili_per_min = 1000 * 60
		mili_per_hour = 1000 * 60 * 60
	
		sequences = []
		prev_seq = Sequence(0, 0, "")
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
				prev_seq._end = end_time / 1000
			elif (s != prev_s):
				prev_seq._sentence = prev_s
				sequences.append(prev_seq)
				prev_seq = Sequence(begin_time/1000, end_time/1000, "")
				prev_s = s
		prev_seq._sentence = prev_s
		sequences.append(prev_seq)
		
		return sequences[1:]
		
	def _process(self, sequences):
		self.ext_bar.setValue(0)
		self.thread = Process_thread(sequences, self.begin, self.end, self.audio_format, self.audio_path)
		self.thread.percent.connect(self._update_ext_bar)
		self.thread.start()
	
	def _update_ext_bar(self, val):
		self.ext_bar.setValue(val)

	def _cleanAudio(self):
		audio_folder = os.path.join(home, "audio/*")
		files = glob.glob(audio_folder.replace("\\", "/"))
		for f in files:
			os.remove(f)
	
	def _cleanDownloads(self):
		download_folder = os.path.join(home, "downloads/*")
		files = glob.glob(download_folder.replace("\\", "/"))
		for f in files:
			os.remove(f)	

	def run_download(self):
		try:
			self._cleanDownloads()
			self._download()
		except Exception as e:
			error_message("Error:  Something went wrong with the downloading process: \n{}".format(e))
			return 1
		return 0

	def run_extract(self):
		try:	
			sequences = self._make_list()
			self._cleanAudio()
			self._process(sequences)
		except Exception as e:
			error_message("Error:  Something went wrong with the extracting process: \n{}".format(e))
			return 1
		return 0
	
	def run(self):
		try:
			self._download()
			self._convert_to_srt()
			sequences = self._make_list()
			self._cleanAudio()
			self._process(sequences)
		except:
			return 1
		return 0

class MW(MineWindow):
	def __init__(self, browser, nids):
		super().__init__()
		self.browser = browser
		self.nids = nids
		self.sub_cutter = None
		self.setup_ui()

	def setup_ui(self):
		self.language_box.addItems(lang_list)
		self.col = self.browser.mw.col
		self._set_fields()
		self.download_button.clicked.connect(self.download)
		self.extract_button.clicked.connect(self.extract)
		self.add_button.clicked.connect(self.add_audio)
		self.download_bar.setValue(0)
		self.extract_bar.setValue(0)
		self.add_bar.setValue(0)
		self.time_slider.setDisabled(True)
		self.begin_box.setDisabled(True)
		self.end_box.setDisabled(True)
		self.time_len = 1000
		self.time_slider.startValueChanged.connect(self._update_begin)
		self.time_slider.endValueChanged.connect(self._update_end)
		self._get_options()
		self.language_box.currentTextChanged.connect(self._save_options)
		self.phrase_box.currentTextChanged.connect(self._save_options)
		self.audio_box.currentTextChanged.connect(self._save_options)
		self.setup_slider()
	
	def setup_slider(self):
		mp3_path = os.path.join(home, "downloads", "SC.mp3")
		have_prev_mp3 = os.path.exists(mp3_path)
		output = None
		
		if have_prev_mp3:
			args = ("ffprobe", "-show_entries", "format=duration", "-i", mp3_path)
			popen = subprocess.Popen(args, stdout = subprocess.PIPE)
			popen.wait()
			output = popen.stdout.read()
			#Ffprobe output pattern for Windows
			w_pat = re.compile(r'\[FORMAT\]\r\nduration=([\d\.]+)\r\n\[/FORMAT\]\r\n')
			#Ffprobe output pattern for Linux
			l_pat = re.compile(r'\[FORMAT\]\nduration=([\d\.]+)\n\[/FORMAT\]\n')
			
			m = w_pat.match(output.decode('utf8'))
			if not m:
				m = l_pat.match(output.decode('utf8'))
			
			self.time_len = float(m[1])
			self.time_slider.setStart(0)
			self.time_slider.setEnd(100)
			self.time_slider.setDisabled(False)

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
		self.phrase_box.addItems(fields)
		self.audio_box.addItems(fields)
	
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
		self.sub_cutter = SubCutter(href = link, 
									lang = sub_lang, 
									dl_bar = self.download_bar, 
									ext_bar = self.extract_bar,
									setup_range=self.setup_slider)
		self.sub_cutter.run_download()
	
	def extract(self):
		begin = int(self.time_len * self.time_slider.start() / 100)
		end = int(self.time_len * self.time_slider.end() / 100)
		if self.sub_cutter is None:
			download_dir = os.path.join(home, "downloads")
			srt_file = None
			mp3_file = None
			srt_file = getFile(self, _("Choose .srt file:"), dir = download_dir.replace("\\", "/"), cb = None, filter = _("*.srt"))
			if srt_file is None:
				return
			mp3_file = getFile(self, _("Choose .mp3 file:"), dir = download_dir.replace("\\", "/"), cb = None, filter = _("*.mp3"))
			if mp3_file is None:
				return
			self.download_bar.setValue(100)
			self.sub_cutter = SubCutter(begin = begin, end = end, 
										dl_bar = self.download_bar, 
										ext_bar = self.extract_bar)
			self.sub_cutter.sub_path = srt_file
			self.sub_cutter.audio_path = mp3_file
		self.sub_cutter.begin = begin
		self.sub_cutter.end = end
		self.sub_cutter.run_extract()
			
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
		expr_fld = self.phrase_box.currentText()
		audio_fld = self.audio_box.currentText()

		if not expr_fld:
			error_message("Please choose a type for phrase field.")
			return
		if not audio_fld:
			error_message("Please choose a type for audio field.")
			return

		total = len(self.nids)
		cur = 0

		for nid in self.nids:
			cur = cur + 1
			self.add_bar.setValue(cur / total * 100)

			note = mw.col.getNote(nid)
			if expr_fld in note and audio_fld in note:
				if not note[expr_fld]:
					continue
				pat = re.compile(r"(.+\." + atype + r")\-(\[.+\]):(.+)")
				with codecs.open(seq_path.replace("\\", "/"), 'r', 'UTF-8') as seq_map:
					sequences = seq_map.readlines()
					for s in sequences:
						matches = pat.match(s)
						if not matches:
							continue
						if matches[3].find(note[expr_fld]) != -1:
							audiofname = mw.col.media.addFile(matches[1])
							note[audio_fld] = "[sound:" + audiofname + "]"
				cnt += 1
				note.flush()
		self.browser.model.endReset()
		mw.requireReset()
		mw.progress.finish()
		mw.reset()
		tooltip("<b>Updated</b> {0} notes.".format(cnt), parent = self.browser)

	def _save_options(self):
		opts = {}
		path = opt_path.replace("\\", "/")
		opts['lang'] = self.language_box.currentText()
		opts['expr_fld'] = self.phrase_box.currentText()
		opts['audio_fld'] = self.audio_box.currentText()

		with codecs.open(path, 'w', 'UTF-8') as opt_file:
			opt_file.write(str(opts))

	def _get_options(self):
		opts = {}
		path = opt_path.replace("\\", "/")
		if os.stat(path).st_size:
			try:
				with codecs.open(path, 'r', 'UTF-8') as opt_file:
					opts = eval(opt_file.read())
				if opts['lang']:
					self.language_box.setCurrentText(opts['lang'])
				if opts['expr_fld']:
					self.phrase_box.setCurrentText(opts['expr_fld'])
				if opts['audio_fld']:
					self.audio_box.setCurrentText(opts['audio_fld'])
			except:
				return

def onBatchEdit(browser):
	dl_dir = os.path.join(home, 'downloads')
	audio_dir = os.path.join(home, 'audio')
	if not os.path.exists(dl_dir):
		os.makedirs(dl_dir)
	if not os.path.exists(audio_dir):
		os.makedirs(audio_dir)
		
	nids = browser.selectedNotes()
	if not nids:
		tooltip("No cards selected.")
		return
	browser.widget = MW(browser, nids)
	browser.widget.show()

def setupMenu(browser):
	menu = browser.form.menuEdit
	menu.addSeparator()
	a = menu.addAction('Mine audio...')
	a.setShortcut(QKeySequence('Ctrl+Alt+M'))
	a.triggered.connect(lambda _, b=browser: onBatchEdit(b))

def addToBrowser():
	addHook("browser.setupMenus", setupMenu)
