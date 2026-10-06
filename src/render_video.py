"""Render Biscuit's 30-second vertical story video (1080x1920, 30 fps, H.264 + AAC).

Usage:
  python src/render_video.py <assets_dir> <out.mp4>            full render (+ poster.jpg beside it)
  python src/render_video.py <assets_dir> <out.mp4> 3.3 13.5   preview frames only (preview_<s>.jpg)

assets_dir holds biscuit.jpg (real kennel photo), biscuit-clean.jpg (bars removed and yard
background added with AI), yard-clip.mp4 (AI image-to-video of the clean photo), note.png
(staff sticky note, transparent corners), cartoon/{walk-a,walk-b,sit,wave}.png (optional,
transparent; the cartoon is skipped if any is missing), fonts/*.ttf and tokens.json
(palette + font files).

Timeline (s): 0-4.4 kennel photo, 4.4-7.4 staff note, 7.4-8.6 the bars wipe away,
8.6-17.6 play-yard clip (with its own audio), 17.6-23.6 clean photo while the cartoon
walks by, 23.6-30 end card with phone, email and the AI disclosure.
"""
import functools
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
DURATION = 30.0
ASSETS = Path(sys.argv[1])
OUT = sys.argv[2]
T = json.loads((ASSETS / "tokens.json").read_text())
C = {k: tuple(int(v.lstrip("#")[i:i + 2], 16) for i in (0, 2, 4)) for k, v in T["colors"].items()}


@functools.lru_cache(maxsize=None)
def font(role, size):
    f = ImageFont.truetype(str(ASSETS / "fonts" / T["fonts"][role]), size)
    axes = T.get("axes", {}).get(role)
    if axes:  # variable font: pin the weight/optical size the flyer uses
        f.set_variation_by_axes(axes)
    return f


def ease(x):
    x = max(0.0, min(1.0, x))
    return x * x * (3 - 2 * x)


def fade(t, start, dur=0.6):
    return ease((t - start) / dur)


def text_block(img, lines, y, role, size, color, alpha, max_w=920, gap=1.18, align="center"):
    """Draw wrapped text with an alpha fade and a small upward drift. Returns bottom y."""
    if alpha <= 0:
        return y
    f = font(role, size)
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    wrapped = []
    for line in lines:
        words, cur = line.split(), ""
        for w in words:
            trial = (cur + " " + w).strip()
            if d.textlength(trial, font=f) <= max_w:
                cur = trial
            else:
                wrapped.append(cur)
                cur = w
        wrapped.append(cur)
    yy = y + int((1 - alpha) * 30)
    for line in wrapped:
        lw = d.textlength(line, font=f)
        x = (W - lw) / 2 if align == "center" else (W - max_w) / 2
        d.text((x, yy), line, font=f, fill=color + (int(255 * alpha),))
        yy += int(size * gap)
    img.alpha_composite(layer)
    return yy


def paste_center(img, src, cx, cy, scale, alpha=1.0, angle=0.0, shadow=True):
    s = src.resize((int(src.width * scale), int(src.height * scale)), Image.LANCZOS).convert("RGBA")
    if angle:
        s = s.rotate(angle, resample=Image.BICUBIC, expand=True)
    if alpha < 1:
        a = s.getchannel("A").point(lambda p: int(p * alpha))
        s.putalpha(a)
    if shadow:
        sh = Image.new("RGBA", (s.width + 80, s.height + 80), (0, 0, 0, 0))
        sh.paste((0, 0, 0, int(110 * alpha)), (40, 52, 40 + s.width, 52 + s.height), s.getchannel("A"))
        sh = sh.filter(ImageFilter.GaussianBlur(22))
        img.alpha_composite(sh, (int(cx - sh.width / 2), int(cy - sh.height / 2)))
    img.alpha_composite(s, (int(cx - s.width / 2), int(cy - s.height / 2)))


