"""
sync_monetization.py: creates and updates the game passes and developer products listed
in ShopConfig using Roblox Open Cloud, so you never need the Creator Hub UI.

Every run:
  1. Reads ShopConfig (from Roblox Studio if this place is open there, otherwise ShopConfig.lua).
  2. For each pass / product:
       id = 0, nothing with that name exists yet  -> creates it (passes get a placeholder icon)
       id = 0, one with the exact same name exists -> reuses it (never makes duplicates)
       id already set                              -> updates name, description or price if they changed
     Everything is set to "for sale", except egg items (needsEggs = true) while
     ShopConfig.EggsEnabled = false: those are kept off sale. Set EggsEnabled = true and re-run
     to put them on sale (see EGG_ITEMS_FOLLOW_EGGS_ENABLED below).
  3. Writes new IDs into ShopConfig (in Studio and in ShopConfig.lua).
  4. Prints a table of what happened.

Run it:
  python sync_monetization.py               create / update everything
  python sync_monetization.py --dry-run     only show what would happen (never changes anything)
  python sync_monetization.py --no-studio   use ShopConfig.lua only, don't touch Studio
  python sync_monetization.py --update-icons  re-upload pass icons from the icons folder

Needs ROBLOX_API_KEY=... in a file called .env (or .env.txt) in this folder. The key needs these
permissions for this experience: game-pass:read, game-pass:write, developer-product:read,
developer-product:write. The key is never printed. Only uses built-in Python (no installs).
"""

import argparse
import glob
import json
import os
import queue
import re
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
PLACE_ID = 86395856666175  # "Build your Startup!"; the universe ID is looked up from this
CONFIG_FILE = os.path.join(HERE, "ShopConfig.lua")
ICON_DIR = os.path.join(HERE, "icons")
STUDIO_CONFIG_PATH = "game.ReplicatedStorage.ShopConfig"
API = "https://apis.roblox.com"

# True: items with needsEggs = true are only for sale while ShopConfig.EggsEnabled = true
# (flip EggsEnabled, re-run, and they go on or off sale automatically).
# False: every item is always put on sale.
EGG_ITEMS_FOLLOW_EGGS_ENABLED = True

KINDS = {
    "pass": {
        "label": "Game pass",
        "list": "/game-passes/v1/universes/{u}/game-passes/creator",
        "list_key": "gamePasses",
        "get": "/game-passes/v1/universes/{u}/game-passes/{id}/creator",
        "create": "/game-passes/v1/universes/{u}/game-passes",
        "update": "/game-passes/v1/universes/{u}/game-passes/{id}",
        "id_field": "gamePassId",
        "icon_field": "iconAssetId",
    },
    "product": {
        "label": "Dev product",
        "list": "/developer-products/v2/universes/{u}/developer-products/creator",
        "list_key": "developerProducts",
        "get": "/developer-products/v2/universes/{u}/developer-products/{id}/creator",
        "create": "/developer-products/v2/universes/{u}/developer-products",
        "update": "/developer-products/v2/universes/{u}/developer-products/{id}",
        "id_field": "productId",
        "icon_field": "iconImageAssetId",
    },
}

API_KEY = None  # loaded in main(); never printed


# API key -------------------------------------------------------------------

def load_api_key():
    if os.environ.get("ROBLOX_API_KEY"):
        return os.environ["ROBLOX_API_KEY"].strip()
    for name in (".env", ".env.txt"):  # Notepad often saves ".env" as ".env.txt"
        path = os.path.join(HERE, name)
        if os.path.isfile(path):
            with open(path, encoding="utf-8-sig") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ROBLOX_API_KEY="):
                        key = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if key:
                            return key
    sys.exit("No ROBLOX_API_KEY found. Put a line ROBLOX_API_KEY=<your key> in a file named .env in this folder.")


# Open Cloud HTTP -------------------------------------------------------------

class ApiError(Exception):
    def __init__(self, status, body):
        super().__init__(f"HTTP {status}: {body}")
        self.status = status
        self.body = body


def encode_multipart(fields, files):
    boundary = "----StartupTycoon" + uuid.uuid4().hex
    chunks = []
    for name, value in fields.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
            + str(value).encode("utf-8") + b"\r\n"
        )
    for name, (filename, data, content_type) in files.items():
        chunks.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode()
            + data + b"\r\n"
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), f"multipart/form-data; boundary={boundary}"


