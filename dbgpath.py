import sys, os
print("CWD:", os.getcwd())
print("cwd in path:", os.getcwd() in sys.path)
print("empty str in path:", "" in sys.path)
print("sys.path[:4]:", sys.path[:4])
