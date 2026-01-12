# reise-cli v0.1.2
<img src="images/reise_jb.png" width="500">

`reise` is Norwegian for `journey` or `travel`. This small command-line tool
searches for public transports and departure times from any place you want.

Will find any place, stop or not, and give you a choice when searching.
Caches the places in `<repo>/stops.json` with all the information you would need.
The tool allows you to filter out modes of travel, be it bus or tram, and only
display those.

Future enhancements will be journey planning, location of vehicle, delays and
distance to the user.

>[!WARNING]
>Early in development - API-breaking changes may occur at any moment!
>Pull latest changes and reinstall dependencies if needed:
>
>```sh
>git pull
>pip install -r requirements.txt
>```

---

## Installation

Clone this repo

```sh
git clone https://github.com/abnore/reise-cli
cd reise-cli
```

### Make it runnable everywhere
To have `reise.py` as an executable, symlink it in your local path as `reise`
or copy/move after doing a `chmod +x` on the script. First find out what your
`$PATH` is by writing

```sh
echo $PATH | tr : "\n"
```
This will list out your path, and you may choose whichever on that list.
For example, if my path is `~/.local/bin`, then you can write:

```sh
chmod +x reise.py
ln -s /full/path/reise.py ~/.local/bin/reise
```

Now you can use it like any other command

```sh
reise jernbanetorget -b
```
---

### Optional: Install in a virtual environment

It is recommended to install dependencies in an isolated environment
instead of system-wide in newer versions of Python:

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

---

## Usage
If symlinked or installed then usage is simple:

```
reise [OPTIONS] <stop name>
```
Flags can be on **before** or **after** the stop name, and in any order.
The filter flags, `[-Rbmtwrfx]` can also be combined
### Examples

```
reise <stop>             show departures
reise <stop> -b          buses only
reise -m <stop>          metro only
reise <stop> -t          trams only
reise <stop> -r          train/rail only
reise <stop> -bm         bus + metro
reise -R <stop>          bypass cache, show all matches

reise -l/--list          list cached stops
reise -i/--info <stop>   show cached metadata
reise -n a : b           rename cached stop
reise -d <stop>          delete from cache
reise -c                 clear cache
reise -v                 show version
```
