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

import xml.etree.cElementTree as ET
from xml.dom import minidom


def write(ink, filename):
    """Save strokes to a inkml file

    Reference:
        https://www.w3.org/TR/InkML/
    Args:
        ink: list of strokes where each stroke is a list of (x, y) tuples
             or an array[len, 2]
        filename (str): filename to save (should end on ".inkml")

    Returns:
        None
    """
    root = ET.Element("ink")
    root.set('xmlns', 'http://www.w3.org/2003/InkML')
    root.append(ET.Comment("created by neo pen (github.com/antemons/neo-pen)"))

    for stroke in ink:
        trace = ET.SubElement(root, "trace")
        for dot in stroke:
            if trace.text is None:
                trace.text = ("{} {}".format(*dot))
            else:
                trace.text += (", {} {}".format(*dot))

    tree = ET.ElementTree(root)
    with open(filename, "w") as f:
        f.write(minidom.parseString(ET.tostring(root)).toprettyxml())

if __name__ == "__main__":
    ink = [
        [[0, 0], [0, 1], [2,4]],
        [[4, 2], [1, 1]]]
    write(ink, "test.inkml")
