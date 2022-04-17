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
import time
import threading
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
			audio_fld = seq['note']['audio_fld'] if 'audio_fld' in seq['note'] else None
			sentence_fld = seq['note']['sentence_fld'] if 'sentence_fld' in seq['note'] else None
			url_fld = seq['note']['url_fld'] if 'url_fld' in seq['note'] else None

			note = mw.col.getNote(nid)
			if audio_fld:
				if 'filepath' not in seq:
					continue
				filepath = seq['filepath']
				audiofname = mw.col.media.addFile(filepath)
				note[audio_fld] = "[sound:" + audiofname + "]"
			if sentence_fld:
				note[sentence_fld] = seq['line']
			# Get the Youtube URL from the video's id and start time
			if url_fld:
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
			

class DownloadThread(QtCore.QThread):
	done_info = QtCore.pyqtSignal(dict)
	percent = QtCore.pyqtSignal(float)
	amount = QtCore.pyqtSignal(str)
	finished = QtCore.pyqtSignal()

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
			filename = os.path.basename(d['filename'])
			url = filename.split(".")[0]
			_info = youtube_dl.YoutubeDL().extract_info(url, download=False)
			_info['filename'] = d['filename']
			self.done_info.emit(_info)
			self._current = self._current + 1
			self.amount.emit(str(self._current))
			if self._current == self._total:
				self.finished.emit()

		if d['status'] == 'downloading':
			p = d['_percent_str']
			p = p.replace('%','')
			#Check if p is convertible to float
			try:
				p = float(p) if float(p) >= 1 else 1
			except:
				p = 0
			self.percent.emit(p)
			
	def _download_urls(self, urls, options, extract_info = True):
		prev_current = self._current
		to_be_downloaded = []
		if extract_info:
			for href in urls:
				ydl = youtube_dl.YoutubeDL({
					'extract_flat': True,
				})
				info = ydl.extract_info(href, download=False)
				if 'entries' in info:
					# Can be a playlist or a list of videos
					entries = info['entries']
					to_be_downloaded.extend([entry['url'] for entry in entries])
				else:
					# Just a video
					to_be_downloaded.append(info['id'])
			self._total = len(to_be_downloaded)
		else:
			to_be_downloaded = urls
		ydl = youtube_dl.YoutubeDL(options)
		try:
			ydl.download(to_be_downloaded)
		except Exception as e:
			if "HTTP Error 429: Too Many Requests" in str(e):
				to_be_downloaded = to_be_downloaded[(self._current - prev_current):]
				return self._download_urls(to_be_downloaded, options, extract_info = False)
			else:
				raise e

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
			# error_message('Urls and lang: ' + str(urls) + ' ' + str(lang))
			audio_opts = {'format': 'bestaudio/best',
						'progress_hooks': [self._download_hook],
						"outtmpl": os.path.join(self.download_path, "%(id)s.%(ext)s"),
						"quiet":True, "no_warnings":True}
			self._download_urls(urls, audio_opts)

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
			except:
				continue

		self.done_files.emit(files)

