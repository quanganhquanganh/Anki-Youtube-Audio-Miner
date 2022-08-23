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
				dl_bar = None,
				ext_bar = None,
				add_bar = None,
				dl_status = None,
				ext_status = None,
				add_status = None,):
		
		self._db = db
		self._browser = browser
		self.audio_format = audio_format
		self.lang = lang
		self.extract_path = os.path.normpath(audio_dir)
		self.download_path = os.path.normpath(dl_dir)
		self._dl_bar = dl_bar
		self._ext_bar = ext_bar
		self._add_bar = add_bar
		self._dl_status = dl_status
		self._ext_status = ext_status
		self._add_status = add_status
		self._ffmpeg = "ffmpeg"

		#Threads related
		self._dl_thread = None
		self._ext_thread = None
		self._add_thread = None
		self._search_thread = None
		self._matchings = None
		self._downloaded_videos = None
		self._finish_download = False
		self.done_flag = False

	def update_options(self, **kwargs):
		for key, value in kwargs.items():
			setattr(self, key, value)

	def _download_info(self, hrefs, finished_callback = None):
		self._dl_bar.setValue(0)
		# if self._dl_thread is not None:
		# 	self._dl_thread.terminate()
		self._dl_thread = DownloadThread(hrefs = hrefs, lang = self.lang, 
								download_path = self.download_path,
								only_info = True)
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
	# 	video_id = info['id']
	# 	filename = info['filename']
	# 	if not self._matchings:
	# 		self._matchings = {}
	# 	self._matchings[video_id] = {}

	# 	srt_filepath = None
	# 	try:
	# 		srt_filepath = self._convert_to_srt(filename)
	# 		sequences = []
	# 		for s in self._make_list(srt_filepath):
	# 			s[2] = s[2].replace("\n", "")
	# 			sequences.append(s)
	# 		for s in sequences:
	# 			self._matchings[video_id][s[0]] = s[1]


	def _add_downloaded(self, done_info):
			if 'id' in done_info and 'filename' in done_info:
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
				self._ext_status.setText("Finished")
				# Start AddThread
				# if self._ext_thread is not None:
				# 	self._ext_thread.terminate()
				# if self._add_thread is not None:
				# 	self._add_thread.terminate()
				self._add_thread = AddThread(self._matchings, self._browser)
				self._add_thread.percent.connect(self._add_bar.setValue)
				self._add_thread.done.connect(self.close)
				self._add_thread.start()
			else:			
				self._ext_status.setText("Waiting for download...")
			self._ext_thread = None
			return
		# if self._ext_thread is not None:
		# 	self._ext_thread.terminate()

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
		self._ext_status.setText("Extracting audio for {0}...".format(video['title']))

	def _process(self, matchings: dict):
		self._dl_bar.setValue(0)
		self._ext_bar.setValue(0)
		self._add_bar.setValue(0)
		
		# if self._dl_thread is not None:
		# 	self._dl_thread.terminate()
		# if self._ext_thread is not None:
		# 	self._ext_thread.terminate()
		# if self._add_thread is not None:
		# 	self._add_thread.terminate()
		
		self._finish_download = False
		self._matchings = matchings
		if len(self._matchings) == 0:
			self._dl_status.setText("No match found")
			return
		audio_hrefs = []
		to_be_extracted = []
		for vid in self._matchings:
			for seq in self._matchings[vid].values():
				if seq['pos'] in seq['note']['audio_flds']:
					audio_hrefs.append(vid)
					break
		download_folder = os.path.join(dl_dir, "*")
		files = glob.glob(download_folder.replace("\\", "/"))
		for f in files:
			# Check if file name is in audio_hrefs
			video_id = os.path.basename(f).split(".")[0]
			if video_id in audio_hrefs and len(os.path.basename(f).split(".")) == 2:
				to_be_extracted.append(self._db.get_video(video_id))
				audio_hrefs.remove(video_id)
			else:
				os.remove(f)
		self._downloaded_videos = iter(to_be_extracted)
		if len(audio_hrefs) == 0:
			self._finish_download = True
		else:
			self._dl_status.setText("Downloading {0} videos".format(len(audio_hrefs)))

			self._dl_thread = DownloadThread(hrefs = audio_hrefs, lang = self.lang, 
									download_path = self.download_path,
									only_info = False)
			self._dl_thread.done_info.connect(self._add_downloaded)
			self._dl_thread.percent.connect(self._dl_bar.setValue)
			self._dl_thread.amount.connect(self._dl_status.setText)
			def finish_dl_thread():
				self._finish_download = True
				self._dl_thread.terminate()
				self._dl_thread = None
			self._dl_thread.done.connect(finish_dl_thread)
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
		self._db.delete_all_files()
	
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
		if self._ext_thread is not None:
			self._ext_thread.terminate()
			self._ext_thread = None
		self.done_flag = False
