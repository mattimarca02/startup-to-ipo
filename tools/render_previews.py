#!/usr/bin/env python3
"""Draws two pictures of the world and icons pass for the owner to look at on GitHub, before Studio.

Run:   python3 tools/render_previews.py           (writes docs/previews/world_topdown.svg and docs/previews/icons_sheet.svg)
       python3 tools/render_previews.py --check   (only says whether the two files are up to date with the data)

It needs the free Luau command-line tool, like tools/world_test.py (LUAU=/path/to/luau). Plain Python otherwise, standard
library only. It builds the real world (WorldArt, WorldVisuals, and the plots, signs and VIP Lounge from the real
TycoonCore and ShopServer code) and every real icon (IconArt, IconVisuals, CreatureModels) in the tests' fake Roblox,
then draws what it gets:
  - world_topdown.svg: the parts' boxes seen from above (paths, kerbs, lawns, lamps, trees, signs, the plots, the lounge,
    the spawn pad), a scale bar, labels, and a small map of the whole Baseplate with the hills;
  - icons_sheet.svg: every icon at 96 px: the drawn icons from their shapes (outline, plate, light from the top-left),
    the 3D icons as a front view through each icon's own camera (box faces shaded by the same light), with a caption.
These are APPROXIMATIONS: boxes and flat shading, no materials, no real fonts. Only Studio shows the real thing.
"""

import math
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import icon_test  # noqa: E402  (the same fake Roblox and module loading as the tests)
import world_test  # noqa: E402

OUT_DIR = os.path.join(ROOT, "docs", "previews")
WORLD_SVG = os.path.join(OUT_DIR, "world_topdown.svg")
ICONS_SVG = os.path.join(OUT_DIR, "icons_sheet.svg")


def luau_path():
    import shutil
    luau = os.environ.get("LUAU") or shutil.which("luau")
    if not luau:
        raise SystemExit("Luau not found. Download it from https://github.com/luau-lang/luau/releases and set LUAU=/path/to/luau")
    return luau


def run(source):
    result = world_test.run_luau(luau_path(), source)
    if result.returncode != 0:
        raise SystemExit("the fake Roblox run failed: " + (result.stderr.strip() or result.stdout.strip())[-2000:])
    return [line.split("\t") for line in result.stdout.split("\n") if line]


def head_of(source):
    """A test program up to its first numbered part: the fake, the real modules and the helpers, no test."""
    return source[:source.index("-- 1. The data ---")]


WORLD_DUMP = r"""
local function out(...)
	local t = {}
	for i = 1, select("#", ...) do
		local v = select(i, ...)
		t[i] = type(v) == "number" and string.format("%.3f", v) or tostring(v)
	end
	print_real(table.concat(t, "\t"))
end
local real = realPlotCenter(REAL.spacing, REAL.count)
local site = WorldVisuals.site(WorldArt, REAL.spacing, REAL.count, real)
local world = WorldVisuals.build(nil, WorldArt, site)
local function dump(kind, group, item, p)
	local b = WorldVisuals.boxOf(p.CFrame, p.Size)
	local c = p.Color.rgb
	local lit = "0"
	for _, child in ipairs(p:GetChildren()) do if child.ClassName == "PointLight" then lit = "1" end end
	out(kind, group, item, p.Name, p.Shape.Name, b[1], b[2], b[3], b[4], b[5], b[6], c[1], c[2], c[3], p.Material.Name, lit)
end
for _, d in ipairs(world:GetDescendants()) do
	if d:IsA("BasePart") then
		local parent = d.Parent
		if parent.Parent == world then
			dump("W", parent.Name, "", d)
		else
			dump("W", parent.Parent.Name, parent.Name, d)
		end
	elseif d.ClassName == "TextLabel" and d.Parent.Name == "TextFront" then
		local board = d.Parent.Parent
		local b = WorldVisuals.boxOf(board.CFrame, board.Size)
		out("T", board.Parent.Name, d.Text, (b[1] + b[2]) / 2, (b[5] + b[6]) / 2)
	end
end
for slot = 1, REAL.count do
	local folder = newInstance("Folder")
	local center = real(slot)
	local floor = tycoonMakePart(folder, "Floor", Vector3.new(REAL.floor[1], REAL.floor[2], REAL.floor[3]), center, Color3.fromRGB(90, 90, 100))
	dump("R", "Plot", tostring(slot), floor)
	for _, sign in ipairs({ { "BuySign", REAL.buySign }, { "IpoSign", REAL.ipoSign } }) do
		local pos = center + Vector3.new(sign[2][1], 0.5, sign[2][2])
		local board = tycoonMakePart(folder, sign[1], Vector3.new(REAL.board[1], REAL.board[2], REAL.board[3]), pos + Vector3.new(0, REAL.boardY, 0), Color3.fromRGB(0, 140, 70))
		dump("R", "Sign", tostring(slot), board)
	end
	out("PLOT", tostring(slot), center.X, center.Z)
end
buildRealLounge()
for _, p in ipairs(workspace:FindFirstChild("VipLounge"):GetChildren()) do
	if p:IsA("BasePart") then dump("R", "Lounge", "", p) end
end
dump("R", "Spawn", "", spawnPad)
local base = WorldVisuals.boxOf(baseplate.CFrame, baseplate.Size)
out("BASE", base[1], base[2], base[5], base[6], baseplate.Color.rgb[1], baseplate.Color.rgb[2], baseplate.Color.rgb[3])
out("PREVIEWSTAGES", site.preview and site.preview[1] or 0, site.preview and site.preview[2] or 0, site.preview and site.preview[5] or 0, site.preview and site.preview[6] or 0)
"""


