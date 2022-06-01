from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os, sys

home = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,home)
os.makedirs(os.path.join(home, "user_files"), exist_ok=True)

import fileinput
import imghdr
from . import ytminer

ytminer.addToBrowser()