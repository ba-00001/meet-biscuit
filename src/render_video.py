"""Render Biscuit's 30-second vertical story video (1080x1920, 30 fps, H.264).

Usage: python src/render_video.py <assets_dir> <out.mp4>
assets_dir holds biscuit.jpg, note.png (staff sticky note, transparent corners),
fonts/*.ttf and tokens.json (palette + font files).
"""
import functools
import json
import math
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
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


def lerp(a, b, k):
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


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


photo = Image.open(ASSETS / "biscuit.jpg").convert("RGB")
photo_grey = ImageEnhance.Brightness(ImageEnhance.Color(photo).enhance(0.15)).enhance(0.7)
note = Image.open(ASSETS / "note.png").convert("RGBA")

# Scene timeline in seconds.
S = [0, 5, 10, 15, 21, 26.5, 32]
DURATION = S[-1]


def frame(t):
    dark, light = C["ink"], C["paper"]
    warm = C["accent"]
    if t < S[2]:
        bg = dark
    elif t < S[3]:
        bg = lerp(dark, C["deep"], fade(t, S[2], 1.2))
    elif t < S[5]:
        bg = lerp(C["deep"], light, fade(t, S[3], 1.0))
    else:
        bg = lerp(light, warm, fade(t, S[5], 0.8))
    img = Image.new("RGBA", (W, H), bg + (255,))

    if t < S[3]:
        # Scene 1-3: the kennel photo. Colour drains in scene 2, shrinks in scene 3.
        k = (t - S[0]) / (S[3] - S[0])
        scale = 1.9 + 0.25 * k
        if t >= S[2]:
            scale *= 1 - 0.35 * fade(t, S[2], 1.4)
        src = photo if t < S[1] else Image.blend(photo, photo_grey, fade(t, S[1], 1.2))
        out = 1 - fade(t, S[3] - 0.6, 0.6)
        paste_center(img, src, W / 2, 920 - 260 * fade(t, S[2], 1.4), scale, alpha=out)

    # Scene 1
    if t < S[1] + 0.4:
        a = fade(t, 0.5) * (1 - fade(t, S[1] - 0.2, 0.6))
        text_block(img, ["This is Biscuit."], 230, "display", 120, light, a)
        text_block(img, ["Shepherd mix · about 3 years old"], 1480, "body", 52, C["muted_on_dark"], fade(t, 1.6) * (1 - fade(t, S[1] - 0.2, 0.6)))
    # Scene 2
    if S[1] - 0.2 < t < S[2] + 0.4:
        a = fade(t, S[1] + 0.2) * (1 - fade(t, S[2] - 0.2, 0.6))
        text_block(img, ["In his kennel,", "he’s nervous."], 150, "display", 96, light, a)
        text_block(img, ["Most people walk right past him."], 1480, "body", 58, light, fade(t, S[1] + 1.8) * (1 - fade(t, S[2] - 0.2, 0.6)))
    # Scene 3
    if S[2] - 0.2 < t < S[3] + 0.2:
        a = fade(t, S[2] + 0.4) * (1 - fade(t, S[3] - 0.5, 0.5))
        y = text_block(img, ["He’s been waiting", "since January."], 1130, "display", 100, light, a, max_w=980)
        text_block(img, ["He isn’t even on our website."], y + 40, "body", 54, C["muted_on_dark"], fade(t, S[2] + 1.8) * (1 - fade(t, S[3] - 0.5, 0.5)))

    # Scene 4: staff sticky note, quoted large so it reads on a phone.
    if S[3] - 0.2 < t < S[4] + 0.4:
        out = 1 - fade(t, S[4] - 0.3, 0.6)
        text_block(img, ["What his caretakers say:"], 200, "body", 56, C["ink"], fade(t, S[3] + 0.4) * out)
        drop = 1 - ease((t - S[3] - 0.6) / 0.8)
        paste_center(img, note, W / 2, 780 - 300 * drop, 1.3, alpha=fade(t, S[3] + 0.6, 0.5) * out, angle=-3 + 3 * drop)
        text_block(img, ["\u201cTotal sweetheart in the yard.", "Don’t judge him at the front!\u201d"], 1260, "display", 70, C["ink"], fade(t, S[3] + 2.0) * out, max_w=980)
        text_block(img, ["Kennel staff note"], 1480, "body", 46, C["muted_on_light"], fade(t, S[3] + 2.6) * out)

    # Scene 5: what he’s like.
    if S[4] - 0.2 < t < S[5] + 0.4:
        out = 1 - fade(t, S[5] - 0.3, 0.6)
        text_block(img, ["In the play yard,", "he’s a different dog."], 260, "display", 96, C["ink"], fade(t, S[4] + 0.2) * out, max_w=1000)
        items = ["Leans on you, one-on-one", "House trained", "Ignored the office cat", "Neutered and vaccinated"]
        y = 760
        for i, item in enumerate(items):
            a = fade(t, S[4] + 1.2 + i * 0.6) * out
            if a > 0:
                d = ImageDraw.Draw(img)
                r = 18
                cx = 140
                d.ellipse((cx - r, y + 37 - r, cx + r, y + 37 + r), fill=C["accent"] + (int(255 * a),))
            text_block(img, [item], y, "body", 56, C["ink"], a, max_w=740, align="left")
            y += 150
        paste_center(img, photo, W / 2, 1560, 0.62, alpha=fade(t, S[4] + 3.4) * out)

    # Scene 6: call to action.
    if t > S[5] - 0.2:
        a = fade(t, S[5] + 0.2)
        text_block(img, ["Meet Biscuit", "in the play yard."], 330, "display", 104, C["on_accent"], a)
        paste_center(img, photo, W / 2, 1010, 1.05, alpha=fade(t, S[5] + 0.6))
        text_block(img, ["(555) 010-2200"], 1400, "display", 96, C["highlight"], fade(t, S[5] + 1.2))
        text_block(img, ["Second Chance Rescue · Whitcomb", "Adoption fee $150"], 1530, "body", 52, C["on_accent"], fade(t, S[5] + 1.6))
        text_block(img, ["Training exercise · fictional shelter"], 1800, "body", 30, C["on_accent"], fade(t, S[5] + 2.0) * 0.8)
    return img.convert("RGB")


def main():
    n = int(DURATION * FPS)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "slow", "-crf", "23",
           "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for i in range(n):
        p.stdin.write(frame(i / FPS).tobytes())
    p.stdin.close()
    p.wait()
    frame(S[5] + 3).save(Path(OUT).with_name("poster.jpg"), quality=88)


if __name__ == "__main__":
    if len(sys.argv) > 3:  # preview: render single frames at given seconds
        for s in sys.argv[3:]:
            frame(float(s)).save(Path(OUT).parent / f"preview_{s}.jpg", quality=80)
    else:
        main()