ICONS_DUMP = r"""
local function out(...)
	local t = {}
	for i = 1, select("#", ...) do
		local v = select(i, ...)
		t[i] = type(v) == "number" and string.format("%.3f", v) or tostring(v)
	end
	print_real(table.concat(t, "\t"))
end
local SIZE = 96
local holder = newInstance("Folder")
local d = IconArt.Style.lightDirection
local toLight = (-Vector3.new(d[1], d[2], d[3])).Unit -- in the camera's frame
for _, group in ipairs(IconVisuals.GROUPS) do
	for _, key in ipairs(EXPECT[group]) do
		local recipe = IconArt[group][key]
		local icon = IconVisuals.buildUncapped(holder, IconArt, group, key, SIZE, DEPS)
		local plate = recipe.plate and IconArt.Palette[recipe.plate]
		out("I", group, key, recipe.name, recipe.kind, plate and plate[1] or -1, plate and plate[2] or -1, plate and plate[3] or -1)
		if recipe.kind == "ui" then
			for _, s in ipairs(recipe.shapes) do
				local c = IconArt.Palette[s.color]
				out("U", s.kind, s.name, s.x, s.y, s.w, s.h, s.rotation or 0, c[1], c[2], c[3], s.transparency or 0, s.outline and "1" or "0",
					s.shade and "1" or "0", s.thickness or 0, s.text or "")
			end
		else
			local view = icon:FindFirstChild("View")
			local camera = view.CurrentCamera
			local t = math.tan(math.rad(camera.FieldOfView) / 2)
			local eye = camera.CFrame.Position
			local function screen(p)
				local c = camera.CFrame:PointToObjectSpace(p)
				local depth = -c.Z
				return SIZE / 2 + (c.X / (depth * t)) * SIZE / 2, SIZE / 2 - (c.Y / (depth * t)) * SIZE / 2, depth
			end
			for _, part in ipairs(view:FindFirstChild("Model"):GetDescendants()) do
				if part:IsA("BasePart") and part.Transparency < 1 then
					local c = part.Color.rgb
					local neon = part.Material.Name == "Neon" and "1" or "0"
					local cf, s = part.CFrame, part.Size
					local r = cf.r
					local axes = { Vector3.new(r[1], r[4], r[7]), Vector3.new(r[2], r[5], r[8]), Vector3.new(r[3], r[6], r[9]) }
					local half = { s.X / 2, s.Y / 2, s.Z / 2 }
					local round = part.Shape.Name == "Ball"
					for _, child in ipairs(part:GetChildren()) do
						if child.ClassName == "SpecialMesh" and child.MeshType.Name == "Sphere" then round = true end
					end
					if round then
						local xs, ys, depthSum = {}, {}, 0
						for _, sx in ipairs({ -1, 1 }) do for _, sy in ipairs({ -1, 1 }) do for _, sz in ipairs({ -1, 1 }) do
							local p = cf.Position + axes[1] * (half[1] * sx) + axes[2] * (half[2] * sy) + axes[3] * (half[3] * sz)
							local x, y, depth = screen(p)
							table.insert(xs, x)
							table.insert(ys, y)
							depthSum += depth
						end end end
						local cx, cy, depth = screen(cf.Position)
						local rx = (math.max(table.unpack(xs)) - math.min(table.unpack(xs))) / 2 * 0.86
						local ry = (math.max(table.unpack(ys)) - math.min(table.unpack(ys))) / 2 * 0.86
						out("B", depth, c[1], c[2], c[3], neon, cx, cy, rx, ry)
					else
						for axis = 1, 3 do
							for _, sign in ipairs({ -1, 1 }) do
								local n = axes[axis] * sign
								local centre = cf.Position + n * half[axis]
								if (eye - centre).X * n.X + (eye - centre).Y * n.Y + (eye - centre).Z * n.Z > 0 then
									local u, v = axes[axis % 3 + 1], axes[(axis + 1) % 3 + 1]
									local hu, hv = half[axis % 3 + 1], half[(axis + 1) % 3 + 1]
									local pts, depthSum = {}, 0
									for _, k in ipairs({ { -1, -1 }, { 1, -1 }, { 1, 1 }, { -1, 1 } }) do
										local x, y, depth = screen(centre + u * (hu * k[1]) + v * (hv * k[2]))
										table.insert(pts, x)
										table.insert(pts, y)
										depthSum += depth
									end
									local nc = camera.CFrame:VectorToObjectSpace(n)
									local bright = 0.62 + 0.38 * math.max(0, nc.X * toLight.X + nc.Y * toLight.Y + nc.Z * toLight.Z)
									out("Q", depthSum / 4, c[1], c[2], c[3], neon, bright, table.unpack(pts))
								end
							end
						end
					end
				end
			end
		end
	end
end
"""


