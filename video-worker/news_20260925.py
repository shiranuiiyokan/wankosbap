from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import os,math
from scheduled_renderer import render_scheduled_job
from voicevox import synthesize,wait_until_ready
from youtube_upload import upload_video

ROOT=Path(__file__).parent; ASSET=ROOT/"wolfdog_news_assets"; OUT=ROOT/"wolfdog_news_output"; ASSET.mkdir(exist_ok=True); OUT.mkdir(exist_ok=True)
W,H=1920,1080
NAVY=(14,31,55); BLUE=(27,95,160); RED=(207,43,49); YELLOW=(246,190,45); BG=(242,246,250); INK=(22,30,42); WHITE=(255,255,255)
def ft(n,b=False):
 p="/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if b else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"; return ImageFont.truetype(p,n)
def wrap(s,n): return "\n".join(s[i:i+n] for i in range(0,len(s),n))
def base(section,title,sub=""):
 im=Image.new("RGB",(W,H),BG); d=ImageDraw.Draw(im); d.rectangle((0,0,W,92),fill=NAVY); d.text((55,19),"WANKO NEWS  |  2026.09.26",font=ft(36,1),fill=WHITE)
 d.rounded_rectangle((65,135,300,205),18,fill=RED); d.text((100,148),section,font=ft(32,1),fill=WHITE); d.text((65,245),title,font=ft(65,1),fill=INK)
 if sub:d.text((70,345),sub,font=ft(31),fill=(72,83,98))
 return im
def wolf(d,x,y,s=1):
 # intentionally illustrated silhouette, not photorealistic
 pts=[(x,y+190*s),(x+80*s,y+105*s),(x+125*s,y+40*s),(x+155*s,y+115*s),(x+265*s,y+95*s),(x+335*s,y+135*s),(x+380*s,y+110*s),(x+350*s,y+170*s),(x+310*s,y+190*s),(x+295*s,y+290*s),(x+245*s,y+290*s),(x+235*s,y+195*s),(x+130*s,y+200*s),(x+115*s,y+290*s),(x+65*s,y+290*s),(x+70*s,y+205*s)]
 d.polygon(pts,fill=(92,103,116)); d.ellipse((x+120*s,y+105*s,x+145*s,y+130*s),fill=YELLOW)
def card(d,box,head,body,color=BLUE):
 x1,y1,x2,y2=box; d.rounded_rectangle(box,28,fill=WHITE,outline=(205,214,224),width=3); d.rectangle((x1,y1,x2,y1+70),fill=color); d.text((x1+28,y1+14),head,font=ft(32,1),fill=WHITE); d.text((x1+30,y1+105),wrap(body,16),font=ft(35),fill=INK,spacing=15)
