# This file is part of CairoSVG
# Copyright © 2010-2015 Kozea
#
# This library is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU Lesser General Public License for more
# details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with CairoSVG.  If not, see <http://www.gnu.org/licenses/>.

"""
Surface helpers.

"""

from math import cos, sin, tan, atan2, radians
import re

from . import cairo
from .units import size


class PointError(Exception):
    """Exception raised when parsing a point fails."""


def distance(x1, y1, x2, y2):
    """Get the distance between two points."""
    return ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5


def paint(value):
    """Extract from value an uri and a color.

    See http://www.w3.org/TR/SVG/painting.html#SpecifyingPaint

    """
    if not value:
        return None, None

    value = value.strip()

    if value.startswith('url'):
        source = urls(value.split(')')[0])[0][1:]
        color = value.split(')', 1)[-1].strip() or None
    else:
        source = None
        color = value.strip() or None

    return (source, color)


def node_format(surface, node):
    """Return ``(width, height, viewbox)`` of ``node``."""
    width = size(surface, node.get('width'), 'x')
    height = size(surface, node.get('height'), 'y')
    viewbox = node.get('viewBox')
    if viewbox:
        viewbox = re.sub('[ \n\r\t,]+', ' ', viewbox)
        viewbox = tuple(float(position) for position in viewbox.split())
        width = width or viewbox[2]
        height = height or viewbox[3]
    return width, height, viewbox


def normalize(string=None):
    """Normalize a string corresponding to an array of various values."""
    if not string:
        return ''

    string = string.replace('E', 'e')
    string = re.sub('(?<!e)-', ' -', string)
    string = re.sub('[ \n\r\t,]+', ' ', string)
    string = re.sub(r'(\.[0-9-]+)(?=\.)', r'\1 ', string)
    return string.strip()


def point(surface, string=None):
    """Return ``(x, y, trailing_text)`` from ``string``."""
    if not string:
        return (0, 0, '')

    try:
        x, y, string = (string.strip() + ' ').split(' ', 2)
    except ValueError:
        raise PointError(
            'The point cannot be found in string {}'.format(string))

    return size(surface, x, 'x'), size(surface, y, 'y'), string


def point_angle(cx, cy, px, py):
    """Return angle between x axis and point knowing given center."""
    return atan2(py - cy, px - cx)


def preserve_ratio(surface, node):
    """Manage the ratio preservation."""
    if node.tag == 'marker':
        width = size(surface, node.get('markerWidth', '3'), 'x')
        height = size(surface, node.get('markerHeight', '3'), 'y')
        scale_x = 1
        scale_y = 1
        translate_x = -size(surface, node.get('refX'))
        translate_y = -size(surface, node.get('refY'))
    elif node.tag in ('svg', 'image'):
        width, height, _ = node_format(surface, node)
        scale_x = width / node.image_width
        scale_y = height / node.image_height

        align = node.get('preserveAspectRatio', 'xMidYMid').split(' ')[0]
        if align == 'none':
            return scale_x, scale_y, 0, 0
        else:
            mos_properties = node.get('preserveAspectRatio', '').split()
            meet_or_slice = (
                mos_properties[1] if len(mos_properties) > 1 else None)
            if meet_or_slice == 'slice':
                scale_value = max(scale_x, scale_y)
            else:
                scale_value = min(scale_x, scale_y)
            scale_x = scale_y = scale_value

            x_position = align[1:4].lower()
            y_position = align[5:].lower()

            if x_position == 'min':
                translate_x = 0

            if y_position == 'min':
                translate_y = 0

            if x_position == 'mid':
                translate_x = (width / scale_x - node.image_width) / 2.

            if y_position == 'mid':
                translate_y = (height / scale_y - node.image_height) / 2.

            if x_position == 'max':
                translate_x = width / scale_x - node.image_width

            if y_position == 'max':
                translate_y = height / scale_y - node.image_height

    return scale_x, scale_y, translate_x, translate_y


def quadratic_points(x1, y1, x2, y2, x3, y3):
    """Return the quadratic points to create quadratic curves."""
    xq1 = x2 * 2 / 3 + x1 / 3
    yq1 = y2 * 2 / 3 + y1 / 3
    xq2 = x2 * 2 / 3 + x3 / 3
    yq2 = y2 * 2 / 3 + y3 / 3
    return xq1, yq1, xq2, yq2, x3, y3


