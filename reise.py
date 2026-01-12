#!/usr/bin/env python3

__version__ = "0.1.2"

"""
reise-cli — A small command-line tool for querying public transport
information using the Entur GraphQL API.

Docs: https://developer.entur.org/
Version: {}
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
""".format(__version__)

import requests, json, os, sys, datetime, unicodedata
from argparse import ArgumentParser, RawDescriptionHelpFormatter

from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich import box

from find import find_places


SCRIPT_PATH = os.path.realpath(__file__)
SCRIPT_DIR  = os.path.dirname(SCRIPT_PATH)
CACHE = os.path.join(SCRIPT_DIR, "stops.json")

URL  = "https://api.entur.io/journey-planner/v3/graphql"
HEADERS = { "ET-Client-Name": "reise-cli" }

MODE_COLORS = {
    "bus":   "#C62828", # red
    "metro": "#EF6C00", # orange
    "tram":  "#1565C0", # light blue
    "train": "#003DA5", # dark blue
    "ferry": "#6A1B9A", # purple
    "air":   "#880E4F", # wine red
}


console = Console()
known_stops = {}

try:
    with open(CACHE) as f:
        known_stops.update(json.load(f))
except Exception:
    pass


# utilites ----------------------------
def save_cache():
    """Opens stops.json and writes to file.
    Knowns stops as it currently is will be stored
    """
    with open(CACHE, "w") as f:
        json.dump(known_stops, f, indent=2)

def normalize(s):
    """Normalized strings, making it case- and symbol insensitive
    Simple fuzzy finder, removes accents and -, spaces and case
    i.e. oslo-s Oslo S and OslOS are equal
    """
    s = s.lower().strip()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = s.replace("-", "").replace(" ", "")
    return s


def normalize_mode(raw):
    """Entur API has rails, regionaltrain, longdistancetrain, coach
    and airportexpress. Counts as train here.
    Same with water, watertransport and ferry will count as ferry
    Also airplane, air, plane and flight is now all air
    """
    m = raw.lower()
    if m in ("train", "rail", "regionaltrain", "longdistancetrain",
             "airportexpress", "coach"):
        return "train"
    if m in ("water", "watertransport"):
        return "ferry"
    if m in ("airplane", "air", "plane", "flight"):
        return "air"
    return m

# actions -----------------------------

def departures(stop_id):
    """Send a post request to EnTur API via grapql.
    returns json format
    """
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
    """Helper for time tables. returns time from Zulu time to local time
    in known format
    """
    dt = datetime.datetime.fromisoformat(t.replace("Z","+00:00"))
    return dt.strftime("%H:%M:%S")

def list_stops():
    """Pretty-print all cached stops as a small table.
    Uses rich for formatting. If no stops are cached, warn user.
    """
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
    """Clear the entire stop cache.
    If force=False, prompt the user for confirmation.
    If force=True, wipe without asking (like rm -rf).
    """
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

def _resolve_key(name):
    """Return a valid stop key based on fuzzy name or index."""
    # number shortcut
    if name.isdigit():
        idx = int(name)
        keys = list(known_stops.keys())
        if idx < 0 or idx >= len(keys):
            return None
        return keys[idx]

    # fallback to fuzzy
    norm = normalize(name)
    matches = [k for k in known_stops if normalize(k) == norm]
    return matches[0] if matches else None

def _delete_single_stop(name, force):
    """Delete a single cached stop by fuzzy name match."""
    key = _resolve_key(name)
    if not key:
        console.print(f"[red]'{name}' not found in cache[/red]")
        console.print("[yellow]Deleting by name supports only one stop at a time.[/yellow]")
        console.print("[yellow]hint: use indices from `reise -l`, e.g. `reise -d 7 8`.[/yellow]")
        return

    if not force:
        ans = Prompt.ask(f"[red]Delete '{key}'?[/red]", choices=["y","n"], default="n")
        if ans != "y":
            console.print("[cyan]Canceled[/cyan]")
            return

    del known_stops[key]
    save_cache()
    console.print(f"[green]Deleted '{key}'[/green]")


