#!/usr/bin/env python3
"""Gravação REAL de tela para Reels da Agência RCA (05/11/2026).

Quando o briefing de um Reels pede "gravar a tela durante um teste real do PageSpeed
Insights", ninguém precisa sentar no computador: este script pergunta ao admin quais
Reels esperam gravação, abre o teste de verdade no pagespeed.web.dev num Chromium,
grava a tela em formato vertical (1080x1920), espera o resultado do dia aparecer,
rola até as recomendações e manda o mp4 para o admin, que guarda na pasta do mês
de "reels · vídeos brutos" no Drive do cliente. O Tom usa esse vídeo como vídeo real.

Nada é simulado: se o teste não terminar, não há envio.
"""
import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

TOKEN = os.environ.get("RCA_REELS_TOKEN", "")
BASE = os.environ.get("RCA_BASE", "https://agenciarca.com.br")
API = "/portal-admin/api/reels-gravacao.php"


def log(*a):
    print(*a, flush=True)


def pedir(caminho, metodo="GET", corpo=None, tipo=None):
    req = urllib.request.Request(BASE + API + caminho, data=corpo, method=metodo)
    req.add_header("X-Reels-Token", TOKEN)
    req.add_header("User-Agent", "rca-gravar-tela/1.0")
    if tipo:
        req.add_header("Content-Type", tipo)
    with urllib.request.urlopen(req, timeout=180) as r:
        return json.loads(r.read().decode("utf-8"))


def enviar(post_id, mp4):
    b = "rca" + uuid.uuid4().hex
    dados = open(mp4, "rb").read()
    corpo = (f"--{b}\r\nContent-Disposition: form-data; name=\"id\"\r\n\r\n{post_id}\r\n"
             f"--{b}\r\nContent-Disposition: form-data; name=\"f\"; filename=\"tela.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").encode() + dados + f"\r\n--{b}--\r\n".encode()
    return pedir("?acao=enviar", "POST", corpo, "multipart/form-data; boundary=" + b)


def gravar(t, pasta):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        nav = p.chromium.launch()
        ctx = nav.new_context(viewport={"width": 432, "height": 768}, device_scale_factor=2.5, locale="pt-BR",
                              record_video_dir=pasta, record_video_size={"width": 1080, "height": 1920})
        pg = ctx.new_page()
        pg.goto(t["teste"], wait_until="domcontentloaded", timeout=60000)
        # espera o resultado real do teste (a nota de desempenho aparece no medidor)
        fim = time.time() + 150
        ok = False
        while time.time() < fim:
            txt = pg.inner_text("body")
            if ("Desempenho" in txt or "Performance" in txt) and ("Diagnosticar" in txt or "Diagnose" in txt or "Oportunidades" in txt or "Métricas" in txt):
                ok = True
                break
            pg.wait_for_timeout(2000)
        if ok:
            pg.wait_for_timeout(3000)
            # rola devagar até as recomendações reais
            for _ in range(14):
                pg.mouse.wheel(0, 220)
                pg.wait_for_timeout(700)
            pg.wait_for_timeout(2000)
        video = pg.video.path() if pg.video else None
        ctx.close()
        nav.close()
        return ok, video


def main():
    if not TOKEN:
        log("sem RCA_REELS_TOKEN")
        sys.exit(1)
    fila = pedir("?acao=fila").get("trabalhos") or []
    log(f"{len(fila)} reels esperando gravação de tela")
    for t in fila[:2]:
        with tempfile.TemporaryDirectory() as tmp:
            try:
                ok, webm = gravar(t, tmp)
            except Exception as e:  # noqa: BLE001
                log(f"post {t['id']}: navegador falhou: {e}")
                continue
            if not ok or not webm:
                log(f"post {t['id']}: o teste não terminou; nada enviado")
                continue
            mp4 = os.path.join(tmp, "tela.mp4")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-vf", "scale=1080:1920,fps=30",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-an", mp4], check=True)
            r = enviar(t["id"], mp4)
            log(f"post {t['id']}: {r.get('mensagem')}")


if __name__ == "__main__":
    main()
