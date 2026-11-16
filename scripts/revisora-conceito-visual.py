#!/usr/bin/env python3
"""Revisão técnica com configuração do conceito aprovado, sem aprovar arte automaticamente."""
import json, sys, re, subprocess, unicodedata, urllib.request, tempfile, os
from PIL import Image

def norm(s):
    s=unicodedata.normalize("NFD",s.lower())
    s="".join(c for c in s if unicodedata.category(c)!="Mn")
    return re.sub(r"[^a-z0-9]+"," ",s).strip()

def fetch(url,path):
    if not url.startswith("https://"): raise ValueError("Exige URL HTTPS")
    req=urllib.request.Request(url,headers={"User-Agent":"RCA-Revisora-Conceito/1.0"})
    with urllib.request.urlopen(req,timeout=35) as r:
        ct=r.headers.get("content-type","")
        if not (ct.startswith("image/") or ct=="application/octet-stream"):
            raise ValueError("URL não forneceu imagem: "+ct)
        b=r.read(18000001)
        if len(b)>18000000: raise ValueError("Arquivo excedeu 18MB")
    with open(path,"wb") as f:f.write(b)
    return len(b)

def logo_no_lugar(arte,logo,reg):
    ref=logo.convert("RGBA")
    lo,hi=ref.getchannel("A").getextrema()
    if lo>240: return {"status":"MANUAL","motivo":"logo fonte sem transparência verificável"}
    x,y,w,h=(int(reg[k]) for k in ("x","y","w","h"))
    if x<0 or y<0 or x+w>arte.width or y+h>arte.height:
        return {"status":"REPROVADO","motivo":"logo fora da área da arte"}
    ref=ref.resize((w,h),Image.Resampling.LANCZOS)
    patch=arte.crop((x,y,x+w,y+h)).convert("RGB")
    pa=patch.load();ma=ref.getchannel("A").load()
    n=ok=0
    for yy in range(0,h,2):
        for xx in range(0,w,2):
            if ma[xx,yy]>=230:
                n+=1
                if min(pa[xx,yy])>=170:ok+=1
    if n<60:return {"status":"MANUAL","motivo":"amostragem insuficiente"}
    hit=ok/n
    return {"status":"OK" if hit>=0.78 else "REPROVADO",
            "proporcao_logo_claro":round(hit,3),"amostras":n,
            "limite":"Amostra luminosidade na posição indicada, não certifica desenho nem versão."}

def main():
    cfg=json.load(open(sys.argv[1],encoding="utf-8"))
    os.makedirs("relatorios",exist_ok=True)
    errs=[];details={}
    req=["cliente","conceito_versao","arte_url","logo_oficial_url","logo_regiao","texto_final","formato"]
    for k in req:
        if not cfg.get(k): errs.append("Faltou parâmetro: "+k)
    if not errs:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                artwork=os.path.join(tmp,"arte.png");logofile=os.path.join(tmp,"logo.webp")
                details["bytes"]=fetch(cfg["arte_url"],artwork)
                im=Image.open(artwork).convert("RGB")
                details["tamanho"]=[im.width,im.height]
                if details["tamanho"]!=cfg["formato"]:
                    errs.append("Formato incorreto; tamanho lido "+str(details["tamanho"]))
                r=subprocess.run(["tesseract",artwork,"stdout","-l","por","--psm","11"],capture_output=True,text=True,timeout=50)
                if r.returncode:errs.append("OCR indisponível: "+r.stderr[:130])
                read=norm(r.stdout);details["ocr"]=r.stdout[:1200]
                for phrase in cfg["texto_final"]:
                    words=norm(phrase).split()
                    if words:
                        coverage=sum(bool(re.search(r"\b"+re.escape(w)+r"\b",read)) for w in words)/len(words)
                        if coverage<0.67:errs.append("Texto não conferiu OCR ("+str(round(coverage*100))+"%): "+phrase)
                fetch(cfg["logo_oficial_url"],logofile)
                details["logo"]=logo_no_lugar(im,Image.open(logofile),cfg["logo_regiao"])
                if details["logo"]["status"]!="OK":errs.append("Logo não validado: "+details["logo"]["motivo"])
            except Exception as e:
                errs.append("Erro de acesso/validação: "+str(e)[:350])
    result={"cliente":cfg.get("cliente"),"conceito_versao":cfg.get("conceito_versao"),
        "status":"BLOQUEADO" if errs else "PRE_AUDITORIA_OK_REQUER_INSPECAO_VISUAL",
        "erros":errs,"detalhes":details,"aprovacao_humana":False,
        "nota":"Revisão de tipografia Poppins, paleta, estilo, hierarquia, versão do logo e aderência ao conceito requer inspeção visual da direção. Este teste não aprova nem publica."}
    with open("relatorios/conceito-visual.json","w") as f:json.dump(result,f,indent=2,ensure_ascii=False)
    md="# Pré-auditoria por conceito visual\n\n**Cliente:** "+str(cfg.get("cliente"))+" | **Conceito:** "+str(cfg.get("conceito_versao"))+"\n\n**Resultado:** "+result["status"]+"\n\n"+("\n".join("- "+x for x in errs) if errs else "Sem impedimento técnico identificado.")+"\n\n"+result["nota"]+"\n"
    with open("relatorios/conceito-visual.md","w") as f:f.write(md)
    print(md)
    sys.exit(2 if errs else 0)
if __name__=="__main__":main()
