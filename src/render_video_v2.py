"""Render Biscuit's v2 promo, "Kennel Him vs Yard Him" (1080x1920, 30 fps, 26.0 s, H.264 + AAC).

Usage:
  python src/render_video_v2.py [assets_dir] [out.mp4]                full render (+ poster-v2.jpg beside it)
  python src/render_video_v2.py <assets_dir> <out.mp4> 4.2 10.2       preview frames only (preview_v2_<s>.jpg)

assets_dir (default: the repo's assets/) holds biscuit.jpg (the real kennel photo), note.png, yard-clip.mp4
(clip E, AI image-to-video), cartoon/{walk-a,walk-b,sit,wave}.png, fonts/ and v2/. The four new AI clips are
read from v2/V1.mp4..V4.mp4 when present, else from the stand-ins v2/standin-V1.mp4..V4.mp4 (cut from
yard-clip.mp4). The cartoon is one Gemini pose; the head peek, ears, tilt, lean, squash and wave are crops,
rotations and scales of it. The soundtrack comes from beat_v2.py (synthesized beat + SFX + clip ambience).

Timeline (s, 120 BPM, every cut on a beat): 0-1 kennel photo tight on his eyes (hook), 1-2 kennel photo wide,
2-3 staff note, 3-4 lime wipe + 3-2-1, 4-6 V1 (drop), 6-7.5 V2 (tilt), 7.5-9 E trot at 2x, 9-10 E lean starts
(music out), 10-11.5 E lean in slow motion (CERTIFIED LEANER), 11.5-13 E ear scratch, 13-14.5 V3, 14.5-19 stats
card over blurred V3, 19-22.5 V4, 22.5-26 end card with the AI disclosure (23.0-26.0).
"""
import functools
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
import beat_v2  # noqa: E402

W, H, FPS = 1080, 1920, 30
DURATION = 26.0
ROOT = Path(__file__).resolve().parent.parent
ASSETS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "assets"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "biscuit-story-v2.mp4"
SAFE = (60, 250, 900, 1300)  # text must stay inside x 60-900, y 250-1300
LANE = 1560  # cartoon's feet over footage: below his face (it dips into the bottom UI band, text never does)
CHIP_Y, REAL_Y = 360, 640  # kennel chip on his forehead, REAL PHOTO chip under it (lower left would cover his mouth)
SOCIAL = False               # True adds "Link in bio" to the end card (social posts only)

INK, PAPER, YARD, YARD_DEEP = (31, 26, 22), (250, 244, 234), (44, 90, 55), (30, 64, 39)
LIME, PINK, STEEL, WHEAT = (215, 240, 74), (255, 159, 198), (88, 97, 107), (233, 217, 166)


# ------------------------------------------------------------------ fonts + easing

@functools.lru_cache(maxsize=None)
def brico(size):  # Bricolage Grotesque 800, wdth 82, opsz 96 (the flyer's "Kennel shy. Yard guy." face)
    f = ImageFont.truetype(str(ASSETS / "fonts" / "bricolage.ttf"), size)
    f.set_variation_by_axes([96, 800, 82])
    return f


@functools.lru_cache(maxsize=None)
def fraunces(size):  # Fraunces 700, SOFT 50, opsz 144 (same axes as render_video.py)
    f = ImageFont.truetype(str(ASSETS / "fonts" / "display.ttf"), size)
    f.set_variation_by_axes([144, 700, 50, 0])
    return f


@functools.lru_cache(maxsize=None)
def figtree(size, weight=600):
    f = ImageFont.truetype(str(ASSETS / "fonts" / "body.ttf"), size)
    f.set_variation_by_axes([weight])
    return f


def clamp(x, a=0.0, b=1.0):
    return max(a, min(b, x))


def ease(x):
    x = clamp(x)
    return x * x * (3 - 2 * x)


