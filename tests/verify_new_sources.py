import requests

h = {"User-Agent": "HorizonView/3.0 (public data demo)"}
tests = [
    "https://api.open-meteo.com/v1/forecast?latitude=39.68&longitude=-75.47&current=temperature_2m,precipitation,rain,snowfall,wind_speed_10m,visibility&timezone=America/New_York",
    "https://api.weather.gov/points/39.68,-75.47",
    "https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%5Btimeout%3A10%5D%3Bway%5Bhighway%3Dconstruction%5D%2840.70%2C-74.20%2C40.73%2C-74.15%29%3Bout%20center%203%3B",
]
for u in tests:
    try:
        r = requests.get(u, headers=h, timeout=35)
        print(r.status_code, len(r.content), u.split("/")[2], r.text[:260].replace("\n", " "))
    except Exception as e:
        print("ERR", type(e).__name__, str(e)[:140])
