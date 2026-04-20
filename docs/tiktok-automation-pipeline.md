# Cannabliss TikTok Automation Pipeline

## End-to-End System Overview

```
cannabliss-engine (GitHub Action)
        |
        v
  weekly refresh output
  (which songs added/promoted/held/removed)
        |
        v
  audio snippet fetcher
  (iTunes preview → Spotify preview → yt-dlp fallback)
        |
        v
  video assembler
  (visual loop + audio snippet + text overlays via ffmpeg)
        |
        v
  scheduling / posting
  (Buffer free tier → TikTok)
```

Every Friday after the major refresh, this pipeline produces 1-3 ready-to-post
TikTok videos. You review them, tweak captions if needed, and schedule via Buffer.

The goal: under 15 minutes of human time per week.

---

## Phase 1: Song Data (already done)

The cannabliss-engine already outputs:
- which songs were added (result.summary["added"])
- which songs were promoted
- which songs held
- which songs were removed
- the full ordered track list with artist, title, URI

This is the input to everything else. No new work needed here.

---

## Phase 2: Audio Snippets

### Priority chain (automated, tries each in order):

1. **iTunes Search API** — free, no auth, very reliable 30-sec previews
2. **Spotify preview_url** — works for ~50-70% of indie tracks
3. **Deezer API** — free, no auth, reliable backup
4. **yt-dlp** — fallback, downloads from YouTube

### Then trim to the best 4-6 second hook with ffmpeg.

Script: `scripts/fetch-snippets.py`

```python
"""Fetch audio snippets for Cannabliss tracks."""

import json
import subprocess
import sys
from pathlib import Path

import requests


def itunes_preview(artist: str, title: str) -> str | None:
    """Try iTunes Search API first — most reliable."""
    r = requests.get(
        "https://itunes.apple.com/search",
        params={"term": f"{artist} {title}", "media": "music", "limit": 1},
        timeout=10,
    )
    data = r.json()
    if data.get("resultCount", 0) > 0:
        return data["results"][0].get("previewUrl")
    return None


def deezer_preview(artist: str, title: str) -> str | None:
    """Try Deezer API — free, no auth."""
    r = requests.get(
        "https://api.deezer.com/search",
        params={"q": f"{artist} {title}"},
        timeout=10,
    )
    data = r.json()
    if data.get("data"):
        return data["data"][0].get("preview")
    return None


def download_preview(url: str, output_path: Path) -> bool:
    """Download a preview URL to a file."""
    r = requests.get(url, timeout=30)
    if r.status_code == 200:
        output_path.write_bytes(r.content)
        return True
    return False


def trim_snippet(input_path: Path, output_path: Path, start_sec: float = 8.0, duration: float = 6.0):
    """Trim audio to the best snippet. Default: 6 seconds starting at 8s into the preview."""
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(input_path),
            "-ss", str(start_sec),
            "-t", str(duration),
            "-b:a", "192k",
            str(output_path),
        ],
        capture_output=True,
        check=True,
    )


def fetch_snippet(artist: str, title: str, output_dir: Path) -> Path | None:
    """Try each source in priority order. Returns path to trimmed snippet."""
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = f"{artist} - {title}".replace("/", "-")[:60]
    raw_path = output_dir / f"{safe_name}_raw.mp3"
    snippet_path = output_dir / f"{safe_name}.mp3"

    # 1. iTunes
    url = itunes_preview(artist, title)
    if url and download_preview(url, raw_path):
        print(f"  ✅ iTunes: {artist} - {title}")
        trim_snippet(raw_path, snippet_path)
        raw_path.unlink(missing_ok=True)
        return snippet_path

    # 2. Deezer
    url = deezer_preview(artist, title)
    if url and download_preview(url, raw_path):
        print(f"  ✅ Deezer: {artist} - {title}")
        trim_snippet(raw_path, snippet_path)
        raw_path.unlink(missing_ok=True)
        return snippet_path

    print(f"  ❌ No preview found: {artist} - {title}")
    return None
```

---

## Phase 3: Visual Loops

### Approach: Pre-built loop library

Generate 20-30 psychedelic visual loops once. Reuse weekly by mood/color.