def ease_out(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def ease_out_back(x, s=1.7):
    x = clamp(x) - 1
    return 1 + x * x * ((s + 1) * x + s)


def pop_curve(r, dur=0.2):
    """Pop-in: 0.6 -> 1.08 -> 1.0 over 6 frames."""
    u = r / dur
    if u >= 1:
        return 1.0
    if u < 0.65:
        return 0.6 + 0.48 * ease_out(u / 0.65)
    return 1.08 - 0.08 * ease((u - 0.65) / 0.35)


def slam_curve(r, frames=4, s0=1.4):
    """Slam: s0 -> 1.0, accelerating into the hit."""
    u = clamp(r * FPS / frames)
    return s0 - (s0 - 1) * u * u


# ------------------------------------------------------------------ text

def text_w(text, f, track):
    return f.getlength(text) + max(0, len(text) - 1) * track * f.size


def text_img(text, f, fill, stroke=0, stroke_fill=INK, shadow=0, track=-0.02):
    """Text sprite with tracking, optional ink stroke and hard offset shadow. Returns (img, pad)."""
    asc, desc = f.getmetrics()
    pad = stroke + shadow + 6
    im = Image.new("RGBA", (math.ceil(text_w(text, f, track)) + 2 * pad, asc + desc + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    xs = [f.getlength(text[:i]) + i * track * f.size for i in range(len(text))]

    def run(dx, dy, color, sw):
        for ch, x in zip(text, xs):
            if ch != " ":
                d.text((pad + x + dx, pad + dy), ch, font=f, fill=color, stroke_width=sw, stroke_fill=color)

    if shadow:
        run(shadow, shadow, INK, stroke)
    if stroke:
        run(0, 0, stroke_fill, stroke)
    run(0, 0, fill, 0)
    return im, pad


def paste_scaled(img, sprite, cx, cy, scale=1.0, angle=0.0):
    """Composite sprite centred at (cx, cy), scaled and rotated (angle in CSS degrees: + is clockwise)."""
    if scale <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        sprite = sprite.resize((max(1, round(sprite.width * scale)), max(1, round(sprite.height * scale))), Image.BICUBIC)
    if angle:
        sprite = sprite.rotate(-angle, resample=Image.BICUBIC, expand=True)
    img.alpha_composite(sprite, (round(cx - sprite.width / 2), round(cy - sprite.height / 2)))


SAFE_LOG = []


def check_safe(name, cx, cy, w, h, angle):
    """Record any text box (unscaled, rotated) that leaves the safe zone."""
    a = math.radians(angle)
    ew = abs(w * math.cos(a)) + abs(h * math.sin(a))
    eh = abs(w * math.sin(a)) + abs(h * math.cos(a))
    box = (cx - ew / 2, cy - eh / 2, cx + ew / 2, cy + eh / 2)
    if box[0] < SAFE[0] - 1 or box[1] < SAFE[1] - 1 or box[2] > SAFE[2] + 1 or box[3] > SAFE[3] + 1:
        SAFE_LOG.append((name, tuple(round(v) for v in box)))


class Cap:
    """A caption in one of the four treatments: 'hl' highlighter (ink on lime bars; with keywords the bars are
    paper and the keywords get the lime), 'over' (paper, ink stroke, hard shadow), 'chip' (paper on a steel box),
    'sticker' (ink on pink, ink outline, -6 degrees). anim: 'none', 'pop', 'words', 'slam', 'stamp'."""

    def __init__(self, t0, t1, lines, style="hl", size=100, x=60, y=300, center=False, anim="pop",
                 keyword=(), kw_at=None, angle=None, exit_scale=False, name=None):
        self.t0, self.t1, self.style, self.anim, self.exit_scale = t0, t1, style, anim, exit_scale
        self.keyword, self.kw_at = set(keyword), kw_at
        self.angle = angle if angle is not None else {"hl": -1.5, "sticker": -6.0, "chip": -1.0}.get(style, 0.0)
        self.name = name or " / ".join(lines)
        max_w = SAFE[2] - SAFE[0] - 40
        while True:
            self.f = brico(size)
            self._layout(lines, size)
            if self.bw <= max_w or size <= 60:
                break
            size -= 4
        self.size = size
        self.x = SAFE[0] + (SAFE[2] - SAFE[0] - self.bw) / 2 if center else x
        self.y = y
        a = math.radians(self.angle)  # nudge so the rotated box stays inside the safe zone
        ew = abs(self.bw * math.cos(a)) + abs(self.bh * math.sin(a))
        eh = abs(self.bw * math.sin(a)) + abs(self.bh * math.cos(a))
        self.x += max(0.0, SAFE[0] - (self.x + self.bw / 2 - ew / 2))
        self.y += max(0.0, SAFE[1] - (self.y + self.bh / 2 - eh / 2))
        n = len(self.words)
        self.word_t = [t0 + (i * 4 / FPS if anim == "words" else 0) for i in range(n)]

    def _layout(self, lines, size):
        f, track = self.f, -0.02
        cap_top = f.getbbox("H")[1]
        asc = f.getmetrics()[0]
        self.pv, self.ph = (14, 22) if self.style != "over" else (0, 0)
        if self.style == "sticker":
            self.pv, self.ph = 18, 30
        line_h = (asc - cap_top) + int(0.2 * size) + 2 * self.pv
        gap = 10 if self.style in ("hl", "chip") else int(0.06 * size)
        space = f.getlength(" ") + track * size
        self.words, self.lines = [], []
        y = 0
        widths = []
        for li, line in enumerate(lines):
            x = self.ph
            first = len(self.words)
            for word in line.split(" "):
                w = text_w(word, f, track)
                self.words.append({"text": word, "line": li, "x": x, "w": w})
                x += w + space
            widths.append(x - space + self.ph)
            self.lines.append({"y": y, "h": line_h, "first": first, "last": len(self.words) - 1})
            y += line_h + gap
        self.bw = max(widths)
        self.bh = y - gap
        self.text_dy = self.pv - cap_top  # text origin y inside a line box

    def _word_sprite(self, word, keyword_on):
        f = self.f
        if self.style == "over" and not keyword_on:
            return text_img(word, f, PAPER, stroke=6, shadow=7)
        if self.style == "chip":
            return text_img(word, f, PAPER)
        return text_img(word, f, INK)

    def draw(self, img, t):
        if not (self.t0 <= t < self.t1):
            return
        r = t - self.t0
        scale = {"pop": pop_curve(r), "slam": slam_curve(r), "stamp": slam_curve(r, 3, 1.5)}.get(self.anim, 1.0)
        if self.exit_scale and t > self.t1 - 0.1:
            scale *= 1 - ease((t - (self.t1 - 0.1)) / 0.1)
        M = 40
        cv = Image.new("RGBA", (math.ceil(self.bw) + 2 * M, math.ceil(self.bh) + 2 * M), (0, 0, 0, 0))
        d = ImageDraw.Draw(cv)
        visible = [i for i, wt in enumerate(self.word_t) if t >= wt]
        if not visible:
            return
        if self.style == "sticker":
            box = (M, M, M + self.bw, M + self.bh)
            d.rounded_rectangle(tuple(v + 7 for v in box), 22, fill=INK)
            d.rounded_rectangle(box, 22, fill=PINK, outline=INK, width=4)
        if self.style == "chip":
            box = (M, M, M + self.bw, M + self.bh)
            d.rounded_rectangle(tuple(v + 5 for v in box), 10, fill=INK)
            d.rounded_rectangle(box, 10, fill=STEEL)
        for ln in self.lines:
            vis = [i for i in visible if ln["first"] <= i <= ln["last"]]
            if not vis:
                continue
            if self.style == "hl":
                last = self.words[vis[-1]]
                x0, x1 = M, M + last["x"] + last["w"] + self.ph
                y0, y1 = M + ln["y"], M + ln["y"] + ln["h"]
                d.rectangle((x0 + 7, y0 + 7, x1 + 7, y1 + 7), fill=INK)
                d.rectangle((x0, y0, x1, y1), fill=PAPER if self.keyword else LIME)
            for i in vis:
                wd = self.words[i]
                kw = wd["text"] in self.keyword
                kw_p = 1.0
                if kw and self.kw_at is not None:
                    kw_p = ease_out((t - max(self.kw_at, self.word_t[i])) / (6 / FPS))
                if kw and kw_p > 0:
                    bx0 = M + wd["x"] - 10
                    by0, by1 = M + ln["y"] + (4 if self.style == "hl" else -6), M + ln["y"] + ln["h"] - (4 if self.style == "hl" else -10)
                    if self.style == "over":
                        d.rectangle((bx0 + 7, by0 + 7, bx0 + 7 + (wd["w"] + 20) * kw_p, by1 + 7), fill=INK)
                    d.rectangle((bx0, by0, bx0 + (wd["w"] + 20) * kw_p, by1), fill=LIME)
                spr, pad = self._word_sprite(wd["text"], kw and kw_p > 0.5)
                ws = pop_curve(t - self.word_t[i]) if self.anim == "words" else 1.0
                cx = M + wd["x"] - pad + spr.width / 2
                cy = M + ln["y"] + self.text_dy - pad + spr.height / 2
                paste_scaled(cv, spr, cx, cy, ws)
        cx, cy = self.x + self.bw / 2, self.y + self.bh / 2
        check_safe(self.name, cx, cy, self.bw, self.bh, self.angle)
        paste_scaled(img, cv, cx, cy, scale, self.angle)

    def impact(self):
        """Time of the slam/stamp hit (for the screen shake), or None."""
        return {"slam": self.t0 + 4 / FPS, "stamp": self.t0 + 3 / FPS}.get(self.anim)


def label(img, text, f, x, y, fill=PAPER, stroke=3, shadow=4, alpha=1.0, name=None):
    spr, pad = text_img(text, f, fill, stroke=stroke, shadow=shadow, track=0)
    check_safe(name or text, x + (spr.width - 2 * pad) / 2, y + (spr.height - 2 * pad) / 2, spr.width - 2 * pad,
               f.getmetrics()[0], 0)
    if alpha < 1:
        spr.putalpha(spr.getchannel("A").point(lambda p: int(p * alpha)))
    img.alpha_composite(spr, (round(x - pad), round(y - pad)))


# ------------------------------------------------------------------ images

def cover(src, z, fx, fy, ax, ay, size=(W, H)):
    """Fill size from src at zoom z (1 = cover), putting source point (fx, fy) at screen point (ax, ay)."""
    sw, sh = src.size
    k = max(size[0] / sw, size[1] / sh) * z
    bw, bh = size[0] / k, size[1] / k
    x0 = min(max(0.0, fx * sw - ax * bw), sw - bw)
    y0 = min(max(0.0, fy * sh - ay * bh), sh - bh)
    return src.resize(size, Image.BICUBIC, box=(x0, y0, x0 + bw, y0 + bh)).convert("RGBA")


def zoom(frame, z, fx=0.5, fy=0.5):
    return cover(frame, z, fx, fy, fx, fy)


photo = Image.open(ASSETS / "biscuit.jpg").convert("RGB")  # the real kennel photo (480x480)
note = Image.open(ASSETS / "note.png").convert("RGBA")
EYE = (0.485, 0.385)  # his near eye in biscuit.jpg

CART = ASSETS / "cartoon"
POSES = {n: Image.open(CART / f"{n}.png").convert("RGBA") for n in ("walk-a", "walk-b", "sit", "wave")}
P = 160  # padding around each pose so rotations don't clip
HEAD_CUT = (570, 380)    # in sit.png: the head is everything right of x 570 and above y 380
PIVOT = (745, 385)       # neck pivot for the head tilt
EYES = ((758, 213), (838, 207))
HEAD_BOX = (575, 10, 915, 430)
EARS_BOX = (600, 10, 900, 205)


@functools.lru_cache(maxsize=None)
def pose_img(name, head=0.0):
    """Padded pose; with head != 0 (CSS degrees), the head is split at the neck and tilted around PIVOT."""
    im = POSES[name]
    bb = im.getbbox()
    out = Image.new("RGBA", (im.width + 2 * P, im.height + 2 * P), (0, 0, 0, 0))
    if not head:
        out.alpha_composite(im, (P, P))
    else:
        feather = 50
        body = im.copy()
        a = body.getchannel("A")
        ImageDraw.Draw(a).rectangle((HEAD_CUT[0], 0, im.width, HEAD_CUT[1]), fill=0)
        body.putalpha(a)
        hl = Image.new("RGBA", out.size, (0, 0, 0, 0))
        crop = im.crop((HEAD_CUT[0], 0, im.width, HEAD_CUT[1] + feather))
        ramp = Image.linear_gradient("L").resize((crop.width, feather)).point(lambda v: 255 - v)
        m = Image.new("L", crop.size, 255)
        m.paste(ramp, (0, HEAD_CUT[1]))
        ca = Image.composite(crop.getchannel("A"), Image.new("L", crop.size, 0), m)
        crop.putalpha(ca)
        hl.alpha_composite(crop, (P + HEAD_CUT[0], P))
        hl = hl.rotate(-head, resample=Image.BICUBIC, center=(P + PIVOT[0], P + PIVOT[1]))
        out.alpha_composite(body, (P, P))
        out.alpha_composite(hl)
    return out, (bb[0] + P, bb[1] + P, bb[2] + P, bb[3] + P)


@functools.lru_cache(maxsize=512)
def pose_scaled(name, height, flip, sx, sy, head):
    im, bb = pose_img(name, head)
    k = height / (bb[3] - bb[1])
    s = im.resize((max(1, round(im.width * k * sx)), max(1, round(im.height * k * sy))), Image.LANCZOS)
    ax, ay = (bb[0] + bb[2]) / 2 * k * sx, bb[3] * k * sy
    if flip:
        s = s.transpose(Image.FLIP_LEFT_RIGHT)
        ax = s.width - ax
    return s, ax, ay


def put_cartoon(img, name, height, cx, bottom, flip=False, lean=0.0, sx=1.0, sy=1.0, head=0.0, shadow=True):
    """Place a pose by its bottom centre. lean rotates the whole body around the feet (CSS degrees)."""
    s, ax, ay = pose_scaled(name, int(height), flip, round(sx, 2), round(sy, 2), round(head * 2) / 2)
    if shadow:
        sw = int(height * 0.85)
        sh = Image.new("RGBA", (sw + 40, 60), (0, 0, 0, 0))
        ImageDraw.Draw(sh).ellipse((20, 20, 20 + sw, 40), fill=(0, 0, 0, 80))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(8)), (int(cx - sh.width / 2), int(bottom - 30)))
    if lean:
        r = int(math.hypot(max(ax, s.width - ax), max(ay, s.height - ay))) + 2
        cv = Image.new("RGBA", (2 * r, 2 * r), (0, 0, 0, 0))
        cv.alpha_composite(s, (int(r - ax), int(r - ay)))
        s, ax, ay = cv.rotate(-lean, resample=Image.BICUBIC), r, r
    img.alpha_composite(s, (round(cx - ax), round(bottom - ay)))


def cartoon_point(name, height, cx, bottom, src_xy, flip=False):
    """Screen position of a point of the (unrotated) pose, e.g. its eyes."""
    bb = POSES[name].getbbox()
    k = height / (bb[3] - bb[1])
    dx = (src_xy[0] - (bb[0] + bb[2]) / 2) * k
    return cx + (-dx if flip else dx), bottom + (src_xy[1] - bb[3]) * k


@functools.lru_cache(maxsize=None)
def crop_part(box, height, sy=1.0):
    c = POSES["sit"].crop(box)
    return c.resize((round(c.width * height / c.height), max(1, round(height * sy))), Image.LANCZOS)


GLASSES = ["##############",
           ".#ww##..#ww##.",
           ".##w##..##w##.",
           "..###....###.."]


def draw_glasses(img, cx, cy, unit):
    """Pixel 'deal with it' sunglasses centred at (cx, top=cy)."""
    u = max(2, round(unit))
    x0 = round(cx - len(GLASSES[0]) * u / 2)
    d = ImageDraw.Draw(img)
    for r, row in enumerate(GLASSES):
        for c, ch in enumerate(row):
            if ch != ".":
                d.rectangle((x0 + c * u, cy + r * u, x0 + (c + 1) * u - 1, cy + (r + 1) * u - 1),
                            fill=(10, 10, 10, 255) if ch == "#" else (255, 255, 255, 255))


# ------------------------------------------------------------------ clips

def probe(path, entry):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", entry, "-of",
                          "csv=p=0", str(path)], capture_output=True, text=True, check=True).stdout.strip()
    return out.split("\n")[0]


