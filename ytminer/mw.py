from .gui import MineWindow

from PyQt5 import QtCore
from .subcutter import SubCutter
from .storage import Storage
from .paths import storage_path, downloaded_ffmpeg
from .messages import error_message
from .constants import LANGUAGES, lang_list

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
    self._set_fields()
    self.store_button.clicked.connect(self.store_video)
    self.delete_button.clicked.connect(self.delete_videos)
    self.sub_delete_button.clicked.connect(self.delete_subs)
    self.sub_edit_button.clicked.connect(self.edit_subs)
    self.add_button.clicked.connect(self.extract)
    self.create_deck_button.clicked.connect(self.create_deck)
    self.download_bar.setValue(0)
    self.extract_bar.setValue(0)
    self.add_bar.setValue(0)
    self._get_options()
    self.language_box.currentTextChanged.connect(self._save_options)
    self.save_button.clicked.connect(self._save_options)
    self._video_page : int = 1
    self._sub_page : int = 1
    self.prev_page.clicked.connect(self._prev_vid_page)
    self.next_page.clicked.connect(self._next_vid_page)
    self.prev_page_2.clicked.connect(self._prev_sub_page)
    self.next_page_2.clicked.connect(self._next_sub_page)
    self.video_search_button.clicked.connect(lambda: self._load_videos())
    self.sub_search_button.clicked.connect(lambda: self._load_subs())
    self.video_search.returnPressed.connect(self._load_videos)
    self.sub_search.returnPressed.connect(self._load_subs)
    # Setup Search Tab
    self._load_tables()
    # Detect if there's ffmpeg installed in the terminal
    self._check_ffmpeg()

  @QtCore.pyqtSlot(float)
  def set_dl_bar(self, value):
    self.download_bar.setValue(value)

  @QtCore.pyqtSlot(str)
  def set_dl_status(self, status):
    self.download_status.setText(status)

  @QtCore.pyqtSlot(float)
  def set_extract_bar(self, value):
    self.extract_bar.setValue(value)

  @QtCore.pyqtSlot(str)
  def set_extract_status(self, status):
    self.extract_status.setText(status)

  @QtCore.pyqtSlot(float)
  def set_add_bar(self, value):
    self.add_bar.setValue(value)

  @QtCore.pyqtSlot(str)
  def set_add_status(self, status):
    self.add_status.setText(status)

  def _get_sub_cutter(self, **kwargs):
    if self.sub_cutter is None:
      self.sub_cutter = SubCutter(browser=self.browser,
                      db = self.db,
                      set_dl_bar = self.set_dl_bar,
                      set_ext_bar = self.set_extract_bar,
                      set_add_bar = self.set_add_bar,
                      set_dl_status=self.set_dl_status,
                      set_ext_status=self.set_extract_status,
                      set_add_status=self.set_add_status,
                      **kwargs)
    else:
      self.sub_cutter.update_options(**kwargs)

  def _check_ffmpeg(self):
    from subprocess import check_output
    import os
    try:
      check_output(["ffmpeg", "-version"])
      self.ffmpeg = "ffmpeg"
    except:
      if os.path.exists(downloaded_ffmpeg):
        self.ffmpeg = downloaded_ffmpeg
      else:
        self._download_ffmpeg()
    self._get_sub_cutter(ffmpeg=self.ffmpeg)

  def _download_ffmpeg(self):
    self._get_sub_cutter()
    self.sub_cutter.download_ffmpeg()
    self.ffmpeg = downloaded_ffmpeg

  def get_notes(self):
    nids = self.browser.selectedNotes()
    notes = {}
    self.nids = nids
    fields = self._get_fields()
    match_fld = fields['match_fld']
    for nid in nids:
      note = self.col.get_note(nid)
      if match_fld in note:
        if not note[match_fld]:
          continue
        # An ordered dictionary of the fields, used for getting multiple subtitles
        notes[nid] = {
          'expr': note[match_fld],
          'audio_flds': {},
          'sentence_flds': {},
          'url_flds': {},
          'screenshot_flds': {},
        }
        for idx, audio_fld in enumerate(fields['audio_flds']):
          if audio_fld in note:
            # Check if the audio field has an id that already exists in the db
            if note[audio_fld]:
              try:
               audio_id = note[audio_fld].split(":")[1].split("]")[0].split(".")[0]
               if self.db.get_sequence(audio_id) is not None:
                continue
              except Exception as e:
               pass
            notes[nid]['audio_flds'][idx] = audio_fld
        for idx, sentence_fld in enumerate(fields['sentence_flds']):
          if sentence_fld in note:
            if note[sentence_fld]:
              continue
            notes[nid]['sentence_flds'][idx] = sentence_fld
        for idx, url_fld in enumerate(fields['url_flds']):
          if url_fld in note:
            if note[url_fld]:
              continue
            notes[nid]['url_flds'][idx] = url_fld
        for idx, screenshot_fld in enumerate(fields['screenshot_flds']):
          if screenshot_fld in note:
            if note[screenshot_fld]:
              continue
            notes[nid]['screenshot_flds'][idx] = screenshot_fld
        if not notes[nid]['audio_flds'] and not notes[nid]['sentence_flds'] and not notes[nid]['url_flds'] and not notes[nid]['screenshot_flds']:
          del notes[nid]
    return notes

  def _set_fields(self):
    # Set fields found in all cards for the match box
    fields = []
    notes = self.col.models.all_names()
    for n in notes:
      for x in self.browser.mw.col.models.by_name(str(n))['flds']:
        if x['name'] not in fields:
          fields.append(x['name'])
    self.match_box.addItems(fields)

  def _get_fields(self):
    fields = {}
    separator = ','
    if not self.match_box.currentText():
      error_message("Invalid fields.")
      return
    fields['match_fld'] = self.match_box.currentText()
    # Split the current texts using separator
    sentence_flds = self.sentence_box.text().split(separator)
    audio_flds = self.audio_box.text().split(separator)
    url_flds = self.youtube_box.text().split(separator)
    screenshot_flds = self.screenshot_box.text().split(separator)
    # Remove spaces
    sentence_flds = [x.strip() for x in sentence_flds if x.strip()]
    audio_flds = [x.strip() for x in audio_flds if x.strip()]
    url_flds = [x.strip() for x in url_flds if x.strip()]
    screenshot_flds = [x.strip() for x in screenshot_flds if x.strip()]
    fields['sentence_flds'] = sentence_flds
    fields['audio_flds'] = audio_flds
    fields['url_flds'] = url_flds
    fields['screenshot_flds'] = screenshot_flds
    return fields

  def _prev_vid_page(self):
    if self._video_page > 1:
      self._video_page -= 1
      self.page_label.setText("Page: {}".format(self._video_page))
      return self._load_videos(page=self._video_page, clear_if_none=False)

  def _next_vid_page(self):
    return self._load_videos(page=self._video_page + 1, clear_if_none=False)

  def _prev_sub_page(self):
    if self._sub_page > 1:
      self._sub_page -= 1
      self.page_label_2.setText("Page: {}".format(self._sub_page))
      return self._load_subs(page=self._sub_page, clear_if_none=False)

  def _next_sub_page(self):
    return self._load_subs(page=self._sub_page + 1, clear_if_none=False)

  def _load_videos(self, page=1, limit=10, clear_if_none=True):
    video_query = self.video_search.text()
    videos = self.db.get_matched_videos_page(video_query, page, limit)

    if len(videos) == 0:
      self.next_page.setEnabled(False)
      if not clear_if_none:
        return
    else:
      self._video_page = page
      self.next_page.setEnabled(True)
    self.page_label.setText("Page: {}".format(self._video_page))

    if self.video_table.rowCount() > 0:
      self.video_table.clearContents()
    self.video_table.setRowCount(len(videos))
    for idx, video in enumerate(videos):
      data = [video['id'], video['title'], video['lang'], video['date']]
      self._add_to_table(self.video_table, idx, data)
    self.video_table.resizeColumnsToContents()

  def _load_subs(self, page=1, limit=10, clear_if_none=True):
    sub_query = self.sub_search.text()
    subs = self.db.get_matched_sequences_page(sub_query, page, limit)
    
    if len(subs) == 0:
      self.next_page_2.setEnabled(False)
      if not clear_if_none:
        return
    else:
      self._sub_page = page
      self.next_page_2.setEnabled(True)
    self.page_label_2.setText("Page: {}".format(self._sub_page))

    if self.sub_table.rowCount() > 0:
      self.sub_table.clearContents()
    self.sub_table.setRowCount(len(subs))
    for idx, sub in enumerate(subs):
      data = [sub['id'], sub['line'], sub['start_time'], sub['end_time'],
      "https://www.youtube.com/watch?v={}&t={}".format(sub['video_id'], int(float(sub['start_time'])))]
      self._add_to_table(self.sub_table, idx, data)
    self.sub_table.resizeColumnsToContents()

  def _load_tables(self):
    self._load_videos()
    self._load_subs()
  
  def extract(self):
    self._get_sub_cutter()
    notes = self.get_notes()
    if len(notes) == 0:
      self.download_status.setText("No new cards needs to be added")
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
    self._get_sub_cutter(lang = sub_lang)
    self.sub_cutter.run_store([link])

  def delete_videos(self):
    rows = self.video_table.selectionModel().selectedRows()
    if len(rows) == 0:
      error_message("No videos selected.")
      return
    video_ids = [self.video_table.item(row.row(), 0).text() for row in rows]
    self.db.delete_videos_by_ids(video_ids)
    self._load_videos(page=self._video_page)

  def delete_subs(self):
    rows = self.sub_table.selectionModel().selectedRows()
    if len(rows) == 0:
      error_message("No subs selected.")
      return
    sub_ids = [self.sub_table.item(row.row(), 0).text() for row in rows]
    self.db.delete_subs_by_ids(sub_ids)
    self._load_subs(page=self._sub_page)

  def edit_subs(self):
    for row in range(self.sub_table.rowCount()):
      sub_id = self.sub_table.item(row, 0).text()
      sub_text = self.sub_table.item(row, 1).text()
      if sub_text == "":
        continue
      self.db.update_sub(sub_id, sub_text)
    self._load_subs(page=self._sub_page)

  def create_deck(self):
    link = str(self.link_box.text())
    try:
      sub_lang = {v:k for k, v in LANGUAGES.items()}[str(self.language_box.currentText())]
    except:
      error_message("Invalid language.")
      return
    if not link.startswith("https://www.youtube.com/"):
      error_message("Invalid youtube link.")
      return
    self._get_sub_cutter(lang = sub_lang)
    self.sub_cutter.run_create_decks([link], self._get_fields())

  def _save_options(self):
    self.db.insert_setting('lang', self.language_box.currentText())
    self.db.insert_setting('match_fld', self.match_box.currentText())
    self.db.insert_setting('audio_fld', self.audio_box.text())
    self.db.insert_setting('sentence_fld', self.sentence_box.text())
    self.db.insert_setting('url_fld', self.youtube_box.text())
    self.db.insert_setting('screenshot_fld', self.screenshot_box.text())
  
  def _get_options(self):
    settings = self.db.get_settings()
    if len(settings) == 0:
      return
    for setting in settings:
      if setting['name'] == 'lang':
        self.language_box.setCurrentText(setting['value'])
      if setting['name'] == 'match_fld':
        self.match_box.setCurrentText(setting['value'])
      if setting['name'] == 'audio_fld':
        self.audio_box.setText(setting['value'])
      if setting['name'] == 'sentence_fld':
        self.sentence_box.setText(setting['value'])
      if setting['name'] == 'url_fld':
        self.youtube_box.setText(setting['value'])
      if setting['name'] == 'screenshot_fld':
        self.screenshot_box.setText(setting['value'])

  #  On exit
  def closeEvent(self, event):
    if self.sub_cutter is not None:
      self.sub_cutter.close()
    self.sub_cutter = None
    event.accept()