def cover(src, z, fx, fy, ax, ay):
    """Fill the frame from src at zoom z (1 = cover), putting source point (fx, fy) at screen
    point (ax, ay), all as 0-1 fractions. The crop box is clamped inside the source."""
    sw, sh = src.size
    k = max(W / sw, H / sh) * z
    bw, bh = W / k, H / k
    x0 = min(max(0.0, fx * sw - ax * bw), sw - bw)
    y0 = min(max(0.0, fy * sh - ay * bh), sh - bh)
    return src.resize((W, H), Image.BICUBIC, box=(x0, y0, x0 + bw, y0 + bh)).convert("RGBA")


def gradient(img, top=True, strength=170, height=760):
    g = Image.linear_gradient("L").resize((W, height))
    if top:
        g = g.transpose(Image.FLIP_TOP_BOTTOM)
    layer = Image.new("RGBA", (W, height), (0, 0, 0, 0))
    layer.putalpha(g.point(lambda p: int(p * strength / 255)))
    img.alpha_composite(layer, (0, 0 if top else H - height))


photo = Image.open(ASSETS / "biscuit.jpg").convert("RGB")
clean = Image.open(ASSETS / "biscuit-clean.jpg").convert("RGB")
note = Image.open(ASSETS / "note.png").convert("RGBA")
CLIP = ASSETS / "yard-clip.mp4"  # AI-generated (Veo) image-to-video of the clean photo
EYE = (0.485, 0.385)  # his near eye; same spot in both photos (the clean one is registered to the original)

CARTOON_DIR = ASSETS / "cartoon"
HAS_CARTOON = all((CARTOON_DIR / f"{n}.png").exists() for n in ("walk-a", "walk-b", "sit", "wave"))


@functools.lru_cache(maxsize=None)
def cartoon(name, height, flip=False):
    im = Image.open(CARTOON_DIR / f"{name}.png").convert("RGBA")
    im = im.crop(im.getbbox())
    im = im.resize((round(im.width * height / im.height), height), Image.LANCZOS)
    return im.transpose(Image.FLIP_LEFT_RIGHT) if flip else im


def put_cartoon(img, name, height, cx, bottom, flip=False):
    """Place a cartoon pose by its bottom centre, with a soft ground shadow."""
    c = cartoon(name, height, flip)
    sw = int(c.width * 0.8)
    sh = Image.new("RGBA", (sw + 60, 90), (0, 0, 0, 0))
    ImageDraw.Draw(sh).ellipse((30, 30, 30 + sw, 60), fill=(0, 0, 0, 70))
    sh = sh.filter(ImageFilter.GaussianBlur(10))
    img.alpha_composite(sh, (int(cx - sh.width / 2), int(bottom - 45)))
    img.alpha_composite(c, (int(cx - c.width / 2), int(bottom - c.height)))


def probe_duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out)


class ClipReader:
    """Streams the yard clip as 1080x1920 frames at FPS, cover-cropped."""

    def __init__(self, path):
        self.path = path
        self.proc = None
        self.index = -1
        self.last = None

    def _open(self, start=0.0):
        vf = f"fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        self.proc = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-ss", f"{start:.3f}", "-i", str(self.path),
                                      "-vf", vf, "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)

    def get(self, local_t, sequential=True):
        local_t = max(0.0, min(local_t, CLIP_LEN - 1 / FPS))
        want = int(local_t * FPS)
        if not sequential:
            self._open(local_t)
            buf = self.proc.stdout.read(W * H * 3)
            self.proc.kill()
            self.proc = None
            return Image.frombytes("RGB", (W, H), buf) if len(buf) == W * H * 3 else self.last
        if self.proc is None:
            self._open()
        while self.index < want:
            buf = self.proc.stdout.read(W * H * 3)
            if len(buf) < W * H * 3:
                break  # clip ended: hold the last frame
            self.last = Image.frombytes("RGB", (W, H), buf)
            self.index += 1
        return self.last


CLIP_LEN = min(probe_duration(CLIP), 10.0)
CLIP_IN = 1.0  # clip second shown at YARD (skips the far-away first second)
clip = ClipReader(CLIP)
SEQUENTIAL = True

