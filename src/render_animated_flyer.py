"""Render the animated version of flyer page 1 (looping MP4, no audio).

Usage: python src/render_animated_flyer.py <flyer_page1.png> <anim.json> <assets_dir> <out.mp4> [page1-mask.png]

The still flyer render supplies the layout. anim.json (written alongside the
flyer render) gives, in page1.png pixels:
  photo: {x0, y0, x1, y1, rotation_deg}   inner image box of the photo, before rotation
  lane:  {y_bottom, x_start, x_end, max_height}   empty strip a small cartoon can cross
The Veo yard clip plays inside the photo box and the cartoon Biscuit trots out
and back along the lane, so the loop is seamless and no text is covered.
Optional page1-mask.png is the same render with the photo filled #FF00FF; the clip
then shows only where that magenta is visible, so stickers on the photo stay on top.
"""
import json
import subprocess
import sys

from PIL import Image, ImageChops

PAGE, ANIM, ASSETS, OUT = sys.argv[1:5]
MASK = sys.argv[5] if len(sys.argv) > 5 else None
FPS, DUR = 30, 10.0

page = Image.open(PAGE).convert("RGB")
W, H = page.size
spec = json.load(open(ANIM))
ph, lane = spec["photo"], spec["lane"]
bw, bh = int(ph["x1"] - ph["x0"]), int(ph["y1"] - ph["y0"])
cx, cy = (ph["x0"] + ph["x1"]) / 2, (ph["y0"] + ph["y1"]) / 2
angle = float(ph.get("rotation_deg", 0))  # CSS degrees: positive = clockwise

# The still photo as it appears on the page, un-rotated, so the fade back to it is exact.
still = page.rotate(angle, resample=Image.BICUBIC, center=(cx, cy)).crop(
    (int(cx - bw / 2), int(cy - bh / 2), int(cx - bw / 2) + bw, int(cy - bh / 2) + bh))

hgt = int(lane["max_height"])
walk = [Image.open(f"{ASSETS}/cartoon/walk-{k}.png").convert("RGBA") for k in "ab"]
walk = [w.crop(w.getbbox()) for w in walk]
walk = [w.resize((int(w.width * hgt / w.height), hgt), Image.LANCZOS) for w in walk]
walk_back = [w.transpose(Image.FLIP_LEFT_RIGHT) for w in walk]


visible = None
if MASK:  # where the photo is actually visible on the page (not under a sticker)
    r, g, b = Image.open(MASK).convert("RGB").split()
    visible = ImageChops.multiply(
        ImageChops.multiply(r.point(lambda v: 255 if v > 200 else 0), g.point(lambda v: 255 if v < 60 else 0)),
        b.point(lambda v: 255 if v > 200 else 0))


def place_photo(frame, img):
    """Paste a box-sized image onto the page at the photo's rotation."""
    tile = img.convert("RGBA").rotate(-angle, resample=Image.BICUBIC, expand=True)
    layer = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    layer.alpha_composite(tile, (int(cx - tile.width / 2), int(cy - tile.height / 2)))
    if visible is not None:
        layer.putalpha(ImageChops.multiply(layer.getchannel("A"), visible))
    frame.alpha_composite(layer)


# Cover-crop the vertical clip to the photo box around Biscuit, streamed as raw frames.
vf = (f"fps={FPS},scale={bw}:{bh}:force_original_aspect_ratio=increase,"
      f"crop={bw}:{bh}:(iw-{bw})/2:(ih-{bh})*0.35")
clip = subprocess.Popen(["ffmpeg", "-loglevel", "error", "-i", f"{ASSETS}/yard-clip.mp4", "-vf", vf,
                         "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
enc = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                        "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-crf", "22",
                        "-pix_fmt", "yuv420p", "-movflags", "+faststart", OUT], stdin=subprocess.PIPE)
last = still
for i in range(int(DUR * FPS)):
    t = i / FPS
    buf = clip.stdout.read(bw * bh * 3)
    if len(buf) == bw * bh * 3:
        last = Image.frombytes("RGB", (bw, bh), buf)
    # Fade from the still photo into the clip and back, so the loop is seamless.
    k = max(0.0, min(1.0, t / 0.8, (DUR - t) / 0.8))
    frame = page.convert("RGBA")
    place_photo(frame, Image.blend(still, last, k))
    half = DUR / 2
    out = t < half
    u = (t if out else DUR - t) / half          # 0 -> 1 -> 0
    x = int(lane["x_start"] + (lane["x_end"] - lane["x_start"] - walk[0].width) * u)
    step = int(t / 0.18) % 2
    pose = (walk if out else walk_back)[step]
    frame.alpha_composite(pose, (x, int(lane["y_bottom"]) - pose.height - 3 * step))
    enc.stdin.write(frame.convert("RGB").tobytes())
enc.stdin.close()
enc.wait()
clip.kill()
