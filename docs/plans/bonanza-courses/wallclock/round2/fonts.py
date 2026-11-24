"""The per-facing clock digits (round 2): 4 x 7 glyphs drawn IN each facing's own perspective, 8 lines tall with
the face's 1:2 slope (a 4-px glyph on a face falls exactly one line across its width, so it fits ONE 8-line
block).  Hand-shaped: every 'horizontal' stroke is drawn parallel to the face's top edge (two px, then a line
down on `sw`, up on `se`), verticals stay vertical, and each diagonal is re-drawn rather than sheared.
A glyph must start on an ODD picture column (the face's staircase steps there), so in a word it sits at columns
1 - 4 or 3 - 6.  Row strings, top to bottom: '#' ink, '.' the art under it."""

SW = {   # the LEFT face (+y): falls to the right
    0: ".#.. #.#. #..# #..# #..# #..# .#.# ..#.",
    1: ".... .##. ..#. ..#. ..#. ..#. .##. ..##",
    2: ".#.. #.#. ...# ..#. .#.. #... ##.. ..##",
    3: "##.. ..## ...# .##. ...# #..# .#.# ..#.",
    4: "#... #... #.#. #.#. ###. ..## ..#. ..#.",
    5: "##.. #.## #... ##.. ..#. ...# #..# .##.",
    6: ".#.. #.#. #... ##.. #.#. #..# .#.# ..#.",
    7: "##.. ..## ...# ..#. ..#. .#.. .#.. .#..",
    8: ".#.. #.#. #..# .#.# #.#. #..# .#.# ..#.",
    9: ".#.. #.#. #..# .#.# ..## ...# .#.# ..#.",
}
SE = {   # the RIGHT face (+x): rises to the right
    0: "..#. .#.# #..# #..# #..# #..# #.#. .#..",
    1: "..#. ..#. .##. ..#. ..#. ..#. ..## .#..",
    2: "..#. .#.# #..# ..#. .#.. #... #.## ##..",
    3: "..#. ##.# ...# ..#. .#.# ...# ..#. ##..",
    4: "...# #..# #..# #.## ##.# ...# ...# ....",
    5: "..## ##.. #... #.#. ##.# ...# ..#. ##..",
    6: "..#. .#.. #... #.#. ##.# #..# #.#. .#..",
    7: "..## ##.# ...# ..#. .#.. .#.. .#.. .#..",
    8: "..#. .#.# #..# #.#. .#.# #..# #.#. .#..",
    9: "..#. .#.# #..# #.## .#.# ...# ..#. .#..",
}


def glyph(table, d):
    """-> {(k, r)} ink of digit d, k 0 - 3 across, r 0 - 7 down"""
    return {(k, r) for r, row in enumerate(table[d].split()) for k, ch in enumerate(row) if ch == "#"}