def save(i,im): p=ASSET/f"scene{i:02d}.png"; im.save(p); return p.name
sc=[]
# 1 headline
im=base("速報","ウルフドッグ逃走　92歳女性が重傷","北海道・奈井江町／7月8日の事故をめぐり9月24日に飼い主を逮捕")
d=ImageDraw.Draw(im); wolf(d,180,470,1.45); card(d,(900,455,1800,900),"今回確認されたこと","体重24.4kgの成犬が逃走\n女性は全治2か月以上\n飼い主を重過失傷害容疑で逮捕",RED)
sc.append({"image":save(1,im),"narration":"北海道奈井江町で、飼われていたウルフドッグが逃げ出し、92歳の女性に重傷を負わせた事件です。警察は9月24日、67歳の飼い主を重過失傷害の疑いで逮捕しました。"})
# 2 timeline
im=base("経緯","事件はどう起きた？","報道各社が警察発表をもとに報道"); d=ImageDraw.Draw(im); d.line((180,570,1740,570),fill=BLUE,width=16)
events=[(240,"7月8日 未明","自宅から逃走"),(760,"午前4:40頃","92歳女性を襲う"),(1280,"9月24日","飼い主を逮捕")]
for x,h,b in events:d.ellipse((x-35,535,x+35,605),fill=RED); d.text((x-95,640),h,font=ft(35,1),fill=INK); d.text((x-95,700),wrap(b,9),font=ft(34),fill=(60,70,82))
sc.append({"image":save(2,im),"narration":"警察によると、犬は7月8日未明に自宅から逃走。同日午前4時40分ごろ、近くを歩いていた92歳の女性にかみつくなどし、けがをさせた疑いが持たれています。"})
# 3 injury / dog
im=base("被害","女性は全治2か月以上の重傷","犬は体重24.4キロの成犬と報じられています"); d=ImageDraw.Draw(im); wolf(d,190,470,1.3); card(d,(930,470,1770,875),"被害状況","両ひざから足首付近をかまれるなどし\n全治2か月以上と報道",RED)
sc.append({"image":save(3,im),"narration":"犬は体重24.4キロの成犬。女性は両ひざから足首付近をかまれるなどし、全治2か月以上の重傷を負ったと報じられています。"})
# 4 escape management diagram
im=base("管理状況","ケージは無施錠、玄関も開いた状態","警察発表をもとにした模式図。実際の住宅・犬ではありません"); d=ImageDraw.Draw(im)
card(d,(100,450,620,860),"室内ケージ","鍵が掛かって\nいなかった",RED); d.text((690,585),"→",font=ft(100,1),fill=RED); card(d,(870,450,1390,860),"玄関","開いた状態\nだったとされる",RED); d.text((1460,585),"→",font=ft(100,1),fill=RED); wolf(d,1600,535,.55)
sc.append({"image":save(4,im),"narration":"警察によると、当時、室内のケージには鍵が掛かっておらず、玄関も開いた状態だったということです。警察は、こうした管理状況を詳しく調べています。"})
# 5 prior incident
im=base("続報","同じ犬は2025年にも逃走・咬傷事故","飼い主は前年の事故をめぐり、今年に過失傷害容疑で書類送検されていました"); d=ImageDraw.Draw(im)
card(d,(120,470,820,880),"2025年","同じウルフドッグが逃走\n別の歩行者をかみ\n重傷を負わせたと報道",NAVY); card(d,(1100,470,1800,880),"2026年","前年の事故で書類送検\n今回の事件で\n重過失傷害容疑の逮捕",RED)
sc.append({"image":save(5,im),"narration":"さらに、この犬は2025年にも逃げ出し、別の歩行者をかんで重傷を負わせていたと報じられています。飼い主は前年の事故について、今年、過失傷害の疑いで書類送検されていました。"})
# 6 arrest status
im=base("現在","逮捕は有罪確定を意味しません","現時点は捜査段階。容疑と確定した事実を分けて扱います"); d=ImageDraw.Draw(im)
card(d,(120,470,850,880),"警察の判断","同様の事案が繰り返されたことなどから\n重大な過失があった疑いとして捜査",RED); card(d,(1070,470,1800,880),"注意点","逮捕＝有罪確定ではありません\n今後の捜査・司法判断を確認",BLUE)
sc.append({"image":save(6,im),"narration":"警察は、同様の事案が繰り返されていることなどから重大な過失があった疑いで捜査しています。ただし、逮捕は有罪が確定したという意味ではありません。"})
# 7 key issue
im=base("ポイント","犬種だけで事故原因を決めつけない","今回の報道で具体的に確認されているのは、逃走防止管理と過去の事故です"); d=ImageDraw.Draw(im)
for j,(h,b) in enumerate([("犬種","ウルフドッグという\n属性だけで断定しない"),("管理","施錠・逸走防止が\n捜査上の重要点"),("再発","前年にも同じ犬の\n逃走・咬傷事故")]):card(d,(90+j*610,470,650+j*610,890),h,b,[BLUE,YELLOW,RED][j])
sc.append({"image":save(7,im),"narration":"このニュースを、ウルフドッグだから危険だった、と単純化するのは適切ではありません。今回具体的に確認されている重要な点は、逃走を防ぐ管理の状況と、前年にも同じ犬による事故が起きていたことです。"})
# 8 summary
im=base("まとめ","大型犬・特殊な犬の飼育管理を考える事件","本動画の犬・住宅・人物表現は説明用イラストで、実際の事件映像ではありません"); d=ImageDraw.Draw(im)
for j,(h,b) in enumerate([("①","逸走防止"),("②","過去の事故後の再発防止"),("③","飼い主の法的責任")]):card(d,(110+j*600,480,650+j*600,840),h,b,BLUE)
d.text((120,930),"出典確認：UHB / HBC / HTB ほか北海道報道　2026年9月24〜26日",font=ft(27),fill=(80,90,105))
sc.append({"image":save(8,im),"narration":"今回の事件は、大型犬や特殊な犬を飼うときの逸走防止、事故後の再発防止、そして飼い主の責任を改めて考えるニュースです。今後、新しい捜査結果や行政対応が公表された場合は続報として確認します。"})

job={"job_id":"NEWS-WOLFDOG-20260926","project_id":"NEWS-WOLFDOG-20260926","series":"news","category":"long","title":"ウルフドッグ逃走ニュース","youtube":{"title":"ウルフドッグが逃走、92歳女性が重傷　飼い主を重過失傷害容疑で逮捕【北海道・奈井江町】","description":"北海道奈井江町で起きたウルフドッグ逃走・咬傷事件について、2026年9月26日時点で確認できた内容を整理しました。\n\n主な確認先：UHB北海道文化放送、HBC北海道放送、HTB北海道ニュース。\n\n※逮捕は有罪確定を意味しません。\n※事件現場・当該犬・被害者を再現した実写風AI画像は使用せず、説明用イラスト・図解で構成しています。","tags":["ウルフドッグ","犬","ペットニュース","北海道","奈井江町","犬の事故"],"category_id":"15","made_for_kids":False,"contains_synthetic_media":True,"schedule_publish":False,"publish_immediately":False},"video":{"width":1920,"height":1080},"voice":{"speed":1.28},"scenes":sc,"narration_enabled":True,"append_common_cta":False}
os.environ["VOICEVOX_SPEED"]="1.28"; wait_until_ready(); video=render_scheduled_job(job,ASSET,OUT,synthesize); res=upload_video(video,job); print("NEWS_UPLOAD_RESULT="+str(res),flush=True)
