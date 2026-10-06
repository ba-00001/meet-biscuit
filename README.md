# meet-biscuit

A one-page site with a short vertical video of Biscuit, a shelter dog. The
QR code on his printed adoption flyer opens this page.

This is a class exercise for MDC Basecamp 2026. Second Chance Rescue, Biscuit,
the phone number and the email address are made up.

Dog photo: MDC Basecamp 2026 course materials.

- `index.html`: the page (GitHub Pages, served from `main`).
- `biscuit-story.mp4` and `poster.jpg`: the 30-second video and its poster frame.
- `assets/`: the video's sources (photos, clip, staff note, fonts, palette).
- `assets/cartoon/`: transparent PNG poses of the cartoon Biscuit
  (`walk-a.png`, `walk-b.png`, `sit.png`, `wave.png`). He walks along the bottom of
  the photo scene and sits and waves on the end card. The video renders without
  him if any pose is missing.
- `src/render_video.py`: renders the video with Pillow and ffmpeg.

## Rebuild the video

```bash
python3 -m venv .venv && .venv/bin/pip install pillow
.venv/bin/python src/render_video.py <assets_dir> biscuit-story.mp4
```

`<assets_dir>` (normally `assets`) holds `biscuit.jpg` (original kennel photo),
`biscuit-clean.jpg` (bars removed with Gemini), `yard-clip.mp4` (Veo
image-to-video of the clean photo), `note.png`, `cartoon/`, `tokens.json` and a
`fonts/` folder. Needs ffmpeg. Add seconds after the output path to render
preview stills instead, e.g. `render_video.py assets /tmp/out.mp4 3.3 13.5`.

The edited photo and the yard clip are AI-generated; the video's end card, the page and the flyer say so.

## Animated flyer

`animated-flyer.mp4` is a 10-second loop of flyer page 1. The Veo yard clip plays in the
photo frame, and the cartoon Biscuit trots across the green band.
`animated-flyer.gif` and `biscuit-story-preview.gif` are small previews for READMEs.

```bash
.venv/bin/python src/render_animated_flyer.py <page1.png> <anim.json> assets animated-flyer.mp4 [page1-mask.png]
```

- `anim.json` gives the tilted photo box and an empty strip for the walking cartoon.
- The optional mask is the same render with the photo filled `#FF00FF`, so stickers on
  the photo stay on top of the clip.
- `assets/flyer-page1.png` is the current (Gen Z) page-1 render.
- `*-classic.*` files are the first flyer design, kept for comparison.
