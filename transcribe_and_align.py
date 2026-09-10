#!/usr/bin/env python3
# GRANITE_VERSION: 2026-09-04.2
"""
Transcribe one hearing video and work out where each docketed bill sits in it.

Design notes, from watching real hearings:
  - Chairs do not use consistent phrasing, so this never searches for a phrase.
    It searches for BILL NUMBERS and uses how densely they cluster over time.
    A bill gets named repeatedly while it is being heard and rarely otherwise.
  - Speech recognition mangles numbers, so instead of parsing numbers out of the
    transcript, we generate the plausible spoken forms of the bills we already
    know are on the agenda and look for those. Small known target set, far more
    robust than general number extraction.
  - Hearings usually run in scheduled order, so bills are assigned in one
    monotonic pass over the whole timeline rather than searched for one at a
    time. Out-of-order items are rare and get flagged rather than forced.
  - Streams keep running through caucuses and lunch with the audio muted. Those
    silences are detected first: they are skipped during transcription (saving
    time) and used as preferred segment boundaries.

Setup (one time):
    pip install yt-dlp faster-whisper
    ffmpeg must be on PATH -- https://ffmpeg.org/download.html

Run:
    python3 transcribe_and_align.py --video VIDEOID --manifest verification_manifest.csv

Each stage caches to disk, so rerunning only redoes what is missing. Alignment
is cheap to re-run once the transcript exists -- use --realign to skip straight
to it after changing settings.
"""

import argparse
import csv
import json
import math
import re
import subprocess
import sys
import child
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------- spoken forms

ONES = {0:"zero",1:"one",2:"two",3:"three",4:"four",5:"five",6:"six",7:"seven",
        8:"eight",9:"nine",10:"ten",11:"eleven",12:"twelve",13:"thirteen",
        14:"fourteen",15:"fifteen",16:"sixteen",17:"seventeen",18:"eighteen",
        19:"nineteen"}
TENS = {2:"twenty",3:"thirty",4:"forty",5:"fifty",6:"sixty",7:"seventy",
        8:"eighty",9:"ninety"}


def two_digit_words(n):
    if n < 20:
        return [ONES[n]]
    t, o = divmod(n, 10)
    return [TENS[t]] if o == 0 else [f"{TENS[t]} {ONES[o]}", f"{TENS[t]}-{ONES[o]}"]


def spoken_forms(num):
    """Plausible ways a bill number gets said aloud.

    Legislators read numbers as digit groups far more than as cardinals:
    HB 261 is 'two sixty one' much more often than 'two hundred sixty one'.
    Both are generated.
    """
    s = str(num)
    out = {s}
    n = int(num)

    if n < 100:
        out.update(two_digit_words(n))
        if n >= 10:
            out.add(f"{ONES[n // 10]} {ONES[n % 10]}")
    elif n < 1000:
        h, rest = divmod(n, 100)
        tail = two_digit_words(rest) if rest >= 10 else ([ONES[rest]] if rest else [])
        for w in tail:
            # Only a two-digit tail reads as a digit group: 261 -> "two sixty one".
            # 405 must NOT yield "four five", which is how HB45 is read aloud.
            if rest >= 10:
                out.add(f"{ONES[h]} {w}")
            out.add(f"{ONES[h]} hundred {w}")
            out.add(f"{ONES[h]} hundred and {w}")
        if rest == 0:
            out.add(f"{ONES[h]} hundred")
        if rest < 10:
            out.add(f"{ONES[h]} oh {ONES[rest]}")          # four oh five
            out.add(f"{ONES[h]} zero {ONES[rest]}")
        d = [ONES[int(c)] for c in s]
        out.add(" ".join(d))                               # two six one
    return out


TYPE_WORDS = {
    "HB": ["hb", "h b", "house bill", "h. b.", "housebill"],
    "SB": ["sb", "s b", "senate bill", "s. b."],
    "CACR": ["cacr", "c a c r", "constitutional amendment concurrent resolution"],
    "HR": ["hr", "h r", "house resolution"],
    "SR": ["sr", "s r", "senate resolution"],
    "HCR": ["hcr", "h c r", "house concurrent resolution"],
    "SCR": ["scr", "s c r", "senate concurrent resolution"],
    "HJR": ["hjr", "h j r", "house joint resolution"],
}