def clip_path(name):
    real = ASSETS / "v2" / f"{name}.mp4"
    return real if real.exists() else ASSETS / "v2" / f"standin-{name}.mp4"


class Clip:
    """Streams a clip as 1080x1920 cover-cropped frames at its native rate; get(s) returns the frame at source
    second s (blending neighbours for slow motion). Sequential reads keep one ffmpeg pipe open."""
    sequential = True

    def __init__(self, path):
        self.path = path
        num, den = probe(path, "stream=r_frame_rate").split("/")
        self.fps = float(num) / float(den)
        self.dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                         "csv=p=0", str(path)], capture_output=True, text=True).stdout)
        self.proc, self.start, self.frames, self.k = None, 0.0, {}, -1

    def _open(self, start):
        self.close()
        vf = f"scale={W}:{H}:force_original_aspect_ratio=increase:flags=bicubic,crop={W}:{H}"
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.4f}", "-i", str(self.path),
                                      "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL)  # killed early on purpose; hide the broken pipe
        self.start, self.frames, self.k = start, {}, -1

    def _read(self):
        buf = self.proc.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            return False
        self.k += 1
        self.frames[self.k] = Image.frombytes("RGB", (W, H), buf)
        self.frames.pop(self.k - 3, None)
        return True

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.wait()
            self.proc = None

    def get(self, s, blend=False):
        s = clamp(s, 0.0, self.dur - 1.5 / self.fps)
        if not Clip.sequential or self.proc is None or s < self.start + (self.k - 2) / self.fps:
            self._open(max(0.0, s - 0.001))
        pos = (s - self.start) * self.fps
        i = int(math.floor(pos + 1e-6))
        while self.k < i + 1 and self._read():
            pass
        if not self.frames:
            return Image.new("RGB", (W, H), INK)
        i = min(i, self.k)
        a = self.frames.get(i) or self.frames[max(self.frames)]
        b = self.frames.get(i + 1)
        frac = pos - i
        out = Image.blend(a, b, frac) if (blend and b is not None and 0.05 < frac < 0.95) else a
        if not Clip.sequential:
            self.close()
        return out


