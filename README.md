# reise-cli v0.1.0

`reise` is Norwegian for `journey` or `travel`. This small command-line tool
searches for public transports and departure times from any place you want.

Will find any place, stop or not, and give you a choice when searching.
Caches the places in `stops.json` with all the information you would need.
The tool allows you to filter out modes of travel, be it bus or tram, and only 
display those. 

Future enhancements will be journey planning, location of vehicle, delays and
distance to the user.

>[!NOTE]
>Early in development - API-breaking changes may occur at any moment!
>Pull latest changes and reinstall dependencies if needed:
>
>```sh
>git pull
>pip install -r requirements.txt
>```

## Installation

Clone this repo

```sh
git clone https://github.com/abnore/reise-cli
cd reise-cli
```

>[!NOTE] 
>To have `reise.py` as an executable, symlink it in your local path as `reise`
>or copy/move after doing a `chmod +x` on the script.

```sh
echo $PATH | tr : "\n"
```
This will list out your path, and you may choose whichever on that list.
For example, my path is `~/.local/bin`, then you can write:

```sh
chmod +x reise.py
ln -s /full/path/reise.py ~/.local/bin/reise
```

Now you can use it like any other tool

```sh
reise jernbanetorget -bus
```

### Optional: Install in a virtual environment

It is recommended to install dependencies in an isolated environment
instead of system-wide:

```sh
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```
To exit the environment later:

```sh
deactivate
```

Although you can also simply break system packages with, e.g.:

```sh
pip3 install rich --break-system-packages
```
This will install globally which made more sense for me, not having to be
in a virtual environment

## Usage

```
reise <stop name> [mode]
```

### Examples

Search for a stop (first time prompts selection, then cached):
```sh
reise jernbanetorget
```
Rename:
```sh
reise --rename jernbanetorget jb
```
If renaming a place with multiple words, make sure to include ""

```sh
reise --rename "nedre bekkelaget" nb
```

Only show buses:
```sh
reise jb -bus
```

Metro-only:
```sh
reise oslo s -metro
```

Trams-only:
```sh
reise bjørvika -tram
```

List cached stops:
```sh
reise --list
```

Show info:
```sh
reise --info bjørvika
```

Delete:
```sh
reise --delete majorstuen
```

Clear cache completely:
```sh
reise --clear-cache
```

Show version:
```sh
reise --version
```