# SVG helpers -------------------------------------------------------------------------------------------------------

def hexc(r, g, b, k=1.0):
    r, g, b = (max(0, min(255, int(round(float(v) * k)))) for v in (r, g, b))
    return "#%02x%02x%02x" % (r, g, b)


def esc(text):
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def n(v):
    s = "%.2f" % float(v)
    s = s.rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


# The world, seen from above -------------------------------------------------------------------------------------------

def world_svg():
    rows = run(head_of(world_test.world_source()) + WORLD_DUMP)
    parts = [r for r in rows if r[0] in ("W", "R")]
    texts = [r for r in rows if r[0] == "T"]
    plots = [r for r in rows if r[0] == "PLOT"]
    base = next(r for r in rows if r[0] == "BASE")
    # The main map: everything but the hills, plus a margin
    xs = [float(r[5]) for r in parts if r[1] != "Hills"] + [float(r[6]) for r in parts if r[1] != "Hills"]
    zs = [float(r[9]) for r in parts if r[1] != "Hills"] + [float(r[10]) for r in parts if r[1] != "Hills"]
    x0, x1, z0, z1 = min(xs) - 12, max(xs) + 12, min(zs) - 12, max(zs) + 12
    scale = 2.0  # px per stud
    width_map, height_map = (x1 - x0) * scale, (z1 - z0) * scale
    pad_top, pad_side, pad_bottom, inset = 70, 24, 40, 230
    width = int(width_map + pad_side * 2)
    height = int(height_map + pad_top + pad_bottom + inset + 30)

    def px(x):
        return pad_side + (x - x0) * scale

    def pz(z):  # +Z (the plots' front) is up on the page
        return pad_top + (z1 - z) * scale

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica, Arial, sans-serif">' % (width, height, width, height)]
    out.append('<rect width="100%%" height="100%%" fill="%s"/>' % "#f4f1ea")
    out.append('<text x="%d" y="28" font-size="20" font-weight="bold" fill="#1c1e26">World pass, seen from above (approximation)</text>' % pad_side)
    out.append('<text x="%d" y="48" font-size="12" fill="#4a4e5a">Drawn by tools/render_previews.py from the parts the real WorldVisuals, TycoonCore and ShopServer code build '
               '(boxes seen from above, flat colors).</text>' % pad_side)
    out.append('<text x="%d" y="63" font-size="12" fill="#4a4e5a">Up the page is +Z, the way the plots face and the default camera looks. Only Studio shows the real look.</text>' % pad_side)
    out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>' % (n(px(x0)), n(pz(z1)), n(width_map), n(height_map), hexc(base[5], base[6], base[7])))

    def box(r, extra=""):
        bx0, bx1, by1, bz0, bz1 = float(r[5]), float(r[6]), float(r[8]), float(r[9]), float(r[10])
        color = hexc(r[11], r[12], r[13])
        shape = r[4]
        if shape == "Ball":
            cx, cz = (bx0 + bx1) / 2, (bz0 + bz1) / 2
            rad = (bx1 - bx0) / 2
            if by1 is not None and float(r[7]) < 0:  # a ball sunk into the ground: its circle at y 0
                cy = (float(r[7]) + by1) / 2
                rad = math.sqrt(max(rad * rad - cy * cy, 0))
            return '<circle cx="%s" cy="%s" r="%s" fill="%s"%s/>' % (n(px(cx)), n(pz(cz)), n(rad * scale), color, extra)
        return '<rect x="%s" y="%s" width="%s" height="%s" fill="%s"%s/>' % (n(px(bx0)), n(pz(bz1)), n((bx1 - bx0) * scale), n((bz1 - bz0) * scale), color, extra)

    # Real objects first (the plots' floors, the lounge, the spawn pad), then the world by height (lowest first)
    for r in parts:
        if r[0] == "R" and r[1] in ("Plot",):
            out.append(box(r, ' stroke="#3a3d48" stroke-width="1"'))
    world = sorted((r for r in parts if r[0] == "W" and r[1] != "Hills"), key=lambda r: (float(r[8]), r[3], r[2]))
    for r in world:
        stroke = ' stroke="#1c1e26" stroke-width="0.6" stroke-opacity="0.5"' if r[1] == "Decor" else ""
        out.append(box(r, stroke))
        if r[15] == "1":  # a lit lamp: its light's reach
            cx, cz = (float(r[5]) + float(r[6])) / 2, (float(r[9]) + float(r[10])) / 2
            out.append('<circle cx="%s" cy="%s" r="%s" fill="#ffd690" fill-opacity="0.18" stroke="#e8a838" stroke-opacity="0.5"/>' % (n(px(cx)), n(pz(cz)), n(20 * scale)))
    for r in parts:
        if r[0] == "R" and r[1] in ("Lounge", "Spawn", "Sign"):
            fill_stroke = ' fill-opacity="0.85" stroke="#1c1e26" stroke-width="0.8"'
            out.append(box(r, fill_stroke))
    # Labels
    def label(x, z, text, size=13, color="#1c1e26", bold=True):
        out.append('<text x="%s" y="%s" font-size="%d" text-anchor="middle" fill="%s"%s>%s</text>' % (n(px(x)), n(pz(z)), size, color, ' font-weight="bold"' if bold else "", esc(text)))
    for p in plots:
        label(float(p[2]), float(p[3]) + 4, "Plot %s" % p[1], 15, "#f4f1ea")
        label(float(p[2]), float(p[3]) - 6, "(room, 60 x 60)", 10, "#dfe3ea", False)
    for t in texts:
        if t[1].startswith("StreetSign"):
            label(float(t[3]), float(t[4]) + 6, "sign " + t[2], 10, "#1c1e26")
    spawn = next(r for r in parts if r[1] == "Spawn")
    label((float(spawn[5]) + float(spawn[6])) / 2, min(float(r[9]) for r in world) - 6, "spawn plaza, around the SpawnLocation (Studio fact)", 11)
    lounge = [r for r in parts if r[1] == "Lounge"]
    lz = max(float(r[10]) for r in lounge)
    label(0, (min(float(r[9]) for r in lounge) + lz) / 2, "VIP Lounge", 13, "#1c1e26")
    label(0, lz + 1.5, "door", 9, "#1c1e26", False)
    front = [r for r in world if r[3].startswith("FrontStreet")]
    back = [r for r in world if r[3].startswith("BackStreet")]
    if front:
        label((float(front[0][5]) + float(front[0][6])) / 2, (float(front[0][9]) + float(front[0][10])) / 2 - 1.5, "front street", 11)
    if back:
        label((float(back[0][5]) + float(back[0][6])) / 2, (float(back[0][9]) + float(back[0][10])) / 2 - 1.5, "back street", 11)
    # Scale bar and compass
    bar_x, bar_y = pad_side + 10, pad_top + height_map + 24
    out.append('<rect x="%d" y="%d" width="%s" height="6" fill="#1c1e26"/>' % (bar_x, bar_y, n(50 * scale)))
    out.append('<text x="%d" y="%d" font-size="12" fill="#1c1e26">50 studs</text>' % (bar_x + int(50 * scale) + 8, bar_y + 7))
    out.append('<text x="%d" y="%d" font-size="12" fill="#1c1e26">Paving and streets: light gray and sand. Kerbs: white. Lawns: green tints. Trees and bushes: round greens. '
               'Lamps: dark squares (yellow circle: a lit lamp\'s light).</text>' % (bar_x + 180, bar_y + 7))
    # The whole Baseplate, with the hills
    m_top = pad_top + height_map + 50
    side = inset - 20
    bx0, bx1, bz0, bz1 = (float(v) for v in base[1:5])
    mscale = side / (bx1 - bx0)

    def mx(x):
        return pad_side + (x - bx0) * mscale

    def mz(z):
        return m_top + (bz1 - z) * mscale
    out.append('<text x="%d" y="%d" font-size="13" font-weight="bold" fill="#1c1e26">The whole Baseplate (2048 x 2048, Studio fact) with the far hills</text>' % (pad_side, m_top - 6))
    out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="%s" stroke="#1c1e26"/>' % (n(mx(bx0)), n(mz(bz1)), n(side), n(side), hexc(base[5], base[6], base[7])))
    for r in parts:
        if r[0] == "W" and r[1] == "Hills":
            cx, cz = (float(r[5]) + float(r[6])) / 2, (float(r[9]) + float(r[10])) / 2
            rad = (float(r[6]) - float(r[5])) / 2
            cy = (float(r[7]) + float(r[8])) / 2
            ground = math.sqrt(max(rad * rad - cy * cy, 0))
            out.append('<circle cx="%s" cy="%s" r="%s" fill="%s" stroke="#1c1e26" stroke-width="0.5"/>' % (n(mx(cx)), n(mz(cz)), n(ground * mscale), hexc(r[11], r[12], r[13])))
    out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#c0392b" stroke-width="1.2"/>' % (n(mx(x0)), n(mz(z1)), n((x1 - x0) * mscale), n((z1 - z0) * mscale)))
    pv = next(r for r in rows if r[0] == "PREVIEWSTAGES")
    if float(pv[2]) != 0:
        out.append('<rect x="%s" y="%s" width="%s" height="%s" fill="none" stroke="#7f8c8d" stroke-dasharray="3,2"/>' % (
            n(mx(float(pv[1]))), n(mz(float(pv[4]))), n((float(pv[2]) - float(pv[1])) * mscale), n((float(pv[4]) - float(pv[3])) * mscale)))
    note_x = pad_side + side + 24
    for i, line in enumerate([
        "Red frame: the big map above. Green circles: the six low hills (sunk spheres, seen where they meet the ground).",
        "Dashed gray: the Studio-only preview rooms (PREVIEW_STAGES), which the world keeps out of.",
        "Parts in the world: %d (budget 600). Lights: %d (budget 8)." % (sum(1 for r in parts if r[0] == "W"), sum(1 for r in parts if r[0] == "W" and r[15] == "1")),
        "The plots, their signs, the lounge and the spawn pad are the game's own objects, drawn where the real code puts them.",
    ]):
        out.append('<text x="%d" y="%d" font-size="12" fill="#1c1e26">%s</text>' % (note_x, m_top + 18 + i * 20, esc(line)))
    out.append("</svg>")
    return "\n".join(out) + "\n"


