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

from . import inkml

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
                              (83 * _PT_PER_MM, 148 * _PT_PER_MM), 50)
    POCKET = NotebookProperties("Pocket_Notebook",
                                (83 * _PT_PER_MM, 144 * _PT_PER_MM), 64)
    BLANK_PLANNER = NotebookProperties("Blank_Planner",
                                       (150 * _PT_PER_MM, 210 * _PT_PER_MM), 152)
    RING =  NotebookProperties("Ring_Notebook",
                               (150 * _PT_PER_MM, 210 * _PT_PER_MM), 152)
    PROFESSIONAL_MINI = NotebookProperties(
        "Professional_Mini", (90 * _PT_PER_MM, 140 * _PT_PER_MM), 200)
    PROFESSIONAL = NotebookProperties(
        "Professional", (205 * _PT_PER_MM, 140 * _PT_PER_MM), 250)
    # ...
    PLAIN = NotebookProperties("Plain_Notebook", DIN_B5, 72)
    # ...
    NCODE_PLAIN = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_STRING = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_GRID = NotebookProperties("Ncode", US_LETTER, 50)
    NCODE_DOT = NotebookProperties("Ncode", US_LETTER, 50)
    # ...


def position_in_pt(dot, with_pressure=False):
    """ converts a dot to (x,y)-tuple in units of pt = (inch / 72)

    Args:
        dot: instance with attributes x, y

    Returns:
        tuple (x, y) of float
    """
    if not with_pressure:
        return (dot.x + _OFFSET) * _UNIT_PT, (dot.y + _OFFSET) * _UNIT_PT
    else:
        return (dot.x + _OFFSET) * _UNIT_PT, (dot.y + _OFFSET) * _UNIT_PT, dot.pressure


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


def download_notebook(path, filename, *_, file_type, **kwargs):
    """ downloads the notebook and save a pdf of it
    """
    if file_type == "pdf":
        name = os.path.basename(path)
        _, (width, height), num_pages = get_notebook_properties(name)
        surface = cairo.PDFSurface(filename, width, height)
        context = cairo.Context(surface)
        for ink in pages_in_notebook(path):
            write_ink(context, ink, **kwargs)
        surface.finish()
    elif file_type == "inkml":
        for page_num, ink in enumerate(pages_in_notebook(path)):
            inkml.write(ink, filename + " " + str(page_num))
    else:
        raise ValueError("file type must be either pdf or inkml")


def download_all_notebooks(pen_dir, save_dir, *_, file_type, **kwargs):
    """ downloads all notebooks in a folder and save each as pdf
    """
    for notebook_path in notebooks_in_folder(pen_dir):
        name = os.path.basename(notebook_path)
        notebook_name, *_ = get_notebook_properties(name)
        filename = os.path.join(save_dir,
                                f"{notebook_name}_{name}.{file_type}")
        download_notebook(notebook_path, filename, file_type=file_type, **kwargs)


def stroke_to_spline(stroke, smoothness = 1/200, preserve_points=False):
    if len(stroke) == 1:
        ret = "dot", np.array(stroke)
    elif len(stroke) == 2:
        ret = "line", np.array(stroke)
    elif len(stroke) == 3:
        (t, c, k), u = interpolate.splprep(np.array(stroke).transpose(), u=None, k=2, s=0)
        c = np.array(c)
        new_c = np.stack([c[:, 0],
                          1/3 * c[:, 0] + 2/3 * c[:, 1],
                          2/3 * c[:, 1] + 1/3 * c[:, 2],
                          c[:, 2]])
        new_c = list(new_c.transpose())
        new_t = 4 * [0] + 4 * [1]
        spline = (new_t, new_c, 3)
        for knot in 4 * [u[1]]:
            spline = interpolate.insert(knot, spline)
        control_points = np.array(spline[1]).transpose()
        control_points = control_points[:max(len(control_points)-4, 4)]
        ret = "curve" , control_points
    else:
        spline, u = interpolate.splprep(
            np.array(stroke).transpose(), k=3, s=len(stroke) * smoothness)
        if preserve_points:
            new_knots = 3 * list(u[2:-2]) + 4 * [u[1], u[-2]]
        else:
            new_knots = 3 * list(spline[0][4:-4])
        for knot in new_knots:
            spline = interpolate.insert(knot, spline)
        control_points = np.array(spline[1]).transpose()
        control_points = control_points[:max(len(control_points)-4, 4)]
        ret = "curve", control_points
    return ret


