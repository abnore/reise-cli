#!/usr/bin/env python3

"""
reise-cli — A small command-line tool for querying public transport
information using the Entur GraphQL API.

Docs:https://developer.entur.org/
Version: 0.1.0
Author: Andreas B. Nore
License: MIT

Search for stops and select from an interactive table the correct one.
Using Geocoder to find information, and will find all places searched for, not
just stops.
It will be cached in a local json file. This file can be cleared, listed and
rename single entries.
See color coded output that correspond to type of transport, bus is red, metro is
orange and tram is blue. Filter out the mode of transportation by selecting at
input.

Future:
    Add journey planning, current location of transport, how far away, delays,
    distance to user and other information relayed by the API

Dependencies:
    - requests
    - rich
"""

import requests, json, os
import sys, datetime
import unicodedata
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich import box

from find import find_places

__version__ = "0.1.0"

SCRIPT_PATH = os.path.realpath(__file__)
SCRIPT_DIR  = os.path.dirname(SCRIPT_PATH)
CACHE = os.path.join(SCRIPT_DIR, "stops.json")

URL  = "https://api.entur.io/journey-planner/v3/graphql"
HEADERS = { "ET-Client-Name": "reise-cli" }
# Same colors of the icons for ruter
MODE_COLORS = {
        "bus": "#C62828",
        "metro": "#EF6C00",
        "tram": "#1565C0",
        }

known_stops = {}
try:
    with open(CACHE) as f:
        known_stops.update(json.load(f))
except (json.JSONDecodeError, FileNotFoundError):
    pass

console = Console()

# Graphql query, limited to next hour and 20 results - Here we can ask
# for whatever we need
def departures(stop_id):
    query = """
            query($id:String!) {
              stopPlace(id:$id) {
                name
                estimatedCalls(timeRange: 3600, numberOfDepartures: 20) {
                  expectedDepartureTime
                  destinationDisplay { frontText }
                  serviceJourney {
                    line {
                      publicCode
                      name
                      transportMode
                    }
                  }
                }
              }
            }
            """

    r = requests.post( URL,
            json={"query": query, "variables": {"id": stop_id}},
            headers=HEADERS)
    r.raise_for_status()
    return r.json()

def format_time(t):
    dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00"))
    return dt.strftime("%H:%M:%S")

def normalize(s):
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("-", "").replace(" ", "")
    return s

