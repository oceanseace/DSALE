from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.units import mm
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os, json, statistics
from collections import defaultdict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(BASE_DIR, "Bursa_35Sales_Model.json")

if not os.path.exists(JSON_PATH):
    raise FileNotFoundError(f"Model dosyası bulunamadı: {JSON_PATH}")

with open(JSON_PATH, "r", encoding="utf-8") as f:
    m = json.load(f)

regs = m["regions"]
target = m["target"]
total = m["total_opportunity"]

# Fonts
font_candidates = [
    r"C:\\Windows\\Fonts\\segoeui.ttf",
    r"C:\\Windows\\Fonts\\arial.ttf",
    r"C:\\Windows\\Fonts\\tahoma.ttf",
    r"C:\\Windows\\Fonts\\calibri.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"
]
bold_candidates = [
    r"C:\\Windows\\Fonts\\segoeuib.ttf",
    r"C:\\Windows\\Fonts\\arialbd.ttf",
    r"C:\\Windows\\Fonts\\tahomabd.ttf",
    r"C:\\Windows\\Fonts\\calibrib.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf"
]
font = next((p for p in font_candidates if p and os.path.exists(p)), None)
bold = next((p for p in bold_candidates if p and os.path.exists(p)), None)

FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
if font:
    pdfmetrics.registerFont(TTFont("TR", font))
    FONT_REGULAR = "TR"
if bold:
    pdfmetrics.registerFont(TTFont("TRB", bold))
    FONT_BOLD = "TRB"

out = os.path.join(BASE_DIR, "Bursa_35Sales_Bolgeleme_Yonetim_Sunumu.pdf")
c = canvas.Canvas(out, pagesize=A4)
W, H = A4

def header(title, subtitle=None):
    c.setFillColor(colors.HexColor("#17365D"))
    c.rect(0, H-28*mm, W, 28*mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 16)
    c.drawString(18*mm, H-16*mm, title)
    if subtitle:
        c.setFont(FONT_REGULAR, 8.5)
        c.drawString(18*mm, H-22.5*mm, subtitle)

def footer(page):
    c.setFillColor(colors.HexColor("#7F8C8D"))
    c.setFont(FONT_REGULAR, 7.5)
    c.drawString(18*mm, 10*mm, "TURKCELL SUPERONLINE - DEHANET | Bursa 35 SALES bölgeleme")
    c.drawRightString(W-18*mm, 10*mm, f"{page}")

def ptext(x, y, text, size=10, color="#222222", fontname=None, maxw=None, leading=None):
    if fontname is None:
        fontname = FONT_REGULAR
    c.setFillColor(colors.HexColor(color))
    c.setFont(fontname, size)
    if maxw:
        from reportlab.pdfbase.pdfmetrics import stringWidth
        words = text.split()
        line=""
        lines=[]
        for w in words:
            test=(line+" "+w).strip()
            if stringWidth(test, fontname, size) <= maxw:
                line=test
            else:
                lines.append(line); line=w
        if line: lines.append(line)
        lead=leading or size*1.35
        yy=y
        for ln in lines:
            c.drawString(x, yy, ln); yy-=lead
        return yy
    c.drawString(x,y,text)
    return y-(leading or size*1.35)

# Page 1
header("BURSA 35 SALES BÖLGELEME", "Üst yönetim için kısa karar notu")
c.setFillColor(colors.HexColor("#F3F6FA"))
c.roundRect(18*mm, H-70*mm, W-36*mm, 34*mm, 5*mm, fill=1, stroke=0)
ptext(24*mm, H-48*mm, "Amaç", 11, "#17365D", FONT_BOLD)
ptext(24*mm, H-55*mm, 
      "621 mahalleyi 35 kalıcı satış bölgesine ayırarak her SALES koduna yönetilebilir ve coğrafi olarak kompakt bir saha alanı tanımlamak.",
      10, "#222222", FONT_REGULAR, W-48*mm, 13)

