import sqlite3

from ytminer.messages import error_message

def dict_factory(cursor, row):
  d = {}
  for idx, col in enumerate(cursor.description):
    d[col[0]] = row[idx]
  return d

class Storage:
  def __init__(self, db_name):
    self.db_name = db_name

  def create_table(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #Enable foreign key constraint
      cursor.execute("""
        CREATE TABLE IF NOT EXISTS videos (
          id TEXT PRIMARY KEY,
          title TEXT,
          lang TEXT,
          date TEXT,
          path TEXT,
          type TEXT
          )""")
      cursor.execute("""
        CREATE TABLE IF NOT EXISTS sequences (
          id TEXT PRIMARY KEY,
          line TEXT,
          start_time TEXT,
          end_time TEXT,
          video_id TEXT,
          FOREIGN KEY (video_id) REFERENCES videos(id) ON DELETE CASCADE
        )""")
      cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          name TEXT,
          value TEXT
        )""")
      # cursor.execute("""
      #   CREATE TABLE IF NOT EXISTS files (
      #     id TEXT PRIMARY KEY,
      #     name TEXT,
      #     path TEXT,
      #     sequence_id TEXT,
      #     FOREIGN KEY (sequence_id) REFERENCES sequences(id) ON DELETE CASCADE
      #   )""")
      db.commit()

  def insert_video(self, title, url, lang, date):
    #Insert video only when it's url is unique and return the video_id
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #Insert video only when it's url is unique
      if self.get_video(url) is None:
        cursor.execute("""
          INSERT INTO videos (id, title, lang, date)
          VALUES (?, ?, ?, ?)""", (url, title, lang, date))
        db.commit()
      else:
        cursor.execute("""
          UPDATE videos SET title = ?, lang = ?, date = ? WHERE id = ?""", (title, lang, date, url))
        db.commit()

  def insert_sequences(self, video_id, sequences):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""PRAGMA foreign_keys = ON""")
      #Delete previous subtitles of the video
      cursor.execute("""
        DELETE FROM sequences WHERE video_id = ?""", (video_id,))
      for index, sequence in enumerate(sequences):
        id = video_id + '_' + str(index)
        cursor.execute("""
          INSERT INTO sequences (id, line, start_time, end_time, video_id)
          VALUES (?, ?, ?, ?, ?)""", (id, sequence[2], sequence[0], sequence[1], video_id))
      db.commit()

  def insert_setting(self, name, value):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #Insert setting only when it's name is unique
      if self.get_setting_by_name(name) is None:
        cursor.execute("""
          INSERT INTO settings (name, value)
          VALUES (?, ?)""", (name, value))
      else:
        cursor.execute("""
          UPDATE settings SET value = ? WHERE name = ?""", (value, name))
      db.commit()

  def insert_file(self, name, path, sequence_id):
    id = name.split('.')[0]
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #Check if the file is already in the database
      if self.get_file(id) is None:
        cursor.execute("""
          INSERT INTO files (id, name, path, sequence_id)
          VALUES (?, ?, ?, ?)""", (id, name, path, sequence_id))
      db.commit()

  def update_path(self, video_id, path):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        UPDATE videos SET path = ? WHERE id = ?""", (path, video_id))
      db.commit()

  def get_video_status(self, video_id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT status FROM videos WHERE id LIKE ?""", (video_id,))
      return cursor.fetchone()

  def get_sequence_from_sentence(self, sentence):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM sequences WHERE line = ?""", (sentence,))
      return cursor.fetchone()

  def get_videos(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM videos""")
      return cursor.fetchall()

  def get_matched_videos_page(self, query, page=1, limit=10):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM videos WHERE id = ? OR title LIKE ? LIMIT ? OFFSET ?""", (query, '%' + query + '%', limit, (page - 1) * limit))
      return cursor.fetchall()

  def get_video(self, video_id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM videos WHERE id = ?""", (video_id,))
      return cursor.fetchone()

  def search_matched_sequences_by_line(self, line):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #If the sequence's line includes the search keyword, then it's a matched sequence
      cursor.execute("""
        SELECT * FROM sequences WHERE line LIKE ?""", ("%" + line + "%",))
      return cursor.fetchall()

  def get_file(self, id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM files WHERE id = ?""", (id,))
      return cursor.fetchone()
  
  def search_matched_audios_by_line(self, line):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #If the sequence's line includes the search keyword, then it's a matched sequence
      cursor.execute("""
        SELECT * FROM files WHERE sequence_id IN (SELECT id FROM sequences WHERE line LIKE ?)""", ("%" + line + "%",))
      return cursor.fetchall()

  def get_matched_videos(self, lines):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      matched_videos = []
      #If the sequence's line includes the search keyword, then it's a matched sequence
      for line in lines:
        cursor.execute("""
          SELECT * FROM videos WHERE id IN (SELECT video_id FROM sequences WHERE line LIKE ?)""", ("%" + line + "%",))
        # matched_videos = list({v['id']:v for v in cursor.fetchall() + matched_videos}.values())
        #Fetch only one video
        matched_videos = list({cursor.fetchone()['id'] + matched_videos}.values())
      return matched_videos

  def get_matched_videos_and_sequences(self, lines) -> dict:
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      matched_videos = {}

      #If the sequence's line includes the search keyword, then it's a matched sequence
      for line in lines:
        cursor.execute("""
          SELECT * FROM sequences WHERE line LIKE ? LIMIT 1""", ("%" + line + "%",))
        seq = cursor.fetchone()
        if seq is not None:
          matched_videos[seq['video_id']] = matched_videos.get(seq['video_id'], []) + [seq]
      return matched_videos

  def get_matchings(self, notes) -> dict:
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      matched_videos = {}
      
      #If the sequence's line includes the search keyword, then it's a matched sequence
      for key, note in notes.items():
        max_idx = max([y for x in note.values() if type(x) == dict for y in x.keys()])
        min_idx = min([y for x in note.values() if type(x) == dict for y in x.keys()])
        cursor.execute("""
          SELECT * FROM sequences WHERE line LIKE ? LIMIT ? OFFSET ?""", 
            ("%" + note['expr'] + "%", max_idx - min_idx + 1, min_idx))
        seqs = cursor.fetchall()
        if seqs is not None:
          for idx, seq in enumerate(seqs):
            if idx in [y for x in note.values() if type(x) == dict for y in x.keys()]:
              seq['note'] = note
              seq['note']['nid'] = key
              seq['pos'] = idx
              matched_videos[seq['video_id']] = matched_videos.get(seq['video_id'], {})
              matched_videos[seq['video_id']][seq['id']] = seq
              # if len(note['audio_flds']) > 0:
              #   matched_videos[seq['video_id']]['audio'] = True
              # if len(note['video_flds']) > 0:
              #   matched_videos[seq['video_id']]['video'] = True
      return matched_videos

  def get_matchings_from_video(self, video_id) -> dict:
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      matched_videos = {}
      
      #If the sequence's line includes the search keyword, then it's a matched sequence
      cursor.execute("""
        SELECT * FROM sequences WHERE video_id = ?""", (video_id,))
      seqs = cursor.fetchall()
      if seqs is not None:
        for seq in seqs:
          matched_videos[seq['video_id']] = matched_videos.get(seq['video_id'], {})
          matched_videos[seq['video_id']][seq['id']] = seq
      return matched_videos

  def get_sequence(self, id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM sequences WHERE id = ?""", (id,))
      return cursor.fetchone()

  def get_matched_sequences(self, lines, video_id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      matched_sequences = []
      for line in lines:
        cursor.execute("""
          SELECT * FROM sequences WHERE line LIKE ? AND video_id = ?""", ("%" + line + "%", video_id))
        matched_sequences.extend(cursor.fetchall())
      return matched_sequences

  def get_matched_sequences_page(self, query, page=1, limit=10):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM sequences WHERE id LIKE ?
        OR line LIKE ? LIMIT ? OFFSET ?""", ('%' + query + '%', '%' + query + '%', limit, (page - 1) * limit))
      return cursor.fetchall()

  def get_settings(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM settings""")
      return cursor.fetchall()

  def get_setting_by_name(self, name):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM settings WHERE name = ?""", (name,))
      return cursor.fetchone()

  def get_files(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM files""")
      return cursor.fetchall()

  def get_file_by_id(self, file_id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM files WHERE id = ?""", (file_id,))
      return cursor.fetchone()

  def get_file_by_name(self, name):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM files WHERE name = ?""", (name,))
      return cursor.fetchone()

  def get_downloaded_videos(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        SELECT * FROM videos WHERE status = ?""", ("downloaded",))
      return cursor.fetchall()

  def delete_video_by_id(self, video_id):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      #Delete all files associated with the video
      cursor.execute("""
        DELETE FROM files WHERE sequence_id IN (SELECT id FROM sequences WHERE video_id = ?)""", (video_id,))
      #Delete all the sequences associated with the video
      cursor.execute("""
        DELETE FROM sequences WHERE video_id = ?""", (video_id,))
      #Delete the video
      cursor.execute("""
        DELETE FROM videos WHERE id = ?""", (video_id,))
      db.commit()
      
  def delete_videos_by_ids(self, video_ids):
      with sqlite3.connect(self.db_name) as db:
          db.row_factory = dict_factory
          cursor = db.cursor()
          #Delete all files associated with the video
          cursor.execute("""
              DELETE FROM files WHERE sequence_id IN (SELECT id FROM sequences WHERE video_id IN ({0}))""".format(','.join(['?' for _ in video_ids])), video_ids)
          #Delete all the sequences associated with the video
          cursor.execute("""
              DELETE FROM sequences WHERE video_id IN ({0})""".format(','.join(['?' for _ in video_ids])), video_ids)
          #Delete the video
          cursor.execute("""
              DELETE FROM videos WHERE id IN ({0})""".format(','.join(['?' for _ in video_ids])), video_ids)
          db.commit()

  def delete_subs_by_ids(self, subs_ids):
      with sqlite3.connect(self.db_name) as db:
          db.row_factory = dict_factory
          cursor = db.cursor()
          #Delete all files associated with the video
          cursor.execute("""
              DELETE FROM sequences WHERE id IN ({0})""".format(','.join(['?' for _ in subs_ids])), subs_ids)
          db.commit()

  def update_sub(self, id, sub):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        UPDATE sequences SET line = ? WHERE id = ?""", (sub, id))
      db.commit()

  def path_update_video(self, video_id, path):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        UPDATE videos SET path = ? WHERE id = ?""", (path, video_id))
      db.commit()

  def type_update_video(self, video_id, type):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        UPDATE videos SET type = ? WHERE id = ?""", (type, video_id))
      db.commit()

  def delete_all_videos(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        UPDATE videos SET status = ? WHERE status = ?""", ("deleted", "downloaded"))
      db.commit()

  def delete_all_files(self):
    with sqlite3.connect(self.db_name) as db:
      db.row_factory = dict_factory
      cursor = db.cursor()
      cursor.execute("""
        DELETE FROM files""")  
      db.commit()