class SubCutter:
	def __init__(self,
				browser,
				db: Storage,
				lang: str = "en", 
				vid_format = 'mp4', 
				audio_format = 'mp3',
				sub_format = 'srt',
				begin = -1, 
				end = 999999,
				dl_bar: QtWidgets.QProgressBar = None,
				ext_bar: QtWidgets.QProgressBar = None,
				add_bar: QtWidgets.QProgressBar = None,
				dl_status: QtWidgets.QLabel = None,
				ext_status: QtWidgets.QLabel = None,
				add_status: QtWidgets.QLabel = None,):
		
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
		self._add_bar = add_bar
		self._dl_status = dl_status
		self._ext_status = ext_status
		self._add_status = add_status
		self._ffmpeg = "ffmpeg"
		self._db = db
		self._browser = browser

		#Threads related
		self._dl_thread = None
		self._ext_thread = None
		self._add_thread = None
		self._search_thread = None
		self._matchings = None
		self._downloaded_videos = None
		self._finish_download = False

	def _download_info(self, hrefs):
		self._dl_bar.setValue(0)
		if self._dl_thread is not None:
			self._dl_thread.terminate()
		self._dl_thread = DownloadThread(hrefs = hrefs, lang = self.lang, 
								download_path = self.download_path,
								only_info = True)
		#Get vtt filename then convert it to srt
		self._dl_thread.done_info.connect(self._store_subtitle)
		self._dl_thread.percent.connect(self._dl_bar.setValue)
		self._dl_thread.amount.connect(self._dl_status.setText)
		self._dl_thread.start()

	# @QtCore.pyqtSlot(dict)
	def _store_subtitle(self, info):
		video_id = info['id']
		filename = info['filename']
		srt_filepath = None
		try:
			srt_filepath = self._convert_to_srt(filename)
			sequences = [s.rstrip() for s in self._make_list(srt_filepath)]
			self._db.insert_video(info['title'], video_id, self.lang, datetime.datetime.now())
			self._db.insert_sequences(video_id, sequences)
		except Exception as e:
			self._db.delete_video_by_id(video_id)
			error_message("Error while processing video {0}".format(e))
		if(os.path.exists(filename)):
			os.remove(filename)
		if(srt_filepath and os.path.exists(srt_filepath)):
			os.remove(srt_filepath)

	def _add_downloaded(self, done_info):
			id = done_info['id']
			filename = done_info['filename']
			filepath = os.path.join(self.download_path, filename)
			self._db.path_update_video(id, filepath)
			self._downloaded_videos = itertools.chain(self._downloaded_videos, [self._db.get_video(id)])
			if self._ext_thread is None:
				self._process_next()
				
	def _process_next(self, files = []):
		# Add filepath to _matchings
		for f in files:
			self._matchings[f['video_id']][f['sequence_id']]['filepath'] = f['filepath']
		video = None
		try:
			video = next(self._downloaded_videos)
		except StopIteration:
			if self._finish_download:
				# Start AddThread
				self._add_thread = AddThread(self._matchings, self._browser)
				self._add_thread.percent.connect(self._add_bar.setValue)
				self._add_thread.start()
			self._ext_thread = None
			return
		if self._ext_thread is not None:
			self._ext_thread.terminate()

		sequences = self._matchings[video['id']]
		# Convert sequences to list
		sequences = list(sequences.values())
		self._ext_thread = ProcessThread(video['path'], 
										extract_path=self.extract_path, 
										sequences=sequences, 
										audio_format=self.audio_format)
		self._ext_thread.done_files.connect(self._process_next)
		self._ext_thread.percent.connect(self._ext_bar.setValue)
		self._ext_thread.start()

	def _process(self, matchings: dict):
		self._dl_bar.setValue(0)
		self._dl_status.setText("")
		self._ext_bar.setValue(0)
		self._ext_status.setText("")
		self._add_bar.setValue(0)
		self._add_status.setText("")
		
		if self._dl_thread is not None:
			self._dl_thread.terminate()
		if self._ext_thread is not None:
			self._ext_thread.terminate()
		if self._add_thread is not None:
			self._add_thread.terminate()
		
		self._matchings = matchings
		if len(self._matchings) == 0:
			# self._ext_status.setText("0")
			error_message("No videos found")
			return

		hrefs = list(self._matchings.keys())
		self._downloaded_videos = iter([])

		error_message("Downloading {0} videos".format(len(hrefs)))
		error_message(str(hrefs))
		error_message(str(self._matchings))

		self._dl_thread = DownloadThread(hrefs = hrefs, lang = self.lang, 
								download_path = self.download_path,
								only_info = False)
		self._dl_thread.done_info.connect(self._add_downloaded)
		self._dl_thread.percent.connect(self._dl_bar.setValue)
		def finish_dl_thread():
			self._finish_download = True
			self._dl_thread.terminate()
			self._dl_thread = None
		self._dl_thread.finished.connect(finish_dl_thread)
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

	def run(self, notes):
		try:
			self._clean_downloads()
			self._search_thread = SearchThread(self._db, notes)
			self._search_thread.matchings.connect(self._process)
			self._search_thread.start()
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
		self.saved_deck = None
		self.saved_deck_type = None
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
		self.time_len = 1000
		self._get_options()
		self.language_box.currentTextChanged.connect(self._save_options)
		self._setup_saved_deck()
	
	def get_expressions(self):
		nids = self.browser.selectedNotes()
		notes = []
		self.nids = nids
		expr_fld = 'sentence'
		audio_fld = 'audio'
		sentence_fld = 'sentence'
		url_fld = 'url'
		for nid in nids:
			note = self.col.getNote(nid)
			if expr_fld in note and audio_fld in note:
				if not note[expr_fld]:
					continue
				if note[audio_fld]:
					audio_id = note[audio_fld].split(":")[1].split("]")[0].split(".")[0]
					if self.db.get_sequence(audio_id) is not None:
						continue
				notes.append({'nid': nid, 'expr': note[expr_fld], 
										'audio_fld': audio_fld, 'expr_fld': expr_fld, 
										'sentence_fld': sentence_fld, 'url_fld': url_fld})
		return notes

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

	def _toggle_buttons(self, state):
		self.store_button.setDisabled(state)
		self.set_fields_button.setDisabled(state)
		self.open_storage_button.setDisabled(state)
		self.add_button.setDisabled(state)
		self.create_deck_button.setDisabled(state)

	def _setup_saved_deck(self):
		# Find the ~::SavedVideos deck, if not found, create it
		deck_name = "~::SavedVideos"
		self.saved_deck = self.col.decks.id(deck_name)
		if self.saved_deck == None:
			self.saved_deck = self.col.decks.new(deck_name)
			self.saved_deck['desc'] = "All of your saved videos"
			self.col.decks.save(self.saved_deck)
			self.col.decks.update_parents(self.saved_deck)
			self.col.decks.flush()
		# Find the notetype for the SavedVideos deck, if not found, create it
		self.saved_deck_type = self.col.models.byName("SavedVideos")
		if self.saved_deck_type == None:
			self.saved_deck_type = self.col.models.new("SavedVideos")
			self.saved_deck_type['flds'] = [
				{'name': 'id', 'ord': 0, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 0, 'did': self.saved_deck},
				{'name': 'title', 'ord': 1, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 1, 'did': self.saved_deck},
				{'name': 'language', 'ord': 2, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 2, 'did': self.saved_deck},
				{'name': 'date', 'ord': 3, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 3, 'did': self.saved_deck},
			]
			self.saved_deck_type['tmpls'].append({
				"name": "SavedVideos",
				"qfmt": "{{id}}",
				"afmt": "{{FrontSide}}<hr id=answer>{{title}}",
				"did": self.saved_deck,
			})
			self.col.models.add(self.saved_deck_type)
		self.saved_deck_type['did'] = self.saved_deck
		self.col.models.save(self.saved_deck_type)
		self.col.models.setCurrent(self.saved_deck_type)
		self.col.models.flush()
		saved_videos = self.db.get_videos()
		# Get the list of notes in the SavedVideos deck
		saved_note_ids = self.col.findNotes("deck:%s" % deck_name)
		saved_notes = []
		for n in saved_note_ids:
			saved_notes.append(self.col.getNote(n))
		# Compare the two lists and add any new videos to the SavedVideos deck
		to_be_downloaded = []
		for note in saved_notes:
			if note['id'] not in [x['id'] for x in saved_videos]:
				video = {'url': note['id'], 'lang': note['language'] }
				# # Remove weird characters from the url
				# video['url'] = video['url'].replace("\\", "")
				to_be_downloaded.append(video)
		for video in saved_videos:
			if video['id'] not in [y['id'] for y in saved_notes]:
				saved_note = self.col.newNote(False)
				saved_note['id'] = video['id']
				saved_note['title'] = video['title']
				saved_note['language'] = video['lang']
				saved_note['date'] = video['date']
				saved_note.model()['did'] = self.saved_deck
				self.col.addNote(saved_note)
				self.col.save()
		if len(to_be_downloaded) > 0:
			error_message("Updating db: %s" % to_be_downloaded)
		self.sub_cutter = SubCutter(browser=self.browser,
											db = self.db,
											dl_bar=self.download_bar,
											ext_bar=self.extract_bar,
											add_bar=self.add_bar,
											dl_status=self.download_status,
											ext_status=self.extract_status,
											add_status=self.add_status)
		self.sub_cutter._download_info(to_be_downloaded)
	
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
		self.sub_cutter = SubCutter(browser=self.browser,
											db = self.db,
											hrefs = link, 
											lang = sub_lang, 
											dl_bar = self.download_bar, 
											ext_bar = self.extract_bar,
											add_bar = self.add_bar,
											dl_status=self.download_status,
											ext_status=self.extract_status,
											add_status=self.add_status)
		self.sub_cutter.run_download()
	
	def extract(self):
		if self.sub_cutter is None:
			self.sub_cutter = SubCutter(browser=self.browser,
												db = self.db,
												dl_bar = self.download_bar, 
												ext_bar = self.extract_bar,
												add_bar = self.add_bar,
												dl_status=self.download_status,
												ext_status=self.extract_status,
												add_status=self.add_status)
		notes = self.get_expressions()
		if len(notes) == 0:
			error_message("No new audio needed to be add.")
			return
		self.sub_cutter.run(notes)

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
		self.sub_cutter = SubCutter(browser=self.browser,
											db = self.db, 
											lang = sub_lang, 
											dl_bar = self.download_bar, 
											ext_bar = self.extract_bar,
											add_bar = self.add_bar,
											dl_status=self.download_status,
											ext_status=self.extract_status,
											add_status=self.add_status)
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