cards=[("621","mahalle"),("35","SALES bölgesi"),(f"{total:,.0f}".replace(",","."),"toplam fırsat"),(f"{target:,.0f}".replace(",","."),"ortalama hedef")]
x0=18*mm
for i,(a,b) in enumerate(cards):
    x=x0+i*44*mm
    c.setFillColor(colors.white); c.roundRect(x,H-105*mm,39*mm,23*mm,4*mm,fill=1,stroke=1)
    c.setStrokeColor(colors.HexColor("#D9E2F3"))
    c.setFillColor(colors.HexColor("#17365D")); c.setFont(FONT_BOLD,16); c.drawCentredString(x+19.5*mm,H-91*mm,a)
    c.setFillColor(colors.HexColor("#667085")); c.setFont(FONT_REGULAR,8); c.drawCentredString(x+19.5*mm,H-99*mm,b)

ptext(18*mm,H-122*mm,"Neden bu şekilde dağıttık?",12,"#17365D",FONT_BOLD)
bullets=[
"Her satışçıya sadece nüfus değil, Superonline erişilebilirliği ve mevcut müşteri tabanı üzerinden oluşan satış fırsatı yüklendi.",
"Büyük ve yoğun alanlar birden fazla SALES bölgesine ayrıldı; küçük ve komşu alanlar gerektiğinde tek bölgede tutuldu.",
"Koordinatlar kullanılarak bölgenin coğrafi olarak kompakt olması hedeflendi; amaç satışçının sahada mümkün olduğunca yakın noktalar arasında çalışmasıdır.",
"SALES01-SALES35 personel değil, kalıcı bölge kodlarıdır. Personel değişse bile bölgenin kimliği ve geçmişi korunur."
]
yy=H-130*mm
for b in bullets:
    c.setFillColor(colors.HexColor("#17365D")); c.circle(20*mm,yy+1.5,1.2,fill=1,stroke=0)
    yy=ptext(25*mm,yy,b,9.5,"#333333",FONT_REGULAR,W-43*mm,12)
    yy-=2*mm

ptext(18*mm,yy-1*mm,"Yönetimsel sonuç",12,"#17365D",FONT_BOLD)
ptext(18*mm,yy-9*mm,
      "Bu çalışma “35 kişiyi 35 ilçeye dağıtma” değildir. Bursa'nın satış fırsatını ve saha yoğunluğunu 35 yönetilebilir coğrafi bölgeye dönüştürme çalışmasıdır.",
      10.5,"#222222",FONT_REGULAR,W-36*mm,14)
footer(1)
c.showPage()

# Page 2
header("BÖLGE SAYILARININ MANTIĞI", "Bölge sayısını neden ilçelere eşit vermedik?")
ptext(18*mm,H-43*mm,
      "Bir ilçenin büyüklüğü, bina yoğunluğu ve satış fırsatı diğer ilçeyle aynı değildir. Bu nedenle satışçı sayısı ilçe adedine göre değil, saha yüküne göre dağıtıldı.",
      10,"#222222",FONT_REGULAR,W-36*mm,13)

# Aggregate by district
agg=defaultdict(lambda:[0,0])
for r in regs:
    for ilce in r["ilceler"].split(","):
        if ilce:
            agg[ilce][0]+=1; agg[ilce][1]+=r["firsat"]
