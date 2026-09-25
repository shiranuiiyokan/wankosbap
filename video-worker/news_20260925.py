from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime, timedelta, timezone
import os, textwrap
from scheduled_renderer import render_scheduled_job
from voicevox import synthesize, wait_until_ready
from youtube_upload import upload_video

ROOT=Path(__file__).parent
ASSET=ROOT/"news_20260925_assets"
OUT=ROOT/"news_20260925_output"
W,H=1920,1080
JST=timezone(timedelta(hours=9))

def font(size,bold=False):
    cands=[
      "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
      "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    ]
    for p in cands:
        if Path(p).exists(): return ImageFont.truetype(p,size)
    return ImageFont.load_default()

def wrap_jp(s,n):
    return "\n".join(s[i:i+n] for i in range(0,len(s),n))

def card(i,kicker,title,sub,tag):
    img=Image.new("RGB",(W,H),(246,247,249)); d=ImageDraw.Draw(img)
    d.rectangle((0,0,W,105),fill=(20,27,38))
    d.text((90,28),"WANKO NEWS  |  2026.09.25",font=font(42,True),fill="white")
    d.rounded_rectangle((90,165,590,245),24,fill=(230,235,241))
    d.text((120,183),kicker,font=font(34,True),fill=(40,48,62))
    d.text((90,310),wrap_jp(title,18),font=font(72,True),fill=(18,23,31),spacing=16)
    d.text((95,650),wrap_jp(sub,31),font=font(38),fill=(75,84,98),spacing=14)
    d.rounded_rectangle((90,910,520,990),22,fill=(20,27,38))
    d.text((120,928),tag,font=font(32,True),fill="white")
    # editorial side panel
    d.rounded_rectangle((1430,165,1815,990),34,fill=(229,233,239))
    d.ellipse((1510,260,1735,485),fill=(255,255,255))
    d.text((1580,305),"PET",font=font(48,True),fill=(20,27,38))
    d.text((1530,535),f"0{i}",font=font(110,True),fill=(20,27,38))
    d.text((1515,735),"NEWS\nBRIEF",font=font(42,True),fill=(70,80,95),spacing=8)
    p=ASSET/f"scene{i:02d}.png"; img.save(p); return p.name

ASSET.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
scenes=[]
items=[
("TODAY","今日のペットニュース","国内を最優先。海外は重要な制度・業界ニュースだけを短く整理します。","4 TOPICS",
"9月25日のペットニュースです。今日は、動物愛護週間の国内動向、災害時の動物支援、イギリスの犬の飼育ルールをめぐる新しい報告、そして台湾のペット登録促進策をまとめます。"),
("国内","動物愛護週間、9月26日まで","長崎県や山口県などで、適正飼養・譲渡・しつけ・ボランティア体験などの啓発企画。","現行・実施中",
"まず国内です。9月20日から26日は動物愛護週間。長崎県では24日にイベント情報を更新し、山口県でも26日まで動物愛護キャンペーンを実施しています。かわいいだけでなく、終生飼養や適正な飼い方を考える一週間です。"),
("国内","災害時の動物支援が表彰","第10回 川島なお美動物愛護賞。大賞は災害派遣獣医療チーム「福岡VMAT」。","9月24日発表",
"続いて、災害とペットです。9月24日に第10回川島なお美動物愛護賞の授賞式が報告され、大賞には福岡VMATが選ばれました。VMATは大規模災害時などに、被災動物の救護や獣医療支援を行うチームです。ペット防災は、飼い主の備えだけでなく、被災後の獣医療体制も重要です。"),
("海外・英国","犬の飼い主責任をめぐる新報告","Defra委託の独立タスクフォース報告。対象はイングランドとウェールズ。","提言段階",
"海外で最も重要なのはイギリスです。24日、政府の環境・食料・農村地域省が、責任ある犬の飼育と犬による攻撃を減らすための独立報告書を公表しました。教育、犬と飼い主のトレーニング、既存法の執行、事故データの改善などが柱です。ここは注意が必要で、新しい法律が施行されたというニュースではありません。現時点では政策提言です。"),
("海外・台湾","ペット登録を促す施策で登録増","台湾の動物福祉当局によると、抽選型バウチャー施策で犬猫登録が1万8500件増加。","9月24日説明",
"台湾では、ペット登録を促すバウチャー抽選施策によって、犬と猫の登録が全国で1万8500件増えたと当局者が説明しました。制度を作るだけでなく、飼い主が実際に登録するきっかけをどう作るかという点で、日本のマイクロチップや登録制度を考える材料にもなります。"),
("まとめ","今日のポイント","愛護啓発／災害時の獣医療／犬の飼い主責任／ペット登録促進","出典は概要欄",
"今日のポイントは、動物愛護を啓発するだけでなく、災害時の支援、飼い主の責任、個体登録まで、ペットを取り巻く仕組みが広がっていること。ニュースは制度の決定と検討段階を分けて、今後も一次情報を中心に追っていきます。")
]
for i,(k,t,s,tag,n) in enumerate(items,1):
    scenes.append({"image":card(i,k,t,s,tag),"narration":n})

job={
 "job_id":"NEWS-20260925","project_id":"NEWS-20260925","series":"news","category":"long",
 "title":"今日のペットニュース｜2026年9月25日",
 "youtube":{
   "title":"今日のペットニュース｜英国で犬の飼育ルール提言・災害時の動物支援ほか【2026年9月25日】",
   "description":"2026年9月25日時点のペット関連ニュースを国内優先でまとめました。\n\n主な出典：\n・長崎県 動物愛護週間イベント（2026/9/24更新）\n・山口県 動物愛護キャンペーン\n・エンジン01文化戦略会議 第10回 川島なお美動物愛護賞（2026/9/24）\n・UK Defra Responsible Dog Ownership report（2026/9/24）\n・Taipei Times / Taiwan Animal Welfare Department（2026/9/25報道）\n\n※英国の内容は2026年9月25日時点で政策提言段階であり、新法施行を意味しません。\n※ニュースは確認時点の情報です。",
   "tags":["ペットニュース","犬","猫","動物愛護","ペット防災","犬の法律","WANKO SNAP"],
   "category_id":"15","made_for_kids":False,"contains_synthetic_media":True,
   "schedule_publish":False,"publish_immediately":False
 },
 "video":{"width":1920,"height":1080},
 "voice":{"speed":1.28},
 "scenes":scenes,"narration_enabled":True,"append_common_cta":False
}
os.environ["VOICEVOX_SPEED"]="1.28"
wait_until_ready()
video=render_scheduled_job(job,ASSET,OUT,synthesize)
res=upload_video(video,job)
print("NEWS_UPLOAD_RESULT="+str(res),flush=True)
