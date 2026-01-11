#!/usr/bin/env python3

"""
reise-cli — A small command-line tool for querying public transport
information using the Entur GraphQL API.

Docs: https://developer.entur.org/
Version: 0.2.0
Author: Andreas B. Nore
License: MIT

Search for stops and select from an interactive table the correct one.
Using Geocoder to find information, and will find all places searched for, not
just stops. It is cached in a local json file. 
This file can be cleared, listed and you can rename single entries.
See color coded output that corresponds to type of transport, bus is red, metro is
orange and tram is blue. Filter out the mode of transportation by selecting at
input.

Future:
    Add journey planning, current location of transport, how far away, delays,
    distance to user and other information relayed by the API

Dependencies:
    - requests
    - rich
"""

import requests, json, os, sys, datetime, unicodedata
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich import box

from find import find_places

__version__ = "0.2.0"

SCRIPT_PATH = os.path.realpath(__file__)
SCRIPT_DIR  = os.path.dirname(SCRIPT_PATH)
CACHE = os.path.join(SCRIPT_DIR, "stops.json")

URL  = "https://api.entur.io/journey-planner/v3/graphql"
HEADERS = { "ET-Client-Name": "reise-cli" }

MODE_COLORS = {
    "bus":   "#C62828",
    "metro": "#EF6C00",
    "tram":  "#1565C0",
    "train": "#003DA5",
    "ferry": "#6A1B9A",
}

console = Console()
known_stops = {}

try:
    with open(CACHE) as f:
        known_stops.update(json.load(f))
except Exception:
    pass


# utilites ----------------------------

def normalize(s):
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("-", "").replace(" ", "")
    return s

def save_cache():
    with open(CACHE, "w") as f:
        json.dump(known_stops, f, indent=2)

def normalize_mode(raw):
    m = raw.lower()
    if m in ("rail", "regionaltrain", "longdistancetrain",
             "airportexpress", "coach"):
        return "train"
    if m in ("water", "watertransport"):
        return "ferry"
    return m

# actions -----------------------------

def departures(stop_id):
    query = """
      query($id:String!) {
        stopPlace(id:$id) {
          name
          estimatedCalls(timeRange: 3600, numberOfDepartures: 20) {
            expectedDepartureTime
            destinationDisplay { frontText }
            serviceJourney {
              line { publicCode name transportMode }
            }
          }
        }
      }"""
    r = requests.post(URL, json={"query": query, "variables": {"id": stop_id}},
                      headers=HEADERS)
    r.raise_for_status()
    return r.json()

def format_time(t):
    dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00"))
    return dt.strftime("%H:%M:%S")

def list_stops():
    if not known_stops:
        console.print("[yellow]No cached stops[/yellow]")
        return

    table = Table(title="[bold underline magenta]Saved stops[/bold underline magenta]",
                  box=box.DOUBLE)
    table.add_column("#", justify="right")
    table.add_column("Key")
    table.add_column("Stop ID")

    for i, (k, v) in enumerate(known_stops.items()):
        table.add_row(str(i), k, v["id"])

    console.print(table)

def clear_cache(force=False):
    count = len(known_stops)
    if count == 0:
        console.print("[yellow]Cache already empty[/yellow]")
        return

    if not force:
        msg = f"[red]Clear ALL {count} cached entr{'y' if count==1 else 'ies'}?[/red]"
        ans = Prompt.ask(msg, choices=["y","n"], default="n")
        if ans != "y":
            console.print("[cyan]Canceled[/cyan]")
            return

    known_stops.clear()
    save_cache()
    console.print("[green]Cache cleared[/green]")

def delete_stop(name, force=False):
    norm = normalize(name)
    matches = [k for k in known_stops if normalize(k) == norm]
    if not matches:
        console.print(f"[yellow]'{name}' not found in cache[/yellow]")
        return
    key = matches[0]

    if not force:
        ans = Prompt.ask(f"[red]Delete '{key}'?[/red]", choices=["y","n"], default="n")
        if ans != "y":
            console.print("[cyan]Canceled[/cyan]")
            return

    del known_stops[key]
    save_cache()
    console.print(f"[green]Deleted '{key}'[/green]")

