import os

from aqt.qt import *
from anki.hooks import addHook
from anki.lang import _
from anki import version as anki_version

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

ANKI20 = anki_version.startswith("2.0")
unicode = str if not ANKI20 else unicode

from .mw import MW
from .paths import dl_dir, audio_dir

def onBatchEdit(browser):
	if not os.path.exists(dl_dir):
		os.makedirs(dl_dir)
	if not os.path.exists(audio_dir):
		os.makedirs(audio_dir)
	browser.ymw_widget = MW(browser)
	browser.ymw_widget.show()

def setupMenu(browser):
	menu = browser.form.menuEdit
	menu.addSeparator()
	a = menu.addAction('Mine audio...')
	a.setShortcut(QKeySequence('Ctrl+Alt+M'))
	a.triggered.connect(lambda _, b=browser: onBatchEdit(b))

def addToBrowser():
	addHook("browser.setupMenus", setupMenu)