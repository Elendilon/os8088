import sys
W = __import__("os").path.abspath(__import__("os").path.join(__import__("os").path.dirname(__file__), "../../../.."))
sys.path.insert(0, W + "/tools")
import bbcourse as B
c = B.compile_course(W + "/apps/bonanza/courses/summit.bbc")
K = {getattr(B, n): n for n in dir(B) if n.startswith("KIND_")}
for wy in range(15, 22):
    print(wy, "  ".join("%d,%d:%s/%s" % (wx, wy, K.get(c.cells.get((wx, wy), [0,0,0])[2] & 15, "?")[5:9], c.cells.get((wx, wy), ["-"])[0]) for wx in range(20, 27)))
print(c.cells.get((23,19)))
