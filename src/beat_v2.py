"""Biscuit v2 soundtrack: a 120 BPM beat plus SFX synthesized in numpy, per the v2 hit map.

Usage:
  python src/beat_v2.py <out.wav>     beat + SFX only (no clip ambience), for auditioning

render_video_v2.py imports build_mix() and passes the clip ambience segments.
Everything here is synthesized from sine, saw and noise, so there is nothing to license.

Hit map (s): 0.0 muffled kick + vinyl crackle (whole mix low-passed at 350 Hz, -6 dB until 3.0),
2.0 paper slap, 2.1-2.5 marker squeak, 3.0-3.9 filter sweep 350 Hz -> 8 kHz + riser + 16th hats,
3.25/3.5/3.75 tick-pops, 3.9-4.0 silence, 4.0 drop + crash, 6.6 boop, 7.5 whoosh + hat roll,
9.0 record scratch then music out until 10.0, 10.0 stamp thunk + bass hit (beat back),
11.5 caption pop, 14.0 whoop, 14.5 select chime, 15.0-17.5 row ticks, 19.0 bass out,
21.0 bass back, 21.5-22.5 snare roll, 22.5 final hit + crash + ring-out, 25.5 muffled kick (loop).
"""
import json
import subprocess
import sys
import wave

import numpy as np

SR = 48000
BPM = 120
BEAT = 60 / BPM          # 0.5 s
BAR = 4 * BEAT           # 2.0 s
DURATION = 26.0
N = int(round(DURATION * SR))
RNG = np.random.default_rng(7)  # fixed seed: the same mix every render

# A minor loop, one chord per bar: Am, F, C, G (sub-bass roots A1, F1, C2, G1).
ROOTS = [55.00, 43.65, 65.41, 49.00]
CHORDS = [[220.00, 261.63, 329.63], [174.61, 220.00, 261.63], [196.00, 261.63, 329.63], [196.00, 246.94, 293.66]]


def db(x):
    return 10 ** (x / 20)


def tt(seconds):
    return np.arange(int(seconds * SR)) / SR


def place(buf, t0, sig, gain=1.0):
    """Add sig into buf starting at t0 seconds (clipped to the buffer)."""
    i = int(round(t0 * SR))
    if i >= len(buf) or i + len(sig) <= 0:
        return
    s = sig[max(0, -i):len(buf) - i]
    i = max(0, i)
    buf[i:i + len(s)] += gain * s


def fft_filter(x, lo=None, hi=None, order=4):
    """Zero-phase band filter by spectral weighting (Butterworth-shaped magnitude)."""
    n = len(x)
    f = np.fft.rfftfreq(n, 1 / SR)
    X = np.fft.rfft(x)
    g = np.ones_like(f)
    if hi:
        g *= 1 / np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        g *= 1 / np.sqrt(1 + (np.maximum(lo, 1e-9) / np.maximum(f, 1e-9)) ** (2 * order))
    return np.fft.irfft(X * g, n)


def noise(seconds):
    return RNG.uniform(-1, 1, int(seconds * SR))


def stft_lowpass(x, cutoff_at, gain_at=None, nfft=2048, hop=256):
    """Time-varying low-pass (24 dB/oct) by STFT overlap-add. cutoff_at(t) -> Hz, gain_at(t) -> linear."""
    win = np.hanning(nfft)
    pad = np.concatenate([np.zeros(nfft), x, np.zeros(nfft)])
    out = np.zeros_like(pad)
    norm = np.zeros_like(pad)
    f = np.fft.rfftfreq(nfft, 1 / SR)
    for start in range(0, len(pad) - nfft, hop):
        t = (start + nfft / 2 - nfft) / SR
        seg = pad[start:start + nfft] * win
        g = 1 / np.sqrt(1 + (f / cutoff_at(t)) ** 8)
        if gain_at:
            g = g * gain_at(t)
        out[start:start + nfft] += np.fft.irfft(np.fft.rfft(seg) * g, nfft) * win
        norm[start:start + nfft] += win ** 2
    out = out / np.maximum(norm, 1e-6)
    return out[nfft:nfft + len(x)]


