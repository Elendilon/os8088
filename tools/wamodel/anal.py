import json, sys, collections
ev = json.load(open(sys.argv[1]))
# drop up to first G.render
i0 = next(i for i, e in enumerate(ev) if e["k"] == "G.render")
ev = ev[i0:]
frames = sum(1 for e in ev if e["k"] == "G.render") - 1
seg = collections.defaultdict(lambda: [0, 0])
spans = []   # (cycles, cols opened, range cols, room?)
faces = collections.defaultdict(lambda: [0, 0])
room = False
for a, b in zip(ev, ev[1:]):
    d = b["c"] - a["c"]
    k = a["k"]
    if k == "wa_render.walked": room = True
    if k == "G.render": room = False
    if k == "wa_span":
        opened = a["left"] - b["left"]
        c1 = (a["c1"] + 7) >> 4; c2 = ((a["c2"] + 7) >> 4) - 1
        spans.append((d, opened, room))
        seg["span"][0] += 1; seg["span"][1] += d
    elif k == "wa_face":
        outc = "drew->span" if b["k"] == "wa_span" else "ended"
        faces[(room, outc)][0] += 1; faces[(room, outc)][1] += d
        seg["face " + ("room " if room else "box ") + outc][0] += 1
        seg["face " + ("room " if room else "box ") + outc][1] += d
    elif k == "wa_leaf":
        outc = "->face" if b["k"] == "wa_face" else "culled"
        seg["leaf " + outc][0] += 1; seg["leaf " + outc][1] += d
    else:
        seg[k + " -> " + b["k"]][0] += 1; seg[k + " -> " + b["k"]][1] += d
tot = sum(v[1] for v in seg.values())
print("frames %d, cycles/frame %.0f (%.1f ms)" % (frames, tot / frames, tot / frames / 4772.727))
for k, (n, c) in sorted(seg.items(), key=lambda x: -x[1][1]):
    print("  %-40s n/frame %5.2f  avg %6.0f clk  per frame %7.0f clk %5.2f ms" % (k, n / frames, c / n, c / frames, c / frames / 4772.727))
# span cost vs columns: least squares
import statistics
xs = [s[1] for s in spans]; ys = [s[0] for s in spans]
mx, my = statistics.mean(xs), statistics.mean(ys)
b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)
a = my - b * mx
print("span cost = %.0f + %.0f x columns opened (n=%d, mean cols %.1f)" % (a, b, len(spans), mx))
h = collections.Counter(min(s[1], 9) for s in spans)
print("cols opened histogram", sorted(h.items()))
for rm in (False, True):
    ss = [s for s in spans if s[2] == rm]
    if ss:
        print(" room" if rm else " box", "spans/frame %.2f cols/frame %.2f clk/frame %.0f" % (len(ss) / frames, sum(s[1] for s in ss) / frames, sum(s[0] for s in ss) / frames))