def write_ink(ctx, ink, color, pressure_sensitive=False, as_spline=False):
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
    if as_spline:
        if not pressure_sensitive:
            for stroke in ink:
                stroke_in_pt = np.array([position_in_pt(dot) for dot in stroke])
                spline_type, points = stroke_to_spline(stroke_in_pt)
                ctx.move_to(*points[0])
                if spline_type == "dot":
                    ctx.line_to(*points[0])
                elif spline_type == "line":
                    ctx.line_to(*points[1])
                elif spline_type == "curve":
                    for control_1, control_2, knot in zip(points[1:][::4],
                                                          points[2:][::4],
                                                          points[3:][::4]):
                        ctx.curve_to(*control_1, *control_2, *knot)
                else:
                    raise ValueError("unknown spline type")
                ctx.stroke()
        else:
            for stroke in ink:
                stroke_in_pt = np.array([position_in_pt(dot, with_pressure=True)
                                         for dot in stroke])
                spline_type, tmp = stroke_to_spline(stroke_in_pt)
                points, pressure = tmp[:, :2], tmp[:, 2]

                if spline_type == "dot":
                    ctx.move_to(*points[0])
                    ctx.line_to(*points[0])
                    ctx.set_line_width(.1 + np.mean(pressure))
                elif spline_type == "line":
                    ctx.move_to(*points[0])
                    ctx.line_to(*points[1])
                    ctx.set_line_width(.1 + np.mean(pressure))
                elif spline_type == "curve":
                    for i, _ in enumerate(points[::4]):
                        knot_0, control_0, control_1, knot_1 = points[4*i: 4*(i+1)]
                        mean_pressure = np.mean(pressure[4*i: 4*(i+1)])
                        ctx.move_to(*knot_0)
                        ctx.set_line_width(.1 + mean_pressure)
                        ctx.curve_to(*control_0, *control_1, *knot_1)
                        ctx.stroke()
                else:
                    raise ValueError("unknown spline type")
                ctx.stroke()
    else:
        for stroke in ink:
            ctx.move_to(*position_in_pt(stroke[0]))
            if len(stroke) == 1:
                if pressure_sensitive:
                    ctx.set_line_width(.1 + stroke[0].pressure)
                ctx.line_to(*position_in_pt(stroke[0]))
            else:
                for dot, previous_dot in zip(stroke[1:], stroke):
                    if pressure_sensitive:
                        ctx.set_line_width(.1 +
                            (dot.pressure + previous_dot.pressure) / 2)
                    ctx.line_to(*position_in_pt(dot))
                    if pressure_sensitive:
                        ctx.stroke()
                        ctx.move_to(*position_in_pt(dot))
            if not pressure_sensitive:
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
    if a == 49:  # Todo(dv): I have no clue what this data packet could mean
        return None
    return stroke_len

def _remove_outliners(stroke, distance=1):
    """Replaces outliners from a stroke by the mid position of neighbors

    Args:
        stroke: list of Dot
        distance (float): the point is replaced when the previous
            and next point is more than distance away

    Returns:
        None (the argument stroke is changed)

    Example:
        >>> stroke = [Dot(0, 0, 1, 1), Dot(0, .1, 3, 1),
        ...           Dot(0, 10, 1, 1), Dot(.1, .3, 1, 1)]
        >>> _remove_outliners(stroke)
        >>> for dot in stroke:
        ...     print(dot.x, dot.y, dot.pressure, dot.duration)
        0 0 1 1
        0 0.1 3 1
        0 0.2 1 1
        0.1 0.3 1 1
    """
    for i in range(1, len(stroke)-1):
        distance_prev = abs(stroke[i].x - stroke[i-1].x)
        distance_next = abs(stroke[i].x - stroke[i+1].x)
        distance_neighbors = abs(stroke[i-1].x - stroke[i+1].x)
        if (distance_prev > distance and
                distance_next > distance > distance_neighbors):
            stroke[i] = Dot(x=(stroke[i-1].x + stroke[i+1].x) / 2,
                            y=stroke[i].y,
                            pressure=stroke[i].pressure,
                            duration=stroke[i].duration)

        distance_prev = abs(stroke[i].y - stroke[i-1].y)
        distance_next = abs(stroke[i].y - stroke[i+1].y)
        distance_neighbors = abs(stroke[i-1].y - stroke[i+1].y)
        if (distance_prev > distance and
                distance_next > distance > distance_neighbors):
            stroke[i] = Dot(x=stroke[i].x,
                            y=(stroke[i-1].y + stroke[i+1].y) / 2,
                            pressure=stroke[i].pressure,
                            duration=stroke[i].duration)

def _remove_duplicates(stroke):
    """Removes all duplicated dots from a stroke.

    Hereby cumulate the total duration and choose the maximal pressure

    Args:
        stroke: a list of Dot

    Returns:
        None (the argument is altered)

    Example:
        >>> stroke = [Dot(0, 0, 1, 1), Dot(0, 1, 3, 1),
        ...           Dot(0, 1, 1, 1), Dot(1, 1, 1, 1)]
        >>> _remove_duplicates(stroke)
        >>> for dot in stroke:
        ...     print(dot.x, dot.y, dot.pressure, dot.duration)
        0 0 1 1
        0 1 3 2
        1 1 1 1
    """
    new_stroke = []
    for position, same_dots in groupby(stroke, lambda dot: (dot.x, dot.y)):
        same_dots = list(same_dots)
        dot = Dot(*position,
                  pressure=max(dot.pressure for dot in same_dots),
                  duration=sum(dot.duration for dot in same_dots))
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