def show_info(name):
    norm = normalize(name)
    matches = [k for k in known_stops if normalize(k) == norm]
    if not matches:
        console.print(f"[red]'{name}' not found in cache[/red]")
        return
    k = matches[0]
    entry = known_stops[k]

    table = Table(title=f"[bold magenta]Info for \"{k}\"[/bold magenta]",
                  box=box.DOUBLE)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    for fld in ["id","name","label","county","layer","is_stop"]:
        table.add_row(fld, str(entry.get(fld)))

    console.print(table)

def rename_stop(old,new):
    # Fuzzy match old
    norm = normalize(old)
    matches = [k for k in known_stops if normalize(k) == norm]
    if not matches:
        console.print(f"[red]'{old}' not found in cache[/red]")
        return

    old_real = matches[0]
    if new in known_stops:
        console.print(f"[yellow]'{new}' already exists[/yellow]")
        return

    known_stops[new] = known_stops.pop(old_real)
    save_cache()
    console.print(f"[green]Renamed '{old_real}' -> '{new}'[/green]")


# main query --------------------------

def lookup_and_display(name, modes=None):
    norm = normalize(name)
    matches = [k for k in known_stops if normalize(k) == norm]

    if matches:
        real_key = matches[0]
    else:
        # Query API
        places = find_places(name, HEADERS)
        stops = [p for p in places if p["is_stop"]]
        if not stops:
            console.print(f"[red]No StopPlaces found for '{name}'[/red]")
            for p in places[:5]:
                console.print(f"  {p['label']}")
            return

        if len(stops) == 1:
            chosen = stops[0]
        else:
            table = Table(title=f"[bold underline magenta]Matches for '{name}'\
                                  [/bold underline magenta]", box=box.DOUBLE)
            table.add_column("#", justify="right")
            table.add_column("Name")
            table.add_column("County")
            table.add_column("Label")

            for i, s in enumerate(stops):
                table.add_row(str(i), s["name"], s["county"], s["label"])
            console.print(table)

            choices = [str(i) for i in range(len(stops))] + ["q"]
            ans = Prompt.ask("Pick a stop (or q)", choices=choices)
            if ans == "q": return
            chosen = stops[int(ans)]

        real_key = chosen["name"].lower()
        known_stops[real_key] = chosen
        save_cache()
        console.print(f"[green]Saved {real_key} -> {chosen['id']}[/green]")

    entry = known_stops[real_key]
    data = departures(entry["id"])
    stop = data.get("data",{}).get("stopPlace")
    if not stop:
        console.print("[red]API error[/red]")
        return

    calls = stop.get("estimatedCalls") or []

    if modes:
        calls = [
            c for c in calls
            if normalize_mode(c["serviceJourney"]["line"]["transportMode"]) in modes
        ]
        if not calls:
            console.print(
                f"[yellow]No {', '.join(modes)} departures[/yellow]"
            )
            return

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Time", justify="right")
    table.add_column("Line", justify="right")
    table.add_column("Destination", justify="left")

    for c in calls:
        t = format_time(c["expectedDepartureTime"])
        svc = c["serviceJourney"]["line"]
        line = f"{svc['publicCode']:>2}"

        m = normalize_mode(svc["transportMode"])
        bg = MODE_COLORS.get(m, "grey23")

        styled = f"[white on {bg}]{line} [/white on {bg}]"
        table.add_row(t, styled, c["destinationDisplay"]["frontText"])

    console.print(table)


# argparse entry ----------------------
def preprocess_force(argv):
    """
    Rewrite combined destructive flags so that -f comes first.

    Examples:
        -df → -f -d
        -fd → -f -d
        -cf → -f -c
        -fc → -f -c
    """
    out = []
    for arg in argv:
        if arg in ("-df", "-fd"):
            out.extend(["-f", "-d"])
        elif arg in ("-cf", "-fc"):
            out.extend(["-f", "-c"])
        else:
            out.append(arg)
    return out