def delete_stop(args, force=False):
    """Handle multiple deletions by index or single named deletions."""
    if all(p.isdigit() for p in args):
        keys = list(known_stops.keys())
        for idx in sorted((int(p) for p in args), reverse=True):
            if 0 <= idx < len(keys):
                _delete_single_stop(keys[idx], force=True if force else False)
            else:
                console.print(f"[red]{idx} out of range[/red]")
        save_cache()
        return

    name = " ".join(args).strip()
    _delete_single_stop(name, force)

def _show_info_single(name):
    """Pretty-print metadata for one cached stop."""
    key = _resolve_key(name)
    if not key:
        console.print(f"[red]'{name}' not found in cache[/red]")
        console.print("[yellow]Info by name supports only one stop at a time.[/yellow]")
        console.print("[yellow]hint: use indices from `reise -l`, e.g. `reise -i 7 8`.[/yellow]")
        return

    entry = known_stops[key]

    table = Table(title=f"[bold magenta]Info for \"{key}\"[/bold magenta]",
                  box=box.DOUBLE)
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")

    for fld in ["id","name","label","county","layer","is_stop"]:
        table.add_row(fld, str(entry.get(fld)))

    console.print(table)

def show_info(parts):
    """Show info for one or several cached stops (names or indices)."""
    if all(p.isdigit() for p in parts):
        for raw in parts:
            _show_info_single(raw)
        return

    name = " ".join(parts).strip()
    _show_info_single(name)

def rename_stop(args):
    """Rename a cached stop key while preserving its stored data.
    Uses fuzzy matching for the old name and refuses collisions on new.
    """
    parts = args
    if ":" not in parts:
        console.print("[red]Rename requires ':' separator[/red]")
        console.print("[yellow]hint: reise -n oslo s : oslos[/yellow]")
        return

    sep = parts.index(":")
    old_words = parts[:sep]
    new_words = parts[sep+1:]

    if not old_words or not new_words:
        console.print("[red]Invalid rename syntax[/red]")
        return

    old = " ".join(old_words).strip()
    new = " ".join(new_words).strip()

    # Fuzzy match old
    old_real = _resolve_key(old)
    if not old_real:
        console.print(f"[red]'{old}' not found in cache[/red]")
        return
    if new in known_stops:
        console.print(f"[yellow]'{new}' already exists[/yellow]")
        return

    known_stops[new] = known_stops.pop(old_real)
    save_cache()
    console.print(f"[green]Renamed '{old_real}' -> '{new}'[/green]")


# main query --------------------------
def _render_places_table(places, name):
    """Display all matches from Entur for a search"""
    table = Table(
        title=f"[bold underline magenta]Matches for '{name}'[/bold underline magenta]",
        box=box.DOUBLE
    )
    table.add_column("#", justify="right")
    table.add_column("Name")
    table.add_column("County")
    table.add_column("Label")
    table.add_column("Stop?", justify="center")

    for i, p in enumerate(places):
        table.add_row(str(i), p["name"], p["county"], p["label"],
                      "Stop" if p["is_stop"] else "-")

    console.print(table)

def _prompt_for_stop(places, stops):
    """Ask user to pick one stop index from a mixed result list"""
    index_map = {i: j for j, s in enumerate(stops)
                       for i, p in enumerate(places)
                       if p is s}

    # Allow only valid place indexes that map to stops, may change in future
    choices = list(index_map.keys()) + ["q"]
    choices_str = [str(c) for c in index_map.keys()] + ["q"]

    ans = Prompt.ask("Pick a stop to view departures (or q)", choices=choices_str)
    if ans == "q":
        return None

    return stops[index_map[int(ans)]]

