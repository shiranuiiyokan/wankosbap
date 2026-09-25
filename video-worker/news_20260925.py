from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageOps,ImageFilter
from datetime import timedelta,timezone
import os,urllib.request
from scheduled_renderer import render_scheduled_job
from voicevox import synthesize,wait_until_ready
from youtube_upload import upload_video

ROOT=Path(__file__).parent; ASSET=ROOT/"news_20260925_tv_assets"; OUT=ROOT/"news_20260925_tv_output"
ASSET.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
W,H=1920,1080
def ft(n,b=False):
 p="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if b else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
 return ImageFont.truetype(p,n)
def wrap(s,n): return "\n".join(s[i:i+n] for i in range(0,len(s),n))
def dl(name,url):
 p=ASSET/name
 if not p.exists():
  try:
   req=urllib.request.Request(url,headers={"User-Agent":"WankoNews/1.0"}); p.write_bytes(urllib.request.urlopen(req,timeout=30).read())
  except Exception as e: print("IMAGE_DOWNLOAD_WARNING",name,e)
 return p
def photo_bg(path):
 try:
  im=Image.open(path).convert("RGB"); return ImageOps.fit(im,(W,H),method=Image.Resampling.LANCZOS)
 except: return Image.new("RGB",(W,H),(220,225,230))
def lower(img,kicker,headline,source=""):
 d=ImageDraw.Draw(img,"RGBA"); d.rectangle((0,0,W,82),fill=(13,20,31,235)); d.text((65,18),"WANKO NEWS  2026.09.25",font=ft(34,1),fill="white")
 d.rounded_rectangle((55,730,1865,1020),28,fill=(8,13,22,220)); d.rounded_rectangle((85,760,355,825),18,fill=(220,45,55,245))
 d.text((115,773),kicker,font=ft(30,1),fill="white"); d.text((90,850),wrap(headline,24),font=ft(54,1),fill="white",spacing=8)
 if source:d.text((90,985),source,font=ft(22),fill=(220,225,232))
 return img
def save(i,img): p=ASSET/f"scene{i:02d}.png"; img.save(p,quality=95); return p.name
def diagram(i,title,cols,footer=""):
 im=Image.new("RGB",(W,H),(244,246,249)); d=ImageDraw.Draw(im); d.rectangle((0,0,W,90),fill=(15,23,36)); d.text((65,20),"WANKO NEWS  |  KEY POINT",font=ft(36,1),fill="white")
 d.text((90,150),title,font=ft(64,1),fill=(18,25,38))
 n=len(cols); gap=35; cw=(W-180-gap*(n-1))//n
 for j,(h,b) in enumerate(cols):
  x=90+j*(cw+gap); d.rounded_rectangle((x,300,x+cw,850),30,fill="white",outline=(205,211,220),width=3)
  d.text((x+35,350),h,font=ft(40,1),fill=(30,48,75)); d.text((x+35,450),wrap(b,13),font=ft(34),fill=(55,65,80),spacing=16)
 if footer:d.text((90,930),footer,font=ft(30,1),fill=(90,45,45))
 return save(i,im)

