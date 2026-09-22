import json
import os
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

WIDTH, HEIGHT, FPS = 1080, 1920, 30
SCENE_TAIL = float(os.getenv("SCENE_TAIL", "0.55"))
CTA_ENABLED = os.getenv("CTA_ENABLED", "true").lower() == "true"
CTA_DURATION = max(0.8, min(1.5, float(os.getenv("CTA_DURATION", "1.2"))))
CTA_TEXT = os.getenv("CTA_TEXT", "ペットとツーショット撮るなら、WANKO SNAP。")
CTA_SUBTEXT = os.getenv("CTA_SUBTEXT", "プロフィールから")
CTA_ICON_PATH = os.getenv("CTA_ICON_PATH", "")


def run(cmd):
    print("+", " ".join(str(x) for x in cmd))
    subprocess.run(cmd, check=True)


def audio_duration(path):
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)
    ], text=True)
    return float(json.loads(out)["format"]["duration"])


def _video_filter():
    return (f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
            f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:white,setsar=1,fps={FPS}")


def render_scene(image, audio, caption, output, index, fixed_duration=None):
    duration = float(fixed_duration) if fixed_duration is not None else audio_duration(audio) + SCENE_TAIL
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(image), "-i", str(audio),
         "-vf", _video_filter(), "-af", f"apad,atrim=0:{duration:.3f}", "-t", f"{duration:.3f}",
         "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", str(output)])
    return output


def render_silent_scene(image, duration, output):
    duration = max(0.5, float(duration))
    run(["ffmpeg", "-y", "-loop", "1", "-i", str(image),
         "-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000",
         "-t", f"{duration:.3f}", "-vf", _video_filter(), "-r", str(FPS),
         "-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
         "-movflags", "+faststart", str(output)])
    return output


def concatenate(files, output):
    manifest = output.with_suffix(".concat.txt")
    manifest.write_text("\n".join(f"file '{p.resolve()}'" for p in files), encoding="utf-8")
    run(["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(manifest),
         "-c", "copy", "-movflags", "+faststart", str(output)])
    return output


def _font(size, bold=True):
    configured=os.getenv("CTA_FONT_PATH", "")
    candidates=[configured,
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]
    path=next((p for p in candidates if p and Path(p).is_file()),None)
    if not path: raise RuntimeError("CTA font not found")
    return ImageFont.truetype(path,size)


def _fit_font(draw,text,max_width,start=66,minimum=40):
    for size in range(start,minimum-1,-2):
        font=_font(size)
        box=draw.textbbox((0,0),text,font=font)
        if box[2]-box[0] <= max_width: return font
    return _font(minimum)


def create_cta_card(output,text=CTA_TEXT,subtext=CTA_SUBTEXT,icon_path=CTA_ICON_PATH):
    canvas=Image.new("RGB",(WIDTH,HEIGHT),"#17110F"); draw=ImageDraw.Draw(canvas)
    draw.rounded_rectangle((110,570,970,1350),48,fill="#211916",outline="#F28C28",width=5)
    if icon_path and Path(icon_path).is_file():
        with Image.open(icon_path) as source:
            icon=ImageOps.contain(source.convert("RGBA"),(190,190),Image.Resampling.LANCZOS)
            canvas.paste(icon,((WIDTH-icon.width)//2,650),icon)
        brand_y=875
    else:
        draw.rounded_rectangle((315,675,765,795),60,fill="#F28C28")
        font=_font(47); label="WANKO SNAP"; box=draw.textbbox((0,0),label,font=font)
        draw.text(((WIDTH-(box[2]-box[0]))/2,702),label,font=font,fill="white"); brand_y=890
    lines=text.split("、",1)
    if len(lines)==2: lines=[lines[0]+"、",lines[1]]
    y=brand_y
    for line in lines:
        font=_fit_font(draw,line,790); box=draw.textbbox((0,0),line,font=font)
        draw.text(((WIDTH-(box[2]-box[0]))/2,y),line,font=font,fill="white"); y+=105
    font=_font(38,False); box=draw.textbbox((0,0),subtext,font=font)
    draw.text(((WIDTH-(box[2]-box[0]))/2,1190),subtext,font=font,fill="#F7D2AE")
    output.parent.mkdir(parents=True,exist_ok=True); canvas.save(output,"PNG",optimize=True)
    return output


def render_cta(output_dir):
    image=output_dir/"cta.png"; clip=output_dir/"cta.mp4"; create_cta_card(image)
    return render_silent_scene(image,CTA_DURATION,clip)


def render_job(job, job_dir, output_dir, synthesize_fn):
    output_dir.mkdir(parents=True, exist_ok=True); rendered=[]
    narration_enabled=bool(job.get("narration_enabled",True))
    for i,scene in enumerate(job["scenes"],1):
        clip=output_dir/f"scene_{i:02d}.mp4"
        if narration_enabled and scene.get("narration"):
            audio=output_dir/f"voice_{i:02d}.wav"; synthesize_fn(scene["narration"],audio)
            fixed=scene.get("duration") if job.get("fixed_scene_durations") else None
            render_scene(job_dir/scene["image"],audio,scene.get("caption",""),clip,i,fixed)
        else:
            render_silent_scene(job_dir/scene["image"],scene.get("duration",3.0),clip)
        rendered.append(clip)
    if CTA_ENABLED and job.get("append_common_cta",True): rendered.append(render_cta(output_dir))
    return concatenate(rendered,output_dir/"final.mp4")