def _show_departures(key, modes=None):
    """Display filtered departures for a cached stop key."""
    entry = known_stops.get(key)
    if not entry:
        console.print(f"[red]Unknown stop '{key}'[/red]")
        return

    data = departures(entry["id"])
    stop = data.get("data", {}).get("stopPlace")
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
    table.add_column("Line", justify="center")
    table.add_column("Destination", justify="left")

    for c in calls:
        t = format_time(c["expectedDepartureTime"])
        svc = c["serviceJourney"]["line"]
        m = normalize_mode(svc["transportMode"])

        public = svc.get("publicCode")
        name   = svc.get("name", "")

        # --- FLIGHT HANDLING ---
        if m == "air":
            if public:
                code = public
            elif "-" in name or "–" in name:
                parts = [p.strip() for p in name.replace("–", "-").split("-")]
                if len(parts) >= 2:
                    code = f"{parts[0][:3].upper()}-{parts[-1][:3].upper()}"
            else:
                code = "✈"
            line = f"{code:>7}"

        # --- NORMAL STUFF ---
        else:
            code = public or "?"
            line = f"{code:>2}"

        bg = MODE_COLORS.get(m, "grey23") # default to grey23
        styled = f"[white on {bg}]{line} [/white on {bg}]"
        table.add_row(t, styled, c["destinationDisplay"]["frontText"])

    console.print(table)

def lookup_and_display(name, modes=None, raw=False):
    """Display a resolved stop. Uses cached stop if exact match or accepted
    at prompt, otherwise will query Entur. If multiple StopPlaces will prompt
    user. Caches new stops by name, will avoid multiple of same by id.
    Finally will show departures
    """
    norm = normalize(name)
    # numeric lookup ALWAYS uses cached, no questions ---
    if raw:
        key = None
    else:
        if name.isdigit():
            key = _resolve_key(name)
            if key:
                return _show_departures(key, modes)
            console.print(f"[red]{name} out of range[/red]")
            return
        # Try cache by index or fuzzy
        key = _resolve_key(name)

    # If no direct match we go live
    if not key:
        pass

    else:
        # Exact key match? (user typed exact key)
        if name.lower().strip() == key:
            return _show_departures(key, modes)

        # Otherwise it’s fuzzy
        ans = Prompt.ask(
            f"{name} is already saved as '{key}'. Use cached?",
            choices=["y","n"],
            default="y"
        )
        if ans == "y":
            return _show_departures(key, modes)
        # else fall through and query Entur

    # Ask Entur API
    places = find_places(name, HEADERS)
    if not places:
        console.print(f"No matches found for '{name}'")
        return

    stops = [p for p in places if p.get("is_stop")]

    # First we try matching by id
    id_matches = [
        k for k, entry in known_stops.items()
        for p in stops
        if entry.get("id") == p["id"]
    ]

    if len(id_matches) == 1 and not raw:
        key = id_matches[0]
        ans = Prompt.ask(
            f"{name} is already saved as '{key}'. Use cached?",
            choices=["y","n"],
            default="y"
        )
        if ans == "y":
            return _show_departures(key, modes)
        # else continue to full

    elif len(id_matches) > 1:
        console.print(f"{name} maps to multiple saved stops. Searching live…")

    _render_places_table(places, name)

    if not stops:
        console.print("No StopPlaces in results — cannot show departures")
        return

    if len(stops) == 1:
        chosen = stops[0]
    else:
        chosen = _prompt_for_stop(places, stops)
        if not chosen:
            return

    # If chosen maps to existing cache ID, reuse it
    for key, entry in known_stops.items():
        if entry.get("id") == chosen["id"]:
            console.print(f"Already cached {key}")
            return _show_departures(key, modes)

    # Else we save it
    key = chosen["name"].lower()
    known_stops[key] = chosen
    save_cache()
    console.print(f"Saved {key}")

    return _show_departures(key, modes)


# argparse entry ----------------------

def _preprocess_force(argv):
    """
    Rewrite combined destructive flags so that -f comes first.
    Workaround since -d accepts one arg, f was messing with that.
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
    Turn things like ['-wt', '-bm'] into ['-w', '-t', '-b', '-m'].
    Leaves long options (--list) and single short flags (-b) alone.
    """
    args = _preprocess_force(argv)
    out = []
    for arg in args:
        # Only touch short options like -bm, not --long
        if arg.startswith("-") and not arg.startswith("--") and len(arg) > 2:
            # split -bm -> -b, -m
            for ch in arg[1:]:
                out.append(f"-{ch}")
        else:
            out.append(arg)
    return out