E_PATH = ASSETS / "yard-clip.mp4"


def speed_ramp(t, t0, src0, v0, v1=None, ra=None, rb=None):
    """Source second for a speed ramp: v0 until ra, linear to v1 by rb, then v1."""
    if v1 is None:
        return src0 + v0 * (t - t0)
    s = v0 * (min(t, ra) - t0)
    if t > ra:
        u = min(t, rb) - ra
        s += v0 * u + (v1 - v0) * u * u / (2 * (rb - ra))
    if t > rb:
        s += v1 * (t - rb)
    return src0 + s


# ------------------------------------------------------------------ shots

KENNEL_BLUR = cover(photo, 1.0, *EYE, 0.5, 0.45).filter(ImageFilter.GaussianBlur(18))
KENNEL_BLUR = Image.blend(KENNEL_BLUR, Image.new("RGBA", (W, H), INK + (255,)), 0.35)


def unsharp(im):
    return im.filter(ImageFilter.UnsharpMask(radius=3, percent=60, threshold=2))


def shot_tight(t):
    z = 1.35 * (1 + 0.15 * ease_out(t / 1.0))  # punch-in 1.00 -> 1.15 (on a tight base crop)
    ax = 0.56 + 2 / W * math.sin(2 * math.pi * 0.9 * t)  # 2 px handheld drift
    ay = 0.52 + 2 / H * math.cos(2 * math.pi * 0.7 * t)
    return unsharp(cover(photo, z, EYE[0], EYE[1], ax, ay))


STEEL_LAYER = Image.new("RGBA", (W, H), STEEL + (255,))


def shot_wide(t):
    r = t - 1.0
    z = 1.0 + 0.12 * (1 - ease_out(r / 0.25))  # quick zoom-out
    im = cover(photo, z, EYE[0], EYE[1], 0.5, 0.45)
    im = ImageEnhance.Color(im.convert("RGB")).enhance(0.6).convert("RGBA")  # 40% desaturated
    return Image.blend(im, STEEL_LAYER, 0.22)                                 # steel tint


