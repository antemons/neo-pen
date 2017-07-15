#!/usr/bin/env python3

"""
    This file is part of Neo Pen.

    Neo Pen (reads and parse data from Neo Smartpen)
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
    along with Smart Manuscript.  If not, see <http://www.gnu.org/licenses/>.
"""


from collections import namedtuple
import struct

__author__ = "Daniel Vorberg"
__copyright__ = "Copyright (c) 2017, Daniel Vorberg"
__license__ = "GPL"

__all__ = ["read_penfile"]


Stroke = list
Point = namedtuple('Point', ['x', 'y', 'pressure', 'duration'])


def read_penfile(filename):
    with open(filename, "rb") as file:
        data = file.read()
    return parse_pendata(data)


def _parse_point(data):
    _POINT_FORMAT = "<BHHBBB"
    duration, x1, y1, x2, y2, pressure = \
        struct.unpack(_POINT_FORMAT, data)
    return Point(x=x1 + x2/100,
                 y=y1 + y2/100,
                 pressure=pressure,
                 duration=duration)

def _parse_gap(data):
    _GAP_FORMAT = "<BBQQIIBB"
    _, _, time_start, time_end, stroke_len, _, _, _, = \
        struct.unpack(_GAP_FORMAT, data)
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


def main():
    import numpy as np
    import pylab as plt
    import argparse

    parser = argparse.ArgumentParser(description='Neo Pen')
    parser.add_argument('filename', type=str,
                        help='path to a file')
    args = parser.parse_args()

    ink = read_penfile(args.filename)
    for stroke in ink:
        pos = np.array([[p.x, -p.y] for p in stroke])
        plt.plot(*pos.transpose())

    plt.axes().set_aspect('equal')
    plt.show()
    
if __name__ == "__main__":
    main()
        
    
    

