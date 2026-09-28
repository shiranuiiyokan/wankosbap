from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import os
from scheduled_renderer import render_scheduled_job
from voicevox import synthesize,wait_until_ready
from youtube_upload import upload_video
ROOT=Path(__file__).parent; ASSET=ROOT/"weekly_news_20260928_assets"; OUT=ROOT/"weekly_news_20260928_output"; ASSET.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
W,H=1080,1920; NAVY=(12,28,52); BLUE=(28,98,170); RED=(205,43,48); Y=(247,190,44); BG=(242,246,250); INK=(22,31,43); WHITE=(255,255,255); MUTED=(90,102,118)
def ft(n,b=False):
 p="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if b else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"; return ImageFont.truetype(p,n)
def txt(d,xy,s,n=54,c=INK,b=False,anchor=None): d.text(xy,s,font=ft(n,b),fill=c,anchor=anchor,spacing=12)
def wrap(s,n): return "\n".join(s[i:i+n] for i in range(0,len(s),n))
def header(d,kicker,num):
 d.rectangle((0,0,W,132),fill=NAVY); txt(d,(58,36),"WANKO NEWS  WEEKLY",42,WHITE,True); txt(d,(1015,66),num,48,Y,True,"rm")
 d.rounded_rectangle((55,165,390,230),20,fill=RED); txt(d,(82,176),kicker,31,WHITE,True)
def source(d,s): txt(d,(60,1790),"出典："+s,24,MUTED,False); txt(d,(60,1835),"※説明用イラスト・図解。事件の再現映像ではありません。",22,MUTED)
def card(d,box,h,b,accent=BLUE):
 d.rounded_rectangle(box,30,fill=WHITE,outline=(210,219,229),width=3); x1,y1,x2,y2=box; d.rectangle((x1,y1,x1+14,y2),fill=accent); txt(d,(x1+40,y1+35),h,38,accent,True); txt(d,(x1+40,y1+105),wrap(b,13),39,INK)
def save(i,im): p=ASSET/f"scene{i:02d}.png"; im.save(p); return p.name
sc=[]
# 1 cover
im=Image.new("RGB",(W,H),NAVY); d=ImageDraw.Draw(im); txt(d,(60,90),"9/22 → 9/28",40,Y,True); txt(d,(60,190),"今週の",88,WHITE,True); txt(d,(60,300),"ペットニュース",92,WHITE,True); txt(d,(60,440),"5 TOPICS",50,(173,201,231),True)
topics=[("01","ウルフドッグ事件",RED),("02","熊本・ペット防災",BLUE),("03","飼い主の高齢化",Y),("04","イオンペット",BLUE),("05","世界狂犬病デー",RED)]
for j,(n,t,c) in enumerate(topics): y=610+j*190; d.rounded_rectangle((65,y,1015,y+145),28,fill=(25,46,75)); d.ellipse((95,y+34,170,y+109),fill=c); txt(d,(132,y+72),n,28,WHITE,True,"mm"); txt(d,(215,y+42),t,45,WHITE,True)
txt(d,(60,1630),"事件・防災・動物福祉・小売・感染症",30,(185,199,217)); txt(d,(60,1710),"2026.09.28",34,Y,True)
sc.append({"image":save(1,im),"narration":"9月22日から28日まで。今週のペットニュースを、事件、防災、動物福祉、ペット小売、感染症の5テーマでまとめます。"})
# 2 wolfdog timeline
im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); header(d,"国内・事件","01"); txt(d,(58,275),"ウルフドッグ逃走",70,INK,True); txt(d,(58,365),"92歳女性が重傷",66,RED,True)
d.line((155,600,155,1370),fill=(177,190,204),width=10)
for y,date,body,col in [(620,"2025","同じ犬が逃走\n歩行者にけが",BLUE),(930,"7/8","自宅から逃走\n92歳女性が重傷",RED),(1240,"9/24","67歳の飼い主を\n重過失傷害容疑で逮捕",RED)]:
 d.ellipse((120,y-25,190,y+45),fill=col); txt(d,(240,y-15),date,40,col,True); txt(d,(240,y+55),body,42,INK,True)
