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
NotebookProperties = namedtuple(
    'NotebookProperties',
    ['name', 'size'])

_UNIT_PT = 72 * 8.5 / (1820 / 20)
_POINT_FORMAT = "<BHHBBB"
_GAP_FORMAT = "<BBQQIIBB"
_MAX_PRESSURE = 256


def position_in_pt(point):
    """ converts a Point to (x,y)-tuple in units of  pt = (inch / 72)

    Args:
        point: instance with attributes x, y

    Returns:
        tuple (x, y) of float
    """
    return point.x * _UNIT_PT, point.y * _UNIT_PT


def unknown_notebook():
    """ returns default properties for a unknown notebook

    Warnings:
        throw warning that norebook is unknown
    """
    warnings.warn("format of document not known {}, "
                  "US Letter is assumed")
    return NotebookProperties(
        name="unknown notebook",
        size=(72 * 8.5, 72 * 11))


paper_format = defaultdict(
    unknown_notebook,
    {   # (width, height) in pt
        "551": NotebookProperties(
            "Letter_blanko", (72 * 8.5, 72 * 11)),
        "604": NotebookProperties(
            "Letter_blanko", (72 * 8.5, 72 * 11)),
        "601": NotebookProperties(
            "Pocket_Notes", (72 * 3.3, 72 * 5.8)),
        "613": NotebookProperties(
            "Letter_blanko", (72 * 8.5, 72 * 11))})


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
        yield read_penfile(
           os.path.join(path, page, "0.pen"))


def download_notebook(path, pdf_file):
    """ downloads the notebook and save a pdf of it
    """
    name = os.path.basename(path)
    _, (width, height) = paper_format[name]
    surface = cairo.PDFSurface(pdf_file, width, height)
    context = cairo.Context(surface)
    for ink in pages_in_notebook(path):
        write_ink(context, ink)
    surface.finish()


def download_all_notebooks(pen_dir, save_dir):
    """ downloads all notebooks in a folder and save each as pdf
    """
    for notebook_path in notebooks_in_folder(pen_dir):
        name = os.path.basename(notebook_path)
        notebook_name, _ = paper_format[name]
        pdf_file = os.path.join(save_dir,
                                f"{notebook_name}_{name}.pdf")
        download_notebook(notebook_path, pdf_file)


def write_ink(ctx, ink):
    """ write ink onto a (cairo) context

    Args:
        ctx: cairo context
        ink (list of Stroke): the pen stroke which are written
    """
    ctx.set_line_cap(1)
    ctx.set_line_join(0)
    ctx.set_source_rgb(0, 0, 1)

    for stroke in ink:
        for start_point, end_point in zip(stroke[:-1], stroke[1:]):
            ctx.move_to(*position_in_pt(start_point))
            ctx.set_line_width(.1 + start_point.pressure)
            ctx.line_to(*position_in_pt(end_point))
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
    a, b, time_start, time_end, stroke_len, c, d, e, = \
        struct.unpack(_GAP_FORMAT, data)
    #print(a, b, c, d, e)
    return stroke_len


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
        ink.append(stroke)

    return ink