**Why this beats generating fresh AI video every week:**
- $0/video after initial creation vs $0.50-1.50/video with cloud AI
- 30 seconds to produce a video vs 2-5 minutes
- More consistent brand look
- Zero API dependency

### Loop categories (6 moods × 3-5 variations):

| Mood     | Colors                               | When to use              |
|----------|--------------------------------------|--------------------------|
| CHILL    | deep purple, lavender, midnight blue | default / most tracks    |
| EUPHORIC | neon green, cyan, aurora              | high-energy additions    |
| MELLOW   | warm amber, golden, burnt orange      | slower / older tracks    |
| HYPE     | hot pink, electric purple, magenta    | standout new drops       |
| DARK     | deep emerald, teal, black smoke       | moody / introspective    |
| COSMIC   | interstellar blue, nebula purple      | hall of fame / specials  |

### How to create the loops:

**Option A: ComfyUI + AnimateDiff (best quality, free with local GPU)**
- Install ComfyUI + AnimateDiff extension
- Use a psychedelic/trippy checkpoint model
- Generate 4-8 second seamless loops at 1080x1920
- Save as MP4
- One-time cost: ~$10-15 on RunPod if no local GPU

**Option B: Kaiber.ai ($10/mo for one month)**
- Best built-in psychedelic aesthetic
- Generate 30 loops manually, cancel subscription
- No API but the manual UI is fast for batch creation

**Option C: Free stock + ffmpeg effects**
- Download abstract/smoke stock loops from Pexels or Pixabay
- Apply color grading with ffmpeg to match Cannabliss palette
- Cheapest but least unique

I'd recommend Option A or B for the initial library.

---

## Phase 4: Video Assembly (ffmpeg)

This is the core production script. Takes a visual loop + audio snippet + text
and produces a ready-to-post TikTok video.

Script: `scripts/assemble-video.sh`

```bash
#!/bin/bash
# assemble-video.sh
# Usage: ./assemble-video.sh <loop.mp4> <audio.mp3> "Artist" "Title" "caption" <output.mp4> [duration]

LOOP="$1"
AUDIO="$2"
ARTIST="$3"
TITLE="$4"
CAPTION="$5"
OUTPUT="$6"
DURATION="${7:-20}"

FONT="/System/Library/Fonts/Helvetica.ttc"
BRAND="cannabliss"

mkdir -p "$(dirname "$OUTPUT")"

ffmpeg -y \
  -stream_loop -1 -i "$LOOP" \
  -i "$AUDIO" \
  -vf "
    scale=1080:1920:force_original_aspect_ratio=increase,
    crop=1080:1920,
    drawtext=text='${ARTIST}':
      fontcolor=white@0.9:fontsize=52:
      x=(w-text_w)/2:y=h*0.33:
      fontfile='${FONT}':
      enable='between(t,1.5,${DURATION}-2)':
      shadowcolor=black@0.6:shadowx=2:shadowy=2,
    drawtext=text='${TITLE}':
      fontcolor=white@0.75:fontsize=40:
      x=(w-text_w)/2:y=h*0.40:
      fontfile='${FONT}':
      enable='between(t,2,${DURATION}-2)':
      shadowcolor=black@0.5:shadowx=2:shadowy=2,
    drawtext=text='${CAPTION}':
      fontcolor=0xBB88FF@0.85:fontsize=30:
      x=(w-text_w)/2:y=h*0.52:
      fontfile='${FONT}':
      enable='between(t,3,${DURATION}-3)',
    drawtext=text='${BRAND}':
      fontcolor=white@0.4:fontsize=22:
      x=(w-text_w)/2:y=h*0.92:
      fontfile='${FONT}':
      enable='between(t,1,${DURATION})',
    fade=t=in:st=0:d=1.5,
    fade=t=out:st=$((DURATION-2)):d=2
  " \
  -t "$DURATION" -shortest \
  -c:v libx264 -preset medium -crf 23 \
  -c:a aac -b:a 192k \
  -movflags +faststart \
  "$OUTPUT"

echo "Done: $OUTPUT"
```

### For the Weekly Drop (3 songs in one video):

A separate script concatenates 3 single-song clips with crossfades,
adds the hook text at the start and CTA at the end.

---