NOTE_SCALE, NOTE_C = 1.45, (480, 800)
# The highlighter path across "total sweetheart in" / "the yard." in note.png pixels: (x0, y0, x1, y1) per line.
NOTE_HL = [(214, 92, 538, 74), (34, 153, 192, 144)]


@functools.lru_cache(maxsize=64)
def note_marked(p):
    """note.png with the lime highlighter swept p (0-1) along NOTE_HL, keeping the handwriting dark."""
    im = note.copy()
    if p <= 0:
        return im
    lens = [math.hypot(x1 - x0, y1 - y0) for x0, y0, x1, y1 in NOTE_HL]
    todo = p * sum(lens)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for (x0, y0, x1, y1), ln in zip(NOTE_HL, lens):
        if todo <= 0:
            break
        k = min(1.0, todo / ln)
        xe, ye = x0 + (x1 - x0) * k, y0 + (y1 - y0) * k
        d.line((x0, y0, xe, ye), fill=LIME + (215,), width=40)
        todo -= ln
    lum = im.convert("L")
    text_mask = lum.point(lambda v: 255 if v < 120 else 0)
    im.alpha_composite(layer)
    im.paste(note, (0, 0), text_mask)  # put the ink back on top
    return im


def note_layer(img, t):
    r = t - 2.0
    keys = [1.3, 1.12, 0.97, 0.99, 1.0]  # slap-in over 4 frames
    f = int(r * FPS)
    s = keys[f] if f < len(keys) else 1.0
    rot = [-6, -3, -1, 0, 0][f] if f < 5 else 0
    p = round(ease((t - 2.1) / 0.4) * 24) / 24
    spr = note_marked(p)
    paste_scaled(img, spr, NOTE_C[0], NOTE_C[1], NOTE_SCALE * s, rot)


def ears_behind_note(img, t):
    r = t - 2.0
    bounce = 1.0
    if 0.25 <= r < 0.65:  # ears perk up: scale-Y bounce
        u = (r - 0.25) / 0.4
        bounce = 1 + 0.28 * math.sin(math.pi * u) * (1 - u) * 2
    ears = crop_part(EARS_BOX, 150, round(bounce, 2))
    img.alpha_composite(ears, (690, 440 - ears.height))


def shot_note(t):
    img = KENNEL_BLUR.copy()
    ears_behind_note(img, t)
    note_layer(img, t)
    return img


def shot_wipe(t):
    img = KENNEL_BLUR.copy()
    note_layer(img, max(t, 2.99))
    edge = wipe_x(t)
    if edge > 0:
        img.paste(LIME + (255,), (0, 0, min(W, int(edge)), H))
    return img


def walker_x(t):  # the 3.0-3.9 crossing
    return -230 + (W + 460) * clamp((t - 3.0) / 0.88)


def wipe_x(t):
    return W if t >= 3.88 else walker_x(t) - 20


# Clips: (name, path, shot start, mapping t -> source second, blend frames, ambience mode)
CLIPS = {
    "V1": Clip(clip_path("V1")), "V2": Clip(clip_path("V2")), "V3": Clip(clip_path("V3")),
    "V4": Clip(clip_path("V4")),
    "E1": Clip(E_PATH), "E2": Clip(E_PATH), "E3": Clip(E_PATH), "E4": Clip(E_PATH),
}
V3_BG_SPEED = clamp((CLIPS["V3"].dur - 1.5 - 0.1) / 4.5, 0.2, 1.0)


def v3_src(t):
    return t - 13.0 if t < 14.5 else 1.5 + V3_BG_SPEED * (t - 14.5)


def shot_v1(t):
    f = CLIPS["V1"].get(t - 4.0)
    return zoom(f, 1.0 + 0.08 * (1 - ease_out((t - 4.0) / 0.3)))  # 1.08 zoom punch, decays over 0.3 s


def shot_v2(t):
    return zoom(CLIPS["V2"].get(speed_ramp(t, 6.0, 0.0, 1.0, 0.7, 6.4, 6.8), blend=True), 1.02)


def shot_e_trot(t):
    return zoom(CLIPS["E1"].get(2.0 * (t - 7.5), blend=True), 1.0)


def shot_e_wait(t):
    return zoom(CLIPS["E2"].get(5.5 + (t - 9.0)), 1.0 + 0.06 * ease((t - 9.0) / 1.0), 0.5, 0.55)


def shot_e_lean(t):
    s = speed_ramp(t, 10.0, 6.5, 1.0, 0.44, 10.0, 10.3)
    return zoom(CLIPS["E3"].get(s, blend=True), 1.10 + 0.03 * ease((t - 10.0) / 1.5), 0.5, 0.75)


def shot_e_scratch(t):
    r = t - 11.5
    img = zoom(CLIPS["E4"].get(7.6 + r), 1.10 + 0.12 * (1 - ease_out(r / 0.3)), 0.5, 0.75)
    if r < 0.15:  # soft cross-zoom from the lean shot
        prev = shot_e_lean(11.5 - 1 / FPS)
        prev = zoom(prev.convert("RGB"), 1.0 + 0.4 * ease(r / 0.15))
        img = Image.blend(prev, img, ease(r / 0.15))
    return img


def shot_v3(t):
    return zoom(CLIPS["V3"].get(v3_src(t), blend=True), 1.0 + 0.08 * ease((t - 13.0) / 1.5))


DARK = Image.new("RGBA", (W, H), (0, 0, 0, 255))