shiba=dl("shiba.jpg","https://commons.wikimedia.org/wiki/Special:Redirect/file/Shiba-inu%20in%20Japan.jpg")
senior=dl("senior_shiba.jpg","https://commons.wikimedia.org/wiki/Special:Redirect/file/Shiba%20Inu%2015%20year%20old.jpg")
cat=dl("cat.jpg","https://commons.wikimedia.org/wiki/Special:Redirect/file/Cat03.jpg")
sc=[]
def addphoto(i,p,k,h,s,n): sc.append({"image":save(i,lower(photo_bg(p),k,h,s)),"narration":n})
addphoto(1,shiba,"TODAY","犬猫を取り巻く“仕組み”に注目","映像：Wikimedia Commons / 解説用イメージ","9月25日のペットニュースです。今日は国内の動物愛護週間と長寿犬猫、そして海外ではイギリスの犬の飼育責任をめぐる新しい報告を中心に見ていきます。")
addphoto(2,cat,"国内","9月26日まで「動物愛護週間」","環境省の制度に基づく啓発週間","まず国内です。9月20日から26日は動物愛護週間です。全国で、終生飼養や適正な飼い方、動物との関わりを考える啓発が行われています。")
sc.append({"image":diagram(3,"動物愛護週間｜見るポイント",[("迎える前","最後まで飼えるか\n生活環境を確認"),("暮らし","健康管理\n迷子・災害への備え"),("地域","マナーとルール\n適正飼養を共有")],"期間：9月20日〜26日"),"narration":"ポイントは、かわいいという気持ちだけでなく、迎える前から最後まで責任を持つこと。健康管理や迷子対策、災害への備えも、適正飼養の一部です。"})
addphoto(4,senior,"国内","三重県で長寿犬・長寿猫を表彰","9月23日実施／報道ベース","三重県では23日、長生きした犬と猫をたたえる表彰が行われました。報道では、最高齢は犬が19歳、猫が25歳でした。個体差が大きいため、この年齢を犬猫全体の平均寿命として見るものではありません。")
sc.append({"image":diagram(5,"長寿ニュース｜数字の見方",[("今回の表彰","犬 19歳\n猫 25歳"),("注意","最高齢の事例\n平均寿命ではない"),("飼い主目線","定期健診\n食事・体重管理")],"数字は個別事例として扱います"),"narration":"長寿のニュースで大切なのは、最高齢の数字だけを一般化しないことです。日々の食事や体重管理、定期的な健康チェックなど、年齢に合わせたケアを考えるきっかけになります。"})
addphoto(6,shiba,"海外・英国","犬の飼育責任をめぐり20の提言","UK Defra 2026年9月24日公表／イングランド・ウェールズ中心","海外ではイギリスです。24日、政府の環境・食料・農村地域省が、責任ある犬の飼育について独立タスクフォースの報告書を公表しました。報告書には20の提言が盛り込まれています。")
sc.append({"image":diagram(7,"英国報告｜主な論点",[("飼い主","教育・トレーニング\n責任ある飼育"),("専門職","トレーナー等の\n規制方法を検討"),("行政","事故データ\n法執行の改善")],"重要：現時点では「提言」。新法が施行されたわけではありません。"),"narration":"内容には、飼い主への教育やトレーニング、事故データの改善、既存法の執行に加え、ドッグトレーナーや行動専門家をどう規制するかという論点も含まれます。ただし、現時点では提言で、新しい法律が施行されたわけではありません。"})
addphoto(8,shiba,"CHECK","“決まったこと”と“検討中”を分ける","英国の内容は政策提言段階","ペット関連の制度ニュースでは、発表された提言と、成立した法律、実際に施行されたルールを分けて見る必要があります。今回のイギリスの報告は、今後の政府対応を追う段階です。")
sc.append({"image":diagram(9,"今日の3ポイント",[("国内","動物愛護週間\n9月26日まで"),("犬猫","長寿表彰を\nケアのきっかけに"),("海外","英国で犬の\n飼育責任を提言")],"一次情報と制度の現在地を区別して確認"),"narration":"今日の3ポイントです。国内では動物愛護週間。長寿犬猫のニュースは日々のケアを考えるきっかけに。そしてイギリスでは犬の飼育責任について新しい提言が公表されました。"})
addphoto(10,cat,"WANKO NEWS","ペットのニュースを、暮らしにつながる形で","2026年9月25日時点","今後も、犬や猫との暮らしに関係する制度、災害、業界の動きを、決定事項と検討段階を分けながら整理していきます。")
job={"job_id":"NEWS-TV-20260925-V2","project_id":"NEWS-TV-20260925-V2","series":"news","category":"long","title":"今日のペットニュース 2026年9月25日 TV版","youtube":{"title":"今日のペットニュース｜英国で犬の飼育責任20提言・動物愛護週間・長寿犬猫【2026年9月25日】","description":"2026年9月25日時点のペット関連ニュースを国内優先で整理した改訂TVニュース版です。\n\n主な確認先：環境省（動物愛護週間）、三重テレビ（長寿犬猫表彰）、UK Defra Responsible Dog Ownership report（2026/9/24）。\n\n※英国の内容は政策提言段階で、新法施行を意味しません。\n※一部の犬猫映像はニュース内容を説明するイメージ映像です。","tags":["ペットニュース","犬","猫","動物愛護週間","ペット","犬の法律"],"category_id":"15","made_for_kids":False,"contains_synthetic_media":True,"schedule_publish":False,"publish_immediately":False},"video":{"width":1920,"height":1080},"voice":{"speed":1.28},"scenes":sc,"narration_enabled":True,"append_common_cta":False}
os.environ["VOICEVOX_SPEED"]="1.28"; wait_until_ready(); video=render_scheduled_job(job,ASSET,OUT,synthesize); res=upload_video(video,job); print("NEWS_UPLOAD_RESULT="+str(res),flush=True)
