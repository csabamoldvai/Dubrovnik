"""Compact test version of the Dubrovnik Workbench.

Runs dubrovnik_workbench.py with every widget (fonts, entry boxes, buttons,
paddings) scaled down by UI_SCALE. Window and panel widths follow
automatically, since they are computed from the widgets' natural size.
Change UI_SCALE to taste: 0.85 = 15% smaller, 0.90 = 10% smaller.
"""
import os
import runpy
import sys

import customtkinter as ctk

UI_SCALE = .85 # 1, 0.92

# make the project root importable (for "from dubLibs import ...")
here = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(here))

ctk.set_widget_scaling(UI_SCALE)   # must be set before the main window exists
runpy.run_path(os.path.join(here, 'dubrovnik_workbench.py'),
               run_name='__main__')
