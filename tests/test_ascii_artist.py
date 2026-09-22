# test_ascii_artist.py
# __all__: 0

__all__ = []

import ascii_artist


def test_generate_square():
    assert ascii_artist.generate_square(2) == "**\n**"


def test_generate_triangle():
    assert ascii_artist.generate_triangle(3) == "*\n**\n***"


def test_generate_diamond():
    assert ascii_artist.generate_diamond(2) == " *\n***\n *"
