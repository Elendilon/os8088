"""SPEC.md 130.29.12 research: A's dataset as stored - each listed VOID cell's byte +1 = 1 + its list's offset in a
LISTS blob (count, then an (i << 4 | j) byte an entry; lists shared), the blob appended to the world part's
stored form - packed LZB as os88pkg packs a part, against the part without them.  The AV part's own records
come from the far compile; this prices the dataset on the plain part (the grid is the same bytes).
usage: avdata.py course farpickle"""
import sys, os, pickle, struct
sys.path.insert(0, "tools")
import bbcourse as B

course = sys.argv[1]
far = pickle.load(open(sys.argv[2], "rb"))["far"]
c = B.compile_course(open("apps/bonanza/courses/%s.bbc" % course).read(), "apps/bonanza/courses/%s.bbc" % course)
st = bytearray(c.wstored if getattr(c, "split", False) else c.stored)
g = struct.unpack_from("<H", st, 26)[0]
nrows, smin, amin, kw = struct.unpack_from("<HhhH", st, g + 4)
diroff, nsec = struct.unpack_from("<HH", st, 38)
coff = None
for j in range(nsec):
    tag, form, off, ln, dl = struct.unpack_from("<BBHHH", st, diroff + B.DIRENT * j)
    if chr(tag) == "C":
        coff = off + ln - dl
lists, blob = {}, bytearray()
mod = bytearray(st)
bad = 0
for (wx, wy), L in sorted(far.items()):
    L = tuple(L)
    if L not in lists:
        lists[L] = len(blob)
        blob += bytes([len(L)] + [(i << 4) | j for i, j in L])
    r, k = wx + wy - smin, (wx - wy - amin) >> 1
    p = coff + 4 * (r * kw + k) + 1
    if mod[p] != 0 or (mod[p + 1] & 15) != B.KIND_VOID:
        bad += 1
    mod[p] = lists[L] + 1
z0, z1 = B.packed_len(bytes(st), "lzb"), B.packed_len(bytes(mod) + bytes(blob), "lzb")
z2 = B.packed_len(bytes(st) + bytes(blob), "lzb")
print("%s: %d listed cells, blob %d bytes (%s 255); LZB %d -> %d (+%d: the blob alone +%d, the grid bytes +%d)%s" % (
    course, len(far), len(blob), "<=" if len(blob) <= 255 else "OVER", z0, z1, z1 - z0, z2 - z0, z1 - z2,
    "; %d cells whose byte +1 was not 0 or not VOID" % bad if bad else ""))
