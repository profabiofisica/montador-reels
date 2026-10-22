#!/usr/bin/env python3
"""Baixa para trilhas/ as músicas listadas em trilhas/pixabay.json (22/10/2026).

Roda no GitHub Actions (workflow Trilhas). Só baixa o que ainda não está na pasta.
O nome do arquivo começa pelo clima (animado, inspirador, calmo, intenso), que é
como o montador escolhe a trilha de cada reels.
"""
import json
import os
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
PASTA = os.path.join(AQUI, "trilhas")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"

lista = json.load(open(os.path.join(PASTA, "pixabay.json"), encoding="utf-8"))["faixas"]
novos = falhas = 0
for f in lista:
    dest = os.path.join(PASTA, f["arquivo"])
    if os.path.exists(dest) and os.path.getsize(dest) > 50000:
        continue
    req = urllib.request.Request(f["url"], headers={"User-Agent": UA, "Referer": "https://pixabay.com/"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            dados = r.read()
        if len(dados) < 50000 or not (dados[:3] == b"ID3" or dados[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")):
            raise RuntimeError(f"resposta não é mp3 ({len(dados)} bytes)")
        open(dest, "wb").write(dados)
        novos += 1
        print("baixei", f["arquivo"], len(dados) // 1024, "KB")
    except Exception as e:  # noqa: BLE001
        falhas += 1
        print("falhou", f["arquivo"], e)
    time.sleep(2)
print(f"{novos} nova(s), {falhas} falha(s)")
