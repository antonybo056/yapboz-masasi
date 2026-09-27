"""
Yapboz Masası: Python (pygame) sürümü.

Kendi resmini yükle, parçalara ayır ve yeniden birleştir.
Süre, hamle sayacı, ilerleme, ipuçları ve seviye rekorları içerir.

Çalıştırma:
    pip install pygame
    python yapboz.py

Kısayollar:
    P  duraklat / devam et      S  silik resim
    O  önizleme                 D  tek parçaları yeniden dağıt
    N  yeni oyun ekranı         Esc  pencereyi kapat / geri dön
"""

import json
import math
import os
import random
import time
from array import array

import pygame

APP_DIR = os.path.dirname(os.path.abspath(__file__))
SETTINGS_FILE = os.path.join(APP_DIR, "yapboz_rekorlar.json")

LEVELS = [("kolay", "Kolay", 12), ("orta", "Orta", 35), ("zor", "Zor", 70), ("uzman", "Uzman", 150)]

# Renkler: gece puzzle masası (yeşil keçe + pirinç vurgular)
INK = (16, 24, 22)
PANEL = (23, 34, 31)
PANEL2 = (31, 45, 41)
LINE = (45, 64, 58)
FELT = (42, 82, 71)
FELT_DEEP = (23, 48, 41)
TEXT = (237, 241, 234)
MUTED = (152, 174, 165)
BRASS = (226, 174, 74)
BRASS_HI = (240, 196, 110)
BRASS_INK = (39, 26, 3)
OK = (134, 211, 165)

BAR_H = 68
FPS = 60

# Bir çıkıntının (tab) şablonu: u kenar boyunca, v dışarı doğru (kenar birimi)
TAB = [(0.36, 0), (0.42, 0), (0.44, 0.04), (0.40, 0.10), (0.34, 0.18), (0.36, 0.26), (0.50, 0.26),
       (0.64, 0.26), (0.66, 0.18), (0.60, 0.10), (0.56, 0.04), (0.58, 0), (0.64, 0)]


# ====================================================================
# Yardımcılar
# ====================================================================
def clamp(v, a, b):
    return a if v < a else b if v > b else v


def lerp(c0, c1, k):
    return tuple(int(a + (b - a) * k) for a, b in zip(c0, c1))


def grad_color(stops, t):
    for i in range(len(stops) - 1):
        t0, c0 = stops[i]
        t1, c1 = stops[i + 1]
        if t <= t1:
            return lerp(c0, c1, (t - t0) / (t1 - t0) if t1 > t0 else 0)
    return stops[-1][1]


