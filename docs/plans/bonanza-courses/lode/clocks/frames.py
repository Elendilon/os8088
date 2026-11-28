# LODESTONE GORGE's clock CONCEPTS (course 6; the brief is the course guide's G23, ../../mill/clocks/frames.py
# the precedent, ../../clockkit.py the kit that compiles and draws them).  One object a concept, a variant a
# clock: the course's four clocks are the HEADLAND (start), the PEN (the flume's foot), the TURN (the bridge's
# end) and the island's apron by the VAULT, and what changes between them says how far down the quarry the
# player is.  Palette 1's inks (cyan, magenta, white on black); on the Hercules cyan and magenta are one grey
# checker, so every form is carried by white and black as well.
#
#   cart   An ORE CART on a stub of track, the digits painted on its side; it FILLS down the course (empty, a
#          few lumps, half full, heaped and glinting).  INSTALLED: tools/bbcourse.py's `cart0` .. `cart3`
#          (`_clock_cart`, SPEC.md 137.18.5.2) - named here, drawn there.  At a clock's natural spot the cart
#          stands on a timber TRESTLE, clear of the guard rails in front of it.
#   ground The same four frames with `digits 0 16`: the cart two block rows down, its track laid on the tile
#          (no trestle).  Lower, and half behind the rails.
#   davy   A MINER'S SAFETY LAMP hung from a timber gallows, the digits on its lit glass; what lies at the
#          post's foot is the place: a PICK at the headland, a BUCKET at the pen, a HORSESHOE at the turn, a
#          LODESTONE crystal on the island.  Scratch: DRAW below, in this process only.
CONCEPTS = {
    "cart": [("cart0", ""), ("cart1", ""), ("cart2", ""), ("cart3", "")],
    "ground": [("cart0", "digits 0 16"), ("cart1", "digits 0 16"), ("cart2", "digits 0 16"), ("cart3", "digits 0 16")],
    "davy": [("davy0", ""), ("davy1", ""), ("davy2", ""), ("davy3", "")],
}
BASE = "cart"

_FOOT = (("......KK.", ".KKKKKWWK", "KWWWKKKK.", ".KK.KMK..", "....KMK..", "...KMK...", "...KMK...", "..KMK...."),   # a pick
         (".KKKKKK.", "K.KKKK.K", "KWWWWCCK", "KWWWCCCK", ".KWWCCK.", ".KWWCCK.", "..KKKK.."),                       # a bucket
         ("KKK.KKK", "KWK.KWK", "KMK.KMK", "KMK.KMK", "KMKKKMK", "KMMMMMK", ".KMMMK.", "..KKK.."),                    # a horseshoe
         ("...K....", "..KWK.K.", "..KWMKWK", ".KWMMKMK", ".KWMMMDK", "KWMMMDDK", "KWMMDDDK", ".KKKKKK."))            # a crystal


def _clock_davy(B, p, x0, y0, tops, pos):
    BLK, CYN, MAG, WHT = B.BLK, B.CYN, B.MAG, B.WHT
    a = B._ClockArt(p, x0, y0)
    cx, cy, fx, fy, n = a.cx, a.cy, a.fx, a.fy, a.n
    wx0, wx1, wy0, wy1 = a.win
    hw = 4 * n + 2                                  # the glass's half width
    px = wx0 - 9                                    # the gallows post's left edge
    top = wy0 - 15
    B._clock_top_shadow(a, 2, 11.0, 3.6)
    a.column(px, top, cy - 2)
    for y in range(cy - 3, cy):                     # its footing
        for x in range(px - 2, px + 6):
            a.put(x, y, BLK if y == cy - 1 or x in (px - 2, px + 5) else MAG)
    for x in range(px - 2, fx + 6):                 # the beam
        for k, ink in enumerate((BLK, WHT, MAG, BLK)):
            a.put(x, top + k, ink)
    for k in range(7):                              # the brace
        a.put(px + 4 + k, top + 10 - k, BLK)
        a.put(px + 4 + k, top + 9 - k, WHT)
    for y in range(top + 4, wy0 - 8):               # the hook
        a.put(fx - 1, y, BLK)
        a.put(fx, y, WHT)
    cap0, gz0, gl0, gl1, base1 = wy0 - 8, wy0 - 4, wy0 - 1, wy1 + 1, wy1 + 5
    lamp = set()
    for y in range(cap0, base1 + 1):
        if y < gz0:
            h = 3 + (hw - 4) * (y - cap0 + 1) / 4.0
        elif y < gl0:
            h = hw - 2
        elif y <= gl1:
            h = hw
        else:
            h = hw - 1 - (y - gl1 - 1)
        for x in range(int(fx - h), int(fx + h)):
            lamp.add((x, y))

    def ink(x, y):
        if gl0 <= y <= gl1:
            if x in (wx0 - 1, wx1 + 1):
                return BLK                          # the glass's two guard bars
            return WHT
        if gz0 <= y < gl0:
            return CYN if (x + y) & 1 else BLK      # the gauze
        if x < fx - 4:
            return WHT
        return MAG if (x < fx + 4 or (x + y) & 1) else BLK
    a.blob(lamp, ink)
    for (dx, dy) in ((-hw - 3, -3), (-hw - 4, 0), (-hw - 3, 3), (hw + 2, -3), (hw + 3, 0), (hw + 2, 3)):   # its glow
        a.put(fx + dx, fy + dy, WHT, "shadow")
        a.put(fx + dx + (1 if dx > 0 else -1), fy + dy, WHT, "shadow")
    rows = _FOOT[pos]
    a.pattern(rows, cx + 4, cy - len(rows) + 1)
    return a.done(tops)


DRAW = {"davy%d" % k: (lambda q: lambda B, p, x0, y0, tops: _clock_davy(B, p, x0, y0, tops, q))(k)
        for k in (0, 1, 2, 3)}
