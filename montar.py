#!/usr/bin/env python3
"""Montador de reels da Agência RCA (22/10/2026).

Roda no GitHub Actions a cada hora (ou na mão). Pergunta ao admin se tem
reels para montar, baixa os trechos dos vídeos pelo admin (ele busca no
Drive), monta com ffmpeg em 1080x1920 e devolve o MP4 em pedaços.

Variáveis:
  RCA_REELS_TOKEN  senha do montador (aba IA do admin > Reels automáticos)
  RCA_BASE         endereço do site (padrão https://agenciarca.com.br)
Só usa a biblioteca padrão do Python e o ffmpeg.
"""
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import urllib.error
import urllib.request

VERSAO = "1.0"
BASE = os.environ.get("RCA_BASE", "https://agenciarca.com.br").rstrip("/")
TOKEN = os.environ.get("RCA_REELS_TOKEN", "")
AQUI = os.path.dirname(os.path.abspath(__file__))
FONTE = os.path.join(AQUI, "fontes", "Poppins-Bold.ttf")
TRILHAS = os.path.join(AQUI, "trilhas")


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def pedir(caminho, metodo="GET", corpo=None, tipo=None, tentativas=3, tempo=120):
    url = caminho if caminho.startswith("http") else BASE + caminho
    for i in range(tentativas):
        req = urllib.request.Request(url, data=corpo, method=metodo)
        req.add_header("X-Reels-Token", TOKEN)
        req.add_header("User-Agent", "rca-montador-reels/" + VERSAO)
        if tipo:
            req.add_header("Content-Type", tipo)
        try:
            with urllib.request.urlopen(req, timeout=tempo) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", "replace")[:300]
            if e.code < 500 or i == tentativas - 1:
                raise RuntimeError(f"{e.code} em {caminho.split('?')[0]}: {texto}")
        except (urllib.error.URLError, TimeoutError) as e:
            if i == tentativas - 1:
                raise RuntimeError(f"sem conexão com {caminho.split('?')[0]}: {e}")
        time.sleep(3 * (i + 1))


def baixar(caminho, destino):
    url = caminho if caminho.startswith("http") else BASE + caminho
    req = urllib.request.Request(url, headers={"User-Agent": "rca-montador-reels/" + VERSAO})
    for i in range(3):
        try:
            with urllib.request.urlopen(req, timeout=600) as r, open(destino, "wb") as f:
                shutil.copyfileobj(r, f, 1024 * 1024)
            if os.path.getsize(destino) > 1000:
                return
        except Exception as e:  # noqa: BLE001
            if i == 2:
                raise RuntimeError(f"não baixei {os.path.basename(destino)}: {e}")
        time.sleep(5)


def ff(*args):
    cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg: " + (r.stderr or "")[-600:])


def cor(h):
    return "0x" + h.lstrip("#")


def linhas(texto, largura):
    texto = " ".join(str(texto or "").split())
    return textwrap.wrap(texto, width=largura, break_long_words=False)[:4] if texto else []


def filtros_texto(texto, pasta, n, grande, w, h):
    """drawtext linha a linha, centralizado, com entrada suave (sem depender do text_align do ffmpeg)."""
    ls = linhas(texto, 14 if grande else 20)
    if not ls:
        return []
    tam = 96 if grande else 64
    esp = int(tam * 1.18)
    altura = esp * len(ls)
    y0 = (h - altura) // 2 if grande else int(h * 0.70) - altura // 2
    out = []
    for i, l in enumerate(ls):
        arq = os.path.join(pasta, f"t{n}_{i}.txt")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(l)
        out.append(
            f"drawtext=fontfile='{FONTE}':textfile='{arq}':fontsize={tam}:fontcolor=white"
            f":x=(w-text_w)/2:y={y0 + i * esp}+(1-min(1\\,t/0.35))*30:alpha='min(1\\,t/0.35)'"
            + ("" if grande else ":box=1:boxcolor=0x1a0d2e@0.55:boxborderw=22")
            + ":shadowcolor=0x000000@0.45:shadowx=0:shadowy=3"
        )
    return out