def formatter(prog):
    """Simple factor for formatting the help section
    formatter_class needs a class or callable, and without using a lambda,
    we need this simple constructor method.
    The default HelpFormatter doesnt respect new lines or formatted strings
    """
    return RawDescriptionHelpFormatter(
        prog, max_help_position=32, width=70)

def build_parser():
    """Create and configure the ArgumentParser for the CLI.
    Defines flags, modes, and help/epilog. Returns a fully-built parser.
    """
    p = ArgumentParser()

    p.color=True, # Configurable
    p.prog="reise"
    p.usage = "reise [OPTIONS] [stop ...]"
    p.description=(
       "Small cli for Norwegian public transport using the Entur API.\n"
       "Search stops, cache them, rename or delete entries, and filter\n"
       "by bus/metro/tram.\n"
       "\n(hint: if not symlinked or installed in $PATH, use: ./reise.py\n"
       "If not chmod +x then `python3 reise.py` is fine\n")
    p.epilog=(
        "Tip: filter flags combine in any order, and can be used together\n"
        "example:\n"
        "\treise -rb oslo lufthavn\n"
        "\treise skøyen -mw\n"
        "\treise -Rb jernbanetorget\n"
        "\n"
        "Thank you for using me!")
    p.allow_abbrev=False  # important so -bm isn't 'guessed' as something else
    p.formatter_class=formatter

    # positional
    p.add_argument("stop", nargs="*", help="Name of stop (multi-word allowed)")

    # flags
    p.add_argument("-v", "--version", action="store_true",
                   help="Print version number and exit")
    p.add_argument("-l", "--list", action="store_true", help="List all cached stops")
    p.add_argument("-i", "--info", nargs="+",metavar="stop",
                   help="Show info about a cached stop")
    p.add_argument("-n", "--rename", nargs="+", metavar="old name : new name",
                   help="Rename a cached stop using ':' separator")
    p.add_argument("-d", "--delete",nargs="+", metavar="stop",
                  help="Delete a stop from cache")
    p.add_argument("-c", "--clear-cache", action="store_true",
                   help="Clear all cached stops")
    p.add_argument("-R", "--raw", action="store_true",
                   help="Ignore cached stops, search directly")
    # modes
    p.add_argument("-b", "--bus",   action="store_true", help="Only show buses")
    p.add_argument("-m", "--metro", action="store_true", help="Only show metro")
    p.add_argument("-t", "--tram",  action="store_true", help="Only show trams")
    p.add_argument("-w", "--water",  action="store_true", help="Only show water/ferry")
    p.add_argument("-r", "--train",  action="store_true", help="Only show train/rail")
    p.add_argument("-x", "--xray", action="store_true", help="Only show planes/air")

    # global modifier
    p.add_argument("-f", "--force", action="store_true",
                   help="Skip confirmation prompts (delete/clear)")

    return p

def main(argv):
    """cli entry point.
    Preprocess flags, parse arguments, dispatch to the correct sub-command,
    or fall back to query mode or help output.
    """
    parser = build_parser()
    argv = expand_flags(argv)
    args = parser.parse_args(argv)
    modes = []

    if args.version: return print(f"reise {__version__}")
    if args.list: return list_stops()
    if args.clear_cache: return clear_cache(args.force)
    if args.delete: return delete_stop(args.delete, args.force)
    if args.info: return show_info(args.info)
    if args.rename: return rename_stop(args.rename)

    if args.stop:
        stop_name = " ".join(args.stop)

        if args.bus: modes.append("bus")
        if args.metro: modes.append("metro")
        if args.tram: modes.append("tram")
        if args.train: modes.append("train")
        if args.water: modes.append("ferry")
        if args.xray: modes.append("air")

        if not modes:
            modes = None  # no filtering

        return lookup_and_display(stop_name, modes, args.raw)

    parser.print_usage()
    console.print("[yellow](hint: -h for full help message)[/yellow]")

if __name__ == "__main__":
    main(sys.argv[1:])