def api(method, path, fields=None, files=None, auth=True):
    url = path if path.startswith("http") else API + path
    headers = {"Accept": "application/json", "User-Agent": "StartupTycoon-sync/1.0"}
    if auth:
        headers["x-api-key"] = API_KEY
    body = None
    if fields is not None or files:
        body, headers["Content-Type"] = encode_multipart(fields or {}, files or {})

    # A create (POST) is only retried when Roblox says "too many requests", because a server
    # error might come after the item was already made. A re-run then finds it by name instead.
    safe_to_retry = method != "POST"
    for attempt in range(4):
        request = urllib.request.Request(url, data=body, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                raw = response.read()
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            text = e.read().decode("utf-8", "replace")[:600]
            retry = e.code == 429 or (safe_to_retry and e.code in (500, 502, 503, 504))
            if retry and attempt < 3:
                time.sleep(min(int(e.headers.get("Retry-After") or 2 ** (attempt + 1)), 30))
                continue
            raise ApiError(e.code, text) from None
        except urllib.error.URLError as e:
            if safe_to_retry and attempt < 3:
                time.sleep(2 ** attempt)
                continue
            raise ApiError(0, str(e.reason)) from None


def list_all(kind, universe):
    info = KINDS[kind]
    items, token = [], None
    while True:
        query = "?pageSize=50" + (f"&pageToken={urllib.parse.quote(token)}" if token else "")
        data = api("GET", info["list"].format(u=universe) + query) or {}
        items += data.get(info["list_key"]) or []
        token = data.get("nextPageToken")
        if not token:
            return items


def remote_price(remote):
    return (remote.get("priceInformation") or {}).get("defaultPriceInRobux")


# Reading and writing ShopConfig ------------------------------------------------

FIELD_RE = re.compile(r"""(\w+)\s*=\s*("(?:[^"\\\n]|\\.)*"|'(?:[^'\\\n]|\\.)*'|-?\d+(?:\.\d+)?|true|false)""")


def matching_brace(text, open_index):
    """Index just past the } that closes the { at open_index (skips strings and comments)."""
    depth, i, quote = 0, open_index, None
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == "\\":
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif text.startswith("--", i):
            i = text.find("\n", i)
            if i == -1:
                break
            continue
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise ValueError("ShopConfig: unbalanced { }")


def top_level_view(block):
    """The block text with nested tables (like effect = {...}) blanked out, same length."""
    out, depth, quote = [], 0, None
    i = 0
    while i < len(block):
        ch = block[i]
        hidden = depth > 1
        if quote:
            if ch == "\\" and i + 1 < len(block):
                out.append("  " if hidden else block[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "\"'":
            quote = ch
        elif ch == "{":
            depth += 1
            hidden = depth > 1
        elif ch == "}":
            depth -= 1
        out.append(" " if hidden and ch != "\n" else ch)
        i += 1
    return "".join(out)


def lua_value(token):
    if token[0] in "\"'":
        return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)), token[1:-1])
    if token in ("true", "false"):
        return token == "true"
    return float(token) if "." in token else int(token)


def parse_config(text):
    items = []
    for kind, table in (("pass", "Passes"), ("product", "Products")):
        m = re.search(r"ShopConfig\." + table + r"\s*=\s*\{", text)
        if not m:
            raise ValueError(f"ShopConfig: couldn't find ShopConfig.{table}")
        list_start = m.end() - 1
        list_end = matching_brace(text, list_start)
        i = list_start + 1
        while i < list_end - 1:
            j = text.find("{", i, list_end - 1)
            if j == -1:
                break
            end = matching_brace(text, j)
            view = top_level_view(text[j:end])
            fields, id_span = {}, None
            for f in FIELD_RE.finditer(view):
                fields[f.group(1)] = lua_value(text[j + f.start(2):j + f.end(2)])
                if f.group(1) == "id":
                    id_span = (j + f.start(2), j + f.end(2))
            missing = [k for k in ("key", "name", "description", "price", "id") if k not in fields]
            if missing:
                raise ValueError(f"ShopConfig: an item in {table} is missing {', '.join(missing)}")
            items.append({
                "kind": kind,
                "key": fields["key"],
                "name": fields["name"],
                "description": fields["description"],
                "price": int(fields["price"]),
                "id": int(fields["id"]),
                "needsEggs": bool(fields.get("needsEggs")),
                "id_span": id_span,
            })
            i = end
    return items


