#!/usr/bin/env python3
"""The World Today - Wednesday 25 November 2026.

One dense 1024x1024 image summing up world news of 25 November 2026.
Pure Python stdlib, deterministic, no network. Two runs are byte-identical.

Layout (learned from the Nov 23 / Nov 24 top-5 entries, format only):
  36 stories numbered 1-36: 3 hero cards + 10 small illustrated cards
  + 23 one-liners (14-36) beside a world map; counted region bar that sums
  to 36; UTC timeline + day-in-numbers strip (figures tied to story
  numbers); certainty tag + named source on every lead card; red DATE
  CHECK box naming what was left out; light cream paper, black serif
  masthead, red/navy accents.

Rendering: 2x supersampling with true device-space rasterisation
(geometry computed at 2048 and averaged down); hand-built 5x7 bitmap
font, drawn at scale 1 (small text), 2 (card headlines) and 4
(masthead); world map from hand-written coastline coordinates.

Output: $MAKEFUN_OUTPUT_DIR/entry.png when set, else ./entry.png
(the grader runs read-only in /bot with only /output writable).
"""
import os
import struct
import sys
import zlib

W, H = 1024, 1024
SS = 2                      # supersampling factor
DW, DH = W * SS, H * SS

# ---------------------------------------------------------------- palette
PAPER = (247, 242, 231)
INK = (26, 26, 26)
RED = (176, 30, 36)
NAVY = (31, 58, 95)
BLUE = (43, 92, 140)
GOLD = (176, 132, 40)
GREY = (110, 105, 94)
LGREY = (214, 208, 195)
WHITE = (255, 255, 255)
CREAM2 = (238, 231, 214)
SKY = (213, 228, 238)
SEA = (190, 211, 226)
GREEN = (46, 110, 62)
ORANGE = (198, 102, 30)

REGION_COLORS = {
    "EUROPE": (31, 58, 95),
    "ASIA": (176, 30, 36),
    "AMERICAS": (43, 92, 140),
    "MIDDLE EAST": (198, 102, 30),
    "AFRICA": (46, 110, 62),
    "OCEANIA": (120, 72, 140),
    "WORLD": (110, 105, 94),
}

# ---------------------------------------------------------------- 5x7 font
# Each glyph: 7 rows of 5 bits, '#' = ink. Uppercase + digits + punctuation.
FONT = {
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
    "C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
    "D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
    "H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
    "I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
    "J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
    "K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
    "L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
    "O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
    "P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
    "Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
    "T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
    "U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
    "V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
    "W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
    "X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
    "Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
    "Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
    "0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
    "1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
    "2": ("01110", "10001", "00001", "00110", "01000", "10000", "11111"),
    "3": ("11111", "00010", "00100", "00010", "00001", "10001", "01110"),
    "4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
    "5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
    "6": ("00110", "01000", "10000", "11110", "10001", "10001", "01110"),
    "7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
    "8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
    "9": ("01110", "10001", "10001", "01111", "00001", "00010", "01100"),
    " ": ("00000", "00000", "00000", "00000", "00000", "00000", "00000"),
    ".": ("00000", "00000", "00000", "00000", "00000", "01100", "01100"),
    ",": ("00000", "00000", "00000", "00000", "01100", "00100", "01000"),
    ":": ("00000", "01100", "01100", "00000", "01100", "01100", "00000"),
    ";": ("00000", "01100", "01100", "00000", "01100", "00100", "01000"),
    "!": ("00100", "00100", "00100", "00100", "00100", "00000", "00100"),
    "?": ("01110", "10001", "00001", "00110", "00100", "00000", "00100"),
    "'": ("00100", "00100", "01000", "00000", "00000", "00000", "00000"),
    '"': ("01010", "01010", "00000", "00000", "00000", "00000", "00000"),
    "-": ("00000", "00000", "00000", "01110", "00000", "00000", "00000"),
    "\u2013": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "\u2014": ("00000", "00000", "00000", "11111", "00000", "00000", "00000"),
    "(": ("00010", "00100", "01000", "01000", "01000", "00100", "00010"),
    ")": ("01000", "00100", "00010", "00010", "00010", "00100", "01000"),
    "/": ("00001", "00010", "00010", "00100", "01000", "01000", "10000"),
    "$": ("00100", "01111", "10100", "01110", "00101", "11110", "00100"),
    "%": ("11001", "11010", "00010", "00100", "01000", "01011", "10011"),
    "+": ("00000", "00100", "00100", "11111", "00100", "00100", "00000"),
    "&": ("01100", "10010", "10100", "01000", "10101", "10010", "01101"),
    "*": ("00000", "10101", "01110", "10101", "00000", "00000", "00000"),
    "=": ("00000", "00000", "11111", "00000", "11111", "00000", "00000"),
    "<": ("00010", "00100", "01000", "10000", "01000", "00100", "00010"),
    ">": ("01000", "00100", "00010", "00001", "00010", "00100", "01000"),
    "#": ("01010", "01010", "11111", "01010", "11111", "01010", "01010"),
    "@": ("01110", "10001", "10111", "10101", "10110", "10000", "01110"),
    "_": ("00000", "00000", "00000", "00000", "00000", "00000", "11111"),
    "[": ("01110", "01000", "01000", "01000", "01000", "01000", "01110"),
    "]": ("01110", "00010", "00010", "00010", "00010", "00010", "01110"),
    "\u2022": ("00000", "00000", "01100", "01100", "01100", "00000", "00000"),
    "\u00b7": ("00000", "00000", "00000", "01100", "01100", "00000", "00000"),
    "x": ("00000", "10001", "01010", "00100", "01010", "10001", "00000"),
    "~": ("00000", "00000", "01101", "10010", "00000", "00000", "00000"),
    "\u00b0": ("01100", "10010", "10010", "01100", "00000", "00000", "00000"),
    "\u2192": ("00000", "00100", "00010", "11111", "00010", "00100", "00000"),
}
ACCENTS = {"\u00c9": "E", "\u00e9": "E", "\u00c8": "E", "\u00e8": "E",
           "\u00c1": "A", "\u00e1": "A", "\u00cd": "I", "\u00ed": "I",
           "\u00d3": "O", "\u00f3": "O", "\u00da": "U", "\u00fa": "U",
           "\u00d6": "O", "\u00f6": "O", "\u00dc": "U", "\u00fc": "U",
           "\u00c7": "C", "\u00e7": "C", "\u00d1": "N", "\u00f1": "N"}