# The icons sheet --------------------------------------------------------------------------------------------------------

def icons_svg():
    rows = run(head_of(icon_test.icon_source()) + ICONS_DUMP)
    hud_colors = dict(re.findall(r"(\w+) = (\{ \d+, \d+, \d+ \})", icon_test.hud_colors_lua()))
    hud_rgb = {k: [int(x) for x in re.findall(r"\d+", v)] for k, v in hud_colors.items()}
    style_outline = 4.0
    corner = 0.22
    icons, current = [], None
    for r in rows:
        if r[0] == "I":
            current = {"group": r[1], "key": r[2], "name": r[3], "kind": r[4], "plate": [float(v) for v in r[5:8]], "items": []}
            icons.append(current)
        elif current is not None:
            current["items"].append(r)
    cols, cell_w, cell_h, size = 8, 132, 150, 96
    width = cols * cell_w + 40
    height = 90 + ((len(icons) + cols - 1) // cols) * cell_h + 30
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" font-family="Helvetica, Arial, sans-serif">' % (width, height, width, height)]
    out.append('<rect width="100%" height="100%" fill="#1c1e26"/>')
    out.append('<text x="20" y="32" font-size="20" font-weight="bold" fill="#f4f1ea">Icons sheet (approximation)</text>')
    out.append('<text x="20" y="54" font-size="12" fill="#c9cdd8">Every icon of IconArt at 96 px, drawn by tools/render_previews.py from the same data and fake Roblox as the tests: '
               'drawn icons from their shapes,</text>')
    out.append('<text x="20" y="72" font-size="12" fill="#c9cdd8">3D icons as box faces through their own camera, lit from the top-left. No materials, no real font: '
               'only Studio shows the real thing (56 px on cards, 72 px on the biggest card).</text>')
    gid = 0
    for i, icon in enumerate(icons):
        ox = 20 + (i % cols) * cell_w + (cell_w - size) / 2
        oy = 90 + (i // cols) * cell_h
        k = size / 100.0
        out.append('<g transform="translate(%s,%s)">' % (n(ox), n(oy)))
        out.append('<rect x="-12" y="-6" width="%d" height="%d" rx="10" fill="#2a2d38"/>' % (cell_w - 12, cell_h - 12))
        if icon["group"] == "Hud" and icon["key"] in hud_rgb:
            out.append('<rect x="4" y="4" width="88" height="88" rx="18" fill="%s"/>' % hexc(*hud_rgb[icon["key"]]))
        if icon["plate"][0] >= 0:
            pc = icon["plate"]
            out.append('<circle cx="48" cy="48" r="%s" fill="#1c1e26"/>' % n((46 + style_outline) * k))
            out.append('<circle cx="48" cy="48" r="%s" fill="%s"/>' % (n(46 * k), hexc(*pc)))
        if icon["kind"] == "ui":
            shapes = [s for s in icon["items"] if s[0] == "U"]
            defs = []

            def shape_svg(s, grow, outline_copy):
                nonlocal gid
                kind = s[1]
                x, y, w, h, rot = (float(v) for v in s[3:8])
                color = hexc(s[8], s[9], s[10])
                transparency, shade, thickness, text = float(s[11]), s[13] == "1", float(s[14]), s[15]
                x, y, w, h = x - grow, y - grow, w + 2 * grow, h + 2 * grow
                cx, cy = (x + w / 2) * k, (y + h / 2) * k
                angle = rot + (45 if kind == "diamond" else 0)
                tf = ' transform="rotate(%s %s %s)"' % (n(angle), n(cx), n(cy)) if angle else ""
                fill = "#1c1e26" if outline_copy else color
                if shade and not outline_copy:
                    gid += 1
                    defs.append('<linearGradient id="g%d" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="%s"/><stop offset="1" stop-color="%s"/></linearGradient>' % (
                        gid, color, hexc(s[8], s[9], s[10], 0.72)))
                    fill = "url(#g%d)" % gid
                opacity = "" if outline_copy or transparency == 0 else ' fill-opacity="%s"' % n(1 - transparency)
                if kind == "text":
                    if outline_copy:
                        return ""
                    return '<text x="%s" y="%s" font-size="%s" font-weight="bold" text-anchor="middle" dominant-baseline="central" fill="%s"%s>%s</text>' % (
                        n(cx), n(cy), n(h * k * 0.82), color, tf, esc(text))
                if kind in ("ring", "frame"):
                    line = (thickness + (2 * style_outline if outline_copy else 0)) * k
                    stroke = "#1c1e26" if outline_copy else color
                    if kind == "ring":
                        return '<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="%s"/>' % (n(cx), n(cy), n(w * k / 2), stroke, n(line))
                    return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="none" stroke="%s" stroke-width="%s"%s/>' % (
                        n(x * k), n(y * k), n(w * k), n(h * k), n(corner * min(w, h) * k), stroke, n(line), tf)
                if kind == "circle":
                    return '<circle cx="%s" cy="%s" r="%s" fill="%s"%s/>' % (n(cx), n(cy), n(w * k / 2), fill, opacity)
                rx = min(w, h) / 2 if kind == "pill" else corner * min(w, h) * (0.6 if kind == "diamond" else 1)
                return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s%s/>' % (n(x * k), n(y * k), n(w * k), n(h * k), n(rx * k), fill, opacity, tf)

            body = [shape_svg(s, style_outline, True) for s in shapes if s[12] == "1"]
            body += [shape_svg(s, 0, False) for s in shapes]
            if defs:
                out.append("<defs>" + "".join(defs) + "</defs>")
            out.extend(b for b in body if b)
        else:
            gid += 1
            out.append('<defs><clipPath id="c%d"><rect x="0" y="0" width="96" height="96"/></clipPath></defs><g clip-path="url(#c%d)">' % (gid, gid))
            items = sorted((r for r in icon["items"] if r[0] in ("Q", "B")), key=lambda r: -float(r[1]))
            for r in items:
                if r[0] == "Q":
                    bright = 1.0 if r[5] == "1" else float(r[6])
                    pts = [float(v) for v in r[7:15]]
                    out.append('<polygon points="%s" fill="%s" stroke="#1c1e26" stroke-width="0.35" stroke-opacity="0.45"/>' % (
                        " ".join("%s,%s" % (n(pts[j]), n(pts[j + 1])) for j in range(0, 8, 2)), hexc(r[2], r[3], r[4], bright)))
                else:
                    cx, cy, rx, ry = (float(v) for v in r[6:10])
                    base = 1.0 if r[5] == "1" else 0.82
                    out.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="%s" stroke="#1c1e26" stroke-width="0.35" stroke-opacity="0.45"/>' % (
                        n(cx), n(cy), n(rx), n(ry), hexc(r[2], r[3], r[4], base)))
                    out.append('<ellipse cx="%s" cy="%s" rx="%s" ry="%s" fill="#ffffff" fill-opacity="0.22"/>' % (n(cx - rx * 0.3), n(cy - ry * 0.3), n(rx * 0.45), n(ry * 0.45)))
            out.append("</g>")
        caption = "%s: %s" % (icon["group"], icon["name"])
        out.append('<text x="48" y="%d" font-size="11" text-anchor="middle" fill="#f4f1ea">%s</text>' % (size + 22, esc(caption)))
        out.append('<text x="48" y="%d" font-size="9" text-anchor="middle" fill="#9aa0ae">%s</text>' % (size + 36, "3D (ViewportFrame)" if icon["kind"] != "ui" else "drawn shapes"))
        out.append("</g>")
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    pictures = ((WORLD_SVG, world_svg()), (ICONS_SVG, icons_svg()))
    if "--check" in sys.argv:
        stale = []
        for path, text in pictures:
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                stale.append(os.path.relpath(path, ROOT))
        print("previews up to date" if not stale else "previews out of date (run python3 tools/render_previews.py): " + ", ".join(stale))
        return 1 if stale else 0
    os.makedirs(OUT_DIR, exist_ok=True)
    for path, text in pictures:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        print("wrote %s (%d bytes)" % (os.path.relpath(path, ROOT), len(text.encode("utf-8"))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