def bill_patterns(bill):
    """Regexes matching one bill, tolerant of how ASR writes it."""
    m = re.match(r"([A-Z]+)\s*(\d+)", bill.upper())
    if not m:
        return []
    kind, num = m.group(1), m.group(2)
    types = TYPE_WORDS.get(kind, [kind.lower()])
    nums = spoken_forms(num)
    pats = []
    for t in types:
        tp = re.escape(t).replace(r"\ ", r"[\s.]*")
        for nf in nums:
            np_ = re.escape(nf).replace(r"\ ", r"[\s-]+")
            pats.append(re.compile(rf"\b{tp}[\s.,#-]*{np_}\b", re.I))
    # bare number, counted at lower weight -- "moving on to two sixty one"
    for nf in nums:
        if not nf.isdigit() or len(nf) >= 2:
            np_ = re.escape(nf).replace(r"\ ", r"[\s-]+")
            pats.append(re.compile(rf"\b{np_}\b", re.I))
    return pats


def strong_count(bill):
    """How many of this bill's patterns are type-qualified (high confidence)."""
    m = re.match(r"([A-Z]+)\s*(\d+)", bill.upper())
    return len(TYPE_WORDS.get(m.group(1), [""])) * len(spoken_forms(m.group(2)))


# ---------------------------------------------------------------- stages

def run(cmd, **kw):
    return child.run(cmd, check=True, capture_output=True, text=True, **kw)


def fetch_audio(video_id, out):
    if out.exists():
        print(f"  audio cached: {out}")
        return
    print("  downloading audio (this is audio only, not video)...")
    run([sys.executable, "-m", "yt_dlp", "-f", "bestaudio",
         "-x", "--audio-format", "wav", "--postprocessor-args", "-ar 16000 -ac 1",
         "-o", str(out.with_suffix("")) + ".%(ext)s",
         f"https://www.youtube.com/watch?v={video_id}"])