def norm_char(ch):
    if ch in FONT:
        return ch
    if ch in ACCENTS:
        return ACCENTS[ch]
    if ch.islower():
        return ch.upper()
    return "?"


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self):
        self.px = bytearray(DW * DH * 3)
        self.fill(PAPER)

    def fill(self, color):
        r, g, b = color
        row = bytes((r, g, b)) * DW
        for y in range(DH):
            o = y * DW * 3
            self.px[o:o + DW * 3] = row

    def _clip(self, x, y, w, h):
        x0 = max(0, x)
        y0 = max(0, y)
        x1 = min(DW, x + w)
        y1 = min(DH, y + h)
        return x0, y0, x1, y1

    def rect(self, x, y, w, h, color):
        """Filled rect in device pixels."""
        x0, y0, x1, y1 = self._clip(x, y, w, h)
        if x1 <= x0 or y1 <= y0:
            return
        r, g, b = color
        span = bytes((r, g, b)) * (x1 - x0)
        for yy in range(y0, y1):
            o = (yy * DW + x0) * 3
            self.px[o:o + len(span)] = span

    def line(self, x0, y0, x1, y1, color, w=1):
        """Thick line in device pixels (Bresenham steps)."""
        dx = x1 - x0
        dy = y1 - y0
        steps = max(abs(dx), abs(dy), 1)
        hw = w // 2
        for i in range(steps + 1):
            x = x0 + dx * i // steps
            y = y0 + dy * i // steps
            self.rect(x - hw, y - hw, w, w, color)

    def circle(self, cx, cy, r, color):
        for dy in range(-r, r + 1):
            dx = int((r * r - dy * dy) ** 0.5)
            self.rect(cx - dx, cy + dy, 2 * dx + 1, 1, color)

    def poly(self, pts, color):
        """Scanline polygon fill, device pixels."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        for y in range(max(0, min(ys)), min(DH, max(ys) + 1)):
            xs = []
            n = len(pts)
            for i in range(n):
                x0, y0 = pts[i]
                x1, y1 = pts[(i + 1) % n]
                if y0 == y1:
                    continue
                if (y0 <= y < y1) or (y1 <= y < y0):
                    x = x0 + (y - y0) * (x1 - x0) / (y1 - y0)
                    xs.append(x)
            xs.sort()
            for i in range(0, len(xs) - 1, 2):
                self.rect(int(xs[i]), y, max(1, int(xs[i + 1]) - int(xs[i])), 1, color)


# Logical-coordinate helpers (all drawing code uses logical 1024 space).
cv = Canvas()


def R(x, y, w, h, color):
    cv.rect(int(x * SS), int(y * SS), int(w * SS), int(h * SS), color)


def L(x0, y0, x1, y1, color, w=1):
    cv.line(int(x0 * SS), int(y0 * SS), int(x1 * SS), int(y1 * SS), color,
            max(1, int(w * SS)))


def C(cx, cy, r, color):
    cv.circle(int(cx * SS), int(cy * SS), max(1, int(r * SS)), color)


def P(pts, color):
    cv.poly([(int(x * SS), int(y * SS)) for x, y in pts], color)


def text_w(s, scale):
    return len(s) * 6 * scale - scale


def T(x, y, s, scale, color):
    """Draw uppercase text at logical (x, y); scale = logical px per font px."""
    s = "".join(norm_char(ch) for ch in s)
    px = int(scale * SS)
    for ci, ch in enumerate(s):
        glyph = FONT.get(ch, FONT["?"])
        gx = int(x * SS) + ci * 6 * px
        gy = int(y * SS)
        for row in range(7):
            bits = glyph[row]
            for col in range(5):
                if bits[col] == "1":
                    cv.rect(gx + col * px, gy + row * px, px, px, color)


def T_center(cx, y, s, scale, color):
    T(cx - text_w(s, scale) / 2, y, s, scale, color)


def T_right(x, y, s, scale, color):
    T(x - text_w(s, scale), y, s, scale, color)


def wrap(text, max_chars):
    words = text.split()
    lines, cur = [], ""
    for wd in words:
        if cur and len(cur) + 1 + len(wd) > max_chars:
            lines.append(cur)
            cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        lines.append(cur)
    return lines


# ---------------------------------------------------------------- PNG out
def png_bytes():
    # Average each 2x2 device block down to one 1024 pixel.
    raw = bytearray()
    for y in range(H):
        raw.append(0)  # filter: none
        for x in range(W):
            for ch in range(3):
                s = 0
                for dy in range(SS):
                    base = ((y * SS + dy) * DW + x * SS) * 3 + ch
                    s += cv.px[base] + cv.px[base + 3]
                raw.append((s + 2) // 4)
    data = zlib.compress(bytes(raw), 6)

    def chunk(typ, payload):
        c = struct.pack(">I", len(payload)) + typ + payload
        return c + struct.pack(">I", zlib.crc32(typ + payload) & 0xFFFFFFFF)

    out = b"\x89PNG\r\n\x1a\n"
    out += chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
    out += chunk(b"IDAT", data)
    out += chunk(b"IEND", b"")
    return out

# ---------------------------------------------------------------- stories
# tag: CONFIRMED / OFFICIAL / REPORTED / CLAIM. Source named per lead card.
# place: (lon, lat) for map pins 1-13.
STORIES = [
    # --- heroes 1-3
    dict(n=1, region="ASIA", tag="CONFIRMED", src="REUTERS",
         place=(127.0, 37.6),
         head="ASIA CHIP STOCKS PLUNGE AS TARIFF PROBE LOOMS",
         deck="KOSPI falls 5.3%, Taiwan 5.1% and Nikkei 2.9% at the worst point as Washington prepares new duties.",
         scene="chart"),
    dict(n=2, region="ASIA", tag="OFFICIAL", src="REUTERS",
         place=(100.3, 41.0),
         head="SHENZHOU-24 CARRIES FIRST PAKISTANI ASTRONAUT",
         deck="Long March rocket lifts off 00:18 UTC from Jiuquan; Muhammad Zeeshan Ali, 40, first foreigner aboard Tiangong.",
         scene="rocket"),
    dict(n=3, region="AMERICAS", tag="REPORTED", src="REUTERS",
         place=(-77.0, 38.9),
         head="TRUMP READIES NEW TARIFFS AFTER CAPACITY PROBE",
         deck="USTR findings on 16 trading partners, China and the EU included, expected today; duties would stack on existing tariffs.",
         scene="tariffs"),
    # --- small cards 4-13
    dict(n=4, region="ASIA", tag="CONFIRMED", src="REUTERS",
         place=(-74.0, 40.7),
         head="HUAWEI GUILTY ON 10 OF 12 COUNTS IN BROOKLYN",
         deck="Jury convicts on fraud and sanctions charges; sentencing 14 Sep 2027.",
         scene="gavel"),
    dict(n=5, region="EUROPE", tag="CONFIRMED", src="REUTERS",
         place=(30.7, 46.5),
         head="ODESA STRIKE KILLS 2; KYIV SAYS LIBYA SHIP HIT WAS SELF-DEFENCE",
         deck="Russian corvette Merkury sunk off Benghazi; Zaporizhzhia hit leaves 2 dead, 48 wounded.",
         scene="ship"),
    dict(n=6, region="AMERICAS", tag="OFFICIAL", src="AP",
         place=(-86.8, 36.2),
         head="DEMOCRATS CLINCH HOUSE WITH 259 SEATS",
         deck="Largest majority since 1990 after Broderick wins Tennessee-04; Republicans at 173.",
         scene="capitol"),
    dict(n=7, region="AMERICAS", tag="REPORTED", src="REUTERS",
         place=(-122.0, 37.4),
         head="HUANG APOLOGISES, IN THERAPY; NVIDIA SLIDES 5.9%",
         deck="Reinstated chief tells staff he violated the code of conduct; shares fall after Monday's 31.5% surge.",
         scene="chip"),
    dict(n=8, region="MIDDLE EAST", tag="CONFIRMED", src="REUTERS",
         place=(56.3, 26.5),
         head="THREE VESSELS HIT NEAR STRAIT OF HORMUZ",
         deck="UKMTO reports projectiles east through the strait; Brent eases to $90.97.",
         scene="tanker"),
    dict(n=9, region="MIDDLE EAST", tag="CONFIRMED", src="REUTERS",
         place=(34.5, 31.5),
         head="GAZA STRIKE KILLS HAMAS SECURITY CHIEF",
         deck="Naeem Abu Nahel killed in Gaza City; at least 6 Palestinians killed Tuesday.",
         scene="city"),
    dict(n=10, region="AFRICA", tag="OFFICIAL", src="REUTERS",
         place=(-17.4, 14.7),
         head="SENEGAL REINSTATED AS AFRICAN CHAMPIONS",
         deck="CAS restores 1-0 extra-time win over Morocco; CAF's 3-0 forfeit set aside.",
         scene="trophy"),
    dict(n=11, region="OCEANIA", tag="OFFICIAL", src="REUTERS",
         place=(151.2, -33.9),
         head="AUSTRALIA CPI JUMPS TO 4.9%, HIGHEST IN 3 YEARS",
         deck="October inflation beats 4.7% forecast; trimmed mean 3.8% as fuel and clothing climb.",
         scene="bars"),
    dict(n=12, region="OCEANIA", tag="OFFICIAL", src="REUTERS",
         place=(149.1, -35.3),
         head="AUSTRALIA APOLOGISES TO LGBTQ VETERANS",
         deck="Defence minister Marles says sorry in parliament for decades of 'witch hunts' and discharges.",
         scene="parliament"),
    dict(n=13, region="EUROPE", tag="OFFICIAL", src="REUTERS",
         place=(-0.1, 51.5),
         head="UK SANCTIONS HOUTHIS AND FOUR SENIOR FIGURES",
         deck="Group designated under Yemen regime over torture and rape; accused of hitting Saudi civilian sites.",
         scene="document"),
    # --- one-liners 14-36 (headline, region, tag, source)
    dict(n=14, region="MIDDLE EAST", tag="REPORTED", src="AP",
         head="IRAN RULES OUT US TALKS"),
    dict(n=15, region="MIDDLE EAST", tag="CONFIRMED", src="BBC",
         head="SYRIA MINES HIT 995 CHILDREN"),
    dict(n=16, region="ASIA", tag="REPORTED", src="REUTERS",
         head="HASINA TO RETURN 16 DEC"),
    dict(n=17, region="ASIA", tag="OFFICIAL", src="REUTERS",
         head="JAPAN SERVICE PRICES +4.2%"),
    dict(n=18, region="ASIA", tag="REPORTED", src="CRISIL",
         head="INDIA CPI 6.1%, FOOD 8.9%"),
    dict(n=19, region="ASIA", tag="CONFIRMED", src="BBC",
         head="N. KOREAN CHRISTIANS JAILED"),
    dict(n=20, region="WORLD", tag="CONFIRMED", src="REUTERS",
         head="RECORD QUASAR AFTER BIG BANG"),
    dict(n=21, region="EUROPE", tag="CONFIRMED", src="BBC",
         head="RUSSIA: 490,334 SOLDIERS DEAD"),
    dict(n=22, region="EUROPE", tag="REPORTED", src="REUTERS",
         head="UKRAINE NEEDS $125BN IN 2027"),
    dict(n=23, region="EUROPE", tag="OFFICIAL", src="REUTERS",
         head="NATO AWACS TO POLAND"),
    dict(n=24, region="EUROPE", tag="REPORTED", src="REUTERS",
         head="SARKOZY, BRUNI TO STAND TRIAL"),
    dict(n=25, region="EUROPE", tag="REPORTED", src="AP",
         head="PELICOT TO SUE PUBLISHER"),
    dict(n=26, region="EUROPE", tag="OFFICIAL", src="UKHSA",
         head="ENGLAND: 5,258 HEAT DEATHS"),
    dict(n=27, region="EUROPE", tag="CONFIRMED", src="FIDE",
         head="CHESS: GUKESH-SINDAROV DRAW"),
    dict(n=28, region="EUROPE", tag="OFFICIAL", src="UEFA",
         head="REAL MADRID 5-1 PSV"),
    dict(n=29, region="EUROPE", tag="OFFICIAL", src="ATP",
         head="DAVIS CUP: CZECHIA WIN 2-0"),
    dict(n=30, region="EUROPE", tag="REPORTED", src="BBC",
         head="POPE DIARY: 'I SAW THE DEVIL'"),
    dict(n=31, region="AFRICA", tag="REPORTED", src="REUTERS",
         head="175 MIGRANTS LOST OFF SENEGAL"),
    dict(n=32, region="AFRICA", tag="REPORTED", src="REUTERS",
         head="DRC EBOLA TOLL 'OVER 1,000'"),
    dict(n=33, region="AMERICAS", tag="CONFIRMED", src="BBC",
         head="COLOMBIA CAR BOMB WOUNDS 23"),
    dict(n=34, region="AFRICA", tag="CONFIRMED", src="BBC",
         head="EMIR OF DAURA, 92, SUSPENDED"),
    dict(n=35, region="AMERICAS", tag="REPORTED", src="REUTERS",
         head="MICROSOFT 'CODE RED' MEMOS*"),
    dict(n=36, region="OCEANIA", tag="CONFIRMED", src="BBC",
         head="SYDNEY EX-POLICEMAN GUILTY"),
]

REGIONS = [("EUROPE", 12), ("ASIA", 7), ("AMERICAS", 5), ("MIDDLE EAST", 4),
           ("AFRICA", 4), ("OCEANIA", 3), ("WORLD", 1)]

NUMBERS = [
    ("-5.3%", "KOSPI, WORST POINT", 1),
    ("$90.97", "BRENT CRUDE, 01:37 UTC", 8),
    ("259", "HOUSE SEATS, DEMOCRATS", 6),
    ("490,334", "RUSSIAN SOLDIERS DEAD*", 21),
    ("5,258", "ENGLAND HEAT DEATHS", 26),
    ("4.9%", "AUSTRALIA CPI, OCT", 11),
]

TIMELINE = [
    ("00:18", "SHENZHOU LAUNCH", 2, False),
    ("00:30", "AUS CPI 4.9%", 11, False),
    ("01:16", "AUS APOLOGY", 12, False),
    ("01:37", "BRENT $90.97", 8, False),
    ("13:30", "DUE US PCE + GDP", None, True),
    ("14:00", "DUE CHESS GAME 2", 27, True),
    ("15:00", "DUE IOWA BLAST", None, True),
]

# ---------------------------------------------------------------- world map
# Hand-written simplified coastline polygons (lon, lat).
MAP_POLYS = [
    # North America
    [(-168, 66), (-161, 58), (-153, 58), (-145, 60), (-137, 58), (-131, 54),
     (-125, 49), (-124, 40), (-121, 34), (-117, 32), (-112, 29), (-109, 24),
     (-106, 22), (-102, 18), (-97, 16), (-93, 15), (-89, 14), (-86, 12),
     (-83, 9), (-80, 8), (-81, 12), (-84, 15), (-87, 16), (-88, 17),
     (-91, 19), (-91, 21), (-97, 26), (-94, 29), (-90, 29), (-85, 30),
     (-82, 28), (-81, 26), (-80, 32), (-76, 35), (-75, 38), (-74, 40),
     (-71, 42), (-68, 44), (-65, 44), (-60, 46), (-56, 47), (-60, 50),
     (-64, 50), (-61, 52), (-64, 58), (-68, 58), (-73, 60), (-78, 62),
     (-82, 66), (-88, 66), (-94, 68), (-102, 68), (-112, 68), (-122, 70),
     (-134, 69), (-145, 70), (-157, 71), (-165, 68)],
    # Greenland
    [(-58, 64), (-53, 60), (-44, 60), (-41, 63), (-35, 66), (-30, 68),
     (-24, 70), (-20, 74), (-26, 76), (-35, 77), (-48, 76), (-56, 74),
     (-60, 70)],
    # South America
    [(-79, 9), (-77, 4), (-80, -3), (-81, -6), (-78, -10), (-74, -16),
     (-70, -20), (-70, -26), (-71, -32), (-73, -38), (-73, -44),
     (-74, -50), (-70, -54), (-66, -55), (-65, -51), (-62, -46),
     (-58, -40), (-53, -33), (-49, -29), (-44, -24), (-40, -20),
     (-37, -14), (-35, -9), (-35, -6), (-39, -4), (-43, -3), (-48, -1),
     (-51, 2), (-55, 5), (-58, 7), (-62, 9), (-66, 10), (-70, 11),
     (-74, 11), (-77, 9)],
    # Africa
    [(-17, 15), (-16, 19), (-16, 25), (-13, 28), (-10, 31), (-6, 35),
     (-1, 36), (5, 37), (10, 37), (11, 34), (15, 32), (20, 32), (25, 32),
     (30, 31), (33, 30), (35, 28), (37, 24), (38, 21), (41, 16), (43, 12),
     (47, 11), (51, 10), (49, 5), (45, 1), (41, -3), (40, -8), (39, -13),
     (36, -18), (34, -22), (32, -27), (28, -33), (24, -34), (19, -35),
     (16, -30), (14, -24), (12, -18), (13, -12), (12, -6), (10, -2),
     (9, 3), (4, 6), (-3, 5), (-8, 4), (-13, 7), (-16, 11)],
    # Eurasia (Europe + Asia in one outline, via Arabia, India, SE Asia)
    [(-10, 36), (-9, 43), (-3, 44), (-1, 48), (2, 51), (5, 53), (8, 55),
     (8, 58), (6, 61), (11, 65), (16, 69), (22, 70), (28, 71), (34, 69),
     (40, 68), (48, 68), (56, 69), (64, 69), (72, 71), (80, 73), (88, 75),
     (96, 76), (104, 77), (112, 76), (120, 74), (128, 73), (136, 72),
     (144, 71), (152, 70), (160, 69), (168, 66), (176, 65), (178, 62),
     (172, 60), (166, 60), (160, 58), (156, 53), (150, 59), (142, 56),
     (141, 51), (138, 46), (134, 43), (130, 42), (127, 40), (124, 39),
     (121, 37), (120, 34), (122, 31), (120, 28), (115, 23), (110, 21),
     (108, 18), (106, 14), (104, 10), (102, 8), (100, 7), (99, 9),
     (97, 12), (95, 15), (93, 19), (91, 22), (88, 22), (86, 20), (83, 18),
     (80, 15), (79, 10), (77, 8), (75, 11), (73, 16), (71, 20), (68, 23),
     (66, 25), (62, 25), (58, 25), (55, 26), (52, 27), (50, 29), (48, 30),
     (52, 27), (54, 26), (57, 26), (59, 25), (59, 22), (57, 18), (55, 17),
     (52, 15), (48, 14), (45, 13), (43, 13), (41, 16), (39, 20), (37, 24),
     (35, 28), (34, 28), (36, 36), (33, 36), (30, 36), (27, 37), (23, 36),
     (19, 40), (15, 40), (12, 42), (10, 44), (8, 44), (5, 43), (3, 42),
     (0, 39), (-2, 37), (-6, 36)],
    # UK, Iceland, Madagascar, Sri Lanka, Japan, Sumatra, Java, Borneo,
    # New Guinea, Australia, New Zealand, Philippines
    [(-5, 50), (-3, 53), (-5, 56), (-3, 58), (-1, 57), (0, 53), (1, 51),
     (-2, 50)],
    [(-22, 64), (-18, 63), (-15, 64), (-14, 66), (-18, 66), (-22, 65)],
    [(44, -16), (47, -15), (50, -16), (49, -20), (47, -24), (45, -25),
     (44, -21), (43, -17)],
    [(80, 6), (81, 7), (81, 9), (80, 9)],
    [(130, 31), (132, 33), (134, 34), (136, 35), (138, 35), (140, 36),
     (141, 38), (141, 41), (142, 43), (144, 44), (142, 44), (140, 41),
     (139, 38), (137, 37), (135, 34), (133, 34), (131, 32)],
    [(95, 5), (98, 3), (101, 0), (104, -3), (106, -6), (104, -6),
     (101, -4), (98, 0), (95, 3)],
    [(105, -6), (108, -7), (112, -7), (114, -8), (111, -8), (107, -7)],
    [(109, 1), (111, 3), (114, 4), (117, 6), (118, 2), (117, -2),
     (114, -3), (111, -2), (109, 0)],
    [(131, -1), (136, -2), (141, -3), (146, -6), (150, -8), (147, -9),
     (143, -8), (138, -7), (134, -4), (131, -2)],
    [(113, -22), (114, -28), (115, -33), (118, -35), (124, -33),
     (129, -32), (132, -32), (135, -35), (138, -35), (140, -38),
     (145, -38), (150, -37), (153, -32), (153, -27), (150, -23),
     (146, -19), (142, -15), (142, -11), (137, -12), (135, -15),
     (132, -12), (130, -13), (126, -14), (122, -17), (118, -20),
     (114, -21)],
    [(167, -45), (170, -42), (173, -40), (175, -38), (177, -38),
     (175, -41), (173, -42), (170, -44), (167, -46)],
    [(120, 18), (122, 18), (122, 14), (121, 12), (122, 9), (124, 8),
     (123, 10), (121, 13), (120, 16)],
]

# ---------------------------------------------------------------- scenes
def draw_scene(x, y, w, h, kind):
    """Small drawn illustration inside rect (x, y, w, h), logical coords."""
    if kind == "chart":
        R(x, y, w, h, NAVY)
        vals = [("-5.3", 53), ("-5.1", 51), ("-2.9", 29), ("-0.9", 9)]
        bw = w // 5
        for i, (lab, v) in enumerate(vals):
            bx = x + 10 + i * bw
            bh = max(4, (h - 30) * v // 60)
            R(bx, y + h - 22 - bh, bw - 8, bh, RED if i < 2 else GOLD)
            T(bx, y + h - 18, lab, 1, WHITE)
        L(x + 6, y + h - 22, x + w - 6, y + h - 22, WHITE, 1)
        T(x + 8, y + 5, "KOSPI TAIWAN NIKKEI ASX", 1, WHITE)
    elif kind == "rocket":
        R(x, y, w, h, NAVY)
        for sx, sy in [(8, 10), (30, 22), (55, 8), (80, 18), (95, 30),
                       (20, 40), (70, 45), (105, 12)]:
            C(x + sx % w, y + sy % h, 1, WHITE)
        cx = x + w // 2
        P([(cx, y + 12), (cx + 9, y + 30), (cx + 9, y + 62),
           (cx - 9, y + 62), (cx - 9, y + 30)], WHITE)
        P([(cx, y + 12), (cx + 9, y + 30), (cx - 9, y + 30)], RED)
        R(cx - 14, y + 52, 5, 12, RED)
        R(cx + 9, y + 52, 5, 12, RED)
        P([(cx - 6, y + 62), (cx + 6, y + 62), (cx, y + h - 8)], ORANGE)
        C(cx, y + h + 34, 52, BLUE)
        C(cx + 26, y + h + 26, 10, GREEN)
    elif kind == "tariffs":
        R(x, y, w, h, SKY)
        R(x + 10, y + h - 34, w - 20, 16, NAVY)
        P([(x + 6, y + h - 18), (x + w - 6, y + h - 18),
           (x + w - 14, y + h - 6), (x + 14, y + h - 6)], INK)
        for i, c in enumerate([RED, GOLD, BLUE, GREEN]):
            R(x + 16 + i * 22, y + 14, 20, 14, c)
            R(x + 16 + i * 22, y + 30, 20, 14, c)
        T(x + w - 62, y + 8, "301", 2, RED)
        T(x + 12, y + h - 30, "16 PARTNERS", 1, WHITE)
    elif kind == "gavel":
        R(x, y, w, h, CREAM2)
        L(x + 18, y + h - 14, x + w - 22, y + 12, (120, 82, 40), 5)
        R(x + w - 34, y + 8, 22, 12, (120, 82, 40))
        R(x + w - 38, y + 20, 30, 6, (90, 60, 28))
        R(x + 16, y + h - 16, w - 32, 6, (90, 60, 28))
        T(x + 14, y + 6, "10 OF 12", 1, RED)
    elif kind == "ship":
        R(x, y, w, h, SEA)
        P([(x + 12, y + h - 30), (x + w - 12, y + h - 30),
           (x + w - 24, y + h - 12), (x + 24, y + h - 12)], NAVY)
        R(x + w // 2 - 8, y + h - 48, 22, 18, WHITE)
        R(x + 18, y + h - 44, 26, 12, RED)
        R(x + 48, y + h - 44, 26, 12, GOLD)
        L(x + 8, y + h - 8, x + w - 8, y + h - 8, WHITE, 2)
        L(x + 20, y + h - 4, x + w - 20, y + h - 4, WHITE, 1)
    elif kind == "capitol":
        R(x, y, w, h, CREAM2)
        C(x + w // 2, y + 26, 16, WHITE)
        R(x + w // 2 - 16, y + 26, 32, 8, WHITE)
        for i in range(5):
            R(x + 14 + i * 16, y + 36, 7, 18, INK)
        R(x + 10, y + 54, w - 20, 5, INK)
        T(x + w // 2 - 12, y + h - 12, "259", 1, RED)
    elif kind == "chip":
        R(x, y, w, h, NAVY)
        R(x + w // 2 - 16, y + h // 2 - 16, 32, 32, GOLD)
        R(x + w // 2 - 9, y + h // 2 - 9, 18, 18, INK)
        for i in range(4):
            L(x + w // 2 - 16, y + h // 2 - 12 + i * 8,
              x + w // 2 - 26, y + h // 2 - 12 + i * 8, GOLD, 2)
            L(x + w // 2 + 16, y + h // 2 - 12 + i * 8,
              x + w // 2 + 26, y + h // 2 - 12 + i * 8, GOLD, 2)
        T(x + 8, y + 6, "-5.9%", 1, RED)
    elif kind == "tanker":
        R(x, y, w, h, SEA)
        R(x + 8, y + h - 26, w - 16, 12, INK)
        R(x + w - 34, y + h - 42, 18, 16, WHITE)
        C(x + 22, y + h - 40, 7, ORANGE)
        P([(x + 16, y + h - 44), (x + 28, y + h - 44), (x + 22, y + h - 56)],
          ORANGE)
        L(x + 6, y + h - 6, x + w - 6, y + h - 6, WHITE, 2)
        T(x + 8, y + 6, "HORMUZ", 1, WHITE)
    elif kind == "city":
        R(x, y, w, h, (226, 214, 188))
        for i, bh in enumerate([26, 38, 20, 32]):
            R(x + 12 + i * 20, y + h - 14 - bh, 16, bh, GREY)
        C(x + w - 24, y + 16, 5, GREY)
        C(x + w - 30, y + 10, 4, GREY)
        R(x + 8, y + h - 12, w - 16, 4, INK)
    elif kind == "trophy":
        R(x, y, w, h, CREAM2)
        P([(x + w // 2 - 12, y + 10), (x + w // 2 + 12, y + 10),
           (x + w // 2 + 8, y + 34), (x + w // 2 - 8, y + 34)], GOLD)
        L(x + w // 2 - 18, y + 12, x + w // 2 - 12, y + 26, GOLD, 3)
        L(x + w // 2 + 18, y + 12, x + w // 2 + 12, y + 26, GOLD, 3)
        R(x + w // 2 - 3, y + 34, 6, 10, GOLD)
        R(x + w // 2 - 12, y + 44, 24, 5, GOLD)
        T(x + w // 2 - 9, y + h - 12, "1-0", 1, RED)
    elif kind == "bars":
        R(x, y, w, h, NAVY)
        for i, (v, c) in enumerate([(30, RED), (48, WHITE), (38, GOLD)]):
            R(x + 14 + i * 24, y + h - 16 - v, 18, v, c)
        L(x + 8, y + h - 16, x + w - 8, y + h - 16, WHITE, 1)
        T(x + 8, y + 6, "4.9%", 1, WHITE)
    elif kind == "parliament":
        R(x, y, w, h, CREAM2)
        P([(x + 10, y + 22), (x + w - 10, y + 22), (x + w // 2, y + 8)], INK)
        for i in range(4):
            R(x + 14 + i * 20, y + 24, 8, 24, INK)
        R(x + 10, y + 48, w - 20, 5, INK)
    elif kind == "document":
        R(x, y, w, h, CREAM2)
        R(x + w // 2 - 16, y + 8, 32, 42, WHITE)
        L(x + w // 2, y + 8, x + w // 2, y + 50, LGREY, 1)
        for i in range(3):
            L(x + w // 2 - 11, y + 16 + i * 8, x + w // 2 + 11,
              y + 16 + i * 8, GREY, 1)
        C(x + w // 2 + 12, y + h - 12, 7, RED)
        T(x + 8, y + 6, "UK", 1, RED)


# ---------------------------------------------------------------- cards
def hero_card(x, y, w, h, st):
    R(x, y, w, h, WHITE)
    L(x, y, x + w, y, INK, 1)
    L(x, y + h, x + w, y + h, INK, 1)
    L(x, y, x, y + h, INK, 1)
    L(x + w, y, x + w, y + h, INK, 1)
    draw_scene(x + 1, y + 1, w - 2, 100, st["scene"])
    yy = y + 108
    R(x + 8, yy, 16, 10, REGION_COLORS[st["region"]])
    T(x + 28, yy + 1, str(st["n"]) + "  " + st["region"], 1, RED)
    yy += 14
    for ln in wrap(st["head"], 26)[:2]:
        T(x + 8, yy, ln, 2, INK)
        yy += 15
    yy += 2
    for ln in wrap(st["deck"], 50)[:2]:
        T(x + 8, yy, ln, 1, GREY)
        yy += 9
    T(x + 8, y + h - 12, st["tag"] + " - " + st["src"], 1, RED)


def small_card(x, y, w, h, st):
    R(x, y, w, h, WHITE)
    L(x, y, x + w, y, INK, 1)
    L(x, y + h, x + w, y + h, INK, 1)
    L(x, y, x, y + h, INK, 1)
    L(x + w, y, x + w, y + h, INK, 1)
    draw_scene(x + 1, y + 1, w - 2, 56, st["scene"])
    yy = y + 62
    T(x + 8, yy, str(st["n"]) + "  " + st["region"], 1, RED)
    yy += 11
    for ln in wrap(st["head"], 30)[:3]:
        T(x + 8, yy, ln, 1, INK)
        yy += 9
    yy += 1
    for ln in wrap(st["deck"], 30)[:2]:
        T(x + 8, yy, ln, 1, GREY)
        yy += 9
    T(x + 8, y + h - 11, st["tag"] + " - " + st["src"], 1, RED)


# ---------------------------------------------------------------- map
def draw_map(mx, my, mw, mh):
    T(mx, my - 12, "WHERE IT HAPPENED - PINS 1-13", 1, INK)
    R(mx, my, mw, mh, (233, 240, 244))
    L(mx, my, mx + mw, my, INK, 1)
    L(mx, my + mh, mx + mw, my + mh, INK, 1)
    L(mx, my, mx, my + mh, INK, 1)
    L(mx + mw, my, mx + mw, my + mh, INK, 1)
    # graticule
    for lon in range(-150, 181, 30):
        gx = mx + (lon + 180) / 360 * mw
        L(gx, my, gx, my + mh, (210, 220, 230), 1)
    for lat in range(-60, 61, 30):
        gy = my + (78 - lat) / 136 * mh
        L(mx, gy, mx + mw, gy, (210, 220, 230), 1)

    def proj(lon, lat):
        return (mx + (lon + 180) / 360 * mw,
                my + (78 - lat) / 136 * mh)

    for poly in MAP_POLYS:
        pts = [proj(lon, lat) for lon, lat in poly]
        P(pts, (168, 190, 208))
        for i in range(len(pts)):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % len(pts)]
            L(x0, y0, x1, y1, NAVY, 1)
    for st in STORIES[:13]:
        lon, lat = st["place"]
        px, py = proj(lon, lat)
        col = REGION_COLORS[st["region"]]
        C(px, py, 8, col)
        num = str(st["n"])
        T(px - text_w(num, 1) / 2, py - 4, num, 1, WHITE)


# ---------------------------------------------------------------- build
def build():
    MX = 14
    CW = W - 2 * MX  # 996

    # kicker
    T(MX, 12, "THE WORLD IN ONE DAY", 1, RED)
    T_right(MX + CW, 12, "36 STORIES - 7 REGIONS - DAY 329 OF 2026", 1, INK)
    L(MX, 26, MX + CW, 26, INK, 2)

    # masthead
    T_center(MX + CW // 2, 32, "WEDNESDAY 25 NOVEMBER 2026", 4, INK)
    T_center(MX + CW // 2, 64,
             "ASIA CHIP STOCKS PLUNGE - SHENZHOU-24 FLIES - DEMOCRATS TAKE THE HOUSE",
             1, RED)
    L(MX, 78, MX + CW, 78, INK, 1)

    # UTC timeline
    ty = 82
    R(MX, ty, CW, 30, NAVY)
    T(MX + 8, ty + 11, "THE DAY IN UTC", 1, WHITE)
    slots = CW - 130
    for i, (tm, lab, _n, due) in enumerate(TIMELINE):
        sx = MX + 130 + i * slots // 7
        T(sx, ty + 4, tm, 1, GOLD)
        T(sx, ty + 15, lab, 1, WHITE if not due else GOLD)

    # day in numbers
    ny = 118
    bw = (CW - 5 * 5) // 6
    for i, (num, cap, n) in enumerate(NUMBERS):
        bx = MX + i * (bw + 5)
        R(bx, ny, bw, 52, WHITE)
        L(bx, ny, bx + bw, ny, RED, 2)
        L(bx, ny + 52, bx + bw, ny + 52, INK, 1)
        T_center(bx + bw // 2, ny + 7, num, 2, RED)
        T_center(bx + bw // 2, ny + 30, cap, 1, INK)
        T_right(bx + bw - 4, ny + 41, "#" + str(n), 1, GREY)

    # region bar (counts sum to 36; WORLD widened so its label fits)
    ry = 176
    rx = MX
    widths = [315, 193, 138, 110, 110, 83, 47]
    for ri, (name, cnt) in enumerate(REGIONS):
        sw = widths[ri]
        R(rx, ry, sw, 24, REGION_COLORS[name])
        lab = name + " " + str(cnt)
        if text_w(lab, 1) <= sw - 4:
            T_center(rx + sw // 2, ry + 8, lab, 1, WHITE)
        elif text_w(str(cnt), 1) <= sw - 4:
            T_center(rx + sw // 2, ry + 8, str(cnt), 1, WHITE)
        rx += sw
    T_center(MX + CW // 2, ry + 26, "STORIES BY REGION - COUNTS ADD TO 36",
             1, GREY)

    # heroes 1-3
    hy = 208
    hw = (CW - 2 * 12) // 3
    for i, st in enumerate(STORIES[:3]):
        hero_card(MX + i * (hw + 12), hy, hw, 186, st)

    # small cards 4-13 (two rows of five)
    cw = (CW - 4 * 9) // 5
    for row in range(2):
        cy = 402 + row * 150
        for col in range(5):
            st = STORIES[3 + row * 5 + col]
            small_card(MX + col * (cw + 9), cy, cw, 144, st)

    # bottom: map + also-on index
    by = 712
    draw_map(MX, by + 14, 570, 176)
    ix = MX + 584
    iw = CW - 584
    T(ix, by + 2, "ALSO ON WEDNESDAY - 14-36", 1, INK)
    col_w = iw // 2
    for k, st in enumerate(STORIES[13:]):
        col = k // 12
        row = k % 12
        lx = ix + col * col_w
        ly = by + 16 + row * 15
        R(lx, ly + 1, 6, 6, REGION_COLORS[st["region"]])
        line = str(st["n"]) + " " + st["head"]
        maxc = (col_w - 14) // 6
        if len(line) > maxc:
            line = line[:maxc - 1] + ">"
        T(lx + 10, ly, line, 1, INK)

    # date check
    dy = 906
    R(MX, dy, CW, 58, (253, 238, 232))
    L(MX, dy, MX + CW, dy, RED, 2)
    L(MX, dy + 58, MX + CW, dy + 58, RED, 2)
    L(MX, dy, MX, dy + 58, RED, 2)
    L(MX + CW, dy, MX + CW, dy + 58, RED, 2)
    T(MX + 8, dy + 7, "DATE CHECK - 25 NOVEMBER ONLY", 1, RED)
    T(MX + 8, dy + 20,
      "IN: ALL 36 STORIES DATED 24-25 NOV. OUT: GTA VI $3.79BN (19 NOV).",
      1, INK)
    T(MX + 8, dy + 31,
      "MICROSOFT OUTAGE (12-14 NOV) - AFCON FINAL (18 JAN 2026) - SYRIA MINES",
      1, INK)
    T(MX + 8, dy + 42,
      "SINCE DEC 2024 - RUSSIAN DEATHS FEB 2022-SEP 2026 - PCE/GDP DUE 13:30 UTC.",
      1, INK)

    # footer
    fy = 970
    T(MX, fy, "CONFIRMED = MULTIPLE WIRES - OFFICIAL = NAMED AUTHORITY - REPORTED = SINGLE WIRE - CLAIM = UNVERIFIED",
      1, GREY)
    T(MX, fy + 11,
      "SOURCES: REUTERS - AP - BBC - UEFA - ATP - UKHSA - FTC - CRISIL - FIDE. PRESS TIME 03:30 UTC.",
      1, GREY)
    T(MX, fy + 22,
      "* #35 REPORTS THE 24-25 NOV 'CODE RED' MEMOS; THE OUTAGE WAS 12-14 NOV. #21 IS THE REGISTERED COUNT.",
      1, GREY)
    T_right(MX + CW, fy + 22, "THE WORLD TODAY", 1, RED)


def main():
    build()
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or os.getcwd()
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    data = png_bytes()
    with open(path, "wb") as f:
        f.write(data)
    print("wrote %s (%d bytes)" % (path, len(data)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