def eggs_enabled(text):
    m = re.search(r"^\s*ShopConfig\.EggsEnabled\s*=\s*(true|false)", text, re.M)
    if not m:
        raise ValueError("ShopConfig: couldn't find ShopConfig.EggsEnabled = true/false")
    return m.group(1) == "true"


def should_sell(item, eggs_on):
    return not (EGG_ITEMS_FOLLOW_EGGS_ENABLED and item["needsEggs"] and not eggs_on)


def patch_ids(text, items, new_ids):
    """Replaces id = 0 with the real ID for every item in new_ids (key -> id)."""
    for item in sorted(items, key=lambda it: it["id_span"][0], reverse=True):
        if item["key"] in new_ids:
            start, end = item["id_span"]
            text = text[:start] + str(new_ids[item["key"]]) + text[end:]
    return text


# Placeholder pass icons (plain PNG, no image library needed) --------------------

FONT = {  # 5x7 pixel letters
    "A": "01110 10001 10001 11111 10001 10001 10001", "B": "11110 10001 10001 11110 10001 10001 11110",
    "C": "01110 10001 10000 10000 10000 10001 01110", "D": "11110 10001 10001 10001 10001 10001 11110",
    "E": "11111 10000 10000 11110 10000 10000 11111", "F": "11111 10000 10000 11110 10000 10000 10000",
    "G": "01110 10001 10000 10111 10001 10001 01111", "H": "10001 10001 10001 11111 10001 10001 10001",
    "I": "01110 00100 00100 00100 00100 00100 01110", "J": "00111 00010 00010 00010 00010 10010 01100",
    "K": "10001 10010 10100 11000 10100 10010 10001", "L": "10000 10000 10000 10000 10000 10000 11111",
    "M": "10001 11011 10101 10101 10001 10001 10001", "N": "10001 10001 11001 10101 10011 10001 10001",
    "O": "01110 10001 10001 10001 10001 10001 01110", "P": "11110 10001 10001 11110 10000 10000 10000",
    "Q": "01110 10001 10001 10001 10101 10010 01101", "R": "11110 10001 10001 11110 10100 10010 10001",
    "S": "01111 10000 10000 01110 00001 00001 11110", "T": "11111 00100 00100 00100 00100 00100 00100",
    "U": "10001 10001 10001 10001 10001 10001 01110", "V": "10001 10001 10001 10001 10001 01010 00100",
    "W": "10001 10001 10001 10101 10101 10101 01010", "X": "10001 10001 01010 00100 01010 10001 10001",
    "Y": "10001 10001 01010 00100 00100 00100 00100", "Z": "11111 00001 00010 00100 01000 10000 11111",
    "0": "01110 10001 10011 10101 11001 10001 01110", "1": "00100 01100 00100 00100 00100 00100 01110",
    "2": "01110 10001 00001 00010 00100 01000 11111", "3": "11111 00010 00100 00010 00001 10001 01110",
    "4": "00010 00110 01010 10010 11111 00010 00010", "5": "11111 10000 11110 00001 00001 10001 01110",
    "6": "00110 01000 10000 11110 10001 10001 01110", "7": "11111 00001 00010 00100 01000 01000 01000",
    "8": "01110 10001 10001 01110 10001 10001 01110", "9": "01110 10001 10001 01111 00001 00010 01100",
    "+": "00000 00100 00100 11111 00100 00100 00000", " ": "00000 00000 00000 00000 00000 00000 00000",
}
ICON_COLORS = [(0, 170, 90), (225, 150, 20), (45, 110, 225), (145, 70, 205), (215, 60, 70), (20, 160, 170)]


def png_bytes(width, height, rgb):
    rows = b"".join(b"\x00" + bytes(rgb[y * width * 3:(y + 1) * width * 3]) for y in range(height))

    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows, 9))
            + chunk(b"IEND", b""))