def cena(t, s, n, pasta, clipes):
    w, h, fps = t["w"], t["h"], t["fps"]
    dur = float(s["dur"])
    saida = os.path.join(pasta, f"c{n:02d}.mp4")
    c = t["cores"]
    if s["tipo"] == "video":
        entrada = ["-ss", str(s["inicio"]), "-t", str(dur), "-i", clipes[s["arquivo"]]]
        base = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},"
                f"eq=brightness=-0.03:saturation=1.05,format=yuv420p")
        grande = False
    else:
        entrada = ["-f", "lavfi", "-t", str(dur), "-i",
                   f"gradients=s={w}x{h}:r={fps}:c0={cor(c['cor1'])}:c1={cor(c['cor2'])}:c2={cor(c['cor3'])}:nb_colors=3:speed=0.012:type=linear"]
        base = "[0:v]setsar=1,format=yuv420p"
        grande = True
    vf = ",".join([base] + filtros_texto(s.get("texto", ""), pasta, n, grande, w, h))
    if t.get("logo_arq"):
        entrada += ["-i", t["logo_arq"]]
        lw = int(w * 0.20)
        filtro = f"{vf}[b];[1:v]scale={lw}:-1,format=rgba[l];[b][l]overlay=W-w-{int(w*0.06)}:H-h-{int(h*0.05)}:format=auto,format=yuv420p[v]"
    else:
        filtro = vf + "[v]"
    # fade curto no começo de cada cena
    filtro = filtro.replace("[v]", ",fade=t=in:st=0:d=0.18[v]") if filtro.endswith("[v]") else filtro
    ff(*entrada, "-filter_complex", filtro, "-map", "[v]", "-an", "-t", str(dur), "-r", str(fps),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", saida)
    return saida


def trilha():
    if not os.path.isdir(TRILHAS):
        return None
    ops = [os.path.join(TRILHAS, f) for f in os.listdir(TRILHAS) if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    return random.choice(ops) if ops else None


def montar(t, pasta):
    clipes = {}
    for s in t["cenas"]:
        if s["tipo"] == "video" and s["arquivo"] not in clipes:
            dest = os.path.join(pasta, f"bruto_{len(clipes)}")
            log("  baixando trecho", len(clipes) + 1)
            baixar(s["url"], dest)
            clipes[s["arquivo"]] = dest
    if t.get("logo"):
        try:
            dest = os.path.join(pasta, "logo" + os.path.splitext(t["logo"])[1])
            baixar(t["logo"], dest)
            png = os.path.join(pasta, "logo.png")
            ff("-i", dest, png)
            t["logo_arq"] = png
        except Exception as e:  # noqa: BLE001
            log("  sem logo:", e)
    partes = [cena(t, s, i, pasta, clipes) for i, s in enumerate(t["cenas"])]
    lista = os.path.join(pasta, "lista.txt")
    with open(lista, "w") as f:
        f.writelines(f"file '{p}'\n" for p in partes)
    junto = os.path.join(pasta, "junto.mp4")
    ff("-f", "concat", "-safe", "0", "-i", lista, "-c", "copy", junto)
    total = sum(float(s["dur"]) for s in t["cenas"])
    final = os.path.join(pasta, "reels.mp4")
    mus = trilha()
    if mus:
        ff("-i", junto, "-stream_loop", "-1", "-i", mus, "-map", "0:v", "-map", "1:a", "-t", f"{total:.2f}",
           "-af", f"volume=0.8,afade=t=in:d=0.6,afade=t=out:st={max(0, total-1.2):.2f}:d=1.2",
           "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final)
    else:
        ff("-i", junto, "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo", "-map", "0:v", "-map", "1:a",
           "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", final)
    return final


def entregar(t, arq):
    tam = int(t.get("pedaco") or 2 * 1024 * 1024)
    dados = open(arq, "rb").read()
    total = max(1, -(-len(dados) // tam))
    for n in range(total):
        r = pedir(f"/portal-admin/api/reels.php?acao=parte&post={t['id']}&n={n}&total={total}", "POST",
                  dados[n * tam:(n + 1) * tam], "application/octet-stream")
        if not r.get("ok"):
            raise RuntimeError(r.get("mensagem", "entrega recusada"))
    return r


def main():
    if not TOKEN:
        sys.exit("Falta o segredo RCA_REELS_TOKEN.")
    shutil.which("ffmpeg") or sys.exit("Falta o ffmpeg.")
    fila = pedir(f"/portal-admin/api/reels.php?acao=fila&v={VERSAO}")
    trabalhos = fila.get("trabalhos") or []
    log(f"{len(trabalhos)} reels na fila")
    falhas = 0
    for t in trabalhos:
        log(f"montando #{t['id']} {t.get('cliente', '')}: {t.get('titulo', '')} ({len(t['cenas'])} cenas)")
        pasta = tempfile.mkdtemp(prefix=f"reels{t['id']}_")
        try:
            arq = montar(t, pasta)
            log(f"  pronto: {os.path.getsize(arq) // 1024} KB, entregando")
            r = entregar(t, arq)
            log("  ", r.get("mensagem", "entregue"))
        except Exception as e:  # noqa: BLE001
            falhas += 1
            log("  falhou:", e)
            try:
                pedir(f"/portal-admin/api/reels.php?acao=falha&post={t['id']}", "POST",
                      json.dumps({"erro": str(e)[:280]}).encode(), "application/json")
            except Exception as e2:  # noqa: BLE001
                log("  nem consegui avisar:", e2)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
