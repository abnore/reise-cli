#!/usr/bin/env python3

import requests
import sys

URL = "https://api.entur.io/geocoder/v1/autocomplete"

def find_places(name, header):
    r = requests.get(URL, params={"text": name}, headers=header)
    r.raise_for_status()
    data = r.json()

    results = []
    for feat in data.get("features", []):
        props = feat.get("properties", {})
        pid = props.get("id", "")

        results.append({
            "id": pid,
            "name": props.get("name", ""),
            "county": props.get("county", ""),
            "label": props.get("label", ""),
            "layer": props.get("layer", ""),
            "is_stop": pid.startswith("NSR:StopPlace:"),
            "raw": feat,  # optional: keep everything
        })

    return results



"""This function is purely for testing and will not be executed when imported
thanks to the name guard at the bottom
"""
def main(args):
    if not args:
        print("Usage: ./find.py <name>", file=sys.stderr)
        return 1

    name = " ".join(args).strip()
    for p in find_places(name, { "ET-Client-Name": "reise-cli" }):
        print(p["id"], p["is_stop"], p["label"])

if __name__ == "__main__":
    main(sys.argv[1:])