dist=sorted(agg.items(), key=lambda x:-x[1][0])
table_data=[["İlçe","SALES bölgesi","Bölge fırsatı"]]+[
    [k, str(v[0]), f"{v[1]:,.0f}".replace(",",".")] for k,v in dist
]
tbl=Table(table_data, colWidths=[55*mm,40*mm,55*mm])
tbl.setStyle(TableStyle([
    ("FONTNAME",(0,0),(-1,0),FONT_BOLD),("BACKGROUND",(0,0),(-1,0),colors.HexColor("#17365D")),
    ("TEXTCOLOR",(0,0),(-1,0),colors.white),("FONTNAME",(0,1),(-1,-1),FONT_REGULAR),
    ("FONTSIZE",(0,0),(-1,-1),8.5),("GRID",(0,0),(-1,-1),0.4,colors.HexColor("#D9E1F2")),
    ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white,colors.HexColor("#F7F9FC")]),
    ("ALIGN",(1,1),(-1,-1),"CENTER"),("VALIGN",(0,0),(-1,-1),"MIDDLE")
]))
tbl.wrapOn(c,W,H); tbl.drawOn(c,24*mm,H-128*mm)

ptext(18*mm,H-145*mm,"Öne çıkan kararlar",12,"#17365D",FONT_BOLD)
reasons=[
("Nilüfer - 14 bölge","Bursa'da en yoğun satış potansiyelinin önemli kısmı burada toplandığı için en fazla mikro bölgeleme ihtiyacı burada oluştu."),
("Osmangazi - 6 bölge","Yoğun ve geniş yerleşim alanı nedeniyle tek bir satışçı bölgesi olarak yönetmek saha yürüyüşünü ve kapsama alanını gereksiz büyütür."),
("Yıldırım - 4 bölge","Yüksek yoğunluk nedeniyle birkaç kompakt saha alanına ayrıldı."),
("Mudanya - 3 bölge","Coğrafi yayılım ve ayrı yerleşim kümeleri nedeniyle tek bölge yerine birkaç saha cebi oluşturuldu.")
]
yy=H-153*mm
for t,d in reasons:
    ptext(20*mm,yy,t,9.5,"#17365D",FONT_BOLD)
    yy=ptext(58*mm,yy,d,9.2,"#333333",FONT_REGULAR,W-76*mm,12)
    yy-=3*mm
footer(2); c.showPage()

# Page 3
header("ALGORİTMİK YAKLAŞIM", "Basitçe: denge + yakınlık + bölge bütünlüğü")
ptext(18*mm,H-43*mm,
      "Model, her mahalleyi 35 SALES grubundan birine bağlarken iki hedefi birlikte izledi:",
      10,"#222222",FONT_REGULAR,W-36*mm,13)

# two boxes
for x,title,body in [
    (18*mm,"1. DENGE","Her SALES bölgesinin satış fırsatı birbirine yaklaşsın; tek bir satışçı aşırı yüklenmesin."),
    (107*mm,"2. YAKINLIK","Bir SALES bölgesine atanan mahalleler mümkün olduğunca aynı coğrafi kümede kalsın.")
]:
    c.setFillColor(colors.HexColor("#F3F6FA")); c.roundRect(x,H-80*mm,85*mm,28*mm,4*mm,fill=1,stroke=0)
    ptext(x+5*mm,H-60*mm,title,10,"#17365D",FONT_BOLD)
    ptext(x+5*mm,H-67*mm,body,8.7,"#333333",FONT_REGULAR,75*mm,11)

ptext(18*mm,H-94*mm,"Kullanılan veri mantığı",12,"#17365D",FONT_BOLD)
data_points=[
"621 mahalle: mahalle kodu, adı ve koordinat",
"Superonline bina/HP verisi: RES HP ve aktif müşteri tabanı",
"Mahalle bazında türetilen satış fırsatı",
"35 sabit SALES değişkeni: SALES01 ... SALES35"
]
yy=H-103*mm
for s in data_points:
    c.setFillColor(colors.HexColor("#17365D")); c.circle(20*mm,yy+1.5,1.2,fill=1,stroke=0)
    yy=ptext(25*mm,yy,s,9.3,"#333333",FONT_REGULAR,W-43*mm,12); yy-=1.5*mm