def make_icon(name, color, size=512):
    """Colored square, darker circle (Roblox shows pass icons as circles), name in big white letters."""
    img = bytearray(bytes(color) * (size * size))
    light = tuple(max(0, c - 45) for c in color)  # the circle
    dark = tuple(max(0, c - 120) for c in color)  # letter shadow

    def fill_row(y, x0, x1, c):
        if 0 <= y < size and x1 > x0:
            x0, x1 = max(0, x0), min(size, x1)
            img[(y * size + x0) * 3:(y * size + x1) * 3] = bytes(c) * (x1 - x0)

    center, radius = size // 2, int(size * 0.46)
    for y in range(size):
        dy = y - center
        if abs(dy) <= radius:
            half = int((radius * radius - dy * dy) ** 0.5)
            fill_row(y, center - half, center + half, light)

    words = [w for w in re.split(r"[\s\-]+", name.upper()) if w]
    lines = [words[0][:6]] if len(words) == 1 else [words[0][:6], words[-1][:6]]
    lines = ["".join(ch for ch in line if ch in FONT) or "?" for line in lines]
    widest = max(len(line) for line in lines) * 6 - 1
    tall = len(lines) * 7 + (len(lines) - 1) * 3
    scale = max(4, int(min(size * 0.62 / widest, size * 0.5 / tall)))
    top = (size - tall * scale) // 2
    for n, line in enumerate(lines):
        left = (size - (len(line) * 6 - 1) * scale) // 2
        y0 = top + n * 10 * scale
        for offset, c in ((max(2, scale // 3), dark), (0, (255, 255, 255))):  # shadow, then letters
            for k, ch in enumerate(line):
                for row, bits in enumerate(FONT[ch].split()):
                    for col, bit in enumerate(bits):
                        if bit == "1":
                            x = left + (k * 6 + col) * scale + offset
                            for yy in range(y0 + row * scale + offset, y0 + (row + 1) * scale + offset):
                                fill_row(yy, x, x + scale, c)
    return png_bytes(size, size, img)


def icon_for(item, index):
    """icons/<key>.png. Made once, then reused; put your own 512x512 PNG there to replace it."""
    os.makedirs(ICON_DIR, exist_ok=True)
    path = os.path.join(ICON_DIR, item["key"] + ".png")
    if not os.path.isfile(path):
        with open(path, "wb") as f:
            f.write(make_icon(item["name"], ICON_COLORS[index % len(ICON_COLORS)]))
    with open(path, "rb") as f:
        return os.path.basename(path), f.read(), "image/png"


# Roblox Studio (through its built-in MCP server) -------------------------------

class Studio:
    """Reads and writes ShopConfig in the open Studio place, so the game gets the IDs too."""

    def __init__(self):
        self.proc = None
        self.lines = queue.Queue()
        self.next_id = 1
        self.studio_id = None

    def _send(self, message):
        self.proc.stdin.write((json.dumps(message) + "\n").encode("utf-8"))
        self.proc.stdin.flush()

    def _request(self, method, params, timeout=120):
        request_id = self.next_id
        self.next_id += 1
        self._send({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                line = self.lines.get(timeout=max(0.1, deadline - time.time()))
            except queue.Empty:
                break
            if line is None:
                raise RuntimeError("Studio MCP server stopped")
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(json.dumps(message["error"]))
                return message["result"]
        raise RuntimeError("Studio didn't answer in time")

    def call(self, tool, args):
        if self.studio_id:
            args = dict(args, studio_id=self.studio_id)
        result = self._request("tools/call", {"name": tool, "arguments": args})
        text = "\n".join(c.get("text", "") for c in result.get("content", []) if c.get("type") == "text")
        if result.get("isError"):
            raise RuntimeError(text)
        return text

    def connect(self):
        """Returns (True, "") or (False, reason)."""
        exes = glob.glob(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Roblox", "Versions", "*", "StudioMCP.exe"))
        if not exes:
            return False, "Roblox Studio's MCP server isn't installed"
        self.proc = subprocess.Popen([max(exes, key=os.path.getmtime)], stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

        def reader():
            for line in self.proc.stdout:
                self.lines.put(line)
            self.lines.put(None)

        threading.Thread(target=reader, daemon=True).start()
        self._request("initialize", {"protocolVersion": "2025-06-18", "capabilities": {},
                                     "clientInfo": {"name": "sync_monetization", "version": "1.0"}})
        self._send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        for _ in range(25):  # Studio takes a few seconds to attach
            studios = json.loads(self.call("list_roblox_studios", {}) or "{}").get("studios", [])
            match = [s for s in studios if str(PLACE_ID) in (s.get("name") or "")]  # name is empty while loading
            if match:
                self.studio_id = match[0]["id"]
                break
            time.sleep(1)
        if not self.studio_id:
            return False, "this place isn't open in Roblox Studio"
        if "Current Studio Mode: Edit" not in self.call("get_studio_state", {}):
            return False, "Studio is playtesting; stop the playtest first"
        return True, ""

    def read_config(self):
        text = self.call("execute_luau", {"datamodel_type": "Edit", "code":
            'local s = game.ReplicatedStorage:FindFirstChild("ShopConfig")\n'
            'return game:GetService("HttpService"):JSONEncode({ source = s and s.Source or false })'})
        source = json.loads(text[text.find("{"):text.rfind("}") + 1])["source"]
        return source or None

    def write_config(self, old, new):
        self.call("multi_edit", {"datamodel_type": "Edit", "file_path": STUDIO_CONFIG_PATH,
                                 "edits": [{"old_string": old, "new_string": new}]})
        return self.read_config() == new

    def close(self):
        if self.proc:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()


# Syncing -----------------------------------------------------------------------

def sync_item(item, index, remote_items, universe, dry_run, update_icons, for_sale):
    """Creates or updates one item. Returns (id, status text)."""
    info = KINDS[item["kind"]]
    sale_word = "true" if for_sale else "false"
    by_id = {r[info["id_field"]]: r for r in remote_items}
    by_name = {r["name"]: r for r in remote_items}
    is_pass = item["kind"] == "pass"

    if item["id"]:
        remote = by_id.get(item["id"])
        if not remote:
            return item["id"], f"PROBLEM: ID {item['id']} isn't in this experience (set id = 0 to recreate it)"
        found = "exists"
    else:
        remote = by_name.get(item["name"])
        found = "found existing by name"

    if remote is None:
        fields = {"name": item["name"], "description": item["description"],
                  "price": item["price"], "isForSale": sale_word}
        files = {"imageFile": icon_for(item, index)} if is_pass else {}
        extra = (" with placeholder icon" if is_pass else "") + ("" if for_sale else ", off sale")
        if dry_run:
            return 0, "would create" + extra
        created = api("POST", info["create"].format(u=universe), fields, files)
        return created[info["id_field"]], "created" + extra

    remote_id = remote[info["id_field"]]
    changes, notes = {}, []
    if remote["name"] != item["name"]:
        changes["name"] = item["name"]
        notes.append("name")
    if (remote.get("description") or "") != item["description"]:
        changes["description"] = item["description"]
        notes.append("description")
    if remote_price(remote) != item["price"]:
        changes["price"] = item["price"]
        notes.append(f"price {remote_price(remote)} -> {item['price']}")
    if bool(remote.get("isForSale")) != for_sale:
        changes["isForSale"] = sale_word
        notes.append("put on sale" if for_sale else "taken off sale")
    files = {}
    if is_pass and (update_icons or not remote.get(info["icon_field"])):
        files["imageFile"] = icon_for(item, index)
        notes.append("icon")

    if not changes and not files:
        return remote_id, found + ", unchanged"
    if dry_run:
        return remote_id, f"{found}, would update: " + ", ".join(notes)
    api("PATCH", info["update"].format(u=universe, id=remote_id), changes, files)
    return remote_id, f"{found}, updated: " + ", ".join(notes)


def main():
    global API_KEY
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(description="Create/update Roblox passes and products from ShopConfig.")
    parser.add_argument("--dry-run", action="store_true", help="only show what would happen")
    parser.add_argument("--no-studio", action="store_true", help="use ShopConfig.lua only, don't touch Studio")
    parser.add_argument("--update-icons", action="store_true", help="re-upload pass icons from the icons folder")
    args = parser.parse_args()

    API_KEY = load_api_key()
    universe = int(api("GET", f"/universes/v1/places/{PLACE_ID}/universe", auth=False)["universeId"])
    print(f"Experience: place {PLACE_ID}, universe {universe}" + ("   [DRY RUN: nothing will change]" if args.dry_run else ""))

    studio, source, source_name = None, None, "ShopConfig.lua"
    if not args.no_studio:
        studio = Studio()
        try:
            ok, reason = studio.connect()
            if ok:
                source = studio.read_config()
                source_name = "Roblox Studio"
            else:
                print(f"Studio: {reason}. Using ShopConfig.lua instead.")
        except Exception as e:
            print(f"Studio: couldn't connect ({e}). Using ShopConfig.lua instead.")
        if source is None:
            studio.close()
            studio = None
    if source is None:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            source = f.read()

    items = parse_config(source)
    eggs_on = eggs_enabled(source)
    print(f"Read {len(items)} items from ShopConfig ({source_name}). EggsEnabled = {str(eggs_on).lower()}"
          + ("" if eggs_on or not EGG_ITEMS_FOLLOW_EGGS_ENABLED else ", so egg items stay off sale") + ".\n")

    try:
        remote = {kind: list_all(kind, universe) for kind in KINDS}
    except ApiError as e:
        if e.status in (401, 403):
            sys.exit(f"Roblox refused the API key ({e}).\nCheck the key has game-pass and developer-product "
                     f"read/write permission for universe {universe}, and isn't expired or IP-restricted.")
        raise

    results, new_ids = [], {}
    pass_index = 0
    for item in items:
        try:
            item_id, status = sync_item(item, pass_index, remote[item["kind"]], universe, args.dry_run,
                                        args.update_icons, should_sell(item, eggs_on))
        except ApiError as e:
            item_id, status = item["id"], f"FAILED: {e}"
        if item["kind"] == "pass":
            pass_index += 1
        if item_id and item_id != item["id"]:
            new_ids[item["key"]] = item_id
        results.append((item, item_id, status))
        print(f"  {item['name']}: {status}")

    # Write the new IDs into ShopConfig (Studio and the local file stay identical)
    if new_ids and not args.dry_run:
        new_source = patch_ids(source, items, new_ids)
        if studio:
            try:
                if studio.write_config(source, new_source):
                    print("\nIDs written into ShopConfig in Roblox Studio (remember to save the place).")
                else:
                    print("\nWARNING: couldn't confirm the IDs landed in Studio. Re-run with Studio open.")
            except Exception as e:
                print(f"\nWARNING: couldn't write ShopConfig in Studio ({e}). Re-run with Studio open.")
        with open(CONFIG_FILE, "w", encoding="utf-8", newline="") as f:
            f.write(new_source)
        print("IDs written into ShopConfig.lua.")
    elif studio and not args.dry_run:
        with open(CONFIG_FILE, encoding="utf-8") as f:
            local = f.read()
        if local != source:
            with open(CONFIG_FILE, "w", encoding="utf-8", newline="") as f:
                f.write(source)
            print("\nShopConfig.lua updated to match Studio.")
    if studio:
        studio.close()

    # Check the final state on Roblox and print the table
    print()
    header = f"{'Item':<22} {'Type':<12} {'ID':<14} {'Price':>6}  {'For sale':<9} Result"
    print(header)
    print("-" * len(header))
    for item, item_id, status in results:
        info = KINDS[item["kind"]]
        on_sale, price = "-", item["price"]
        if item_id and not args.dry_run:
            try:
                live = api("GET", info["get"].format(u=universe, id=item_id))
                expected = should_sell(item, eggs_on)
                on_sale = "yes" if live.get("isForSale") else "no"
                if bool(live.get("isForSale")) != expected:
                    on_sale += " (!)"  # not what ShopConfig asks for
                price = remote_price(live)
            except ApiError as e:
                on_sale = f"? ({e.status})"
        egg = " (egg item)" if item["needsEggs"] else ""
        print(f"{item['name']:<22} {info['label']:<12} {str(item_id or '-'):<14} {str(price):>6}  {on_sale:<9} {status}{egg}")


if __name__ == "__main__":
    main()