def show_info(name):
    norm = normalize(name)

    # Find real key behind normalized match
    matches = [k for k in known_stops if normalize(k) == norm]

    if not matches:
        console.print(f"[red]'{name}' not found in cache[/red]")
        return

    real_key = matches[0]
    entry = known_stops[real_key]

    table = Table(
        title=f"[bold magenta]Info for \"{real_key}\"[/bold magenta]",
        box=box.DOUBLE,
    )
    table.add_column("Field", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    def row(key, value):
        if value is not None:
            table.add_row(key, str(value))

    row("Stop ID", entry.get("id"))
    row("Name", entry.get("name"))
    row("Label", entry.get("label"))
    row("County", entry.get("county"))
    row("Layer", entry.get("layer"))
    row("Is Stop", entry.get("is_stop"))

    console.print(table)

def rename_entry(old, new):
    if old not in known_stops:
        console.print(f"[red]'{old}' not found in cache[/red]")
        return

    if new in known_stops:
        console.print(f"[yellow]'{new}' already exists in cache[/yellow]")
        return

    known_stops[new] = known_stops.pop(old)
    with open(CACHE, "w") as f:
        json.dump(known_stops, f, indent=2)

    console.print(f"[green]Renamed '{old}' -> '{new}'[/green]")

USAGE = """reise — tiny CLI for public transport (Using Entur API)

usage: reise [--options] [<stop name>] [-mode]

(hint: if not symlinked or installed in $PATH,
       use ./reise.py
       Or if not chmod +x then python3 reise.py is fine)

Options:
    --list          prints cached stops
    --clear-cache   deletes json cache
    --delete        deletes stop
    --info          print info about the stop
    --rename        rename entry <old name> <new name>
    --version       prints version number

Mode:
    -bus            only shows busses at this stop
    -metro          only shows metro at this stop
    -tram           only shows tram at this stop
"""

def main(args):

    if not args:
        print(USAGE)
        sys.exit(1)

    first = args[0]

    # Mode filter
    mode = None
    valid_modes = {
        "-bus": "bus",
        "-metro": "metro",
        "-tram": "tram",
    }

    if args and args[-1] in valid_modes:
        mode = valid_modes[args[-1]]
        args = args[:-1]    # remove mode flag from stop name args

    # Handle flags (only when first arg starts with "--")
    if first.startswith("--"):
        if first == "--list":
            if not known_stops:
                console.print("[yellow]No cached stops[/yellow]")
                return

            table = Table(
                    title="[bold underline magenta]Saved stops\
                           [/bold underline magenta]",
                    box=box.DOUBLE,
                    )
            table.add_column("#", justify="right")
            table.add_column("Key")
            table.add_column("Stop ID")

            for i, (key, value) in enumerate(known_stops.items()):
                sid = value["id"]
                table.add_row(str(i), key, sid)
            console.print(table)
            return

        elif first == "--clear-cache":
            with open(CACHE, "w") as f:
                json.dump({}, f, indent=2)
            console.print("[yellow]Cache cleared[/yellow]")
            return

        elif first == "--delete":
            if len(args) < 2:
                console.print("[red]Usage: --delete <stop name>[/red]")
                return

            target = " ".join(args[1:])
            norm = normalize(target)
            matches = [k for k in known_stops if normalize(k) == norm]

            if not matches:
                console.print(f"[yellow]'{target}' not found in cache[/yellow]")
                return

            real_key = matches[0]
            del known_stops[real_key]

            with open(CACHE, "w") as f:
                json.dump(known_stops, f, indent=2)

            console.print(f"[green]Deleted '{real_key}' from cache[/green]")
            return

        elif first == "--info":
            if len(args) < 2:
                console.print("[red]Usage: --info <stop name>[/red]")
                return
            name = " ".join(args[1:])
            show_info(name)
            return

        elif first == "--rename":
            if len(args) < 3:
                console.print("[red]Usage: --rename <old name> <new name>[/red]")
                return

            # Drop flag
            parts = args[1:]

            # Try to find the longest prefix match in known_stops
            split_index = None
            old = None

            for i in range(1, len(parts)+1):
                candidate = " ".join(parts[:i])
                norm_candidate = normalize(candidate)

                for k in known_stops:
                    if normalize(k) == norm_candidate:
                        old = k
                        split_index = i
                        break

            if old is None:
                console.print(f"[red]No matching cached stop found in rename input[/red]")
                console.print("[yellow]Try quoting names with spaces, e.g.[/yellow]")
                console.print('  reise --rename "nedre bekkelaget" nb')
                return

            new = " ".join(parts[split_index:]).strip()

            if not new:
                console.print("[red]New name missing after old name[/red]")
                return

            if new in known_stops:
                console.print(f"[yellow]'{new}' already exists in cache[/yellow]")
                return

            known_stops[new] = known_stops.pop(old)
            with open(CACHE, "w") as f:
                json.dump(known_stops, f, indent=2)

            console.print(f"[green]Renamed '{old}' -> '{new}'[/green]")
            return

        if first == "--version":
            print(__version__)
            return

        else:
            print(f"Unknown option: {first}")
            print(USAGE)
            sys.exit(1)

    # else treat all args as stop name (multi-word ok as entur API accepts it)
    name = " ".join(args)
    norm = normalize(name)
    matches = [k for k in known_stops if normalize(k) == norm]

    if matches:
        real_key = matches[0]
        name = real_key
    else:
        places = find_places(name, HEADERS)
        stops  = [p for p in places if p["is_stop"]]

        if not stops:
            console.print(f"[red]No StopPlaces found for '{name}'[/red]")
            console.print("Matches included:")
            for p in places[:5]:
                console.print(f"  {p['label']}")
            return

        if len(stops) == 1:
            chosen = stops[0]
        else:
            table = Table(
               title=f"[bold underline magenta]Multiple stops match \"{name}\" \
                       [/bold underline magenta]",
               box=box.DOUBLE,
               )
            table.add_column("#", justify="right")
            table.add_column("Name")
            table.add_column("County")
            table.add_column("Label")

            for i, s in enumerate(stops):
                table.add_row(str(i), s["name"], s["county"], s["label"])
            console.print(table)

            choices_enum = [str(i) for i in range(len(stops))]
            choices_enum.append("q")

            answer = Prompt.ask("Pick a stop (or q to quit)",
                                choices=choices_enum)

            if answer == "q":
                return

            idx = int(answer)
            chosen = stops[idx]

        name = chosen['name'].lower()
        known_stops[name] = chosen
        console.print(f"[green]Saved {name} -> {chosen['id']}[/green]")

        # Cache
        with open(CACHE, "w") as f:
            json.dump(known_stops, f, indent=2)

    data = departures(known_stops[name]["id"])
    stop = data.get("data", {}).get("stopPlace", None)

    if stop is None:
        print("API returned no stopPlace data")
        print(data)
        sys.exit(1)

    calls = stop.get("estimatedCalls") or []

    if mode:
        calls = [
            c for c in calls
            if c["serviceJourney"]["line"]["transportMode"].lower() == mode
        ]

        if not calls:
            console.print(f"[yellow]No {mode} departures in the next hour[/yellow]")
            return

    table = Table(
        show_header=True,
        header_style="bold magenta"
    )

    table.add_column("Time", justify="right")
    table.add_column("Line", justify="right")
    table.add_column("Destination", justify="left")

    for call in calls:
        t = format_time(call["expectedDepartureTime"])
        service = call["serviceJourney"]["line"]
        line = f"{service['publicCode']:>2}"
        mode = service.get("transportMode", "").lower()
        bg = MODE_COLORS.get(mode, "grey23")  # fallback background

        dest = call["destinationDisplay"]["frontText"]

        styled_line = f"[white on {bg}]{line} [/white on {bg}]"

        table.add_row(t, styled_line, dest)

    console.print(table)

if __name__ == "__main__":
    main(sys.argv[1:])
