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
from collections import namedtuple, defaultdict


__author__ = "Daniel Vorberg"
__copyright__ = "Copyright (c) 2017, Daniel Vorberg"
__license__ = "GPL"


Stroke = list
Point = namedtuple('Point', ['x', 'y', 'pressure', 'duration'])


_PT_PER_INCH = 72
_PT_PER_MM = _PT_PER_INCH / 25.4 # point units (1/72 inch) per mm
_UNIT_PT = _PT_PER_MM * 2.371  # DOTS_PER_INCH / MM_PER_INCH * MM_PER_NCODE_UNIT
                              # see: https://github.com/NeoSmartpen/UWPSDK
DIN_B5 = (176 * _PT_PER_MM, 250 * _PT_PER_MM)
US_LETTER = (216 * _PT_PER_MM, 280 * _PT_PER_MM)

_OFFSET = -6  # this value seems to work optimal
_POINT_FORMAT = "<BHHBBB"
_GAP_FORMAT = "<BBQQIIBB"
_MAX_PRESSURE = 256


NotebookProperties = namedtuple(
    'NotebookProperties',
    ['name', 'size', 'num_pages'])

PLAIN_NOTEBOOK = NotebookProperties("Plain_Notebook", DIN_B5, 72)
POCKET_NOTEBOOK = NotebookProperties("Pocket_Notebook",
                                     (144 * _PT_PER_MM,  83 * _PT_PER_MM), 64)
NCODE_PLAIN_NOTEBOOK = NotebookProperties("Ncode", US_LETTER, 51)
DEFAULT_NOTEBOOK = NotebookProperties("Notebook", US_LETTER, 0)

def position_in_pt(point):
    """ converts a Point to (x,y)-tuple in units of pt = (inch / 72)

    Args:
        point: instance with attributes x, y

    Returns:
        tuple (x, y) of float
    """
    return (point.x + _OFFSET) * _UNIT_PT, (point.y + _OFFSET) * _UNIT_PT


def unknown_notebook():
    """ returns default properties for a unknown notebook

    Warnings:
        throw warning that norebook is unknown
    """
    warnings.warn('format of document not known, '
                  'US Letter is assumed')
    return DEFAULT_NOTEBOOK


paper_format = defaultdict(
    unknown_notebook, {  
        "551": NCODE_PLAIN_NOTEBOOK,
        "604": NCODE_PLAIN_NOTEBOOK,
        "601": POCKET_NOTEBOOK,
        "613": NCODE_PLAIN_NOTEBOOK})


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
    _, (width, height), num_pages = paper_format[name]
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
        notebook_name, *_ = paper_format[name]
        pdf_file = os.path.join(save_dir,
                                f"{notebook_name}_{name}.pdf")
        download_notebook(notebook_path, pdf_file, *args, **kwargs)


def write_ink(ctx, ink, color, pressure_sensitive=False):
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
            for start_point, end_point in zip(stroke[:-1], stroke[1:]):
                ctx.move_to(*position_in_pt(start_point))
                ctx.set_line_width(.1 + start_point.pressure)
                ctx.line_to(*position_in_pt(end_point))
                ctx.stroke()
        else:
            ctx.move_to(*position_in_pt(stroke[0]))
            for point in stroke[1:]:
                ctx.line_to(*position_in_pt(point))
            ctx.stroke()
    ctx.show_page()


def read_penfile(filename):
    with open(filename, "rb") as file:
        data = file.read()
    return parse_pendata(data)


def _parse_point(data):
    duration, x1, y1, x2, y2, pressure = \
        struct.unpack(_POINT_FORMAT, data)
    return Point(x=x1 + x2/100,
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
            stroke[i] = Point(x=(stroke[i-1].x + stroke[i+1].x) / 2,
                              y=stroke[i].y,
                              pressure=stroke[i].pressure,
                              duration=stroke[i].duration)

        distance_prev = abs(stroke[i].y - stroke[i-1].y)
        distance_next = abs(stroke[i].y - stroke[i+1].y)
        distance_neighbors = abs(stroke[i-1].y - stroke[i+1].y)
        if distance_prev > 1 and distance_next > 1 > distance_neighbors:
            stroke[i] = Point(x=stroke[i].x,
                              y=(stroke[i-1].y + stroke[i+1].y) / 2,
                              pressure=stroke[i].pressure,
                              duration=stroke[i].duration)


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
            point = _parse_point(data[i: i+8])
            i += 8
            stroke.append(point)
        _remove_outliners(stroke)
        ink.append(stroke)

    return ink
