#!/usr/bin/env python3

"""
    This file is part of Neo Pen.

    Neo Pen (reads and parse data from a Neo Smartpen)
    Copyright (c) 2017 Daniel Vorberg

    Neo Pen is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    Smart Manuscript is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with Neo Pen.  If not, see <http://www.gnu.org/licenses/>.
"""

import os
import struct
import cairocffi as cairo
import warnings
from collections import namedtuple
from itertools import groupby

try:
    import numpy as np
    from scipy import interpolate
except ImportError:
    warnings.warn("install numpy and scipy when you want"
                  "to use the spline option")


__author__ = "Daniel Vorberg"
__copyright__ = "Copyright (c) 2017, Daniel Vorberg"
__license__ = "GPL"


Stroke = list
Dot = namedtuple('Dot', ['x', 'y', 'pressure', 'duration'])


_PT_PER_INCH = 72
_PT_PER_MM = _PT_PER_INCH / 25.4 # point units (1/72 inch) per mm
_UNIT_PT = _PT_PER_MM * 2.371  # DOTS_PER_INCH / MM_PER_INCH * MM_PER_NCODE_UNIT
                               # see: https://github.com/NeoSmartpen/UWPSDK
DIN_B5 = (176 * _PT_PER_MM, 250 * _PT_PER_MM)
US_LETTER = (216 * _PT_PER_MM, 280 * _PT_PER_MM)

_OFFSET = -6  # this value seems to work optimal
_DOT_FORMAT = "<BHHBBB"
_GAP_FORMAT = "<BBQQIIBB"
_MAX_PRESSURE = 256


NotebookProperties = namedtuple(
    'NotebookProperties',
    ['name', 'size', 'num_pages'])

class Notebook:
    """The properties of the notebooks

    The dimensions are taken from:
        https://www.neosmartpen.com/en/notebook/
    and from the document properties of the Ncode pdfs
        https://www.neosmartpen.com/en/ncode-pdf/

    The following list is not complete.
    """

    DEFAULT = NotebookProperties("Notebook", US_LETTER, 0)
    MEMO = NotebookProperties("Memo_Notebook",
                              (83 * _PT_PER_MM,  148 * _PT_PER_MM), 50)
    POCKET = NotebookProperties("Pocket_Notebook",
                                (83 * _PT_PER_MM,  144 * _PT_PER_MM), 64)
    BLANK_PLANNER = NotebookProperties("Blank_Planner",
                                       (150 * _PT_PER_MM,  210 * _PT_PER_MM), 152)
    RING =  NotebookProperties("Ring_Notebook",
                               (150 * _PT_PER_MM,  210 * _PT_PER_MM), 152)
    PROFESSIONAL_MINI = NotebookProperties(
        "Professional_Mini", (90 * _PT_PER_MM,  140 * _PT_PER_MM), 200)
    PROFESSIONAL = NotebookProperties(
        "Professional", (205 * _PT_PER_MM,  140 * _PT_PER_MM), 250)
    # ...
    PLAIN = NotebookProperties("Plain_Notebook", DIN_B5, 72)
    # ...
    NCODE_PLAIN = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_STRING = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_GRID = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_DOT = NotebookProperties("Ncode", US_LETTER, 50)
    # ...


def position_in_pt(dot):
    """ converts a dot to (x,y)-tuple in units of pt = (inch / 72)

    Args:
        dot: instance with attributes x, y

    Returns:
        tuple (x, y) of float
    """
    return (dot.x + _OFFSET) * _UNIT_PT, (dot.y + _OFFSET) * _UNIT_PT

notebook_table = {
        "551": Notebook.NCODE_PLAIN,
        "604": Notebook.NCODE_PLAIN,
        "601": Notebook.POCKET,
        "610": Notebook.PLAIN,
        "611": Notebook.PLAIN,
        "612": Notebook.PLAIN,
        "613": Notebook.NCODE_PLAIN}

def get_notebook_properties(name):
    try:
        notebook = notebook_table[name]
    except KeyError:
        msg = (f'format of document {name} not known, '
               f'US Letter is assumed')
        warnings.warn(msg)
        notebook = Notebook.DEFAULT
    return notebook



def notebooks_in_folder(folder):
    """ yields all paths of notebook directories in a directory
    """
    for foo in os.listdir(folder):
        # TODO(dv): what is this folder level for?
        for notebook in os.listdir(os.path.join(folder, foo)):
            yield os.path.join(folder, foo, notebook)


def pages_in_notebook(path):
    """ yields all paths of pages in a notebook directory
    """
    pages = os.listdir(path)
    for page in sorted(pages, key=int):
        ink = []
        parts = os.listdir(os.path.join(path, page))
        for part in sorted(parts, key=lambda s: int(s[:-4])):
            ink.extend(read_penfile(os.path.join(path, page, part)))
        yield ink


def download_notebook(path, pdf_file, *args, **kwargs):
    """ downloads the notebook and save a pdf of it
    """
    name = os.path.basename(path)
    _, (width, height), num_pages = get_notebook_properties(name)
    surface = cairo.PDFSurface(pdf_file, width, height)
    context = cairo.Context(surface)
    for ink in pages_in_notebook(path):
        write_ink(context, ink, *args, **kwargs)
    surface.finish()


