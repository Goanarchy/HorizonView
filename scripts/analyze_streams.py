"""Analiza el contenido real de las playlists y segmentos de las fuentes."""
import json
import pathlib
import requests
import urllib.parse

D = pathlib.Path(__file__).resolve().parents[1] / "data"
de = json.loads((D / "de_cameras.json").read_text(encoding="utf-8"))
nj = json.loads((D / "nj_cameras.json").read_text(encoding="utf-8"))

H = {"User-Agent": "Mozilla/5.0", "Accept": "*/*"}


def analyze(label, cam, referer):
    url = cam["stream"]
    h = {**H, "Referer": referer}
    print("\n---", label, cam["id"], url[:100])
    try:
        r = requests.get(url, headers=h, timeout=15)
        print("playlist:", r.status_code, r.headers.get("Content-Type", ""), len(r.content))
        body = r.text
        print("head:", body[:180].replace("\n", " | "))
        lines = [x.strip() for x in body.splitlines() if x.strip() and not x.startswith("#")]
        if not lines:
            return
        print("variantes:", len(lines))
        master = "#EXT-X-STREAM-INF" in body
        media_url = urllib.parse.urljoin(url, lines[0])
        if master:
            mr = requests.get(media_url, headers=h, timeout=15)
            print("media:", mr.status_code, mr.headers.get("Content-Type", ""), len(mr.content))
            segs = [x.strip() for x in mr.text.splitlines() if x.strip() and not x.startswith("#")]
            if segs:
                media_url = urllib.parse.urljoin(media_url, segs[0])
        sr = requests.get(media_url, headers=h, timeout=15)
        b = sr.content[:64]
        print("segmento:", sr.status_code, sr.headers.get("Content-Type", ""), len(sr.content),
              "bytes=", b[:24].hex())
        kinds = []
        if b[:1] == b"\x47":
            kinds.append("MPEG-TS OK")
        if b"ftyp" in b[:32]:
            kinds.append("fMP4 OK")
        low = sr.content[:400].lower()
        if b"<html" in low or b"<!doctype" in low:
            kinds.append("HTML (error)")
        if b"error" in low and len(sr.content) < 4000:
            kinds.append("posible error")
        print("clasificación:", ", ".join(kinds) or "desconocido")
    except Exception as e:
        print("ERROR:", type(e).__name__, str(e)[:200])


for c in [x for x in nj if x.get("stream")][:2]:
    analyze("NJ", c, "https://511nj.org/")
for c in de[:2]:
    analyze("DE", c, "https://deldot.gov/")
