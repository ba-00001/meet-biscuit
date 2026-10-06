# meet-biscuit

A one-page site with a short vertical video of Biscuit, a shelter dog. The
QR code on his printed adoption flyer opens this page.

This is a class exercise for MDC Basecamp 2026. Second Chance Rescue, Biscuit,
the phone number and the email address are made up.

- `index.html`: the page (GitHub Pages, served from `main`).
- `biscuit-story.mp4` and `poster.jpg`: the video and its poster frame.
- `src/render_video.py`: renders the video with Pillow and ffmpeg.

## Rebuild the video

```bash
python3 -m venv .venv && .venv/bin/pip install pillow
.venv/bin/python src/render_video.py <assets_dir> biscuit-story.mp4
```

`<assets_dir>` holds `biscuit.jpg` (original kennel photo), `biscuit-clean.jpg`
(bars removed with Gemini), `yard-clip.mp4` (Veo image-to-video of the clean
photo), `note.png`, `tokens.json` and a `fonts/` folder. Needs ffmpeg.

The edited photo and the yard clip are AI-generated; the video and the page
label them that way.
