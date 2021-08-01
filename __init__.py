"""
Module-level entry point for the add-on into Anki 2.0/2.1
"""

from __future__ import (absolute_import, division,
                        print_function, unicode_literals)

import os, sys

home = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0,home)

from main import addToBrowser  # noqa: F401

addToBrowser()