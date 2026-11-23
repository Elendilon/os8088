import sys; sys.path.insert(0, "tools")
import bbcourse as B
B.TRAP_CHECK = False
sys.argv = ["bbcourse.py", sys.argv[1], "--png", sys.argv[2]]
B.main() if hasattr(B, "main") else None