def fmt_time(sec):
    t = int(sec)
    h, m, s = t // 3600, t % 3600 // 60, t % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def load_settings():
    try:
        with open(SETTINGS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def save_settings(data):
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except OSError:
        pass


# ====================================================================
# Parça geometrisi
# ====================================================================
def grid_for(n, aspect):
    best, bs = None, float("inf")
    for cols in range(2, 41):
        rows = max(2, round(cols / aspect))
        cell = (aspect * rows) / cols
        sc = abs(cols * rows - n) / n + abs(math.log(cell)) * 0.9
        if sc < bs:
            bs, best = sc, (cols, rows)
    return best


def make_edges(cols, rows, rng):
    def e():
        return {"s": 1 if rng.random() < 0.5 else -1, "j": (rng.random() - 0.5) * 0.14, "k": 0.9 + rng.random() * 0.2}
    h = [[e() for _ in range(cols)] for _ in range(rows - 1)]
    v = [[e() for _ in range(cols - 1)] for _ in range(rows)]
    return {"h": h, "v": v}


def edge_pts(L, s, e):
    """Kanonik yatay kenar: (0,0) -> (L,0). Dönüş: P0 + kübik üçlüler."""
    if not e:
        return [(0, 0), (0, 0), (L, 0), (L, 0)]
    cx, sc = L / 2 + e["j"] * s, s * e["k"]
    m = [(cx + (u - 0.5) * sc, v * sc * e["s"]) for u, v in TAB]
    pts = [(0, 0), (0, 0), m[0], m[0]] + m[1:] + [m[-1], (L, 0), (L, 0)]
    return pts


def piece_segs(r, c, cw, ch, E, cols, rows):
    s = min(cw, ch)
    top = edge_pts(cw, s, E["h"][r - 1][c] if r > 0 else None)
    right = [(cw + b, a) for a, b in edge_pts(ch, s, E["v"][r][c] if c < cols - 1 else None)]
    bottom = [(a, ch + b) for a, b in edge_pts(cw, s, E["h"][r][c] if r < rows - 1 else None)][::-1]
    left = [(b, a) for a, b in edge_pts(ch, s, E["v"][r][c - 1] if c > 0 else None)][::-1]
    return [top, right, bottom, left]


def cubic(p0, c1, c2, p1, t):
    u = 1 - t
    a, b, c, d = u * u * u, 3 * u * u * t, 3 * u * t * t, t * t * t
    return (a * p0[0] + b * c1[0] + c * c2[0] + d * p1[0], a * p0[1] + b * c1[1] + c * c2[1] + d * p1[1])


def outline(segs, steps=10):
    pts = [segs[0][0]]
    for seg in segs:
        for i in range(1, len(seg), 3):
            p0, c1, c2, p1 = seg[i - 1], seg[i], seg[i + 1], seg[i + 2]
            if c1 == p0 and c2 == p1:
                pts.append(p1)
            else:
                pts.extend(cubic(p0, c1, c2, p1, k / steps) for k in range(1, steps + 1))
    return pts


# ====================================================================
# Örnek resimler (koddan üretilir, dosya gerekmez)
# ====================================================================
def sample_sunset():
    W, H = 1500, 1000
    surf = pygame.Surface((W, H))
    rnd = random.Random(7)
    hz = int(H * 0.62)
    sky = [(0, (19, 26, 71)), (0.38, (74, 42, 108)), (0.72, (214, 97, 122)), (1, (255, 197, 111))]
    for y in range(hz):
        pygame.draw.line(surf, grad_color(sky, y / hz), (0, y), (W, y))
    fx = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(260):
        sx, sy = rnd.random() * W, rnd.random() * hz * 0.55
        a = int(255 * (1 - sy / (hz * 0.55)) * (0.3 + 0.7 * rnd.random()))
        pygame.draw.circle(fx, (255, 255, 255, a), (sx, sy), rnd.random() * 1.7 + 0.8)
    # hilal
    mx, my = W * 0.15, H * 0.15
    pygame.draw.circle(fx, (251, 241, 210, 255), (mx, my), 40)
    pygame.draw.circle(fx, (0, 0, 0, 0), (mx + 17, my - 9), 36)
    surf.blit(fx, (0, 0))
    # güneş ışıması
    sx, sy, sr = W * 0.64, hz - 70, 150
    glow = pygame.Surface((W, H), pygame.SRCALPHA)
    for i in range(24, 0, -1):
        pygame.draw.circle(glow, (255, 200, 130, 5), (sx, sy), sr + i * 14)
    surf.blit(glow, (0, 0))
    # şeritli güneş: şerit satırları boş bırakılır, gökyüzü görünür
    stripes = []
    for i in range(7):
        y0 = sy - 10 + i * 24
        stripes.append((y0, y0 + 3 + i * 2.2))
    sun = [(0, (255, 243, 166)), (0.6, (255, 176, 90)), (1, (255, 122, 74))]
    for y in range(int(sy - sr), int(sy + sr)):
        if any(a <= y < b for a, b in stripes):
            continue
        half = math.sqrt(max(0, sr * sr - (y - sy) ** 2))
        pygame.draw.line(surf, grad_color(sun, (y - (sy - sr)) / (2 * sr)), (sx - half, y), (sx + half, y))
    # bulutlar
    cl = pygame.Surface((W, H), pygame.SRCALPHA)
    for cx, cy, w, col in [(W * 0.3, H * 0.3, 420, (255, 160, 190, 80)), (W * 0.82, H * 0.22, 360, (255, 190, 210, 64)),
                           (W * 0.48, H * 0.44, 300, (120, 60, 130, 90))]:
        for i in range(6):
            ex, ey = cx + (i - 2.5) * w * 0.17, cy + math.sin(i * 1.7) * 6
            pygame.draw.ellipse(cl, col, (ex - w * 0.2, ey - w * 0.05, w * 0.4, w * 0.1))
    surf.blit(cl, (0, 0))
    # dağlar

    def ridge(base, amp, col, seed, freq):
        r = random.Random(seed)
        pts = [(0, H)]
        for i in range(121):
            n = abs(math.sin(i * freq + seed)) * 0.6 + abs(math.sin(i * freq * 2.7 + seed * 3)) * 0.3 + r.random() * 0.08
            pts.append((i / 120 * W, base - amp * n))
        pts.append((W, H))
        pygame.draw.polygon(surf, col, pts)
    ridge(hz, 250, (138, 74, 126), 2, 0.045)
    ridge(hz, 170, (92, 49, 112), 5, 0.07)
    ridge(hz, 95, (52, 33, 79), 9, 0.11)
    # göl
    for y in range(hz, H):
        pygame.draw.line(surf, lerp((67, 48, 95), (13, 19, 48), (y - hz) / (H - hz)), (0, y), (W, y))
    rf = pygame.Surface((W, H), pygame.SRCALPHA)
    for _ in range(90):
        t = rnd.random() ** 1.4
        yy, ww = hz + 6 + t * (H - hz - 10), (1 - t) * 230 * (0.4 + rnd.random()) + 20
        pygame.draw.rect(rf, (255, 170 + int(rnd.random() * 50), 110, int(255 * (0.55 * (1 - t) + 0.08))),
                         (sx - ww / 2 + (rnd.random() - 0.5) * 60, yy, ww, 2 + rnd.random() * 3))
    surf.blit(rf, (0, 0))
    # ön kıyılar, çamlar, kulübe
    dark = (11, 14, 34)
    left = [(0, hz + 40)] + [cubic((0, hz + 40), (W * 0.18, hz + 30), (W * 0.3, H * 0.84), (W * 0.42, H), k / 30) for k in range(1, 31)] + [(0, H)]
    right = [(W, hz + 110)] + [cubic((W, hz + 110), (W * 0.9, hz + 120), (W * 0.84, H * 0.9), (W * 0.78, H), k / 30) for k in range(1, 31)] + [(W, H)]
    pygame.draw.polygon(surf, dark, left)
    pygame.draw.polygon(surf, dark, right)

    def pine(px, py, h):
        for i in range(4):
            w, y0 = h * (0.34 - i * 0.06), py - h * (0.2 + i * 0.22)
            pygame.draw.polygon(surf, dark, [(px, y0 - h * 0.34), (px - w, y0 + h * 0.1), (px + w, y0 + h * 0.1)])
        pygame.draw.rect(surf, dark, (px - h * 0.03, py - h * 0.2, h * 0.06, h * 0.2))
    for a in [(40, hz + 60, 230), (120, hz + 80, 300), (205, hz + 95, 210), (290, hz + 120, 260), (360, hz + 160, 180),
              (W - 40, hz + 140, 260), (W - 120, hz + 150, 200), (W - 190, hz + 175, 240)]:
        pine(*a)
    kx, ky = 410, hz + 215
    pygame.draw.rect(surf, (21, 22, 46), (kx, ky - 60, 110, 60))
    pygame.draw.polygon(surf, (21, 22, 46), [(kx - 14, ky - 58), (kx + 55, ky - 110), (kx + 124, ky - 58)])
    for wx in (kx + 20, kx + 68):
        pygame.draw.rect(surf, (255, 207, 107), (wx, ky - 44, 22, 20))
    rr = pygame.Surface((W, H), pygame.SRCALPHA)
    for wx in (kx + 18, kx + 66):
        pygame.draw.rect(rr, (255, 207, 107, 64), (wx, ky + 20, 26, 60))
    surf.blit(rr, (0, 0))
    # kuşlar
    for bx, by, s in [(900, 260, 18), (950, 240, 14), (990, 275, 12), (860, 290, 10)]:
        pygame.draw.lines(surf, (42, 27, 59), False, [(bx - s, by - s * 0.4), (bx - s * 0.4, by - s * 0.55), (bx, by),
                                                        (bx + s * 0.4, by - s * 0.55), (bx + s, by - s * 0.4)], 3)
    return surf


def sample_mosaic():
    W, H, T = 1400, 1000, 200
    surf = pygame.Surface((W, H))
    rnd = random.Random(21)
    pal = [(29, 53, 87), (38, 70, 83), (42, 157, 143), (142, 202, 230), (233, 196, 106), (244, 162, 97),
           (231, 111, 81), (241, 250, 238), (181, 131, 141), (109, 89, 122)]

    def pick(ex):
        while True:
            c = rnd.choice(pal)
            if c not in ex:
                return c
    for r in range(H // T):
        for c in range(W // T):
            X, Y = c * T, r * T
            bg = pick([])
            fg = pick([bg])
            ac = pick([bg, fg])
            surf.set_clip(pygame.Rect(X, Y, T, T))
            surf.fill(bg)
            kind, q = int(rnd.random() * 6), int(rnd.random() * 4)
            if kind == 0:
                pygame.draw.circle(surf, fg, (X + T // 2, Y + T // 2), int(T * 0.36))
                pygame.draw.circle(surf, ac, (X + T // 2, Y + T // 2), int(T * 0.14))
            elif kind == 1:
                pygame.draw.circle(surf, fg, (X + (q & 1) * T, Y + (q >> 1) * T), T)
            elif kind == 2:
                a = q * math.pi / 2
                pygame.draw.circle(surf, fg, (X + T / 2 + math.cos(a) * T / 2, Y + T / 2 + math.sin(a) * T / 2), T // 2)
            elif kind == 3:
                k = [(X, Y), (X + T, Y), (X + T, Y + T), (X, Y + T)]
                pygame.draw.polygon(surf, fg, [k[q], k[(q + 1) % 4], k[(q + 2) % 4]])
            elif kind == 4:
                for i in range(4):
                    if q & 1:
                        surf.fill(fg, (X + i * T // 4, Y, T // 8, T))
                    else:
                        surf.fill(fg, (X, Y + i * T // 4, T, T // 8))
            else:
                for i in range(3, 0, -1):
                    pygame.draw.circle(surf, fg if i % 2 else ac, (X + T // 2, Y + T // 2), int(T * 0.14 * i))
            surf.set_clip(None)
            if rnd.random() < 0.35:
                pygame.draw.circle(surf, ac, (X + T * (0.2 + rnd.random() * 0.6), Y + T * (0.2 + rnd.random() * 0.6)), 9)
    return surf


def normalize(img):
    """Aşırı uzun/geniş resimleri 3:1'e kırp, en uzun kenarı 1800 px'e indir."""
    w, h = img.get_size()
    sx, sy, sw, sh = 0, 0, w, h
    if sw / sh > 3:
        sw = sh * 3
        sx = (w - sw) // 2
    elif sh / sw > 3:
        sh = sw * 3
        sy = (h - sh) // 2
    img = img.subsurface((sx, sy, sw, sh)).copy()
    k = min(1, 1800 / max(sw, sh))
    if k < 1:
        img = pygame.transform.smoothscale(img, (max(1, int(sw * k)), max(1, int(sh * k))))
    return img


def ask_image_path():
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        path = filedialog.askopenfilename(
            title="Yapboz için bir resim seç",
            filetypes=[("Resimler", "*.png *.jpg *.jpeg *.bmp *.gif *.webp *.tga"), ("Tüm dosyalar", "*.*")])
        root.destroy()
        return path or None
    except Exception:
        return None


# ====================================================================
# Ses (dosya gerekmez, dalgalar koddan üretilir)
# ====================================================================
class Sounds:
    def __init__(self):
        self.ok = False
        try:
            init = pygame.mixer.get_init()
            if not init:
                return
            self.rate, _, self.channels = init
            self.click = self._make([(900, 480, 0, 0.11, 0.35, "tri")])
            self.place = self._make([(440, 220, 0, 0.11, 0.35, "tri"), (660, 660, 0.05, 0.12, 0.2, "sin")])
            self.win = self._make([(f, f, i * 0.11, 0.5, 0.22, "sin") for i, f in enumerate([523.25, 659.25, 783.99, 1046.5])])
            self.ok = True
        except Exception:
            self.ok = False

    def _make(self, tones):
        total = max(start + dur for _, _, start, dur, _, _ in tones) + 0.03
        n = int(self.rate * total)
        buf = [0.0] * n
        for f0, f1, start, dur, vol, kind in tones:
            s0, ln = int(start * self.rate), int(dur * self.rate)
            phase = 0.0
            for i in range(ln):
                t = i / self.rate
                k = min(1.0, t / (dur * 0.7))
                f = f0 * (f1 / f0) ** k
                phase += 2 * math.pi * f / self.rate
                w = math.sin(phase) if kind == "sin" else 2 / math.pi * math.asin(math.sin(phase))
                env = min(1.0, t / 0.006) * math.exp(-5.5 * t / dur)
                if s0 + i < n:
                    buf[s0 + i] += w * env * vol
        data = array("h")
        for v in buf:
            s = int(clamp(v, -1, 1) * 32000)
            data.extend([s] * self.channels)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def play(self, name, enabled):
        if self.ok and enabled:
            getattr(self, name).play()


# ====================================================================
# Oyun modeli
# ====================================================================
class Piece:
    __slots__ = ("id", "r", "c", "x", "y", "g", "locked", "img", "shadow", "flash", "mask")


class Game:
    def __init__(self, source, level, prep, stage, ghost):
        cols, rows, edges = prep
        self.cols, self.rows, self.edges, self.level, self.ghost = cols, rows, edges, level, ghost
        sx, sy, sw, sh = stage
        self.stage = pygame.Rect(stage)
        aspect = source.get_width() / source.get_height()
        bw = min(sw * 0.56, sh * 0.72 * aspect)
        bh = bw / aspect
        self.cw, self.ch = max(8, int(bw / cols)), max(8, int(bh / rows))
        bw, bh = self.cw * cols, self.ch * rows
        self.board = pygame.Rect(sx + (sw - bw) // 2, sy + (sh - bh) // 2, bw, bh)
        self.s = min(self.cw, self.ch)
        self.pad = int(self.s * 0.3) + 4
        self.board_img = pygame.transform.smoothscale(source, (bw, bh)).convert_alpha()
        self.ghost_img = self.board_img.copy()
        self.ghost_img.set_alpha(62)
        self.moves = 0
        self.elapsed = 0.0
        self.t0 = None  # saat çalışırken başlangıç zamanı
        self.done = False
        self.pieces, self.grid, self.groups = [], [], {}
        for r in range(rows):
            row = []
            for c in range(cols):
                p = Piece()
                p.id, p.r, p.c, p.x, p.y, p.g, p.locked = len(self.pieces), r, c, 0.0, 0.0, len(self.pieces), False
                self._render(p)
                row.append(p)
                self.pieces.append(p)
                self.groups[p.g] = [p]
            self.grid.append(row)
        for p, (x, y) in zip(self.pieces, self.scatter_positions(self.pieces)):
            p.x, p.y = x, y
        self.order = self.pieces[:]
        random.shuffle(self.order)

    # ---- sprite üretimi ----
    def _render(self, p):
        cw, ch, pad = self.cw, self.ch, self.pad
        fw, fh = cw + 2 * pad, ch + 2 * pad
        pts = [(x + pad, y + pad) for x, y in outline(piece_segs(p.r, p.c, cw, ch, self.edges, self.cols, self.rows))]
        # 2x çizip küçülterek yumuşak kenarlı maske
        big = pygame.Surface((fw * 2, fh * 2), pygame.SRCALPHA)
        pygame.draw.polygon(big, (255, 255, 255, 255), [(x * 2, y * 2) for x, y in pts])
        mask = pygame.transform.smoothscale(big, (fw, fh))
        img = pygame.Surface((fw, fh), pygame.SRCALPHA)
        X0, Y0 = p.c * cw - pad, p.r * ch - pad
        ax, ay = max(0, X0), max(0, Y0)
        bx, by = min(self.board.w, X0 + fw), min(self.board.h, Y0 + fh)
        img.blit(self.board_img, (ax - X0, ay - Y0), pygame.Rect(ax, ay, bx - ax, by - ay))
        # karton kabartması: üst-sol ışık, alt-sağ gölge, ince kontur
        bevel = pygame.Surface((fw, fh), pygame.SRCALPHA)
        pygame.draw.lines(bevel, (0, 0, 0, 95), True, [(x - 1, y - 1) for x, y in pts], 3)
        pygame.draw.lines(bevel, (255, 255, 255, 100), True, [(x + 1, y + 1) for x, y in pts], 3)
        pygame.draw.lines(bevel, (8, 10, 10, 150), True, pts, 1)
        img.blit(bevel, (0, 0))
        img.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        p.img = img
        p.mask = pygame.mask.from_surface(img, 100)
        sh = mask.copy()
        sh.fill((0, 0, 0, 255), special_flags=pygame.BLEND_RGBA_MULT)
        small = pygame.transform.smoothscale(sh, (max(1, fw // 5), max(1, fh // 5)))
        sh = pygame.transform.smoothscale(small, (fw, fh))
        sh.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
        p.shadow = sh
        fl = pygame.Surface((fw, fh), pygame.SRCALPHA)
        pygame.draw.lines(fl, BRASS_HI + (255,), True, pts, 3)
        p.flash = fl

    # ---- yerleşim ----
    def home(self, p):
        return self.board.x + p.c * self.cw, self.board.y + p.r * self.ch

    def scatter_positions(self, pieces):
        st, b, gap = self.stage, self.board, self.pad * 0.4
        m = max(6, self.pad * 0.5)
        out = []
        for _ in pieces:
            x = y = 0
            for _ in range(80):
                x = st.x + m + random.random() * max(1, st.w - self.cw - 2 * m)
                y = st.y + m + random.random() * max(1, st.h - self.ch - 2 * m)
                if (x + self.cw < b.x - gap or x > b.right + gap or y + self.ch < b.y - gap or y > b.bottom + gap):
                    break
            out.append((x, y))
        return out

    def sort_locked(self):
        self.order.sort(key=lambda p: not p.locked)

    def hit(self, mx, my):
        for p in reversed(self.order):
            lx, ly = int(mx - p.x + self.pad), int(my - p.y + self.pad)
            w, h = p.mask.get_size()
            if 0 <= lx < w and 0 <= ly < h and p.mask.get_at((lx, ly)):
                return None if p.locked else p
        return None

    def neighbors(self, p):
        r, c = p.r, p.c
        if r > 0:
            yield self.grid[r - 1][c]
        if r < self.rows - 1:
            yield self.grid[r + 1][c]
        if c > 0:
            yield self.grid[r][c - 1]
        if c < self.cols - 1:
            yield self.grid[r][c + 1]

    def shift(self, gid, dx, dy):
        for p in self.groups[gid]:
            p.x += dx
            p.y += dy

    def merge(self, a, b):
        A, B = self.groups[a], self.groups.pop(b)
        locked = A[0].locked or B[0].locked
        for p in B:
            p.g = a
            A.append(p)
        if locked:
            for p in A:
                p.locked = True

    def settle(self, gid):
        """Bırakılan grubu tahtaya ya da komşularına oturtur. (birleşenler, tahtaya_oturdu_mu)"""
        tol = self.s * 0.3
        joined, placed, changed = [], False, True
        while changed:
            changed = False
            grp = self.groups[gid]
            if not grp[0].locked:
                for p in grp:
                    hx, hy = self.home(p)
                    if math.hypot(p.x - hx, p.y - hy) < tol:
                        self.shift(gid, hx - p.x, hy - p.y)
                        for q in grp:
                            q.locked = True
                        placed = changed = True
                        joined.extend(grp)
                        break
            for p in list(self.groups[gid]):
                for q in self.neighbors(p):
                    if q.g == gid:
                        continue
                    ex, ey = p.x + (q.c - p.c) * self.cw, p.y + (q.r - p.r) * self.ch
                    if math.hypot(q.x - ex, q.y - ey) < tol:
                        mine, theirs = self.groups[gid][0].locked, self.groups[q.g][0].locked
                        if not (mine and theirs):
                            if mine:
                                self.shift(q.g, ex - q.x, ey - q.y)
                            else:
                                self.shift(gid, q.x - ex, q.y - ey)
                            joined += [p, q]
                        self.merge(gid, q.g)
                        changed = True
                        break
                if changed:
                    break
        self.sort_locked()
        return list(dict.fromkeys(joined)), placed

    def progress(self):
        n = len(self.pieces)
        return (n - len(self.groups)) / (n - 1)

    # ---- saat ----
    def time(self):
        return self.elapsed + (time.perf_counter() - self.t0 if self.t0 is not None else 0)

    def start_clock(self):
        if self.t0 is None and not self.done:
            self.t0 = time.perf_counter()

    def stop_clock(self):
        if self.t0 is not None:
            self.elapsed += time.perf_counter() - self.t0
            self.t0 = None


# ====================================================================
# Uygulama
# ====================================================================
class App:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 1, 512)
        pygame.init()
        info = pygame.display.Info()
        self.W = max(1024, min(1440, info.current_w - 80))
        self.H = max(680, min(900, info.current_h - 120))
        self.screen = pygame.display.set_mode((self.W, self.H))
        pygame.display.set_caption("Yapboz Masası")
        pygame.display.set_icon(self._icon_surface(32))
        self.clock = pygame.time.Clock()
        self.stage = pygame.Rect(0, BAR_H, self.W, self.H - BAR_H)

        def font(size, bold=False, mono=False):
            names = "consolas,dejavusansmono,couriernew" if mono else "segoeui,dejavusans,arial"
            return pygame.font.SysFont(names, size, bold=bold)
        self.f_brand = font(22, True)
        self.f_title = font(30, True)
        self.f_h2 = font(32, True)
        self.f_btn = font(15, True)
        self.f_body = font(15)
        self.f_small = font(13)
        self.f_label = font(11, True)
        self.f_value = font(19, True, mono=True)
        self.f_big_value = font(24, True, mono=True)
        self.f_mono_small = font(12, mono=True)

        self.settings = load_settings()
        self.level = clamp(int(self.settings.get("level", 1)), 0, len(LEVELS) - 1)
        self.sound_on = bool(self.settings.get("sound", True))
        self.ghost_opt = bool(self.settings.get("ghost", False))
        self.sounds = Sounds()

        self.felt = self._make_felt(self.stage.w, self.stage.h)
        self.dim = pygame.Surface(self.stage.size, pygame.SRCALPHA)
        self.dim.fill((8, 14, 12, 165))
        self.samples = {"sunset": sample_sunset().convert(), "mosaic": sample_mosaic().convert()}
        self.thumbs = {k: pygame.transform.smoothscale(v, (68, 46)) for k, v in self.samples.items()}

        self.game = None
        self.state = "setup"         # setup | play | pause | won
        self.drag = None
        self.anims, self.flashes, self.timers = [], [], []
        self.hot = []                # bu karede çizilen tıklanabilir alanlar
        self.show_peek = False
        self.toast_msg, self.toast_until = "", 0
        self.win_info = None

        self.set_source(self.samples["sunset"], "Örnek · Gün batımı", "sunset")
        self.new_game()              # ilk açılışta parçalar karışık gelir

    # ---------- varlıklar ----------
    def _icon_surface(self, size):
        surf = pygame.Surface((size, size), pygame.SRCALPHA)
        s = size * 0.62
        e = {"s": -1, "j": 0, "k": 1}
        segs = [edge_pts(s, s, e), [(s + b, a) for a, b in edge_pts(s, s, {"s": 1, "j": 0, "k": 1})],
                [(a, s + b) for a, b in edge_pts(s, s, None)][::-1], [(b, a) for a, b in edge_pts(s, s, e)][::-1]]
        off = (size - s) / 2
        pygame.draw.polygon(surf, BRASS, [(x + off - s * 0.08, y + off + s * 0.08) for x, y in outline(segs, 8)])
        return surf

    def _make_felt(self, w, h):
        surf = pygame.Surface((w, h))
        surf.fill(FELT_DEEP)
        steps = 48
        for i in range(steps):
            k = i / steps
            rw, rh = w * 1.6 * (1 - k), h * 1.4 * (1 - k)
            pygame.draw.ellipse(surf, lerp(FELT_DEEP, FELT, k ** 0.8), (w / 2 - rw / 2, h * 0.45 - rh / 2, rw, rh))
        noise = pygame.Surface((160, 160), pygame.SRCALPHA)
        rnd = random.Random(3)
        for _ in range(5200):
            noise.set_at((rnd.randrange(160), rnd.randrange(160)), (0, 0, 0, rnd.randrange(10, 42)))
        for x in range(0, w, 160):
            for y in range(0, h, 160):
                surf.blit(noise, (x, y))
        return surf

    # ---------- kaynak & hazırlık ----------
    def set_source(self, surf, name, sample_key=None):
        self.source, self.source_name, self.sample_key = surf, name, sample_key
        self.prepare()

    def prepare(self):
        aspect = self.source.get_width() / self.source.get_height()
        cols, rows = grid_for(LEVELS[self.level][2], aspect)
        self.pending = (cols, rows, make_edges(cols, rows, random.Random()))
        self._build_preview()

    def _build_preview(self):
        cols, rows, edges = self.pending
        box_w, box_h = self._setup_layout()["preview"].size
        aw, ah = self.source.get_size()
        k = min((box_w - 24) / aw, (box_h - 24) / ah)
        w, h = max(1, int(aw * k)), max(1, int(ah * k))
        pv = pygame.transform.smoothscale(self.source, (w, h))
        lines = pygame.Surface((w, h), pygame.SRCALPHA)
        cw, ch = w / cols, h / rows
        for r in range(rows):
            for c in range(cols):
                pts = [(x + c * cw, y + r * ch) for x, y in outline(piece_segs(r, c, cw, ch, edges, cols, rows), 6)]
                pygame.draw.lines(lines, (255, 255, 255, 140), True, pts, 1)
        pv.blit(lines, (0, 0))
        self.preview = pv

    def load_image(self, path):
        try:
            img = pygame.image.load(path)
            img = normalize(img.convert())
        except Exception:
            self.toast("Bu dosya açılamadı. JPG, PNG, BMP, GIF veya WEBP bir resim seç.")
            return
        self.set_source(img, os.path.basename(path))
        self.open_setup()
        self.toast("Resim yüklendi. Zorluğu seçip oyunu başlatabilirsin.")

    def upload(self):
        path = ask_image_path()
        if path:
            self.load_image(path)

    # ---------- oyun akışı ----------
    def new_game(self):
        self.game = Game(self.source, self.level, self.pending, self.stage, self.ghost_opt)
        self.drag, self.anims, self.flashes, self.timers = None, [], [], []
        self.state = "play"
        self.game.start_clock()

    def replay(self):
        self.prepare()
        self.new_game()

    def open_setup(self):
        if self.game:
            self.game.stop_clock()
        self.drag = None
        self.state = "setup"

    def resume_from_setup(self):
        if self.game and not self.game.done:
            self.state = "play"
            self.game.start_clock()

    def pause(self):
        if self.state == "play" and self.game and not self.game.done:
            self.game.stop_clock()
            self.drag = None
            self.state = "pause"

    def resume(self):
        if self.state == "pause":
            self.state = "play"
            self.game.start_clock()

    def toggle_ghost(self):
        if self.game:
            self.game.ghost = not self.game.ghost
            self.ghost_opt = self.game.ghost
            self._save()

    def toggle_sound(self):
        self.sound_on = not self.sound_on
        self._save()
        self.sounds.play("click", self.sound_on)

    def scatter(self):
        g = self.game
        if not g or self.state != "play":
            return
        loose = [p for p in g.pieces if not p.locked and len(g.groups[p.g]) == 1]
        if not loose:
            self.toast("Dağıtılacak tek parça kalmadı.")
            return
        targets = g.scatter_positions(loose)
        self.tween([(p, x, y) for p, (x, y) in zip(loose, targets)], 0.45)
        random.shuffle(loose)
        g.order = [p for p in g.order if p not in loose] + loose
        g.sort_locked()
        self.toast(f"{len(loose)} parça masaya yeniden dağıtıldı.")

    def tween(self, items, dur, done=None):
        now = time.perf_counter()
        self.anims.append({"items": [(p, p.x, p.y, x, y) for p, x, y in items], "t0": now, "dur": dur, "done": done})

    def finish(self):
        g = self.game
        if g.done:
            return
        g.stop_clock()
        g.done = True

        def reveal():
            for p in g.pieces:
                p.locked = True
            self.flashes.append((g.pieces[:], time.perf_counter()))
            self.sounds.play("win", self.sound_on)
            self.timers.append((time.perf_counter() + 0.9, self.show_win))
        if not g.pieces[0].locked:
            self.tween([(p, *g.home(p)) for p in g.pieces], 0.6, reveal)
        else:
            reveal()

    def show_win(self):
        g = self.game
        lid, lname, _ = LEVELS[g.level]
        best_all = self.settings.setdefault("best", {})
        prev = best_all.get(lid)
        notes = []
        if not prev:
            notes.append("Bu seviyedeki ilk derecen kaydedildi")
            best_all[lid] = {"time": g.elapsed, "moves": g.moves}
        else:
            if g.elapsed < prev["time"]:
                notes.append("Yeni süre rekoru")
            if g.moves < prev["moves"]:
                notes.append("En az hamle rekoru")
            best_all[lid] = {"time": min(prev["time"], g.elapsed), "moves": min(prev["moves"], g.moves)}
        self._save()
        self.win_info = {"line": f"{lname} seviyesi · {g.cols} × {g.rows} yapboz", "record": " · ".join(notes)}
        self.state = "won"

    def _save(self):
        self.settings.update({"level": self.level, "sound": self.sound_on, "ghost": self.ghost_opt})
        save_settings(self.settings)

    def toast(self, msg):
        self.toast_msg, self.toast_until = msg, time.perf_counter() + 2.6

    # ---------- olaylar ----------
    def handle(self, ev):
        if ev.type == pygame.DROPFILE:
            self.load_image(ev.file)
        elif ev.type == pygame.KEYDOWN:
            self.on_key(ev)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            for rect, cb in reversed(self.hot):
                if rect.collidepoint(ev.pos):
                    cb()
                    return
            if self.state == "play":
                self.start_drag(ev.pos)
        elif ev.type == pygame.MOUSEMOTION and self.drag:
            self.move_drag(ev.pos)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and self.drag:
            self.end_drag()
        elif ev.type == pygame.WINDOWFOCUSLOST:
            self.pause()

    def on_key(self, ev):
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.state == "setup" and self.game and not self.game.done:
                self.resume_from_setup()
            elif self.state == "pause":
                self.resume()
            else:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
            return
        if self.state in ("play", "pause") and k == pygame.K_p:
            self.resume() if self.state == "pause" else self.pause()
        elif self.state == "play":
            if k == pygame.K_s:
                self.toggle_ghost()
            elif k == pygame.K_o:
                self.show_peek = not self.show_peek
            elif k == pygame.K_d:
                self.scatter()
            elif k == pygame.K_n:
                self.open_setup()
        elif self.state == "setup" and k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self.new_game()

    def start_drag(self, pos):
        g = self.game
        if not g or g.done:
            return
        p = g.hit(*pos)
        if not p:
            return
        for a in self.anims:
            a["items"] = [it for it in a["items"] if it[0].g != p.g]
        grp = g.groups[p.g]
        g.order = [q for q in g.order if q.g != p.g] + grp
        self.drag = {"g": p.g, "last": pos, "dist": 0.0}

    def move_drag(self, pos):
        g, st = self.game, self.stage
        x, y = clamp(pos[0], st.left, st.right - 1), clamp(pos[1], st.top, st.bottom - 1)
        lx, ly = self.drag["last"]
        dx, dy = x - lx, y - ly
        self.drag["dist"] += math.hypot(dx, dy)
        self.drag["last"] = (x, y)
        g.shift(self.drag["g"], dx, dy)

    def end_drag(self):
        g, d = self.game, self.drag
        self.drag = None
        if d["dist"] > 4:
            g.moves += 1
        joined, placed = g.settle(d["g"])
        if joined:
            self.flashes.append((joined, time.perf_counter()))
            self.sounds.play("place" if placed else "click", self.sound_on)
        if len(g.groups) == 1:
            self.finish()

    # ---------- güncelleme ----------
    def update(self):
        now = time.perf_counter()
        keep = []
        for a in self.anims:
            k = 1.0 if a["dur"] <= 0 else min(1.0, (now - a["t0"]) / a["dur"])
            e = 1 - (1 - k) ** 3
            for p, fx, fy, tx, ty in a["items"]:
                p.x, p.y = fx + (tx - fx) * e, fy + (ty - fy) * e
            if k >= 1:
                if a["done"]:
                    a["done"]()
            else:
                keep.append(a)
        self.anims = keep
        self.flashes = [f for f in self.flashes if now - f[1] < 0.75]
        due = [t for t in self.timers if t[0] <= now]
        self.timers = [t for t in self.timers if t[0] > now]
        for _, fn in due:
            fn()

    # ---------- çizim yardımcıları ----------
    def text(self, s, font, color, pos, anchor="topleft"):
        img = font.render(s, True, color)
        r = img.get_rect(**{anchor: pos})
        self.screen.blit(img, r)
        return r

    def button(self, rect, label, cb, kind="tool", active=False, enabled=True, font=None):
        rect = pygame.Rect(rect)
        hover = enabled and rect.collidepoint(pygame.mouse.get_pos())
        if kind == "brass":
            bg, fg, border = (BRASS_HI if hover else BRASS), BRASS_INK, None
        elif active:
            bg, fg, border = ((52, 52, 34) if hover else (44, 46, 32)), BRASS_HI, BRASS
        else:
            bg, fg, border = ((PANEL2 if hover else (PANEL if kind == "tool" else PANEL2))), TEXT, (MUTED if hover and kind != "tool" else LINE)
        if not enabled:
            fg = lerp(fg, PANEL, 0.6)
            border = lerp(LINE, PANEL, 0.4)
        pygame.draw.rect(self.screen, bg, rect, border_radius=10)
        if border:
            pygame.draw.rect(self.screen, border, rect, 1, border_radius=10)
        self.text(label, font or self.f_btn, fg, rect.center, "center")
        if enabled:
            self.hot.append((rect, cb))
        return rect

    def card(self, rect):
        rect = pygame.Rect(rect)
        shadow = pygame.Surface((rect.w + 60, rect.h + 60), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 90), (30, 40, rect.w, rect.h), border_radius=24)
        shadow = pygame.transform.smoothscale(pygame.transform.smoothscale(shadow, ((rect.w + 60) // 6, (rect.h + 60) // 6)), shadow.get_size())
        self.screen.blit(shadow, (rect.x - 30, rect.y - 30))
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=18)
        pygame.draw.rect(self.screen, LINE, rect, 1, border_radius=18)
        return rect

    # ---------- çizim ----------
    def draw(self):
        self.hot = []
        scr = self.screen
        scr.fill(INK)
        scr.blit(self.felt, self.stage.topleft)
        g = self.game
        if g and self.state in ("play", "won", "setup"):
            self.draw_table()
        if self.state == "pause":
            scr.blit(self.dim, self.stage.topleft)
            self.draw_pause()
        elif self.state == "setup":
            scr.blit(self.dim, self.stage.topleft)
            self.draw_setup()
        elif self.state == "won":
            scr.blit(self.dim, self.stage.topleft)
            self.draw_win()
        self.draw_bar()
        if self.toast_msg and time.perf_counter() < self.toast_until:
            img = self.f_body.render(self.toast_msg, True, TEXT)
            r = img.get_rect(midbottom=(self.W // 2, self.H - 18)).inflate(28, 16)
            pygame.draw.rect(scr, PANEL, r, border_radius=10)
            pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
            scr.blit(img, img.get_rect(center=r.center))
        pygame.display.flip()

    def draw_table(self):
        g, scr = self.game, self.screen
        b = g.board
        slot = pygame.Surface((b.w + 16, b.h + 16), pygame.SRCALPHA)
        pygame.draw.rect(slot, (6, 18, 14, 97), slot.get_rect(), border_radius=8)
        pygame.draw.rect(slot, (255, 255, 255, 18), slot.get_rect(), 1, border_radius=8)
        pygame.draw.rect(slot, (0, 0, 0, 50), (8, 8, b.w, b.h))
        scr.blit(slot, (b.x - 8, b.y - 8))
        if g.ghost:
            scr.blit(g.ghost_img, b.topleft)
        pad = g.pad
        lifted = self.drag["g"] if self.drag else None
        for p in g.order:
            x, y = round(p.x) - pad, round(p.y) - pad
            if p.g == lifted:
                scr.blit(p.shadow, (x + 5, y + 11))
            else:
                scr.blit(p.shadow, (x + 1, y + 2))
            scr.blit(p.img, (x, y))
        now = time.perf_counter()
        for pieces, t0 in self.flashes:
            a = int(255 * max(0.0, 1 - (now - t0) / 0.75))
            for p in pieces:
                p.flash.set_alpha(a)
                scr.blit(p.flash, (round(p.x) - pad, round(p.y) - pad))
                p.flash.set_alpha(255)
        if self.show_peek and self.state == "play":
            aw, ah = self.source.get_size()
            w = 260
            h = int(w * ah / aw)
            if h > 220:
                h, w = 220, int(220 * aw / ah)
            r = pygame.Rect(self.W - w - 28, self.H - h - 28, w + 12, h + 12)
            pygame.draw.rect(scr, PANEL, r, border_radius=12)
            pygame.draw.rect(scr, LINE, r, 1, border_radius=12)
            scr.blit(pygame.transform.smoothscale(g.board_img, (w, h)), (r.x + 6, r.y + 6))

    def draw_bar(self):
        scr, g = self.screen, self.game
        pygame.draw.rect(scr, PANEL, (0, 0, self.W, BAR_H))
        pygame.draw.line(scr, LINE, (0, BAR_H - 1), (self.W, BAR_H - 1))
        scr.blit(self._icon_surface(30), (16, BAR_H // 2 - 15))
        if self.W >= 1150:
            self.text("Yapboz Masası", self.f_brand, TEXT, (54, BAR_H // 2), "midleft")
        # istatistikler
        live = g is not None
        vals = [("SÜRE", fmt_time(g.time()) if live else "00:00"),
                ("HAMLE", str(g.moves) if live else "0"),
                ("İLERLEME", f"%{round(g.progress() * 100)}" if live else "%0")]
        x = 240 if self.W >= 1150 else 60
        for i, (k, v) in enumerate(vals):
            r = pygame.Rect(x + i * 104, 10, 96, BAR_H - 20)
            pygame.draw.rect(scr, PANEL2, r, border_radius=10)
            pygame.draw.rect(scr, LINE, r, 1, border_radius=10)
            self.text(k, self.f_label, MUTED, (r.x + 11, r.y + 6))
            self.text(v, self.f_value, TEXT, (r.x + 11, r.y + 19))
            if i == 2:
                tr = pygame.Rect(r.x + 11, r.bottom - 8, r.w - 22, 3)
                pygame.draw.rect(scr, (40, 56, 51), tr, border_radius=2)
                if live:
                    pygame.draw.rect(scr, BRASS, (tr.x, tr.y, int(tr.w * g.progress()), 3), border_radius=2)
        # araç düğmeleri (sağdan sola)
        playing = self.state == "play"
        tools = [("Yeni oyun", self.open_setup, "brass", False, self.state != "setup"),
                 ("Ses: Açık" if self.sound_on else "Ses: Kapalı", self.toggle_sound, "tool", self.sound_on, True),
                 ("Duraklat", self.pause, "tool", False, playing),
                 ("Dağıt", self.scatter, "tool", False, playing),
                 ("Silik resim", self.toggle_ghost, "tool", bool(g and g.ghost), playing),
                 ("Önizleme", lambda: setattr(self, "show_peek", not self.show_peek), "tool", self.show_peek, playing)]
        right = self.W - 16
        for label, cb, kind, active, enabled in tools:
            w = self.f_btn.size(label)[0] + 26
            self.button((right - w, 16, w, BAR_H - 32), label, cb, kind, active, enabled)
            right -= w + 6

    def _setup_layout(self):
        cw, ch = min(980, self.W - 48), min(560, self.stage.h - 40)
        card = pygame.Rect(0, 0, cw, ch)
        card.center = self.stage.center
        pw = int((cw - 70) * 0.56)
        preview = pygame.Rect(card.x + 24, card.y + 24, pw, ch - 72)
        side = pygame.Rect(preview.right + 26, card.y + 24, card.right - preview.right - 50, ch - 48)
        return {"card": card, "preview": preview, "side": side}

    def draw_setup(self):
        L = self._setup_layout()
        scr = self.screen
        self.card(L["card"])
        pr = L["preview"]
        pygame.draw.rect(scr, (12, 20, 18), pr, border_radius=14)
        pygame.draw.rect(scr, LINE, pr, 1, border_radius=14)
        img_r = self.preview.get_rect(center=pr.center)
        scr.blit(self.preview, img_r)
        self.hot.append((pr, self.upload))
        if pr.collidepoint(pygame.mouse.get_pos()):
            pygame.draw.rect(scr, BRASS, pr, 2, border_radius=14)
            hint = self.f_small.render("Tıkla veya resmi pencereye sürükle", True, TEXT)
            hr = hint.get_rect(midbottom=(pr.centerx, pr.bottom - 14)).inflate(22, 10)
            pygame.draw.rect(scr, (16, 24, 22), hr, border_radius=12)
            scr.blit(hint, hint.get_rect(center=hr.center))
        name = self.source_name if len(self.source_name) <= 48 else self.source_name[:45] + "..."
        self.text(name, self.f_small, MUTED, (pr.x + 2, pr.bottom + 10))
        self.text(f"{self.source.get_width()} × {self.source.get_height()}", self.f_mono_small, MUTED, (pr.right - 2, pr.bottom + 11), "topright")

        s = L["side"]
        x, y = s.x, s.y
        self.text("YENİ YAPBOZ", self.f_label, BRASS, (x, y))
        y += 18
        self.text("Resmini seç, parçala,", self.f_title, TEXT, (x, y))
        y += 36
        self.text("yeniden birleştir.", self.f_title, TEXT, (x, y))
        y += 54
        self.text("RESİM", self.f_label, MUTED, (x, y))
        y += 18
        self.button((x, y, 130, 46), "Resim yükle", self.upload, "plain")
        tx = x + 140
        for key in ("sunset", "mosaic"):
            r = pygame.Rect(tx, y, 72, 46)
            scr.blit(self.thumbs[key], (r.x + 2, r.y))
            pygame.draw.rect(scr, BRASS if self.sample_key == key else LINE, r.inflate(0, 4), 2, border_radius=8)
            label = "Örnek · Gün batımı" if key == "sunset" else "Örnek · Mozaik"
            self.hot.append((r, lambda k=key, n=label: self.set_source(self.samples[k], n, k)))
            tx += 80
        y += 54
        self.text("Resim dosyasını pencereye sürükleyip de bırakabilirsin.", self.f_small, MUTED, (x, y))
        y += 34
        self.text("ZORLUK", self.f_label, MUTED, (x, y))
        y += 18
        aspect = self.source.get_width() / self.source.get_height()
        bw = (s.w - 18) // 4
        for i, (_, lname, n) in enumerate(LEVELS):
            c, r_ = grid_for(n, aspect)
            r = pygame.Rect(x + i * (bw + 6), y, bw, 50)
            sel = i == self.level
            hov = r.collidepoint(pygame.mouse.get_pos())
            pygame.draw.rect(scr, (46, 48, 33) if sel else (PANEL2 if not hov else (38, 54, 49)), r, border_radius=10)
            pygame.draw.rect(scr, BRASS if sel else LINE, r, 1, border_radius=10)
            self.text(lname, self.f_btn, TEXT, (r.centerx, r.y + 6), "midtop")
            self.text(f"{c * r_} parça", self.f_mono_small, BRASS_HI if sel else MUTED, (r.centerx, r.y + 28), "midtop")
            self.hot.append((r, lambda i=i: self._set_level(i)))
        y += 58
        cols, rows, _ = self.pending
        self.text(f"{cols} × {rows} = {cols * rows} parça", self.f_small, MUTED, (x, y))
        y += 30
        box = pygame.Rect(x, y, 18, 18)
        pygame.draw.rect(scr, BRASS if self.ghost_opt else PANEL2, box, border_radius=4)
        pygame.draw.rect(scr, BRASS if self.ghost_opt else MUTED, box, 1, border_radius=4)
        if self.ghost_opt:
            pygame.draw.lines(scr, BRASS_INK, False, [(x + 4, y + 9), (x + 8, y + 13), (x + 14, y + 5)], 2)
        tr = self.text("Tahtada silik resmi göster (ipucu)", self.f_body, TEXT, (x + 28, y - 1))
        self.hot.append((box.union(tr), self._toggle_ghost_opt))
        y += 34
        lid, lname, _ = LEVELS[self.level]
        rec = self.settings.get("best", {}).get(lid)
        best = pygame.Rect(x, y, s.w, 38)
        pygame.draw.rect(scr, PANEL2, best, border_radius=10)
        pygame.draw.rect(scr, LINE, best, 1, border_radius=10)
        msg = (f"En iyi derecen ({lname}): {fmt_time(rec['time'])} · {rec['moves']} hamle" if rec
               else f"{lname} seviyesinde henüz derecen yok. İlkini sen koy.")
        self.text(msg, self.f_small, TEXT if rec else MUTED, (best.x + 12, best.centery), "midleft")
        # eylemler
        ay = s.bottom - 50
        can_resume = self.game and not self.game.done
        if can_resume:
            self.button((x, ay, 130, 50), "Oyuna dön", self.resume_from_setup, "plain")
            self.button((x + 138, ay, s.w - 138, 50), "Oyunu Başlat", self.new_game, "brass", font=self.f_brand)
        else:
            self.button((x, ay, s.w, 50), "Oyunu Başlat", self.new_game, "brass", font=self.f_brand)

    def _set_level(self, i):
        self.level = i
        self._save()
        self.prepare()

    def _toggle_ghost_opt(self):
        self.ghost_opt = not self.ghost_opt
        self._save()

    def draw_pause(self):
        r = pygame.Rect(0, 0, 400, 210)
        r.center = self.stage.center
        self.card(r)
        self.text("Duraklatıldı", self.f_h2, TEXT, (r.centerx, r.y + 34), "midtop")
        self.text("Süre durdu. Parçalar seni bekliyor.", self.f_body, MUTED, (r.centerx, r.y + 86), "midtop")
        self.button((r.x + 28, r.bottom - 74, r.w - 56, 50), "Devam et", self.resume, "brass", font=self.f_brand)

    def draw_win(self):
        g, info = self.game, self.win_info
        r = pygame.Rect(0, 0, 440, 380 if info["record"] else 340)
        r.center = self.stage.center
        self.card(r)
        self.screen.blit(self._icon_surface(56), (r.centerx - 28, r.y + 22))
        self.text("Yapboz tamam!", self.f_h2, TEXT, (r.centerx, r.y + 86), "midtop")
        self.text(info["line"], self.f_body, MUTED, (r.centerx, r.y + 132), "midtop")
        bw = (r.w - 56 - 16) // 3
        for i, (k, v) in enumerate([("SÜRE", fmt_time(g.elapsed)), ("HAMLE", str(g.moves)), ("PARÇA", str(len(g.pieces)))]):
            b = pygame.Rect(r.x + 28 + i * (bw + 8), r.y + 166, bw, 64)
            pygame.draw.rect(self.screen, PANEL2, b, border_radius=12)
            pygame.draw.rect(self.screen, LINE, b, 1, border_radius=12)
            self.text(k, self.f_label, MUTED, (b.centerx, b.y + 10), "midtop")
            self.text(v, self.f_big_value, TEXT, (b.centerx, b.y + 26), "midtop")
        if info["record"]:
            img = self.f_small.render(info["record"], True, OK)
            pr = img.get_rect(midtop=(r.centerx, r.y + 246)).inflate(24, 10)
            pygame.draw.rect(self.screen, (30, 58, 46), pr, border_radius=14)
            self.screen.blit(img, img.get_rect(center=pr.center))
        half = (r.w - 56 - 8) // 2
        self.button((r.x + 28, r.bottom - 74, half, 48), "Yeni resim", self.open_setup, "plain")
        self.button((r.x + 36 + half, r.bottom - 74, half, 48), "Tekrar karıştır", self.replay, "brass")

    # ---------- ana döngü ----------
    def run(self):
        running = True
        while running:
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    running = False
                else:
                    self.handle(ev)
            self.update()
            self.draw()
            self.clock.tick(FPS)
        pygame.quit()


if __name__ == "__main__":
    App().run()