def detect_silence(wav, out, min_len=45.0, thresh="-45dB"):
    """Muted stretches: caucuses, lunch, recesses. Cheap and structurally useful."""
    if out.exists():
        return json.loads(out.read_text(encoding="utf-8"))
    print(f"  scanning for silences longer than {min_len:.0f}s...")
    p = child.run(
        ["ffmpeg", "-i", str(wav), "-af",
         f"silencedetect=noise={thresh}:d={min_len}", "-f", "null", "-"],
        capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", p.stderr)]
    sil = [{"start": s, "end": e} for s, e in zip(starts, ends)]
    out.write_text(json.dumps(sil, indent=2), encoding="utf-8")
    total = sum(s["end"] - s["start"] for s in sil)
    print(f"  {len(sil)} silent stretches, {total/60:.0f} min of dead air")
    return sil


# Rough transcription speed relative to realtime, CPU with int8.
CPU_SPEED = {"tiny": 12, "base": 8, "small": 4, "medium": 1.5, "large-v3": 0.7,
             "large-v2": 0.7, "large": 0.7}


def _is_cuda_lib_error(e):
    m = str(e).lower()
    return any(k in m for k in ("cublas", "cudnn", "cuda", "no kernel image"))


def _run(model, wav, silences, dur_hint=0):
    segs, info = model.transcribe(str(wav), vad_filter=True, word_timestamps=False,
                                  beam_size=1, condition_on_previous_text=False,
                                  language="en", chunk_length=30)
    dur = getattr(info, "duration", dur_hint) or 0

    def in_silence(t):
        return any(s["start"] <= t <= s["end"] for s in silences)

    rows = []
    for i, seg in enumerate(segs):        # errors surface here, not at construction
        if in_silence(seg.start):
            continue
        rows.append({"start": seg.start, "end": seg.end, "text": seg.text.strip()})
        if i % 200 == 0:
            pct = f" ({seg.start / dur:.0%})" if dur else ""
            print(f"    {seg.start / 3600:.2f} h transcribed{pct}", flush=True)
    return rows


def fetch_captions(video_id, out, workdir):
    """Pull YouTube's own auto-generated captions instead of transcribing.

    Seconds instead of hours, and no audio download at all. YouTube has already
    run speech recognition over every one of these videos; there is no reason to
    repeat the work on a laptop unless the result is materially worse.

    Quality is the open question. Auto-captions are usually weaker than Whisper
    on proper nouns, but bill numbers are digits, and searching them by hand in
    the YouTube player does find the right moments -- so the signal we actually
    depend on appears to survive. Run score_alignment.py both ways on a video
    with hand-marked times before trusting it wholesale.
    """
    if out.exists():
        print(f"  transcript cached: {out}")
        return json.loads(out.read_text(encoding="utf-8"))

    base = workdir / "captions"
    print("  fetching YouTube's auto-captions (no audio download needed)")
    try:
        run([sys.executable, "-m", "yt_dlp", "--write-auto-subs", "--sub-langs",
             "en.*", "--sub-format", "json3/vtt", "--skip-download",
             "-o", str(base), f"https://www.youtube.com/watch?v={video_id}"])
    except subprocess.CalledProcessError as e:
        print("  yt-dlp could not fetch captions.")
        print((e.stderr or "")[:400])
        return None

    files = sorted(workdir.glob("captions*.json3")) + sorted(workdir.glob("captions*.vtt"))
    if not files:
        print("  no auto-captions published for this video.")
        return None

    f = files[0]
    rows = []
    if f.suffix == ".json3":
        data = json.loads(f.read_text(encoding="utf-8", errors="replace"))
        for ev in data.get("events", []):
            txt = "".join(sg.get("utf8", "") for sg in ev.get("segs", [])).strip()
            if not txt or txt == "\n":
                continue
            t0 = ev.get("tStartMs", 0) / 1000.0
            rows.append({"start": t0, "end": t0 + ev.get("dDurationMs", 0) / 1000.0,
                         "text": txt})
    else:
        cur, buf = None, []
        for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"(\d+):(\d+):([\d.]+)\s+--&gt;|(\d+):(\d+):([\d.]+)\s+-->", line)
            if m:
                g = [x for x in m.groups() if x]
                if cur is not None and buf:
                    rows.append({"start": cur, "end": cur + 5, "text": " ".join(buf)})
                cur, buf = int(g[0]) * 3600 + int(g[1]) * 60 + float(g[2]), []
            elif line.strip() and not line.startswith(("WEBVTT", "Kind:", "Language:")):
                buf.append(re.sub(r"<[^>]+>", "", line).strip())
        if cur is not None and buf:
            rows.append({"start": cur, "end": cur + 5, "text": " ".join(buf)})

    # Auto-captions arrive as a rolling two-line display, so consecutive cues
    # repeat each other. Merge into sentence-ish chunks before matching.
    merged = []
    for r in rows:
        if merged and r["start"] - merged[-1]["start"] < 6 and \
           len(merged[-1]["text"]) < 220:
            merged[-1]["text"] += " " + r["text"]
            merged[-1]["end"] = r["end"]
        else:
            merged.append(dict(r))
    out.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    print(f"  {len(merged)} caption segments covering "
          f"{max(r['end'] for r in merged)/3600:.2f} h")
    return merged


