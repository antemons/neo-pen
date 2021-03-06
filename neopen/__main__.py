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
import os.path
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
    parser.add_argument("--pressure_sensitive", type=bool)
    feature_parser = parser.add_mutually_exclusive_group(required=False)

    feature_parser.add_argument('--spline', dest='spline', action='store_true')
    feature_parser.add_argument('--no-spline', dest='spline', action='store_false')
    parser.set_defaults(spline=False)
    parser.add_argument("--type", default="pdf", help="pdf|inkml")
    parser.add_argument('--list', dest='list', action='store_true')
    parser.add_argument("--delete", default="", help='delete notebook with given name from pen')
    parser.set_defaults(list=False)
    args = parser.parse_args()

    data_path = os.path.join(args.pen_dir, 'Data')
    pen_dir = data_path if os.path.isdir(data_path) else args.pen_dir

    if args.list:
        pen.list_all_notebooks(pen_dir)
    elif args.delete:
        pen.delete_notebook(pen_dir, args.delete)
    else:
        pen.download_all_notebooks(
            pen_dir,
            args.save_dir,
            color=args.color,
            pressure_sensitive=args.pressure_sensitive,
            as_spline=args.spline,
            file_type=args.type)


if __name__ == "__main__":
    main()
