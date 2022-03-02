import sqlite3

def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

# def sqlite_connect(db_file):
#     conn = sqlite3.connect(db_file)
#     conn.row_factory = dict_factory
#     return conn

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
                    path TEXT
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
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    path TEXT,
                    sequence_id TEXT,
                    FOREIGN KEY (sequence_id) REFERENCES sequences(id) ON DELETE CASCADE
                )""")
            db.commit()

    def insert_video(self, title, url, lang, status, date):
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

    def get_videos(self):
        with sqlite3.connect(self.db_name) as db:
            db.row_factory = dict_factory
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM videos""")
            return cursor.fetchall()

    def get_video(self, video_id):
        with sqlite3.connect(self.db_name) as db:
            db.row_factory = dict_factory
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM videos WHERE id = ?""", (video_id,))
            return cursor.fetchone()

    def get_subtitles(self, video_id):
        with sqlite3.connect(self.db_name) as db:
            db.row_factory = dict_factory
            cursor = db.cursor()
            cursor.execute("""
                SELECT * FROM sub_lines WHERE video_id = ?""", (video_id,))
            return cursor.fetchall()

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
                matched_videos = list({v['id']:v for v in cursor.fetchall() + matched_videos}.values())
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

    def path_update_video(self, video_id, path):
        with sqlite3.connect(self.db_name) as db:
            db.row_factory = dict_factory
            cursor = db.cursor()
            cursor.execute("""
                UPDATE videos SET path = ? WHERE id = ?""", (path, video_id))
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