def rotate(x, y, angle):
    """Rotate a point of an angle around the origin point."""
    return x * cos(angle) - y * sin(angle), y * cos(angle) + x * sin(angle)


def transform(surface, string):
    """Update ``surface`` matrix according to transformation ``string``."""
    if not string:
        return

    # TODO: use a real parser
    transformations = string.split(')')
    matrix = cairo.Matrix()
    for transformation in transformations:
        for ttype in (
                'scale', 'translate', 'matrix', 'rotate', 'skewX', 'skewY'):
            if ttype in transformation:
                transformation = transformation.replace(ttype, '')
                transformation = transformation.replace('(', '')
                transformation = normalize(transformation).strip() + ' '
                values = []
                while transformation:
                    value, transformation = transformation.split(' ', 1)
                    # TODO: manage the x/y sizes here
                    values.append(size(surface, value))
                if ttype == 'matrix':
                    matrix = cairo.Matrix(*values).multiply(matrix)
                elif ttype == 'rotate':
                    angle = radians(float(values.pop(0)))
                    x, y = values or (0, 0)
                    matrix.translate(x, y)
                    matrix.rotate(angle)
                    matrix.translate(-x, -y)
                elif ttype == 'skewX':
                    tangent = tan(radians(float(values[0])))
                    matrix = (
                        cairo.Matrix(1, 0, tangent, 1, 0, 0).multiply(matrix))
                elif ttype == 'skewY':
                    tangent = tan(radians(float(values[0])))
                    matrix = (
                        cairo.Matrix(1, tangent, 0, 1, 0, 0).multiply(matrix))
                elif ttype == 'translate':
                    if len(values) == 1:
                        values += (0,)
                    matrix.translate(*values)
                elif ttype == 'scale':
                    if len(values) == 1:
                        values = 2 * values
                    matrix.scale(*values)
    apply_matrix_transform(surface, matrix)


def apply_matrix_transform(surface, matrix):
    """Apply a ``matrix`` to ``surface``.

    When the matrix is not invertible, this function clips the context to an
    empty path instead of raising an exception.

    """
    try:
        matrix.invert()
    except cairo.Error:
        # Matrix not invertible, clip the surface to an empty path
        active_path = surface.context.copy_path()
        surface.context.new_path()
        surface.context.clip()
        surface.context.append_path(active_path)
    else:
        matrix.invert()
        surface.context.transform(matrix)


def urls(string):
    """Parse a comma-separated list of ``url()`` strings."""
    if not string:
        return []

    # TODO: use a real parser and put this in a separate module
    string = string.strip()
    if string.startswith('url'):
        string = string[3:]
    return [
        link.strip('() \'"') for link in string.rsplit(')')[0].split(',')
        if link.strip('() \'"')]


def rect(string):
    """Parse the rect value of a clip."""
    if not string:
        return []

    # TODO: use a real parser
    string = string.strip()
    if string.startswith('rect'):
        return string[4:].strip('() ').split(',')
    else:
        return []


def rotations(node):
    """Retrieves the original rotations of a `text` or `tspan` node."""
    if 'rotate' in node:
        original_rotate = [
            float(i) for i in normalize(node['rotate']).strip().split(' ')]
        return original_rotate
    return []


def pop_rotation(node, original_rotate, rotate):
    """Removes the rotations of a node that are already used."""
    node['rotate'] = ' '.join(
        str(rotate.pop(0) if rotate else original_rotate[-1])
        for i in range(len(node.text)))


def zip_letters(xl, yl, dxl, dyl, rl, word):
    """Returns a list with the current letter's positions (x, y and rotation).

    E.g.: for letter 'L' with positions x = 10, y = 20 and rotation = 30:
    >>> [[10, 20, 30], 'L']

    Store the last value of each position and pop the first one in order to
    avoid setting an x,y or rotation value that have already been used.

    """
    return (
        ([pl.pop(0) if pl else None for pl in (xl, yl, dxl, dyl, rl)], char)
        for char in word)


def flatten(node):
    """Flatten the text of a node and its children."""
    flattened_text = [node.text or '']
    for child in list(node):
        flattened_text.append(flatten(child))
        flattened_text.append(child.tail or '')
        node.remove(child)
    return ''.join(flattened_text)
