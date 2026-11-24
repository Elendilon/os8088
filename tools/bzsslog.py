#!/usr/bin/env python3
"""bzsslog.py SSLOG.BIN - print the see-saw log a BZSSLOG=1 build of BONANZA writes (apps/bonanza/bzsslog.inc)"""
import sys, struct
d = open(sys.argv[1], "rb").read()
assert d[:4] == b"SSLG", d[:4]
n, crs, mode, fnf = struct.unpack_from("<HBBB", d, 4)
lo, hi = struct.unpack_from("<HH", d, 10)
print("records %d  course %d  mode %d  families %d  STEP list %04X..%04X: %s" % (n, crs, mode, fnf, lo, hi, d[14:14 + hi - lo].hex(" ")))
print(" step    gx    gy    gz air mst mat fhk fst fref  calls(slots 0-7)         slot3 (8)                wake3")
for i in range(n):
    r = d[64 + 32 * i: 96 + 32 * i]
    st, gx, gy, gz = struct.unpack_from("<HHHh", r, 0)
    air, mst, mat, fhk, fst, fref = r[8:14]
    print("%5d %5.2f %5.2f %5d %3d %3d %3d %02X  %3d %3d   %s  %s  %5d" % (
        st, gx / 16, gy / 16, gz, air, mst, mat, fhk, fst, fref, r[14:22].hex(" "), r[22:30].hex(" "), struct.unpack_from("<H", r, 30)[0]))