def transcribe(wav, out, model_size, silences, device="auto"):
    """Transcribe, falling back to CPU if the GPU's CUDA libraries are missing.

    faster-whisper defaults to device='auto', which selects CUDA whenever an
    NVIDIA driver is present, then fails on the first encode if cuBLAS and
    cuDNN are absent. On Windows those cannot be pip installed. The failure
    only appears once the segment generator is consumed, so the retry has to
    wrap the iteration rather than the model construction.
    """
    if out.exists():
        print(f"  transcript cached: {out}")
        return json.loads(out.read_text(encoding="utf-8"))
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        sys.exit("pip install faster-whisper")

    order = [device] if device != "auto" else ["cuda", "cpu"]
    last = None
    for dev in order:
        try:
            model = WhisperModel(model_size, device=dev, compute_type="int8")
            if dev == "cpu":
                rate = CPU_SPEED.get(model_size, 1)
                print(f"  transcribing with '{model_size}' on CPU (~{rate}x realtime)")
                if rate < 2:
                    print("  That is slow for a long hearing. '--model small' finishes")
                    print("  in about a quarter the time and is usually enough to test.")
            else:
                print(f"  transcribing with '{model_size}' on GPU")
            rows = _run(model, wav, silences)
            out.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"  {len(rows)} transcript segments")
            return rows
        except Exception as e:
            last = e
            if dev == "cuda" and _is_cuda_lib_error(e):
                print("  GPU found, but its CUDA libraries (cuBLAS/cuDNN) are missing.")
                print("  Falling back to CPU. See --help to enable the GPU later.")
                continue
            raise
    raise last


# ---------------------------------------------------------------- mentions

def find_mentions(transcript, bills):
    """(time, bill, weight) for every plausible reference."""
    pats = {b: bill_patterns(b) for b in bills}
    strong = {b: strong_count(b) for b in bills}
    hits = []
    for seg in transcript:
        txt = seg["text"]
        for b, ps in pats.items():
            for i, p in enumerate(ps):
                if p.search(txt):
                    hits.append({"t": seg["start"], "bill": b,
                                 "w": 3.0 if i < strong[b] else 1.0})
                    break
    return hits


def density(hits, bill, T, step=30.0, sigma=150.0):
    """Smoothed mention density for one bill across the whole timeline."""
    n = int(T / step) + 1
    d = [0.0] * n
    pts = [(h["t"], h["w"]) for h in hits if h["bill"] == bill]
    if not pts:
        return d
    span = int(3 * sigma / step)
    for t, w in pts:
        c = int(t / step)
        for j in range(max(0, c - span), min(n, c + span + 1)):
            d[j] += w * math.exp(-((j - c) * step) ** 2 / (2 * sigma ** 2))
    return d