def shot_v3_bg(t):
    f = CLIPS["V3"].get(v3_src(t), blend=True).resize((W // 4, H // 4), Image.BILINEAR)
    f = f.filter(ImageFilter.GaussianBlur(5)).resize((W, H), Image.BICUBIC).convert("RGBA")  # ~20 px blur
    return Image.blend(f, DARK, 0.35)


def shot_v4(t):
    return zoom(CLIPS["V4"].get(t - 19.0), 1.0 + 0.10 * ease((t - 19.0) / 3.5), 0.5, 0.6)


GRAIN = []
for seed in range(4):
    g = Image.effect_noise((W // 2, H // 2), 22).resize((W, H), Image.NEAREST)
    green = Image.new("RGB", (W, H), YARD)
    GRAIN.append(Image.blend(green, Image.merge("RGB", (g, g, g)), 0.06).convert("RGBA"))


def end_x(t):  # the bookend walker: crosses to the phone line by 22.9
    return -230 + (790 + 230) * ease_out((t - 22.5) / 0.4)


def end_wipe(t):
    if t >= 23.0:
        return W
    if t < 22.9:
        return end_x(t) - 20
    return 770 + (W - 770) * ease((t - 22.9) / 0.1)


def shot_end(t):
    g = GRAIN[int(t * FPS) % 4].copy()
    edge = end_wipe(t)
    if edge < W:
        bg = shot_v4(t)
        bg.paste(g.crop((0, 0, max(1, int(edge)), H)), (0, 0))
        return bg
    return g


SHOTS = [(0.0, 1.0, shot_tight), (1.0, 2.0, shot_wide), (2.0, 3.0, shot_note), (3.0, 4.0, shot_wipe),
         (4.0, 6.0, shot_v1), (6.0, 7.5, shot_v2), (7.5, 9.0, shot_e_trot), (9.0, 10.0, shot_e_wait),
         (10.0, 11.5, shot_e_lean), (11.5, 13.0, shot_e_scratch), (13.0, 14.5, shot_v3), (14.5, 19.0, shot_v3_bg),
         (19.0, 22.5, shot_v4), (22.5, 26.0, shot_end)]

# Ambience under the beat (clip, source start, t0, t1, mode). Mode 'solo' = the 9.0-10.0 music stop.
AMBIENCE = [(clip_path("V1"), 0.0, 4.0, 6.0, "duck12"), (clip_path("V2"), 0.0, 6.0, 7.5, "duck"),
            (E_PATH, 0.0, 7.5, 9.0, "duck"), (E_PATH, 5.5, 9.0, 10.0, "solo"), (E_PATH, 6.5, 10.0, 11.5, "duck"),
            (E_PATH, 7.6, 11.5, 13.0, "duck"), (clip_path("V3"), 0.0, 13.0, 19.0, "duck"),
            (clip_path("V4"), 0.0, 19.0, 22.5, "duck")]


# ------------------------------------------------------------------ captions + stats card

CAPS = [
    Cap(0.0, 1.0, ["POV: you almost", "walked past him"], "hl", 100, y=300, anim="none",
        keyword=("walked", "past")),
    Cap(1.0, 2.0, ["Kennel him:", "nervous at the front."], "chip", 88, y=CHIP_Y, anim="words"),
    Cap(3.0, 4.0, ["Yard him in"], "over", 104, y=300, anim="pop"),
    Cap(3.25, 3.5, ["3"], "over", 220, center=True, y=560, anim="slam"),
    Cap(3.5, 3.75, ["2"], "over", 220, center=True, y=560, anim="slam"),
    Cap(3.75, 4.0, ["1"], "over", 220, center=True, y=560, anim="slam"),
    Cap(4.0, 6.0, ["YARD GUY."], "hl", 210, center=True, y=330, anim="slam"),
    Cap(6.0, 7.5, ["Different dog.", "Same Biscuit."], "over", 100, y=300, anim="words"),
    Cap(7.5, 9.0, ["Then he does", "the thing…"], "over", 100, y=300, anim="words", keyword=("thing…",),
        kw_at=7.5 + 4 * 4 / FPS),
    Cap(9.0, 10.0, ["wait for it"], "over", 72, y=300, anim="pop"),
    Cap(10.0, 11.5, ["CERTIFIED", "LEANER"], "sticker", 120, y=300, anim="stamp"),
    Cap(11.5, 13.0, ["Ear scratch:", "accepted."], "hl", 100, y=300, anim="pop"),
    Cap(13.0, 14.5, ["Main character", "energy."], "hl", 100, y=300, anim="pop", exit_scale=True),
    Cap(19.0, 20.0, ["Here since", "January 15."], "hl", 100, y=300, anim="words"),
    Cap(20.0, 21.0, ["Ask for him", "by name."], "hl", 100, y=300, anim="words"),
    Cap(21.0, 22.5, ["Come meet the", "real him."], "hl", 100, y=300, anim="words"),
]

STATS = [("CLASS", "Shepherd mix, male, about 3"), ("BUILD", "Large, tan and black"),
         ("SPECIAL MOVE", "The lean (one-on-one)"), ("BUFFS", "Neutered, vaccinated, heartworm negative"),
         ("ALSO", "House trained"), ("HEADS UP", "Shy at the kennel front.")]
CARD_X, CARD_Y, CARD_W = 60, 400, 840
VAL_X = 340


def wrap(text, f, max_w):
    lines, cur = [], ""
    for w in text.split():
        trial = (cur + " " + w).strip()
        if text_w(trial, f, -0.02) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


@functools.lru_cache(maxsize=None)
def stats_parts():
    """Card base (title) and one sprite per row, laid out once."""
    pad = 40
    rows, y = [], 0
    vf, lf = brico(46), figtree(26, 800)
    for lab, val in STATS:
        lines = wrap(val, vf, CARD_W - VAL_X - pad + CARD_X)
        h = 58 * len(lines) + 22
        spr = Image.new("RGBA", (CARD_W - 2 * pad, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(spr)
        lw = lf.getlength(lab)
        chip = STEEL if lab == "HEADS UP" else LIME
        d.rounded_rectangle((0, 6, lw + 24, 50), 8, fill=chip)
        d.text((12, 13), lab, font=lf, fill=PAPER if lab == "HEADS UP" else INK)
        for i, ln in enumerate(lines):
            t_im, tp = text_img(ln, vf, INK)
            spr.alpha_composite(t_im, (VAL_X - CARD_X - pad - tp, i * 58 - tp - 4))
        rows.append((spr, y))
        y += h
    title_h = 170
    card_h = pad + title_h + y + pad - 10
    base = Image.new("RGBA", (CARD_W + 30, card_h + 30), (0, 0, 0, 0))
    d = ImageDraw.Draw(base)
    d.rounded_rectangle((10, 10, CARD_W + 10, card_h + 10), 28, fill=INK)
    d.rounded_rectangle((0, 0, CARD_W, card_h), 28, fill=PAPER, outline=INK, width=4)
    t_im, tp = text_img("BISCUIT", brico(96), INK)
    base.alpha_composite(t_im, (pad - tp, pad - tp - 18))
    fee, fp = text_img("FEE $150", brico(44), INK)
    fx = CARD_W - pad - fee.width + 2 * fp
    d.rectangle((fx - 14, pad + 14, CARD_W - pad + 14, pad + 74), fill=LIME)
    base.alpha_composite(fee, (fx - fp, pad + 14 + 6 - fp - 2))
    d.text((pad, pad + 102), "shepherd mix", font=figtree(34, 700), fill=STEEL)
    d.line((pad, pad + title_h - 14, CARD_W - pad, pad + title_h - 14), fill=INK, width=3)
    return base, rows, pad + title_h, card_h


def draw_stats(img, t):
    base, rows, rows_y, card_h = stats_parts()
    r = t - 14.5
    slide = (1 - ease_out_back(r / 0.3, 1.2)) * 1100  # slides up from below with a small overshoot
    y0 = CARD_Y + slide
    card = base.copy()
    for i, (spr, ry) in enumerate(rows):
        tr = t - (15.0 + 0.5 * i)
        if tr < 0:
            continue
        paste_scaled(card, spr, 40 + spr.width / 2, rows_y + ry + spr.height / 2, pop_curve(tr))
    img.alpha_composite(card, (CARD_X, round(y0)))
    if r >= 0.3:
        check_safe("stats card", CARD_X + CARD_W / 2, y0 + card_h / 2, CARD_W, card_h, 0)
    hdr_a = clamp((t - 14.55) / 0.1)
    if hdr_a > 0:
        label(img, "Character stats:", fraunces(76), 60, 284, PAPER, stroke=0, shadow=5, alpha=hdr_a)
    return y0


# ------------------------------------------------------------------ end card

def end_card(img, t):
    r = t - 22.95
    if r >= 0:
        s = pop_curve(r)
        spr, pad = text_img("Kennel shy.", brico(150), PAPER, shadow=7)
        check_safe("Kennel shy.", 60 + (spr.width - 2 * pad) / 2, 290 + 75, spr.width - 2 * pad, 130, 0)
        paste_scaled(img, spr, 60 - pad + spr.width / 2, 270 - pad + spr.height / 2, s)
    END_CAP.draw(img, t)
    if t >= 23.25:
        s = pop_curve(t - 23.25)
        spr, pad = text_img("Biscuit", fraunces(110), WHEAT, shadow=0, track=0)
        paste_scaled(img, spr, 60 - pad + spr.width / 2, 640 - pad + spr.height / 2, s)
        label(img, "shepherd mix · fee $150", figtree(40, 600), 62, 800, PAPER, stroke=0, shadow=0)
    if t >= 23.4:
        s = pop_curve(t - 23.4)
        spr, pad = text_img("Call (555) 010-2200", brico(120), LIME, shadow=6)
        check_safe("phone", 60 + (spr.width - 2 * pad) / 2, 1030, spr.width - 2 * pad, 130, 0)
        paste_scaled(img, spr, 60 - pad + spr.width / 2, 950 - pad + spr.height / 2, s)
    if t >= 23.55:
        line = "Second Chance Rescue (fictional)" + ("  ·  Link in bio" if SOCIAL else "")
        label(img, line, figtree(38, 600), 62, 1112, PAPER, stroke=0, shadow=0)
    if t >= 23.0:  # disclosure: on screen 23.0-26.0
        label(img, "Yard photo and videos made with AI from his kennel photo", figtree(30, 600), 62, 1200, WHEAT,
              stroke=0, shadow=0)
        label(img, "Training exercise · fictional shelter", figtree(30, 600), 62, 1240, WHEAT, stroke=0, shadow=0)


END_CAP = Cap(23.1, 26.01, ["Yard guy."], "hl", 150, y=450, anim="slam")


# ------------------------------------------------------------------ cartoon choreography

def walk_pose(t, step=0.125):
    return ("walk-a", "walk-b")[int(t / step) % 2]


def bob(t, step=0.125):
    return 6 * abs(math.sin(math.pi * (t % step) / step))


def cartoon_front(img, t, card_y=None):
    if 0.1 <= t < 1.0:  # head peeks up from the bottom-right edge, wide eyes
        u = ease_out_back((t - 0.1) / 0.3)
        wide = 1 + 0.08 * math.sin(math.pi * clamp((t - 0.45) / 0.2))
        head = crop_part(HEAD_BOX, 380, round(wide, 2))
        top = H + 10 - (H + 10 - 1490) * u
        img.alpha_composite(head, (650, round(top - (head.height - 380))))
    elif 3.0 <= t < 3.9:  # walk cycle across, pulling the lime wipe
        put_cartoon(img, walk_pose(t), 340, walker_x(t), 1330 - bob(t))
    elif 6.0 <= t < 7.5:  # pops in lower left, head tilt synced to the real tilt at 6.6
        r = t - 6.1
        if r >= 0:
            s = pop_curve(r)
            tilt = 15 * ease((t - 6.5) / 0.2) * (1 - ease((t - 7.25) / 0.2))
            put_cartoon(img, "sit", 260 * s, 210, LANE, head=tilt)
    elif 7.5 <= t < 9.0:  # walks in from the right, following him
        x = W + 220 - (W + 220 - 790) * ease_out((t - 7.5) / 1.4)
        put_cartoon(img, walk_pose(t), 260, x, LANE - bob(t), flip=True)
    elif 9.0 <= t < 10.0:  # freezes mid-step and looks over at the dog
        look = -12 * ease((t - 9.1) / 0.2)
        put_cartoon(img, "walk-a", 260, 790, LANE, flip=True, head=look)
    elif 10.0 <= t < 11.5:  # leans its whole body into the sticker
        lean = -18 * ease_out_back((t - 10.05) / 0.25)
        put_cartoon(img, "sit", 280, 640, 610, flip=True, lean=lean, shadow=False)
    elif 11.5 <= t < 13.0:  # squash-and-stretch bounces on 12.0 and 12.5
        sx = sy = 1.0
        for b in (12.0, 12.5):
            u = (t - b) / 0.25
            if 0 <= u < 1:
                sq = math.sin(math.pi * u) * (1 - u)
                sx, sy = 1 + 0.25 * sq, 1 - 0.22 * sq
                if u > 0.35:
                    sx, sy = 1 - 0.1 * sq, 1 + 0.14 * sq
        put_cartoon(img, "sit", 250, 790, LANE, sx=sx, sy=sy)
    elif 13.0 <= t < 14.5:  # sits at the bottom; pixel sunglasses drop at 14.0
        put_cartoon(img, "sit", 260, 210, LANE)
        sunglasses(img, t, 260, 210, LANE)
    elif 14.5 <= t < 19.0 and card_y is not None:  # sits on the card's top-right corner, still in shades
        put_cartoon(img, "sit", 200, 790, card_y + 6, shadow=False)
        sunglasses(img, 15.0, 200, 790, card_y + 6)
    elif 19.0 <= t < 21.0:  # sits beside the frame, mirroring his pose
        put_cartoon(img, "sit", 240, 200, LANE)
    elif 21.0 <= t < 22.5:  # waves at the camera
        waving = int((t - 21.0) / 0.25) % 2 == 0
        put_cartoon(img, "wave" if waving else "sit", 250, 200, LANE, lean=-4 if waving else 3)
    elif t >= 22.5:  # bookend walk across, then waves and sits on the phone line
        if t < 22.9:
            put_cartoon(img, walk_pose(t), 260, end_x(t), 960 - bob(t), shadow=False)
        elif t < 24.4:
            waving = int((t - 22.9) / 0.3) % 2 == 0
            put_cartoon(img, "wave" if waving else "sit", 260, 790, 960, lean=-4 if waving else 3, shadow=False)
        else:
            put_cartoon(img, "sit", 260, 790, 960, shadow=False)


def sunglasses(img, t, height, cx, bottom):
    ex = (EYES[0][0] + EYES[1][0]) / 2
    gx, gy = cartoon_point("sit", height, cx, bottom, (ex - 6, 192))
    u = height / 880 * 12
    drop = 1 - ease_out_back((t - 14.0) / 0.18, 1.0)
    if t >= 14.0:
        draw_glasses(img, gx, round(gy - drop * 220), u)


def cartoon_behind(img, t):
    if 1.0 <= t < 2.0:  # ducks behind the caption box: only the ears show
        r = t - 1.0
        dy = -50 * (1 - ease_out(r / 0.2))
        ears = crop_part(EARS_BOX, 120)
        img.alpha_composite(ears, (470, round(CHIP_Y + 36 - ears.height + dy)))


# ------------------------------------------------------------------ frame

def shot_at(t):
    return next(s for s in SHOTS if s[0] <= t < s[1]) if t < DURATION else SHOTS[-1]


IMPACTS = [c.impact() for c in CAPS + [END_CAP] if c.impact() is not None]


def shake(img, t):
    for hit in IMPACTS:
        k = (t - hit) * FPS
        if -0.01 <= k < 6:
            a = 8 * (1 - k / 6)
            dx, dy = round(a * math.cos(k * 2.4)), round(a * math.sin(k * 2.4 + 1.1))
            big = img.resize((W + 24, H + 42), Image.BICUBIC)
            return big.crop((12 + dx, 21 + dy, 12 + dx + W, 21 + dy + H))
    return img


FLASH = Image.new("RGBA", (W, H), LIME + (255,))


def frame(t):
    img = shot_at(t)[2](t)
    if img.mode != "RGBA":
        img = img.convert("RGBA")
    cartoon_behind(img, t)
    card_y = draw_stats(img, t) if 14.5 <= t < 19.0 else None
    for c in CAPS:
        c.draw(img, t)
    if 1.0 <= t < 2.0:
        f = figtree(30, 800)
        r = t - 1.05
        if r >= 0:
            spr = Image.new("RGBA", (int(f.getlength("REAL PHOTO")) + 32, 50), (0, 0, 0, 0))
            d = ImageDraw.Draw(spr)
            d.rounded_rectangle((0, 0, spr.width - 1, 49), 25, fill=INK)
            d.text((16, 9), "REAL PHOTO", font=f, fill=PAPER)
            check_safe("REAL PHOTO", 64 + spr.width / 2, REAL_Y + 25, spr.width, 50, 0)
            paste_scaled(img, spr, 64 + spr.width / 2, REAL_Y + 25, pop_curve(r))
    if 2.1 <= t < 3.0:
        label(img, "Staff note, kennel D-14", figtree(40, 700), 62, 1236, PAPER, stroke=3, shadow=4)
    if t >= 22.5:
        end_card(img, t)
    cartoon_front(img, t, card_y)
    n = round(t * FPS)
    if n in (120, 121):  # the one lime flash, on the drop (2 frames)
        img = Image.blend(img, FLASH, 0.85 if n == 120 else 0.4)
    img = shake(img, t)
    return img.convert("RGB")


# ------------------------------------------------------------------ main

def main():
    n = int(round(DURATION * FPS))
    silent = OUT.with_suffix(".silent.mp4")
    wav = OUT.with_suffix(".wav")
    p = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                          "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "20",
                          "-pix_fmt", "yuv420p", "-profile:v", "high", str(silent)], stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
        if i % 60 == 0:
            print(f"frame {i}/{n}", flush=True)
    p.stdin.close()
    p.wait()
    stats = beat_v2.build_mix(wav, AMBIENCE)
    print("audio", stats)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(silent), "-i", str(wav), "-map", "0:v", "-map",
                    "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{DURATION}", "-movflags",
                    "+faststart", str(OUT)], check=True)
    silent.unlink()
    wav.unlink()
    Clip.sequential = False
    frame(4.3).save(OUT.with_name("poster-v2.jpg"), quality=88)  # "YARD GUY." just after the flash
    if SAFE_LOG:
        print("outside safe zone:", sorted(set(SAFE_LOG)))


if __name__ == "__main__":
    if len(sys.argv) > 3:
        Clip.sequential = False
        for s in sys.argv[3:]:
            frame(float(s)).save(OUT.parent / f"preview_v2_{s}.jpg", quality=85)
        if SAFE_LOG:
            print("outside safe zone:", sorted(set(SAFE_LOG)))
    else:
        main()