# ---------------------------------------------------------------- instruments

def kick():
    t = tt(0.4)
    f = 50 + 100 * np.exp(-t / 0.04)          # 150 -> ~50 Hz inside 120 ms
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / 0.16)
    click = fft_filter(noise(0.4), lo=1500) * np.exp(-t / 0.004) * 0.3
    return np.tanh(1.6 * (body + click)) * 0.95


def clap():
    t = tt(0.3)
    env = np.zeros_like(t)
    for d in (0.0, 0.011, 0.022):              # three quick hand hits, then the tail
        env += (t >= d) * np.exp(-np.maximum(t - d, 0) / (0.006 if d < 0.02 else 0.09))
    return fft_filter(noise(0.3), lo=900, hi=2600, order=2) * env * 0.9


def hat(length=0.03):
    t = tt(0.06)
    return fft_filter(noise(0.06), lo=8000) * np.exp(-t / (length / 3)) * 0.55


def snare():
    t = tt(0.2)
    tone = np.sin(2 * np.pi * 190 * t) * np.exp(-t / 0.05)
    return (0.5 * tone + fft_filter(noise(0.2), lo=1200, hi=9000, order=2) * np.exp(-t / 0.07)) * 0.8


def crash(length=2.2):
    t = tt(length)
    metal = sum(np.sin(2 * np.pi * fr * t + RNG.uniform(0, 6)) for fr in (3150, 4280, 5370, 6620, 7930)) / 5
    return (fft_filter(noise(length), lo=4500) + 0.25 * metal) * np.exp(-t / (length / 4)) * 0.55


def saw(freq, t):
    return 2 * ((freq * t) % 1.0) - 1


def stab(chord, length=0.14):
    t = tt(length)
    s = sum(saw(fr, t) + 0.5 * saw(fr * 1.006, t) for fr in chord) / (1.5 * len(chord))
    return fft_filter(s, hi=1700, order=2) * np.minimum(1, t / 0.004) * np.exp(-t / 0.06) * 0.55


def sub_note(freq, length):
    t = tt(length)
    env = np.minimum(1, t / 0.01) * np.minimum(1, (length - t) / 0.02)
    pump = 1 - 0.65 * np.exp(-(t % BEAT) / 0.07)   # duck after every kick
    return np.sin(2 * np.pi * freq * t) * env * pump * 0.75


def tick(freq=1900):
    t = tt(0.05)
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.012) + fft_filter(noise(0.05), lo=3000) * np.exp(-t / 0.003)) * 0.6


def glide(f0, f1, length, curve=1.0, vib=0.0):
    t = tt(length)
    k = (t / length) ** curve
    f = f0 + (f1 - f0) * k + vib * np.sin(2 * np.pi * 18 * t)
    return np.sin(2 * np.pi * np.cumsum(f) / SR)


def crackle(length):
    n = int(length * SR)
    x = fft_filter(noise(length), lo=800, hi=6000, order=1) * 0.03   # faint hiss
    pops = RNG.random(n) < 40 / SR
    x[pops] += RNG.uniform(-1, 1, pops.sum()) * 0.6
    return fft_filter(x, lo=300, order=1)


# ---------------------------------------------------------------- arrangement