def expand_flags(argv):
    """
    Turn things like ['-wt', '-bm'] into ['-w', 't', '-b', '-m'].
    Leaves long options (--list) and single short flags (-b) alone.
    """
    out = []
    for arg in argv:
        # Only touch short options like -bm, not --long
        if arg.startswith("-") and not arg.startswith("--") and len(arg) > 2:
            # split -bm -> -b, -m
            for ch in arg[1:]:
                out.append(f"-{ch}")
        else:
            out.append(arg)
    return out


def build_parser():
    p = ArgumentParser(
        prog="reise",
        description=(
            "Small CLI for Norwegian public transport using the Entur API.\n"
            "Search stops, cache them, rename or delete entries, and filter\n"
            "by bus/metro/tram."
        ),
        epilog=("Tip: flags combine in any order, and can be used together\n"
                "example:\n"
                "\treise -rb oslo lufthavn\n"
                "\treise skøyen -mw\n"
                "\n"
                "Thank you for using me!"),
        allow_abbrev=False,  # important so -bm isn't 'guessed' as something else
        formatter_class=lambda prog:\
            RawDescriptionHelpFormatter(prog, max_help_position=30, width=70),
       )

    # positional
    p.add_argument("stop", nargs="*", help="Name of stop (multi-word allowed)")

    # flags
    p.add_argument("-v", "--version", action="store_true",
                   help="Print version number and exit")
    p.add_argument("-l", "--list", action="store_true", help="List all cached stops")
    p.add_argument("-i", "--info", nargs="+",metavar="<stop>",
                   help="Show info about a cached stop")
    p.add_argument("-n", "--rename", nargs="+", metavar="<old> : <new>",
                   help="Rename a cached stop using ':' separator")
    p.add_argument("-d", "--delete",nargs="+", metavar="<stop>",
                   help="Delete a stop from cache")
    p.add_argument("-c", "--clear-cache", action="store_true",
                   help="Clear all cached stops")

    # modes
    p.add_argument("-b", "--bus",   action="store_true", help="Only show buses")
    p.add_argument("-m", "--metro", action="store_true", help="Only show metro")
    p.add_argument("-t", "--tram",  action="store_true", help="Only show trams")
    p.add_argument("-w", "--water",  action="store_true", help="Only show water/ferry")
    p.add_argument("-r", "--train",  action="store_true", help="Only show train/rail")


    # global modifier
    p.add_argument("-f", "--force", action="store_true",
                   help="Skip confirmation prompts (delete/clear)")

    return p

def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]

    argv = preprocess_force(argv)
    argv = expand_flags(argv)
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.version:
        print(f"reise version {__version__}")
        return
    if args.list:
        return list_stops()
    if args.clear_cache:
        return clear_cache(args.force)
    if args.delete:
        name = " ".join(args.delete).strip()
        return delete_stop(name, args.force)
    if args.info:
        name = " ".join(args.info).strip()
        return show_info(name)
    if args.rename:
        parts = args.rename
        if ":" not in parts:
            console.print("[red]Rename requires ':' separator[/red]")
            console.print("Example: reise -n oslo bussterminal : obterm")
            return

        sep = parts.index(":")
        old_words = parts[:sep]
        new_words = parts[sep+1:]

        if not old_words or not new_words:
            console.print("[red]Invalid rename syntax[/red]")
            return

        old = " ".join(old_words).strip()
        new = " ".join(new_words).strip()

        return rename_stop(old, new)

    # default path: search
    if args.stop:
        stop_name = " ".join(args.stop)
        modes = []
        if args.bus:
            modes.append("bus")
        if args.metro:
            modes.append("metro")
        if args.tram:
            modes.append("tram")
        if args.train:
            modes.append("train")
        if args.water:
            modes.append("ferry")
        if not modes:
            modes = None  # no filtering

        return lookup_and_display(stop_name, modes)

    parser.print_help()

if __name__ == "__main__":
    main()
