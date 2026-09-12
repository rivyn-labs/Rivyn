import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
req = urllib.request.Request("https://api.github.com/repos/logpai/loghub/contents", headers={"User-Agent": "Mozilla/5.0"})
try:
    with urllib.request.urlopen(req) as resp:
        items = json.loads(resp.read().decode("utf-8"))
        dirs = [it["name"] for it in items if it["type"] == "dir" and not it["name"].startswith(".")]
        print("LogHub Directories:", dirs)
        for d in dirs:
            try:
                sub_req = urllib.request.Request(f"https://api.github.com/repos/logpai/loghub/contents/{d}", headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(sub_req) as sub_resp:
                    sub_items = json.loads(sub_resp.read().decode("utf-8"))
                    files = [f["name"] for f in sub_items if f["type"] == "file"]
                    print(f"{d}: {files}")
            except Exception as e_sub:
                print(f"{d} error: {e_sub}")
except Exception as e:
    print("Error:", e)
