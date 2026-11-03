"""Render a fixed 62 x 36 mm laminated physical-plate identity label."""
import json,sys
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from inmateriis_platelink._vendor.qrcode import QRCode

def render(data,path):
    for name,file in [('PlateSans','DejaVuSans.ttf'),('PlateBold','DejaVuSans-Bold.ttf')]:
        pdfmetrics.registerFont(TTFont(name,'/usr/share/fonts/truetype/dejavu/'+file))
    c=canvas.Canvas(str(path),pagesize=(62*mm,36*mm),invariant=1)
    c.setTitle('PlateLink - '+data['code']);c.setAuthor('Inmateriis')
    qr=QRCode(border=4);qr.add_data(data['url']);qr.make(fit=True);matrix=qr.get_matrix();unit=26*mm/len(matrix)
    for y,row in enumerate(matrix):
        for x,dark in enumerate(row):
            if dark:c.rect(1*mm+x*unit,5*mm+(len(matrix)-1-y)*unit,unit,unit,stroke=0,fill=1)
    x=28*mm;w=32*mm
    c.setFont('PlateBold',5.5);c.drawString(x,29*mm,'PLATELINK / INMATERIIS')
    size=16
    while pdfmetrics.stringWidth(data['code'],'PlateBold',size)>w and size>8:size-=.5
    c.setFont('PlateBold',size);c.drawString(x,19*mm,data['code'])
    text=' / '.join(('Cara '+f['id']+': ' if len(data['faces'])>1 else '')+f['surface'] for f in data['faces'])
    lines=[];line=''
    for word in text.split():
        candidate=(line+' '+word).strip()
        if pdfmetrics.stringWidth(candidate,'PlateSans',8)>w:
            if line:lines.append(line)
            line=word
        else:line=candidate
    if line:lines.append(line)
    for i,line in enumerate(lines[:2]):
        while pdfmetrics.stringWidth(line,'PlateSans',8)>w:line=line[:-2]+'…'
        c.setFont('PlateSans',8);c.drawString(x,(14-i*3.6)*mm,line)
    c.setFont('PlateSans',6);c.drawString(x,4.5*mm,'Escanea para ver la ficha')
    c.showPage();c.save()
if __name__=='__main__':render(json.load(sys.stdin),sys.argv[1])
