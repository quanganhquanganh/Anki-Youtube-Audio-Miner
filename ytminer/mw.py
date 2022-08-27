from .gui import MineWindow

from .subcutter import SubCutter
from .storage import Storage
from .get_ffmpeg import get_ffmpeg_latest_url
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
    self.add_button.clicked.connect(self.extract)
    # self.create_deck_button.clicked.connect(self.add_audio)
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

  def _get_sub_cutter(self, **kwargs):
    if self.sub_cutter is None:
      self.sub_cutter = SubCutter(browser=self.browser,
                      db = self.db,
                      dl_bar = self.download_bar, 
                      ext_bar = self.extract_bar,
                      add_bar = self.add_bar,
                      dl_status=self.download_status,
                      ext_status=self.extract_status,
                      add_status=self.add_status,
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
      note = self.col.getNote(nid)
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
    notes = self.col.models.allNames()
    for n in notes:
      for x in self.browser.mw.col.models.byName(str(n))['flds']:
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
      "https://youtube.com/watch?v={}&t={}".format(sub['video_id'], int(float(sub['start_time'])))]
      self._add_to_table(self.sub_table, idx, data)
    self.sub_table.resizeColumnsToContents()

  def _load_tables(self):
    self._load_videos()
    self._load_subs()

  # def _setup_saved_deck(self):
  #   # Find the ~::SavedVideos deck, if not found, create it
  #   deck_name = "~::SavedVideos"
  #   self.saved_deck = self.col.decks.id(deck_name)
  #   if self.saved_deck == None:
  #     self.saved_deck = self.col.decks.new(deck_name)
  #     self.saved_deck['desc'] = "All of your saved videos"
  #     self.col.decks.save(self.saved_deck)
  #     self.col.decks.update_parents(self.saved_deck)
  #     self.col.decks.flush()
  #   # Find the notetype for the SavedVideos deck, if not found, create it
  #   self.saved_deck_type = self.col.models.byName("SavedVideos")
  #   if self.saved_deck_type == None:
  #     self.saved_deck_type = self.col.models.new("SavedVideos")
  #     self.saved_deck_type['flds'] = [
  #       {'name': 'id', 'ord': 0, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 0, 'did': self.saved_deck},
  #       {'name': 'title', 'ord': 1, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 1, 'did': self.saved_deck},
  #       {'name': 'language', 'ord': 2, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 2, 'did': self.saved_deck},
  #       {'name': 'date', 'ord': 3, 'rtl': 0, 'sticky': False, 'fmt': 0, 'font': 'Arial', 'size': 12, 'brk': False, 'lbrk': 0, 'qcol': False, 'ord': 3, 'did': self.saved_deck},
  #     ]
  #     self.saved_deck_type['tmpls'].append({
  #       "name": "SavedVideos",
  #       "qfmt": "{{id}}",
  #       "afmt": "{{FrontSide}}<hr id=answer>{{title}}",
  #       "did": self.saved_deck,
  #     })
  #     self.col.models.add(self.saved_deck_type)
  #   self.saved_deck_type['did'] = self.saved_deck
  #   self.col.models.save(self.saved_deck_type)
  #   self.col.models.setCurrent(self.saved_deck_type)
  #   self.col.models.flush()
  #   saved_videos = self.db.get_videos()
  #   # Get the list of notes in the SavedVideos deck
  #   saved_note_ids = self.col.findNotes("deck:%s" % deck_name)
  #   saved_notes = []
  #   for n in saved_note_ids:
  #     saved_notes.append(self.col.getNote(n))
  #   # Compare the two lists and add any new videos to the SavedVideos deck
  #   to_be_downloaded = []
  #   for note in saved_notes:
  #     if note['id'] not in [x['id'] for x in saved_videos]:
  #       video = {
  #         'url': 
  #         unicodedata.normalize('NFKD', note['id']), 
  #         'lang':
  #         unicodedata.normalize('NFKD', note['language']),}
  #       to_be_downloaded.append(video)
  #   for video in saved_videos:
  #     if video['id'] not in [y['id'] for y in saved_notes]:
  #       saved_note = self.col.newNote(False)
  #       saved_note['id'] = video['id']
  #       saved_note['title'] = video['title']
  #       saved_note['language'] = video['lang']
  #       saved_note['date'] = video['date']
  #       saved_note.model()['did'] = self.saved_deck
  #       self.col.addNote(saved_note)
  #       self.col.save()
  #   if len(to_be_downloaded) > 0:
  #     error_message("Updating db: %s" % to_be_downloaded)
  #   self.sub_cutter = SubCutter(browser=self.browser,
  #                     db = self.db,
  #                     dl_bar=self.download_bar,
  #                     ext_bar=self.extract_bar,
  #                     add_bar=self.add_bar,
  #                     dl_status=self.download_status,
  #                     ext_status=self.extract_status,
  #                     add_status=self.add_status)
  #   self.sub_cutter._download_info(to_be_downloaded)
  
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

  def create_deck(self):
    return

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