# Shot boundaries (s): kennel photo, note, wipe, yard clip, clean photo, end card.
NOTE, WIPE, YARD, PHOTO, END = 4.4, 7.4, 8.6, 17.6, 23.6
XF = 0.3  # crossfade between shots, centred on each boundary


def shot_kennel(t):
    if t < 2.2:  # slow pull-out on his eyes
        return cover(photo, 1.15 - 0.10 * ease(t / 2.2), *EYE, 0.65, 0.42)
    k = ease((t - 2.2) / 2.2)  # slow drift down the photo
    return cover(photo, 1.05, EYE[0], EYE[1] + 0.05 * k, 0.65, 0.42)


def shot_note(t):
    img = Image.new("RGBA", (W, H), C["paper"] + (255,))
    k = ease((t - NOTE) / (WIPE - NOTE))  # push-in 100 -> 110%
    paste_center(img, note, W / 2, 860, 1.55 * (1 + 0.10 * k))
    return img


def shot_wipe(t):
    z = 1.05 + 0.03 * ease((t - WIPE) / (YARD - WIPE))
    a = cover(photo, z, EYE[0], EYE[1] + 0.05, 0.65, 0.42)
    b = cover(clean, z, EYE[0], EYE[1] + 0.05, 0.65, 0.42)
    edge = ease((t - WIPE - 0.3) / 0.6) * (W + 160) - 80  # bars wipe away left to right over 0.6 s
    row = bytes(max(0, min(255, int((edge - x) * 255 / 80 + 128))) for x in range(W))
    a.paste(b, (0, 0), Image.frombytes("L", (W, 1), row).resize((W, H), Image.NEAREST))
    return a


def shot_yard(t):
    f = clip.get(t - YARD + CLIP_IN, sequential=SEQUENTIAL)
    return f.convert("RGBA") if f is not None else Image.new("RGBA", (W, H), C["ink"] + (255,))


def shot_photo(t):
    # Bottom-anchored so his chin stays above the cartoon's lane; slow push and pan.
    k = ease((t - PHOTO) / (END - PHOTO))
    return cover(clean, 1.08 + 0.07 * k, 0.40, 1.0, 0.52 + 0.08 * k, 1.0)


def shot_end(t):
    return Image.new("RGBA", (W, H), C["accent"] + (255,))


# (start, end, render, has light captions over a picture)
SHOTS = [(0, NOTE, shot_kennel, True), (NOTE, WIPE, shot_note, False), (WIPE, YARD, shot_wipe, True),
         (YARD, PHOTO, shot_yard, True), (PHOTO, END, shot_photo, True), (END, DURATION, shot_end, False)]


def render_shot(i, t):
    img = SHOTS[i][2](t)
    if SHOTS[i][3]:  # soft top gradient behind the light captions
        gradient(img, top=True, strength=185)
    return img


def background(t):
    i = max(j for j, s in enumerate(SHOTS) if t >= s[0])
    img = render_shot(i, t)
    if i + 1 < len(SHOTS) and t > SHOTS[i][1] - XF / 2:
        w = ease((t - SHOTS[i][1] + XF / 2) / XF)
        return Image.blend(img, render_shot(i + 1, t), w)
    if i > 0 and t < SHOTS[i][0] + XF / 2:
        w = ease((t - SHOTS[i][0] + XF / 2) / XF)
        return Image.blend(render_shot(i - 1, t), img, w)
    return img


# Light captions over the photos and the clip: (start, end, lines). Max 7 words each.
CARDS = [
    (0.0, 2.2, ["Staff left a note", "about him."]),
    (2.2, NOTE, ["Biscuit. Stray.", "Here since January 15."]),
    (WIPE, 10.4, ["Out in the yard?", "Different dog."]),
    (12.6, 15.1, ["One-on-one,", "he leans on you."]),
    (15.1, PHOTO, ["House trained.", "Neutered. Vaccinated."]),
    (PHOTO, 19.7, ["Shepherd mix,", "about 3, large."]),
    (19.7, 21.7, ["Some dogs OK,", "slow intros."]),
    (21.7, END, ["Ask us about cats."]),
]


