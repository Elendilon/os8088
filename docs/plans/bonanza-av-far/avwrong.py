"""SPEC.md 130.29.12 research: item 15's WRONG-HIDE (av_wrong, 130.29.7) with A's far lists in the model - the
front of every listed V extended by its far cells (whole cells, read from the part) - against today's model.
usage: avwrong.py course farpickle"""
import sys, os, pickle
sys.path.insert(0, "tools")
import bbcourse as B

course = sys.argv[1]
far = pickle.load(open(sys.argv[2], "rb"))["far"]
c = B.compile_course(open("apps/bonanza/courses/%s.bbc" % course).read(), "apps/bonanza/courses/%s.bbc" % course)
nb, nw, worst, npos = B.av_wrong(c)
print("%s today: WRONG-HIDE %d of %d ball pixels (%.4f%%) over %d positions, worst %s" % (
    course, nw, nb, 100.0 * nw / max(nb, 1), npos, worst))
_front = B.AGrid.front


def front(self, wx, wy, depth=None):
    out = _front(self, wx, wy, depth)
    for i, j in far.get((wx, wy), []):
        b = self.raw(wx + i, wy + j)
        H, X, Y, kr, kl = self.geom(b, wx + wy + i + j, wx + i - wy - j)
        out += [(H, X, Y, kr, True, False), (H, X, Y, kl, False, False)]
    return out


B.AGrid.front = front
nb, nw, worst, npos = B.av_wrong(c)
print("%s far:   WRONG-HIDE %d of %d ball pixels (%.4f%%) over %d positions, worst %s (the bound %.2f%%)" % (
    course, nw, nb, 100.0 * nw / max(nb, 1), npos, worst, 100 * B.OCC_WRONG_MAX))
