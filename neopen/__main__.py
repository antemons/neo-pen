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

import argparse
from . import pen

__author__ = "Daniel Vorberg"
__copyright__ = "Copyright (c) 2017, Daniel Vorberg"
__license__ = "GPL"


def main():
    parser = argparse.ArgumentParser(description='Neo Pen')
    parser.add_argument('pen_dir', type=str,
                        help='path to a file')
    parser.add_argument('save_dir', type=str,
                        help='path to a file')
    parser.add_argument("--color", default="black", help="black|blue")
    parser.add_argument("--pressure_sensitiv", type=bool)
    parser.add_argument("--spline", type=bool)
    args = parser.parse_args()


    pen.download_all_notebooks(
        args.pen_dir,
        args.save_dir,
        color=args.color)


if __name__ == "__main__":
    main()