def card_alpha(t, t0, t1, fin=0.35, fout=0.25):
    return fade(t, t0 + 0.05, fin) * (1 - fade(t, t1 - fout, fout))


def frame(t):
    img = background(t)
    on = C["on_accent"]

    for t0, t1, lines in CARDS:
        if t0 <= t < t1:
            text_block(img, lines, 230, "display", 100, C["paper"], card_alpha(t, t0, t1), max_w=1000)

    if NOTE <= t < WIPE:
        text_block(img, ["Kennel staff note"], 1460, "body", 46, C["muted_on_light"], card_alpha(t, NOTE + 0.4, WIPE))

    if HAS_CARTOON and PHOTO <= t < 23.4:  # walks left to right along the bottom 15%
        step = (t - PHOTO) / 0.18
        cx = -180 + (t - PHOTO) / (23.4 - PHOTO) * (W + 360)
        put_cartoon(img, ("walk-a", "walk-b")[int(step) % 2], 250, cx, 1895 - 8 * math.sin(math.pi * (step % 1)))

    if t >= END:
        text_block(img, ["Meet Biscuit."], 500, "display", 120, on, fade(t, END + 0.2, 0.5))
        text_block(img, ["Adoption fee $150"], 670, "body", 52, on, fade(t, END + 0.5, 0.5))
        text_block(img, ["(555) 010-2200"], 900, "display", 96, C["highlight"], fade(t, 26.6, 0.4))
        text_block(img, ["adopt@secondchancerescue.example.org"], 1030, "body", 40, on, fade(t, 26.8, 0.4), max_w=1000)
        text_block(img, ["Yard photo and video made with AI from his kennel photo", "Training exercise · fictional shelter"],
                   1784, "body", 30, on, fade(t, 26.6, 0.3), max_w=1000)
        if HAS_CARTOON:
            enter = (t - END) / 1.2
            if enter < 1:  # walks in from the right edge, facing left
                step = (t - END) / 0.18
                cx = W + 220 - ease(enter) * (W / 2 + 220)
                put_cartoon(img, ("walk-a", "walk-b")[int(step) % 2], 450, cx,
                            1750 - 8 * math.sin(math.pi * (step % 1)), flip=True)
            else:
                waving = 26.6 <= t < 28.6 and int((t - 26.6) / 0.35) % 2 == 0
                put_cartoon(img, "wave" if waving else "sit", 460, W / 2, 1750)
    return img.convert("RGB")


def main():
    global SEQUENTIAL
    n = int(round(DURATION * FPS))
    silent = str(Path(OUT).with_suffix(".silent.mp4"))
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-pix_fmt", "yuv420p", silent]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    # Yard ambience from the clip (its seconds 1-10), only under the yard scene; silence elsewhere.
    seg = CLIP_LEN - CLIP_IN
    ms = int(YARD * 1000)
    af = (f"[1:a]atrim={CLIP_IN}:{CLIP_LEN},asetpts=PTS-STARTPTS,afade=t=in:d=0.4,afade=t=out:st={seg - 0.6}:d=0.6,"
          f"adelay={ms}|{ms},apad=whole_dur={DURATION}[a]")
    r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-i", str(CLIP), "-filter_complex", af,
                        "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
                        "-shortest", "-movflags", "+faststart", OUT])
    if r.returncode != 0:  # clip has no audio track: ship the silent cut
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", silent, "-c", "copy", "-movflags", "+faststart", OUT], check=True)
    Path(silent).unlink()
    SEQUENTIAL = False  # poster is a random-access frame
    frame(28.8).save(Path(OUT).with_name("poster.jpg"), quality=88)


if __name__ == "__main__":
    if len(sys.argv) > 3:  # preview: render single frames at given seconds
        SEQUENTIAL = False
        for s in sys.argv[3:]:
            frame(float(s)).save(Path(OUT).parent / f"preview_{s}.jpg", quality=80)
    else:
        main()
