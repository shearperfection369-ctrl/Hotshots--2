"""Assemble the polished Hot Shot TMS demo reel for all social platforms.

Inputs : raw/*.webm screen recordings · vo/*.mp3 narration · assets/ intro/outro art
Outputs: /app/frontend/public/demo/hotshot_demo_16x9.mp4 (YouTube/LinkedIn/site)
         /app/frontend/public/demo/hotshot_demo_1x1.mp4  (Instagram/Facebook feed)
         /app/frontend/public/demo/hotshot_demo_9x16.mp4 (TikTok/Reels/Shorts)
"""
import json
import os
import subprocess

D = "/app/demo_reel"
OUT = "/app/frontend/public/demo"
TMP = f"{D}/build"
FONT = "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
SEGMENTS = [
    ("intro", None, "HOT SHOT TMS", "The AI-driven freight platform"),
    ("hunter", "raw/hunter.webm", "AI LOAD HUNTER", "Works the boards 24/7 - ranked money, with reasoning"),
    ("automatch", "raw/automatch.webm", "AUTO-MATCH", "Best carrier for the load in one click"),
    ("liveops", "raw/liveops.webm", "LIVE OPS MAP", "Real road routing - exceptions flagged early"),
    ("routeopt", "raw/routeopt.webm", "ROUTE OPTIMIZER", "Price any lane in seconds, not spreadsheets"),
    ("sandbox", "raw/sandbox.webm", "OPERATIONAL SANDBOX", "Simulate a full month before you bet a dollar"),
    ("whitelabel", "raw/whitelabel.webm", "YOUR BRAND, WHITE-LABEL", "Isolated client workspaces - live in 30 seconds"),
    ("outro", None, "HOT SHOT TMS", "Book a demo - watch it book a load, live"),
]


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{r.stderr[-1500:]}")


def dur(path):
    out = subprocess.run(["ffprobe", "-v", "quiet", "-print_format", "json", "-show_format", path],
                         capture_output=True, text=True).stdout
    return float(json.loads(out)["format"]["duration"])


def caption(title, sub):
    t = title.replace("'", "").replace(":", "\\:")
    s = sub.replace("'", "").replace(":", "\\:")
    return (
        f"drawbox=x=60:y=920:w=940:h=110:color=0x0D1117@0.72:t=fill,"
        f"drawbox=x=60:y=920:w=8:h=110:color=0xF59E0B:t=fill,"
        f"drawtext=fontfile={FONT}:text='{t}':x=92:y=944:fontsize=38:fontcolor=0xF59E0B,"
        f"drawtext=fontfile={FONT}:text='{s}':x=92:y=990:fontsize=24:fontcolor=0xE2E8F0"
    )


def build_segment(name, src, title, sub):
    vo = f"{D}/vo/{name}.mp3"
    seg_dur = dur(vo) + 1.0
    out = f"{TMP}/seg_{name}.mp4"
    fade = f"fade=t=in:st=0:d=0.45,fade=t=out:st={seg_dur - 0.5}:d=0.5"
    if src is None:
        img = f"{D}/assets/{'intro_bg.png' if name == 'intro' else 'outro_bg.png'}"
        vf = f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,{fade},fps=30,format=yuv420p"
        run(["ffmpeg", "-y", "-loop", "1", "-i", img, "-i", vo,
             "-vf", vf, "-t", f"{seg_dur:.2f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", "44100", out])
    else:
        src_path = f"{D}/{src}"
        src_d = dur(src_path)
        usable = max(src_d - 1.2, 3.0)  # skip page-settle
        factor = seg_dur / usable
        vf = (f"trim=start=1.2,setpts=PTS-STARTPTS,scale=1920:1080,"
              f"setpts={factor:.5f}*PTS,fps=30,"
              f"{caption(title, sub)},{fade},format=yuv420p")
        run(["ffmpeg", "-y", "-i", src_path, "-i", vo,
             "-filter_complex", f"[0:v]{vf}[v];[1:a]apad=pad_dur=2[a]",
             "-map", "[v]", "-map", "[a]", "-t", f"{seg_dur:.2f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", "44100", out])
    print(f"  seg {name}: {seg_dur:.1f}s")
    return out


def main():
    os.makedirs(TMP, exist_ok=True)
    os.makedirs(OUT, exist_ok=True)
    segs = [build_segment(*s) for s in SEGMENTS]

    concat_list = f"{TMP}/list.txt"
    with open(concat_list, "w") as f:
        for s in segs:
            f.write(f"file '{s}'\n")
    joined = f"{TMP}/joined.mp4"
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", concat_list, "-c", "copy", joined])
    total = dur(joined)
    print(f"joined: {total:.1f}s")

    # ambient bed under the narration
    master = f"{OUT}/hotshot_demo_16x9.mp4"
    bed = ("sine=frequency=110:sample_rate=44100,tremolo=f=0.15:d=0.6,"
           "volume=0.045,afade=t=in:st=0:d=3")
    run(["ffmpeg", "-y", "-i", joined, "-f", "lavfi", "-t", f"{total:.2f}", "-i", bed,
         "-filter_complex",
         f"[1:a]afade=t=out:st={total - 4}:d=4[bed];[0:a][bed]amix=inputs=2:duration=first:normalize=0[a]",
         "-map", "0:v", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", master])
    print(f"MASTER {master} ({os.path.getsize(master)//1024//1024} MB)")

    for tag, w, h in [("1x1", 1080, 1080), ("9x16", 1080, 1920)]:
        outp = f"{OUT}/hotshot_demo_{tag}.mp4"
        fc = (f"[0:v]split[a][b];"
              f"[a]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=26,eq=brightness=-0.18[bg];"
              f"[b]scale={w}:-2[fg];[bg][fg]overlay=(W-w)/2:(H-h)/2,format=yuv420p[v]")
        run(["ffmpeg", "-y", "-i", master, "-filter_complex", fc,
             "-map", "[v]", "-map", "0:a", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-c:a", "copy", outp])
        print(f"OK {outp} ({os.path.getsize(outp)//1024//1024} MB)")


if __name__ == "__main__":
    main()
