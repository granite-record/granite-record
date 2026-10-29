import hashlib, json, os, sys
from pathlib import Path
B = Path(sys.argv[1]); mode = sys.argv[2]
ORG = "Daily Journal #1, 12-1-10, Organization Day Final.txt"
C = [6, 9, 10, 13, 18, 19, 20, 21, 22, 23, 24, 25]
pairs = ([(f"journals/2010/HJ{n:03d}.txt", f"journals/2011/HJ{n:03d}.txt") for n in C]
         + [(f"journals/2010/{ORG}", f"journals/2011/{ORG}"),
            ("journals/2000/HJ025.txt", "journals/1999/HJ025.txt"),
            ("journals/2000/HJ026.txt", "journals/1999/HJ026.txt")])
files = {}
def put(rel, data):
    p = B / "kit" / rel; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    files[rel] = {"size": len(data), "sha256": hashlib.sha256(data).hexdigest(), "mtime_ns": 1}
for old, new in pairs:
    d = f"text of {new}\n".encode()
    put(old, d)
    if mode != "no-new":
        put(new, d)
put("journals/2011/HJ003.txt", b"other\n")
put("journals/2010/HJ002.txt", b"2010 own\n")
if mode == "differ":
    put("journals/2011/HJ010.txt", b"different\n")
m = B / "state" / "kit-manifest.json"; m.parent.mkdir(parents=True, exist_ok=True)
m.write_text(json.dumps({"prefix": "kit", "files": files, "count": len(files),
                         "bytes": sum(e["size"] for e in files.values())}))
print(len(files), "entries")