card(d,(610,565,1005,1040),"24.4kg","成犬と報道",RED); card(d,(610,1090,1005,1510),"管理状況","ケージ無施錠\n玄関も開いた状態",BLUE); source(d,"HBC 9/25")
sc.append({"image":save(2,im),"narration":"北海道奈井江町では、体重24.4キロのウルフドッグが逃走し、92歳の女性が全治2か月以上の重傷。9月24日、飼い主が重過失傷害の疑いで逮捕されました。同じ犬は2025年にも逃走事故を起こしていました。"})
# 3 disaster flow
im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); header(d,"国内・防災","02"); txt(d,(58,275),"避難した“その後”を",64,INK,True); txt(d,(58,365),"誰が支える？",76,BLUE,True)
nodes=[(90,610,330,820,"被災","飼い主＋\n犬・猫"),(420,610,660,820,"受付","ペット\n救護本部"),(750,610,990,820,"支援","一時預かり\n健康相談")]
for x1,y1,x2,y2,h,b in nodes: card(d,(x1,y1,x2,y2),h,b,BLUE)
txt(d,(375,700),"→",58,RED,True); txt(d,(705,700),"→",58,RED,True)
card(d,(90,990,990,1410),"熊本県の公式支援","県獣医師会・熊本県・熊本市が連携。\n動物病院での一時預かり、健康相談、\n診療支援などを実施。",RED); source(d,"熊本県 9/10更新／ネコのバス報道 9/26")
sc.append({"image":save(3,im),"narration":"熊本では、地震で被災した犬猫と飼い主を支えるペット救護本部が活動中。動物病院での一時預かりや健康相談に加え、猫の一時預かりを支援するネコのバスも活用されています。"})
# 4 ageing social issue
im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); header(d,"国内・動物福祉","03"); txt(d,(58,275),"飼い主の高齢化",72,INK,True); txt(d,(58,365),"犬猫にも影響",70,RED,True)
# relationship map
cx=540; cy=900; d.ellipse((380,740,700,1060),fill=NAVY); txt(d,(540,850),"飼育を",45,WHITE,True,"mm"); txt(d,(540,925),"続けられない",39,WHITE,True,"mm")
for x,y,h,b in [(80,590,"高齢化","入院・施設入所"),(700,590,"多頭飼育","管理が困難に"),(80,1160,"保護団体","受け皿の負担"),(700,1160,"地域福祉","人と動物を支援")]:
 card(d,(x,y,x+300,y+260),h,b,RED if x<400 else BLUE)
for p in [((380,820),(380,720)),((700,820),(700,720)),((380,980),(380,1160)),((700,980),(700,1160))]: d.line(p,fill=(120,135,153),width=8)
txt(d,(80,1540),"「多頭飼育＝悪」で終わらせず",38,INK,True); txt(d,(80,1605),"人の福祉と動物福祉を一緒に考える",38,BLUE,True); source(d,"9/26報道を基に整理")
sc.append({"image":save(4,im),"narration":"飼い主の高齢化や多頭飼育を背景に、犬猫を飼い続けられなくなる問題も報じられました。保護だけではなく、人の福祉と動物福祉を一緒に支える仕組みが課題です。"})
# 5 aeon pet hub
im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); header(d,"企業・業界","04"); txt(d,(58,275),"ペット小売は",66,INK,True); txt(d,(58,365),"“売るだけ”じゃない",68,BLUE,True)
d.ellipse((355,690,725,1060),fill=NAVY); txt(d,(540,820),"PETEMO",55,WHITE,True,"mm"); txt(d,(540,900),"動物愛護週間",37,Y,True,"mm")
for x,y,h,b in [(80,560,"寄付","ペットシーツ\n猫砂"),(700,560,"譲渡会","最大19店舗\n30回予定"),(80,1160,"啓発","適正飼養を\n店頭から"),(700,1160,"MC","マイクロチップ\n装着促進")]:
 card(d,(x,y,x+300,y+270),h,b,BLUE if x>400 else RED); d.line((540,875,x+150,y+135),fill=(170,181,194),width=6)