def align(targets, hits, T, silences, step=30.0, min_len=180.0, recess=600.0):
    """Assign bills to ordered, non-overlapping spans maximising mention density.

    Monotonic by construction: bill i's span always precedes bill i+1's. That
    encodes the fact that hearings run in scheduled order, and it is why this
    beats searching for each bill independently.
    """
    n = int(T / step) + 1
    bills = [t["bill"] for t in targets]
    D = {b: density(hits, b, T, step) for b in set(bills)}

    # A segment should START where audio resumes after a recess.
    bonus = [0.0] * n
    for sl in silences:
        e = int(sl["end"] / step)
        for j in range(max(0, e - 2), min(n, e + 3)):
            bonus[j] += 4.0

    # A long recess is a HARD barrier, not a hint. Nothing is transacted while
    # the room is empty, so no proceeding may span one. Encouraging a boundary
    # there was not enough: on 2025-01-21 an executive session was assigned a
    # span running straight through a 22-minute recess, a 31-minute error.
    bars = [(sl["start"], sl["end"]) for sl in silences
            if sl["end"] - sl["start"] >= recess]

    def spans_recess(i, j):
        a, b = i * step, j * step
        return any(a < rs and b > re_ for rs, re_ in bars)

    pre = {}
    for b in set(bills):
        c, acc = [0.0], 0.0
        for v in D[b]:
            acc += v
            c.append(acc)
        pre[b] = c

    def score(b, i, j):
        inside = pre[b][j] - pre[b][i]
        outside = pre[b][n] - inside
        return inside - 0.35 * outside

    NEG = -1e18
    k = len(targets)
    dp = [[NEG] * (n + 1) for _ in range(k + 1)]
    bk = [[0] * (n + 1) for _ in range(k + 1)]
    dp[0][0] = 0.0
    for b_i in range(1, k + 1):
        b = targets[b_i - 1]["bill"]
        for j in range(1, n + 1):
            best, arg = NEG, 0
            for i in range(b_i - 1, j):
                if dp[b_i - 1][i] == NEG:
                    continue
                if spans_recess(i, j):
                    continue
                v = dp[b_i - 1][i] + score(b, i, j) + bonus[min(i, n - 1)]
                if v > best:
                    best, arg = v, i
            dp[b_i][j], bk[b_i][j] = best, arg

    j, cuts = n, []
    for b_i in range(k, 0, -1):
        i = bk[b_i][j]
        cuts.append((i, j))
        j = i
    cuts.reverse()

    out = []
    for tgt, (i, j) in zip(targets, cuts):
        b = tgt["bill"]
        inside = pre[b][j] - pre[b][i]
        total = pre[b][n] or 1.0
        mine = [h["t"] for h in hits if h["bill"] == b and i * step <= h["t"] < j * step]
        nh = len(mine)
        tot_hits = sum(1 for h in hits if h["bill"] == b)
        # Trim to the mention mass, padded: the chair names the bill a little
        # after opening it and again a little before closing.
        #
        # Trim to CLUSTERED mentions, not the outermost ones. Chairs read the
        # whole day's agenda at gavel-in, so every bill picks up an isolated
        # mention near 0:00. Taking the raw minimum drags the first segment back
        # by twenty minutes; requiring company within 5 minutes ignores it.
        mine.sort()
        core = [t for k, t in enumerate(mine)
                if (k > 0 and t - mine[k - 1] <= 300)
                or (k + 1 < len(mine) and mine[k + 1] - t <= 300)]
        span_pts = core or mine
        if mine:
            lo, hi = max(i * step, min(span_pts) - 90), min(j * step, max(span_pts) + 90)
            # but still prefer a silence edge if one sits just before the start
            for sl in silences:
                if 0 <= lo - sl["end"] <= 240:
                    lo = sl["end"]
        else:
            lo, hi = i * step, j * step
        length = hi - lo
        purity = round(inside / total, 3)
        # The DP must give every docketed proceeding a slice, so leftovers get
        # crushed to the minimum width. Those are not findings; say so.
        # Calibrated against 2025-01-21 Election Law, where hand-marked times
        # exist. Purity turned out to be a poor discriminator: one segment
        # scored 0.46 and landed 3 seconds from the true start, while another
        # scored 0.45 and landed 4 minutes out. Mention COUNT and segment
        # length separate the usable from the useless; purity does not.
        # So: reject only what is clearly empty, and publish everything else
        # with an honest tolerance rather than a false binary.
        # Second recalibration, against 34 hand-marked proceedings.
        #
        # The previous gate rejected seven segments for having no mentions
        # inside them or being short. All seven were ACCURATE, median error
        # 1m33s: the monotonic pass places a bill correctly from the structure
        # around it even when its number is never spoken in its own span.
        # Discarding those threw away good answers.
        #
        # What genuinely signals "not found" is the bill never being mentioned
        # anywhere in the video at all -- which usually means it was not
        # reached that day.
        # Third calibration, after a stratified sample across 271 videos.
        #
        # Accuracy is bimodal: most segments land within about 90 seconds, a
        # minority are wrong by 40 minutes to 2 hours. Mention count alone does
        # not separate them -- two of the failures were in the +/-3 band, the
        # most confident one.
        #
        # Segment LENGTH does carry signal. 487 of 2,177 "located" segments were
        # under a minute, with a median of 4:06 across the whole set. A public
        # hearing is not four minutes long. Those short segments are the mention
        # cluster, not the proceeding, and the cluster can sit far from where the
        # item actually opened. So length now widens the tolerance rather than
        # being ignored.
        located = tot_hits >= 1
        if nh >= 6:
            tol = 180
        elif nh >= 3:
            tol = 300
        elif nh >= 1:
            tol = 600
        else:
            tol = 900
        if length < 120:
            tol, short = 1800, True      # barely more than the cluster itself
        elif length < 300:
            tol, short = max(tol, 900), True
        else:
            short = False
        why = "" if located else "never mentioned in this video - likely not reached"
        if located and short:
            why = "short segment - the estimate may be far from the real start"
        out.append({"bill": b, "kind": tgt.get("kind", ""),
                    "located": located, "why_not": why,
                    "short": short, "tolerance": tol if located else None,
                    "dp_start": i * step, "dp_end": j * step,
                    "start": lo, "end": hi,
                    "mentions_inside": nh,
                    "mentions_total": sum(1 for h in hits if h["bill"] == b),
                    "purity": round(inside / total, 3)})

    # A bill can be taken up, set aside, and returned to later -- common in
    # unscheduled executive sessions. The DP gives each proceeding one span, so
    # look for dense mention clusters that fall outside every assigned span and
    # surface them as extra segments for review rather than losing them.
    extras = []
    for b in set(bills):
        spans = [(s0["dp_start"], s0["dp_end"]) for s0 in out if s0["bill"] == b]
        stray = [h["t"] for h in hits if h["bill"] == b
                 and not any(a <= h["t"] < z for a, z in spans)
                 and min(abs(h["t"] - a) for sp in spans for a in sp) > 600]
        stray.sort()
        run_ = []
        for t in stray + [None]:
            if run_ and (t is None or t - run_[-1] > 300):
                if len(run_) >= 3:
                    extras.append({"bill": b, "kind": "revisit?",
                                   "start": run_[0] - 60, "end": run_[-1] + 60,
                                   "mentions_inside": len(run_),
                                   "mentions_total": sum(1 for h in hits if h["bill"] == b),
                                   "purity": 0.0})
                run_ = []
            if t is not None:
                run_.append(t)
    return out, extras


