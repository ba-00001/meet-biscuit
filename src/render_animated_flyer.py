"""Render the animated version of flyer page 1 (looping MP4, no audio).

Usage: python src/render_animated_flyer.py <flyer_page1.png> <assets_dir> <out.mp4>
The still flyer render supplies the layout; the Veo yard clip plays inside the
photo frame and the cartoon Biscuit trots out and back across the empty strip
at the top of the green band (left of the QR panel), so nothing is covered.
"""
import subprocess
import sys

from PIL import Image

PAGE, ASSETS, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
FPS, DUR = 30, 10.0
BOX = (717, 496, 1140, 920)  # inner photo frame on the 1224x1584 page render
LANE_BOTTOM = 1258            # ground line inside the green band, above "Ask to meet..."
LANE_END = 860                # stop short of the QR panel

page = Image.open(PAGE).convert("RGB")
W, H = page.size
bw, bh = BOX[2] - BOX[0], BOX[3] - BOX[1]
still = page.crop(BOX)
walk = [Image.open(f"{ASSETS}/cartoon/walk-{k}.png").convert("RGBA") for k in "ab"]
walk = [w.crop(w.getbbox()) for w in walk]
walk = [w.resize((int(w.width * 64 / w.height), 64), Image.LANCZOS) for w in walk]
walk_back = [w.transpose(Image.FLIP_LEFT_RIGHT) for w in walk]

# Square crop of the vertical clip around Biscuit, streamed as raw frames.
vf = f"fps={FPS},crop=720:720:0:300,scale={bw}:{bh}"
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
    k = min(1.0, t / 0.8, (DUR - t) / 0.8)
    frame = page.copy()
    frame.paste(Image.blend(still, last, max(0.0, k)), BOX[:2])
    frame = frame.convert("RGBA")
    half = DUR / 2
    out = t < half
    u = (t if out else DUR - t) / half          # 0 -> 1 -> 0
    x = int(-90 + (LANE_END + 90) * u)
    step = int(t / 0.18) % 2
    pose = (walk if out else walk_back)[step]
    frame.alpha_composite(pose, (x, LANE_BOTTOM - pose.height - 3 * step))
    enc.stdin.write(frame.convert("RGB").tobytes())
enc.stdin.close()
enc.wait()
clip.kill()