def download_all_notebooks(pen_dir, save_dir, *args, **kwargs):
    """ downloads all notebooks in a folder and save each as pdf
    """
    for notebook_path in notebooks_in_folder(pen_dir):
        name = os.path.basename(notebook_path)
        notebook_name, *_ = get_notebook_properties(name)
        pdf_file = os.path.join(save_dir,
                                f"{notebook_name}_{name}.pdf")
        download_notebook(notebook_path, pdf_file, *args, **kwargs)


def write_ink(ctx, ink, color, pressure_sensitive=False, spline=False):
    """ write ink onto a (cairo) context

    Args:
        ctx: cairo context
        ink (list of Stroke): the pen stroke which are written
    """
    ctx.set_line_cap(cairo.LINE_CAP_ROUND)
    ctx.set_line_join(cairo.LINE_JOIN_BEVEL)
    ctx.set_line_width(1.)
    if color == "blue":
        ctx.set_source_rgb(0, 0, 1)
    elif color == "black":
        ctx.set_source_rgb(0, 0, 0)
    else:
        raise ValueError(f"unknown color {color}")
    for stroke in ink:
        if pressure_sensitive:
            if len(stroke) == 1:
                ctx.move_to(*position_in_pt(stroke[0]))
                ctx.set_line_width(.1 + stroke[0].pressure)
                ctx.line_to(*position_in_pt(stroke[0]))
                ctx.stroke()

            for start_dot, end_dot in zip(stroke[:-1], stroke[1:]):
                ctx.move_to(*position_in_pt(start_dot))
                ctx.set_line_width(.1 + start_dot.pressure)
                ctx.line_to(*position_in_pt(end_dot))
                ctx.stroke()
        else:
            ctx.move_to(*position_in_pt(stroke[0]))
            if (len(stroke) == 1):
                ctx.line_to(*position_in_pt(stroke[0]))
            else:
                if len(stroke) < 4 or not spline:
                    for dot in stroke[1:]:
                        ctx.line_to(*position_in_pt(dot))
                else:
                    dots_in_pt = np.array([position_in_pt(dot) for dot in stroke])
                    spline, u = interpolate.splprep(
                        dots_in_pt.transpose(), k=3, s=len(dots_in_pt) / 20)
                    for knot in 3 * list(u[2:-2]) + 4 * [u[1], u[-2]]:
                        spline = interpolate.insert(knot, spline)
                    x, y = spline[1]
                    ctx.move_to(x[0], y[0])
                    for i in range(len(x)//4 - 1):
                        ctx.curve_to(x[4*i+1], y[4*i+1],
                                     x[4*i+2], y[4*i+2],
                                     x[4*i+3], y[4*i+3])
            ctx.stroke()
    ctx.show_page()


def read_penfile(filename):
    with open(filename, "rb") as file:
        data = file.read()
    return parse_pendata(data)


def _parse_dot(data):
    duration, x1, y1, x2, y2, pressure = \
        struct.unpack(_DOT_FORMAT, data)
    return Dot(x=x1 + x2/100,
               y=y1 + y2/100,
               pressure=pressure / _MAX_PRESSURE,
               duration=duration)


def _parse_gap(data):
    a, b, time_start, time_end, stroke_len, c, d, e = \
        struct.unpack(_GAP_FORMAT, data)
    #print("\n", a, b, "  ", stroke_len, c, d, e)
    if a==49:  # Todo(dv): I have no clue what this data packet could mean
        return None
    return stroke_len

def _remove_outliners(stroke):
    for i in range(1, len(stroke)-1):
        distance_prev = abs(stroke[i].x - stroke[i-1].x)
        distance_next = abs(stroke[i].x - stroke[i+1].x)
        distance_neighbors = abs(stroke[i-1].x - stroke[i+1].x)
        if distance_prev > 1 and distance_next > 1 > distance_neighbors:
            stroke[i] = Dot(x=(stroke[i-1].x + stroke[i+1].x) / 2,
                            y=stroke[i].y,
                            pressure=stroke[i].pressure,
                            duration=stroke[i].duration)

        distance_prev = abs(stroke[i].y - stroke[i-1].y)
        distance_next = abs(stroke[i].y - stroke[i+1].y)
        distance_neighbors = abs(stroke[i-1].y - stroke[i+1].y)
        if distance_prev > 1 and distance_next > 1 > distance_neighbors:
            stroke[i] = Dot(x=stroke[i].x,
                            y=(stroke[i-1].y + stroke[i+1].y) / 2,
                            pressure=stroke[i].pressure,
                            duration=stroke[i].duration)

def _remove_duplicates(stroke):
    new_stroke = []
    for position, same_dots in groupby(stroke, lambda dot: (dot.x, dot.y)):
        same_dots = list(same_dots)
        dot = Dot(*position,
            pressure = max(dot.pressure for dot in same_dots),
            duration = sum(dot.duration for dot in same_dots))
        new_stroke.append(dot)
    stroke[:] = new_stroke



def parse_pendata(data):
    i = 0
    ink = []

    while True:
        stroke_len = _parse_gap(data[i: i + 28])
        if not stroke_len:
            break
        i += 28
        stroke = []
        for _ in range(stroke_len):
            dot = _parse_dot(data[i: i+8])
            i += 8
            stroke.append(dot)
        _remove_outliners(stroke)
        _remove_duplicates(stroke)
        ink.append(stroke)

    return ink