def hhmmss(s):
    s = int(s)
    return f"{s//3600}:{(s%3600)//60:02d}:{s%60:02d}"


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="YouTube video id")
    ap.add_argument("--manifest", default="verification_manifest.csv")
    ap.add_argument("--model", default="small", help="tiny|base|small|medium|large-v3")
    ap.add_argument("--workdir", default="work")
    ap.add_argument("--realign", action="store_true", help="skip to alignment")
    ap.add_argument("--source", default="captions",
                    choices=["captions", "whisper", "auto"],
                    help="captions (default) pulls YouTube's own auto-captions in "
                         "seconds; whisper transcribes locally over hours; auto "
                         "tries captions and falls back to whisper")
    ap.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                    help="auto tries the GPU then falls back to CPU. To enable the "
                         "GPU on Windows, download Purfview's whisper-standalone-win "
                         "release, which bundles the cuBLAS and cuDNN DLLs, and drop "
                         "them in this folder.")
    a = ap.parse_args()

    w = Path(a.workdir) / a.video
    w.mkdir(parents=True, exist_ok=True)
    wav = w / "audio.wav"

    rows = [r for r in csv.DictReader(open(a.manifest, encoding="utf-8-sig"))
            if r["video_id"] == a.video]
    if not rows:
        sys.exit(f"No manifest rows for {a.video}.")

    def key(r):
        t = r["sched_time"] or "99:99"
        return t if len(t) == 5 else "0" + t
    rows.sort(key=key)
    targets, seen_slot = [], set()
    for r in rows:
        # The docket sometimes records a hearing and an executive session for
        # the same bill at the same minute. That is one event in the room, and
        # forcing two segments corrupts the running order for everything after.
        k = (r["bill"], r["sched_time"])
        if k in seen_slot:
            print(f"   (skipping duplicate slot: {r['bill']} {r['proceeding']} "
                  f"at {r['sched_time']})")
            continue
        seen_slot.add(k)
        targets.append({"bill": r["bill"], "kind": r["proceeding"],
                        "sched": r["sched_time"]})
    bills = sorted({t["bill"] for t in targets})

    print(f"\n{a.video}: {len(targets)} docketed proceedings expected, in this order:")
    for t in targets:
        print(f"   {t['sched']:>5}  {t['bill']:8} {t['kind']}")

    tr = None
    if a.source in ("captions", "auto"):
        print("\nCaptions")
        tr = fetch_captions(a.video, w / "transcript.json", w)
        if tr is None and a.source == "captions":
            sys.exit("No captions available for this video. "
                     "Rerun with --source whisper.")

    silences = []
    if tr is None:
        print("\nAudio")
        if not a.realign:
            fetch_audio(a.video, wav)
        print("Silence")
        silences = detect_silence(wav, w / "silences.json") if wav.exists() else []
        print("Transcript")
        tr = transcribe(wav, w / "transcript.json", a.model, silences, a.device)
    else:
        sp = w / "silences.json"
        if sp.exists():
            silences = json.loads(sp.read_text(encoding="utf-8"))
            print(f"  reusing {len(silences)} silence spans from an earlier run")
        else:
            # No audio was downloaded, so derive recesses from gaps between
            # caption cues instead. Nobody speaks during a recess, so a long
            # stretch with no captions is the same signal.
            silences = []
            for i in range(1, len(tr)):
                gap = tr[i]["start"] - tr[i - 1]["end"]
                if gap >= 600:
                    silences.append({"start": tr[i - 1]["end"], "end": tr[i]["start"]})
            if silences:
                print(f"  {len(silences)} long gaps in the captions, treated as "
                      "recesses")

    T = max(s["end"] for s in tr) if tr else 0
    print(f"\nAligning across {hhmmss(T)}")
    hits = find_mentions(tr, bills)
    print(f"  {len(hits)} bill mentions found")
    for b in bills:
        c = sum(1 for h in hits if h["bill"] == b)
        if c == 0:
            print(f"  {b}: NO mentions -- may not have been reached")

    segs, extras = align(targets, hits, T, silences)
    (w / "segments.json").write_text(json.dumps(segs + extras, indent=2),
                                 encoding="utf-8")

    print(f"\n{'bill':<9}{'start':>10}{'end':>10}{'length':>9}{'mentions':>10}{'purity':>9}  flag")
    for s in segs:
        L = s["end"] - s["start"]
        flag = (f"+/- {s['tolerance']//60} min" + (" (short)" if s.get("short") else "")
                if s["located"] else "NOT LOCATED - " + s["why_not"])
        print(f"{s['bill']:<9}{hhmmss(s['start']):>10}{hhmmss(s['end']):>10}"
              f"{hhmmss(L):>9}{s['mentions_inside']:>4}/{s['mentions_total']:<5}"
              f"{s['purity']:>9.2f}  {flag}")

    if extras:
        print("\nPossible revisits -- dense mentions outside any assigned span:")
        for e in extras:
            print(f"  {e['bill']:8} {hhmmss(e['start'])} - {hhmmss(e['end'])}"
                  f"  ({e['mentions_inside']} mentions)  CHECK THIS")

    truth = {r["bill"]: r["observed_start"] for r in rows
             if (r.get("observed_start") or "").strip()}
    if truth:
        print("\nScored against your hand-marked times:")
        errs = []
        for s in segs:
            if s["bill"] not in truth:
                continue
            p = truth[s["bill"]].split(":")
            gt = sum(float(x) * m for x, m in zip(reversed(p), (1, 60, 3600)))
            e = s["start"] - gt
            errs.append(abs(e))
            print(f"  {s['bill']:8} predicted {hhmmss(s['start'])}  actual {hhmmss(gt)}"
                  f"   off by {int(e)//60:+d}m{abs(int(e))%60:02d}s")
        if errs:
            print(f"\n  median error {int(sorted(errs)[len(errs)//2])//60}m"
                  f"{int(sorted(errs)[len(errs)//2])%60:02d}s   worst "
                  f"{int(max(errs))//60}m{int(max(errs))%60:02d}s")
            print("  Under about 2 minutes is good enough to cut on.")

    ok = sum(1 for s in segs if s["located"])
    print(f"\n{ok}/{len(segs)} proceedings located, each with a stated tolerance.")
    print("The site shows these as 'around HH:MM' with a link opening early,")
    print("never as an exact timestamp. Anything with no mentions at all is")
    print("left unlocated rather than guessed.")
    print(f"\nWritten to {w}/segments.json")


if __name__ == "__main__":
    main()