ptext(18*mm,yy-3*mm,"Bu ilk sürümde önemli sınırlama",12,"#9A6700",FONT_BOLD)
ptext(18*mm,yy-11*mm,
      "Bina kayıtlarında bina bazlı koordinat bulunmadığı için “kapıdan kapıya yürüme mesafesi” henüz optimize edilmedi. Bu nedenle mevcut çıktı, mahalle koordinatlarıyla oluşturulmuş ilk saha tasarımıdır.",
      9.5,"#5B4636",FONT_REGULAR,W-36*mm,13)

ptext(18*mm,yy-39*mm,"Bir sonraki teknik seviye",12,"#17365D",FONT_BOLD)
ptext(18*mm,yy-47*mm,
      "Bina koordinatları geldiğinde aynı 35 SALES kodu bina seviyesine indirilecek; gerçek yürüme mesafesi, bölge içi kompaktlık ve maksimum erişim süresi doğrudan optimizasyona girecek.",
      9.8,"#222222",FONT_REGULAR,W-36*mm,13)
footer(3); c.showPage()

# Page 4
header("SAHADA NASIL KULLANILACAK?", "Personel değişir, SALES bölgesi kalır")
ptext(18*mm,H-43*mm,
      "Bu yapının kritik tasarım kararı: SALES kodları personel isimlerinden bağımsızdır.",
      10.5,"#222222",FONT_BOLD,W-36*mm,14)

flow_y=H-78*mm
boxes=[("SALES32","Kalıcı bölge"),("MEVCUT PERSONEL","Ahmet"),("DEĞİŞİKLİK","Ahmet ayrıldı"),("YENİ PERSONEL","Mehmet")]
x=18*mm
for i,(a,b) in enumerate(boxes):
    c.setFillColor(colors.HexColor("#F3F6FA")); c.roundRect(x,flow_y,38*mm,23*mm,4*mm,fill=1,stroke=1)
    ptext(x+19*mm,flow_y+14*mm,a,8.5,"#17365D",FONT_BOLD)
    c.setFillColor(colors.HexColor("#333333")); c.setFont(FONT_REGULAR,8); c.drawCentredString(x+19*mm,flow_y+7*mm,b)
    if i<3:
        c.setStrokeColor(colors.HexColor("#98A2B3")); c.line(x+38*mm+2*mm,flow_y+11*mm,x+44*mm,flow_y+11*mm)
        c.line(x+43*mm,flow_y+13*mm,x+46*mm,flow_y+11*mm); c.line(x+43*mm,flow_y+9*mm,x+46*mm,flow_y+11*mm)
    x+=45*mm

ptext(18*mm,H-115*mm,"Yönetim açısından kazanım",12,"#17365D",FONT_BOLD)
gains=[
"Personel ayrıldığında bölge yeniden tasarlanmak zorunda kalmaz.",
"Yeni personel sadece boş kalan SALES koduna atanabilir.",
"Satış hedefi, kurulum hedefi ve saha performansı bölge bazında tarihsel olarak izlenebilir.",
"İleride web uygulamasına geçildiğinde harita, personel atama ve KPI ekranları aynı veri modelini kullanabilir."
]
yy=H-124*mm
for g in gains:
    c.setFillColor(colors.HexColor("#17365D")); c.circle(20*mm,yy+1.5,1.2,fill=1,stroke=0)
    yy=ptext(25*mm,yy,g,9.5,"#333333",FONT_REGULAR,W-43*mm,12); yy-=2*mm

ptext(18*mm,yy-2*mm,"Sonuç cümlesi",12,"#17365D",FONT_BOLD)
ptext(18*mm,yy-10*mm,
      "35 satışçı için 35 kalıcı saha bölgesi tanımlanmış; dağılım ilçeye eşit değil, satış fırsatı ve coğrafi yönetilebilirliğe göre yapılmıştır.",
      10.2,"#222222",FONT_REGULAR,W-36*mm,14)
footer(4)
c.save()

print(out, os.path.getsize(out))
