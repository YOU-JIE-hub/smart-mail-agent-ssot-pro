import runpy, sys
import tools.compat_loader as cl
cl.install()
if len(sys.argv) < 2:
    print("Usage: python3 tools/py_with_compat.py <script.py> [args...]")
    sys.exit(64)
script, *args = sys.argv[1:]
sys.argv = [script] + args
runpy.run_path(script, run_name="__main__")
