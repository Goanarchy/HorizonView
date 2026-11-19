import re
import requests

t = requests.get("https://511nj.org/main-23IT6KDM.js", timeout=90).text
patterns = [
    r'["\'][^"\']{0,60}event[^"\']{0,80}["\']',
    r'getEvents\(\)\{[^}]{0,500}',
    r'apiUrl\s*\+\s*["\'][^"\']+["\']',
]
for p in patterns:
    found = sorted(set(re.findall(p, t, re.I)))
    print("PAT", p, "N", len(found))
    for x in found[:60]:
        print(x[:300])
    print()