## Phase 5: Scheduling & Posting

### Recommendation: Buffer (free tier)

**Why Buffer:**
- Free tier: 3 channels, 10 scheduled posts per channel per month
- That's more than enough for 8-10 TikTok posts/month
- Direct TikTok publishing (not just reminders)
- Captions, hashtags, scheduling time — all supported
- Zero code, clean UI
- You can batch-schedule a week of posts in 5 minutes

**Setup:**
1. Create Buffer account (buffer.com)
2. Connect TikTok Business/Creator account
3. Upload videos, add captions, schedule

**Why not full API automation for posting:**
- TikTok Content Posting API requires developer app approval (2-8 weeks)
- For 2 posts/week, manual scheduling via Buffer is faster to set up
- You probably want to review captions before posting anyway
- Automate the video creation, keep the posting human-in-the-loop

---

## The Full Weekly Workflow

### Automated (runs itself):
1. Friday 6am CT: cannabliss-engine runs via GitHub Action
2. Engine outputs which songs were added/promoted/removed

### Semi-automated (run one script):
3. Run `make-weekly-videos.py` locally
   - Reads engine output → knows which 3 songs were added
   - Fetches audio snippets (iTunes → Spotify → Deezer → yt-dlp)
   - Selects visual loops by mood
   - Assembles videos via ffmpeg
   - Outputs 2-3 ready MP4 files + suggested captions

### Human (5-10 minutes):
4. Review the videos (watch them, make sure they feel right)
5. Upload to Buffer with captions
6. Schedule: Friday Drop + Tuesday/Wednesday Spotlight
7. Done

### Total weekly time: ~15 minutes
- 5 min: run script, review videos
- 5 min: upload to Buffer, write/tweak captions
- 5 min: buffer for thinking about the mood statement hooks

---

## What to Build First (Priority Order)

### Week 1: Manual proof of concept
- Pick 3 songs from latest refresh
- Get audio snippets manually (iTunes preview or screen record)
- Find 2-3 free abstract loop videos (Pexels/Pixabay)
- Assemble with CapCut or iMovie manually
- Post to TikTok manually
- Goal: prove the format works before automating anything

### Week 2: Build the ffmpeg template
- Get the assemble-video.sh script working
- Test with real songs
- Tweak text positioning and timing
- Set up Buffer account and connect TikTok

### Week 3: Build the snippet fetcher
- Get fetch-snippets.py working
- Test iTunes/Deezer/Spotify preview chain
- Automate the trim-to-best-section logic

### Week 4: Generate the visual loop library
- Use ComfyUI/AnimateDiff or Kaiber to create 20-30 loops
- Organize by mood/color
- Tag each loop for easy selection

### Week 5+: Wire it all together
- Build make-weekly-videos.py orchestrator
- Connect to cannabliss-engine output
- One command produces the week's videos

---

## File Structure

```
cannabliss-engine/
├── src/                      # existing engine code
├── tiktok/                   # new TikTok pipeline
│   ├── scripts/
│   │   ├── fetch-snippets.py
│   │   ├── assemble-video.sh
│   │   └── make-weekly-videos.py
│   ├── loops/                # visual loop library
│   │   ├── chill/
│   │   ├── euphoric/
│   │   ├── mellow/
│   │   ├── hype/
│   │   ├── dark/
│   │   └── cosmic/
│   ├── audio/                # downloaded snippets (gitignored)
│   ├── output/               # rendered videos (gitignored)
│   └── captions/             # generated caption suggestions
├── docs/
│   ├── tiktok-content-strategy.md
│   └── tiktok-automation-pipeline.md  # this file
└── .github/workflows/
    ├── weekly.yml
    └── cannabliss-micro.yml
```

---

## Cost Summary

| Item                        | Cost           | Frequency    |
|-----------------------------|----------------|--------------|
| Visual loop generation      | $10-15         | One-time     |
| Buffer (scheduling)         | $0 (free tier) | Monthly      |
| Audio snippets              | $0             | Weekly       |
| ffmpeg                      | $0             | Weekly       |
| TikTok account              | $0             | One-time     |
| Monthly new loops (optional)| $5-10          | Monthly      |

**Total ongoing cost: $0-10/month**