txt(d,(75,1515),"9/1〜9/30　全国の店舗・オンラインで実施",34,INK,True); source(d,"イオンペット公式")
sc.append({"image":save(5,im),"narration":"イオンペットは9月いっぱい、ペテモと考える動物愛護週間を実施。自治体へのペットシーツや猫砂の寄付、譲渡会、マイクロチップ装着促進など、小売店舗を動物愛護の接点として活用しています。"})
# 6 rabies world
im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); header(d,"海外・感染症","05"); txt(d,(58,275),"9月28日は",61,INK,True); txt(d,(58,360),"世界狂犬病デー",78,RED,True); txt(d,(58,470),"2026テーマ：Stronger Together",34,BLUE,True)
# three columns
for x,h,b,col in [(70,"日本","国内発生を\n認めていない",BLUE),(390,"世界","犬のワクチン\n監視・教育",RED),(710,"ブータン","WHOが犬由来の\n人狂犬病排除を認定",Y)]:
 d.rounded_rectangle((x,680,x+300,1190),30,fill=WHITE,outline=(210,219,229),width=3); d.ellipse((x+95,735,x+205,845),fill=col); txt(d,(x+150,790),"●",40,WHITE,True,"mm"); txt(d,(x+150,900),h,42,INK,True,"mm"); txt(d,(x+150,1020),b,34,INK,False,"mm")
card(d,(90,1320,990,1580),"One Health","人・動物・環境を分けず、\n予防接種・監視・医療・教育を連携",NAVY); source(d,"WHO 9/28／WHO Bhutan 9/4")
sc.append({"image":save(6,im),"narration":"そして今日9月28日は世界狂犬病デー。WHOの今年のテーマは、ストロンガー・トゥギャザー。ブータンは今月、犬から人へ感染する狂犬病を公衆衛生上の問題として排除した国としてWHOの認定を受けました。"})
# 7 takeaway
im=Image.new("RGB",(W,H),NAVY); d=ImageDraw.Draw(im); txt(d,(60,95),"THIS WEEK'S TAKEAWAY",34,Y,True); txt(d,(60,200),"今週のニュースは",72,WHITE,True); txt(d,(60,300),"全部つながっている",78,WHITE,True)
items=[("事故防止","逃走を防ぐ管理"),("防災","避難後の支援"),("終生飼養","高齢化への備え"),("小売","販売以外の役割"),("感染症","予防を続ける意味")]
for j,(h,b) in enumerate(items): y=520+j*220; d.rounded_rectangle((65,y,1015,y+165),28,fill=(25,48,78)); d.ellipse((100,y+43,180,y+123),fill=[RED,BLUE,Y,BLUE,RED][j]); txt(d,(140,y+83),str(j+1),28,WHITE,True,"mm"); txt(d,(225,y+32),h,39,Y,True); txt(d,(225,y+88),b,38,WHITE,True)
txt(d,(60,1690),"ワンコ暮らし研究所｜WANKO NEWS",29,(180,197,217))
sc.append({"image":save(7,im),"narration":"今週の5テーマは、事故防止、防災、終生飼養、小売の役割、感染症対策。ニュースをその場限りで終わらせず、普段のペットとの暮らしにどうつながるかまで見ていきます。"})

job={"job_id":"WEEKLY-PET-NEWS-20260928","project_id":"WEEKLY-PET-NEWS-20260928","series":"news","category":"short","title":"今週のペットニュース","youtube":{"title":"今週のペットニュース5選｜ウルフドッグ・災害支援・動物愛護週間・狂犬病【9/22〜9/28】","description":"2026年9月22日〜28日の国内外ペット関連ニュースをまとめました。\n\nウルフドッグ事件、熊本のペット防災、飼い主高齢化、イオンペットの動物愛護週間、世界狂犬病デーを扱います。\n\n※事件を実写風に再現した画像は使用せず、説明用イラスト・図解で構成しています。\n※逮捕は有罪確定を意味しません。","tags":["ペットニュース","犬","猫","動物愛護","狂犬病","ウルフドッグ","ペット防災"],"category_id":"15","made_for_kids":False,"contains_synthetic_media":True,"schedule_publish":False,"publish_immediately":False},"video":{"width":1080,"height":1920},"voice":{"speed":1.52},"scenes":sc,"narration_enabled":True,"append_common_cta":False}
os.environ["VOICEVOX_SPEED"]="1.52"; wait_until_ready(); video=render_scheduled_job(job,ASSET,OUT,synthesize); res=upload_video(video,job); print("NEWS_UPLOAD_RESULT="+str(res),flush=True)
