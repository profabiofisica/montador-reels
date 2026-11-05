#!/usr/bin/env python3
"""Gravação REAL de tela para Reels da Agência RCA (05/11/2026).

Quando o briefing de um Reels pede "gravar a tela durante um teste real do PageSpeed
Insights", ninguém precisa sentar no computador: este script pergunta ao admin quais
Reels esperam gravação, pede ao admin o teste real do dia (API oficial do PageSpeed,
com a conexão Google da RCA), abre o relatório oficial do Lighthouse com esse resultado
(o mesmo motor e o mesmo visual do pagespeed.web.dev, em português), grava a tela em
formato vertical (1080x1920), rola até as recomendações e manda o mp4 para o admin, que
guarda na pasta do mês de "reels · vídeos brutos" no Drive do cliente.

05/11/2026: a página pagespeed.web.dev não termina o teste em navegador de nuvem (a cota
do IP compartilhado estoura). Por isso o teste roda pela API e só o relatório é aberto aqui.
Nada é simulado: sem resultado real, não há envio.
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
    with urllib.request.urlopen(req, timeout=240) as r:
        return json.loads(r.read().decode("utf-8"))


def enviar(post_id, mp4):
    b = "rca" + uuid.uuid4().hex
    dados = open(mp4, "rb").read()
    corpo = (f"--{b}\r\nContent-Disposition: form-data; name=\"id\"\r\n\r\n{post_id}\r\n"
             f"--{b}\r\nContent-Disposition: form-data; name=\"f\"; filename=\"tela.mp4\"\r\nContent-Type: video/mp4\r\n\r\n").encode() + dados + f"\r\n--{b}--\r\n".encode()
    return pedir("?acao=enviar", "POST", corpo, "multipart/form-data; boundary=" + b)


def relatorio(t, pasta):
    """teste real do dia pelo admin e relatório oficial do Lighthouse em HTML."""
    lhr = pedir(f"?acao=psi&id={t['id']}")
    if not lhr.get("ok"):
        raise RuntimeError(lhr.get("mensagem", "sem resultado do PageSpeed"))
    js = os.path.join(pasta, "psi.json")
    with open(js, "w", encoding="utf-8") as f:
        json.dump(lhr, f)
    html = os.path.join(pasta, "relatorio.html")
    subprocess.run(["node", os.path.join(os.path.dirname(os.path.abspath(__file__)), "gerar_relatorio.mjs"), js, html], check=True)
    return html


def gravar(t, pasta):
    from pathlib import Path
    from playwright.sync_api import sync_playwright
    html = relatorio(t, pasta)
    with sync_playwright() as p:
        nav = p.chromium.launch()
        # 05/11/2026: o vídeo sai no tamanho da tela do navegador; com 1080x1920 sobre uma tela de 432x768 a
        # página ficava num canto e o resto cinza (Reels 443). Tela e vídeo do mesmo tamanho e o ffmpeg amplia.
        ctx = nav.new_context(viewport={"width": 540, "height": 960}, device_scale_factor=2, locale="pt-BR",
                              record_video_dir=pasta, record_video_size={"width": 540, "height": 960})
        pg = ctx.new_page()
        pg.goto(Path(html).resolve().as_uri())
        # a nota real aparece no medidor do relatório
        pg.wait_for_selector(".lh-gauge__percentage", timeout=30000, state="attached")
        nota = pg.locator(".lh-gauge__percentage").first.inner_text().strip()
        ok = nota.isdigit()
        if ok:
            log(f"post {t['id']}: desempenho {nota} no celular")
            pg.wait_for_timeout(3500)
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
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", webm, "-vf", "scale=1080:1920:flags=lanczos,fps=30",
                            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p", "-an", mp4], check=True)
            r = enviar(t["id"], mp4)
            log(f"post {t['id']}: {r.get('mensagem')}")


if __name__ == "__main__":
    main()
