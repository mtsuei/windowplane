# filename: nearby_planes.py
import math
import time
import requests

EARTH_RADIUS_KM = 6371.0

def haversine_km(lat1, lon1, lat2, lon2):
    # robust great-circle distance
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(f1)*math.cos(f2)*math.sin(dlon/2)**2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))

def bearing_deg(lat1, lon1, lat2, lon2):
    # initial bearing (0° = North, clockwise)
    f1, f2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    y = math.sin(dlon) * math.cos(f2)
    x = math.cos(f1)*math.sin(f2) - math.sin(f1)*math.cos(f2)*math.cos(dlon)
    brng = math.degrees(math.atan2(y, x))
    return (brng + 360) % 360

def bbox_from_center(lat, lon, radius_km):
    # Approximate: 1 deg lat ~ 111 km; 1 deg lon ~ 111 km * cos(lat)
    dlat = radius_km / 111.0
    dlon = radius_km / (111.0 * max(0.0001, math.cos(math.radians(lat))))
    return (lat - dlat, lat + dlat, lon - dlon, lon + dlon)

def fetch_opensky_states(lat_min, lat_max, lon_min, lon_max, extended=False, timeout=10):
    params = {
        "lamin": f"{lat_min:.5f}",
        "lamax": f"{lat_max:.5f}",
        "lomin": f"{lon_min:.5f}",
        "lomax": f"{lon_max:.5f}",
    }
    if extended:
        params["extended"] = 1
    url = "https://opensky-network.org/api/states/all"
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def pretty_cardinal(deg):
    dirs = ["N","NE","E","SE","S","SW","W","NW","N"]
    idx = int((deg + 22.5) // 45)
    return dirs[idx]

def list_nearby(lat0, lon0, radius_km=50.0, min_alt_m=200, max_results=10):
    lat_min, lat_max, lon_min, lon_max = bbox_from_center(lat0, lon0, radius_km)
    data = fetch_opensky_states(lat_min, lat_max, lon_min, lon_max, extended=True)

    t = data.get("time", int(time.time()))
    states = data.get("states", []) or []

    rows = []
    for s in states:
        # OpenSky "states" row fields by index:
        # 0 icao24, 1 callsign, 5 lon, 6 lat, 7 baro_alt_m, 9 v_ground_mps, 10 track_deg, 11 v_rate_mps,
        # 13 geo_alt_m, 8 on_ground
        callsign = (s[1] or "").strip()
        lon = s[5]; lat = s[6]
        if lon is None or lat is None:
            continue
        on_ground = bool(s[8]) if s[8] is not None else False
        geo_alt_m = s[13] if len(s) > 13 else None
        baro_alt_m = s[7]
        alt_m = geo_alt_m if geo_alt_m is not None else baro_alt_m
        if alt_m is None:
            continue

        dist_km = haversine_km(lat0, lon0, lat, lon)
        if dist_km > radius_km:
            continue
        if on_ground or alt_m < min_alt_m:
            continue

        track = s[10]
        heading = None if track is None else float(track) % 360
        bearing = bearing_deg(lat0, lon0, lat, lon)
        rows.append({
            "callsign": callsign if callsign else "(no callsign)",
            "icao24": s[0],
            "lat": lat, "lon": lon,
            "alt_m": int(alt_m),
            "dist_km": dist_km,
            "bearing_deg": bearing,
            "bearing_card": pretty_cardinal(bearing),
            "heading_deg": heading,
            "ground_speed_mps": s[9],
            "v_rate_mps": s[11],
            "last_update": s[4],
        })

    # nearest first
    rows.sort(key=lambda r: r["dist_km"])
    return t, rows[:max_results]

if __name__ == "__main__":
    # TODO: set your location here (decimal degrees)
    MY_LAT = 33.95812
    MY_LON = -118.39025
    RADIUS_KM = 100.0

    t, planes = list_nearby(MY_LAT, MY_LON, RADIUS_KM)
    if not planes:
        print("No airborne aircraft found in range.")
    else:
        print(f"Found {len(planes)} aircraft near you:")
        for p in planes:
            dist = f"{p['dist_km']:.1f} km"
            alt = f"{p['alt_m']} m"
            brg = f"{int(round(p['bearing_deg']))}° {p['bearing_card']}"
            hdg = "—" if p['heading_deg'] is None else f"{int(round(p['heading_deg']))}°"
            gs  = "—" if p['ground_speed_mps'] is None else f"{int(round(p['ground_speed_mps']*3.6))} km/h"
            print(f"- {p['callsign']}  ({p['icao24']})  {dist}, alt {alt}, bearing {brg}, heading {hdg}, speed {gs}")