def music():
    """Drums, sub, stabs and section shaping. Returns (music, sfx) mono buffers."""
    drums, bass, keys, sfx = (np.zeros(N) for _ in range(4))
    K, CL, H, SN = kick(), clap(), hat(), snare()

    def bar_of(t):
        return int(t // BAR) % 4

    for b in range(int(DURATION / BEAT)):
        t = b * BEAT
        in_gap = 9.0 <= t < 10.0
        if t >= 22.5 or in_gap:
            continue
        place(drums, t, K)
        if b % 2 == 1 and not (19.0 <= t < 21.0):
            place(drums, t, CL, 0.8)
        for k in (0.0, 0.25):                                       # 8th hats
            place(drums, t + k, H, 0.5 if k else 0.35)
        if 4.0 <= t < 9.0 or t >= 10.0:                             # off-beat stabs after the drop
            g = 0.45 if 19.0 <= t < 21.0 else 0.75
            place(keys, t + 0.25, stab(CHORDS[bar_of(t)]), g)
        elif t < 3.0:
            place(keys, t + 0.25, stab(CHORDS[bar_of(t)]), 0.75)

    # 16th hat builds: 3.0-3.9 (into the drop) and 7.5-9.0 (into "the thing"), rising.
    for t0, t1 in ((3.0, 3.875), (7.5, 9.0)):
        for i in range(int(round((t1 - t0) / 0.125))):
            t = t0 + i * 0.125
            place(drums, t + 0.0625, H, 0.25 + 0.45 * (t - t0) / (t1 - t0))

    # Sub bass, one root per bar, with holes for the gap, the record-scratch stop and the 19-21 lift.
    for bar in range(13):
        t0 = bar * BAR
        for c0, c1 in ((0, 3.9), (4.0, 9.0), (10.0, 19.0), (21.0, 22.5)):
            a, z = max(t0, c0), min(t0 + BAR, c1)
            if z - a > 0.05:
                place(bass, a, sub_note(ROOTS[bar_of(t0)], z - a))

    # Snare roll 21.5-22.5: 16ths, then 32nds, crescendo.
    t = 21.5
    while t < 22.48:
        step = 0.125 if t < 22.0 else 0.0625
        place(drums, t, SN, 0.25 + 0.6 * (t - 21.5))
        t += step

    # Soft pad under the 19.0-21.0 lift so the bass-less bars don't fall silent between kicks.
    for t0 in (19.0, 20.0):
        pt = tt(1.0)
        pad = sum(saw(f, pt) + saw(f * 1.004, pt) for f in CHORDS[bar_of(t0)]) / 6
        place(keys, t0, fft_filter(pad, hi=900, order=2) * np.minimum(1, pt / 0.08) * np.minimum(1, (1.0 - pt) / 0.08), 0.35)

    # Riser 3.0-3.9: noise swelling (it rides the same filter sweep as the music). Ends at the gap.
    r = noise(0.9) * (tt(0.9) / 0.9) ** 2 * 0.5
    place(keys, 3.0, r)

    # Drop at 4.0 and the beat's return at 10.0.
    place(drums, 4.0, crash(), 0.9)
    place(bass, 10.0, glide(70, 38, 0.7, 0.5) * np.exp(-tt(0.7) / 0.3), 0.9)      # bass hit

    # 22.5 final hit: kick, long Am chord and root, crash, then ring-out.
    place(drums, 22.5, K)
    place(drums, 22.5, crash(3.0), 1.0)
    ring = tt(3.0)
    chord = sum(saw(f, ring) for f in CHORDS[0]) / 3
    place(keys, 22.5, fft_filter(chord, hi=1400, order=2) * np.exp(-ring / 0.8) * 0.5)
    place(bass, 22.5, np.sin(2 * np.pi * 55 * ring) * np.exp(-ring / 0.9) * 0.8)

    # Loop: the muffled kick from 0.0 comes back at 25.5 (and the crackle under it).
    tail = np.zeros(N)
    place(tail, 25.5, K)
    place(tail, 25.75, H, 0.35)

    mix = drums + 0.9 * bass + keys

    # Section shaping 0-4.0: "music from another room" (LP 350 Hz, -6 dB), sweep open 3.0-3.9.
    def cutoff(t):
        if t < 3.0:
            return 350.0
        return 350.0 * (8000 / 350) ** min(1.0, (t - 3.0) / 0.9)

    def gain(t):
        return db(-6) if t < 3.0 else db(-6 + 6 * min(1.0, (t - 3.0) / 0.9))

    head = int(4.2 * SR)
    mix[:head] = stft_lowpass(mix[:head], cutoff, gain)
    tail = stft_lowpass(tail, lambda t: 350.0, lambda t: db(-6))
    mix += tail

    # Vinyl crackle on the muffled parts.
    place(mix, 0.0, crackle(3.0) * np.minimum(1, (3.0 - tt(3.0)) / 0.3), 0.5)
    place(mix, 25.5, crackle(0.5), 0.5)

    # Silences: the gap and the record-scratch stop.
    for a, z in ((3.9, 4.0), (9.0, 10.0)):
        i0, i1 = int(a * SR), int(z * SR)
        fade = min(int(0.004 * SR), i1 - i0)
        mix[i0:i0 + fade] *= np.linspace(1, 0, fade)
        mix[i0 + fade:i1] = 0

    # ----------------------------------------------------------- SFX
    t = tt(0.12)
    slap = fft_filter(noise(0.12), hi=3500, order=1) * np.exp(-t / 0.018) + np.sin(2 * np.pi * 120 * t) * np.exp(-t / 0.03)
    place(sfx, 2.0, slap, 0.7)

    t = tt(0.4)                                                    # marker squeak 2.1-2.5
    sq = glide(2300, 2900, 0.4, vib=180) * (0.6 + 0.4 * np.sin(2 * np.pi * 23 * t) ** 2)
    sq += fft_filter(noise(0.4), lo=1800, hi=4500, order=2) * 0.4
    place(sfx, 2.1, sq * np.minimum(1, t / 0.02) * np.minimum(1, (0.4 - t) / 0.05), 0.12)

    for i, tk in enumerate((3.25, 3.5, 3.75)):                     # 3 . 2 . 1
        place(sfx, tk, tick(1500 + 300 * i), 0.55)

    t = tt(0.14)                                                   # boop on the head tilt
    place(sfx, 6.6, glide(520, 940, 0.14, 0.7) * np.sin(np.pi * t / 0.14), 0.32)

    t = tt(0.45)                                                   # whoosh at 7.5
    w = fft_filter(noise(0.45), lo=500, hi=4000, order=1) * np.sin(np.pi * t / 0.45) ** 2
    place(sfx, 7.5 - 0.15, w, 0.5)

    t = tt(0.42)                                                   # record scratch at 9.0
    f = 600 + 450 * np.sin(2 * np.pi * 7.5 * t) * np.exp(-t / 0.25) - 300 * t
    scr = np.sign(np.sin(2 * np.pi * np.cumsum(np.maximum(f, 60)) / SR)) * 0.4
    scr = fft_filter(scr + 0.5 * noise(0.42), lo=300, hi=3500, order=2)
    place(sfx, 9.0, scr * np.minimum(1, t / 0.005) * np.exp(-t / 0.16), 0.7)

    t = tt(0.3)                                                    # stamp thunk at 10.0
    thunk = glide(110, 50, 0.3, 0.4) * np.exp(-t / 0.08) + fft_filter(noise(0.3), hi=1500) * np.exp(-t / 0.012)
    place(sfx, 10.0, thunk, 0.8)

    t = tt(0.05)
    place(sfx, 11.5, glide(1300, 600, 0.05) * np.exp(-t / 0.015), 0.35)   # caption pop

    t = tt(0.4)                                                    # sunglasses whoop at 14.0
    place(sfx, 13.95, glide(280, 1250, 0.4, 1.6, vib=30) * np.sin(np.pi * t / 0.4), 0.28)

    for k, fr in ((0.0, 1318.5), (0.11, 1760.0)):                  # select chime at 14.5
        t = tt(0.6)
        bell = (np.sin(2 * np.pi * fr * t) + 0.3 * np.sin(2 * np.pi * 2.76 * fr * t)) * np.exp(-t / 0.18)
        place(sfx, 14.5 + k, bell, 0.25)

    for i in range(6):                                             # one tick per stats row
        place(sfx, 15.0 + 0.5 * i, tick(2400), 0.45)

    return mix, sfx


# ---------------------------------------------------------------- ambience + master

def read_audio(path, start, dur):
    """Decode dur seconds of a clip's audio at start as float32 stereo (None if it has no audio)."""
    out = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(path),
                          "-vn", "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"], capture_output=True)
    if out.returncode != 0 or not out.stdout:
        return None
    a = np.frombuffer(out.stdout, dtype=np.float32).reshape(-1, 2).astype(np.float64)
    return a


def rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-12)


def measure(path):
    """Integrated loudness (LUFS) and true peak (dBTP) via ffmpeg's EBU R128 meter."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af",
                          "loudnorm=print_format=json", "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    return float(j["input_i"]), float(j["input_tp"])


def limit(x, ceiling):
    """Look-ahead peak limiter: gain follows the 5 ms block max, released over ~60 ms."""
    blk = int(0.005 * SR)
    peak = np.abs(x).max(axis=1)
    nb = -(-len(peak) // blk)
    bm = np.pad(peak, (0, nb * blk - len(peak))).reshape(nb, blk).max(axis=1)
    bm = np.maximum(bm, np.concatenate([bm[1:], [0]]))         # look one block ahead
    g = np.minimum(1.0, ceiling / np.maximum(bm, 1e-9))
    for i in range(1, nb):                                     # release
        g[i] = min(g[i], g[i - 1] + (1 - g[i - 1]) * 0.08)
    gs = np.interp(np.arange(len(peak)), np.arange(nb) * blk + blk / 2, g)
    return x * gs[:, None]


def write_wav(path, x):
    pcm = (np.clip(x, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def build_mix(out_wav, ambience=(), target_lufs=-14.0, ceiling_db=-2.0):
    """Write the final stereo WAV. ambience: (clip, src_start, t0, t1, mode) with mode 'duck' (about 15 dB under
    the beat), 'duck12' (12 dB under, for V1 on the drop) or 'solo' (the 9.0-10.0 gap: foreground, no beat)."""
    m, sfx = music()
    music_st = np.stack([m + sfx] * 2, axis=1)
    beat_level = rms_db(m[int(4.0 * SR):int(9.0 * SR)])        # reference: the full beat
    amb = np.zeros((N, 2))
    for clip, src, t0, t1, mode in ambience:
        a = read_audio(clip, src, t1 - t0)
        if a is None or len(a) < 10:
            continue
        a = a - a.mean(axis=0)
        a = np.stack([fft_filter(a[:, c], lo=80, order=2) for c in (0, 1)], axis=1)   # no rumble
        under = {"duck": 15, "duck12": 12, "solo": 4}[mode]
        a *= db(beat_level - under - rms_db(a))
        fl = min(int(0.03 * SR), len(a) // 2)
        ramp = np.linspace(0, 1, fl)[:, None]
        a[:fl] *= ramp
        a[-fl:] *= ramp[::-1]
        i = int(round(t0 * SR))
        amb[i:i + len(a)] += a[:N - i]
    mix = music_st + amb
    tmp = str(out_wav) + ".pre.wav"
    write_wav(tmp, mix * 0.5)
    lufs, _ = measure(tmp)
    mix *= 0.5 * db(target_lufs - lufs)
    mix = limit(mix, db(ceiling_db))
    write_wav(out_wav, mix)
    lufs, tp = measure(out_wav)
    subprocess.run(["rm", "-f", tmp])
    return {"lufs": lufs, "true_peak": tp, "sample_peak_db": 20 * np.log10(np.abs(mix).max() + 1e-12),
            "mono_minus_stereo_db": rms_db(mix.mean(axis=1)) - rms_db(mix)}


if __name__ == "__main__":
    print(build_mix(sys.argv[1]))
