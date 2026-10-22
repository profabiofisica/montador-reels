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

try:
    import musica
except Exception:  # noqa: BLE001
    musica = None

VERSAO = "2.0"
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
        # 22/10/2026: manda a linha do erro (o ffmpeg repete o filtro inteiro antes dela)
        ls = [l for l in (r.stderr or "").splitlines() if l.strip()]
        err = [l for l in ls if any(k in l.lower() for k in ("error", "invalid", "no such", "not found", "unable", "failed"))]
        raise RuntimeError("ffmpeg: " + " | ".join((err or ls)[-3:])[-260:])


def cor(h):
    return "0x" + h.lstrip("#")


def linhas(texto, largura):
    texto = " ".join(str(texto or "").split())
    return textwrap.wrap(texto, width=largura, break_long_words=False)[:4] if texto else []


def filtros_titulo(texto, pasta, n, w, h):
    """título curto no alto da tela (quando a legenda da fala ocupa a parte de baixo)."""
    ls = linhas(texto, 18)
    if not ls:
        return []
    tam, esp = 70, 84
    y0 = int(h * 0.12)
    out = []
    for i, l in enumerate(ls[:2]):
        arq = os.path.join(pasta, f"h{n}_{i}.txt")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(l.upper())
        out.append(
            f"drawtext=fontfile='{FONTE}':textfile='{arq}':fontsize={tam}:fontcolor=white"
            f":x=(w-text_w)/2:y={y0 + i * esp}-(1-min(1\\,t/0.3))*24:alpha='min(1\\,t/0.3)'"
            ":box=1:boxcolor=0x542E81@0.88:boxborderw=18:shadowcolor=0x000000@0.4:shadowx=0:shadowy=4"
        )
    return out


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
    if s["tipo"] == "imagem":
        # foto em movimento (Ken Burns): aproxima, afasta ou passeia, alternando por cena
        quadros = int(dur * fps) + 1
        modo = n % 4
        z = {0: "1.0+0.16*on/{q}", 1: "1.16-0.16*on/{q}", 2: "1.12", 3: "1.04+0.10*on/{q}"}[modo].format(q=quadros)
        x = {0: "iw/2-(iw/zoom/2)", 1: "iw/2-(iw/zoom/2)", 2: "(iw-iw/zoom)*on/{q}", 3: "(iw-iw/zoom)*(1-on/{q})"}[modo].format(q=quadros)
        y = {0: "ih/2-(ih/zoom/2)", 1: "ih/2-(ih/zoom/2)", 2: "ih/2-(ih/zoom/2)", 3: "ih/3-(ih/zoom/3)"}[modo]
        entrada = ["-loop", "1", "-t", str(dur), "-i", clipes[s["arquivo"]]]
        base = (f"[0:v]scale={w*2}:{h*2}:force_original_aspect_ratio=increase,crop={w*2}:{h*2},"
                f"zoompan=z='{z}':x='{x}':y='{y}':d={quadros}:s={w}x{h}:fps={fps},setsar=1,"
                f"eq=contrast=1.04:saturation=1.08,vignette=PI/5,format=yuv420p")
        grande = False
    elif s["tipo"] == "video":
        entrada = ["-ss", str(s["inicio"]), "-t", str(dur), "-i", clipes[s["arquivo"]]]
        base = (f"[0:v]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},"
                f"eq=brightness=-0.03:saturation=1.05,format=yuv420p")
        grande = False
    else:
        entrada = ["-f", "lavfi", "-t", str(dur), "-i",
                   f"gradients=s={w}x{h}:r={fps}:c0={cor(c['cor1'])}:c1={cor(c['cor2'])}:c2={cor(c['cor3'])}:nb_colors=3:speed=0.012:type=linear"]
        base = "[0:v]setsar=1,format=yuv420p"
        grande = True
    if t.get("legendas") and not grande:
        vf = ",".join([base] + filtros_titulo(s.get("texto", ""), pasta, n, w, h))
    else:
        vf = ",".join([base] + filtros_texto(s.get("texto", ""), pasta, n, grande, w, h))
    if t.get("logo_arq") and (n == len(t["cenas"]) - 1 or s["tipo"] == "texto"):
        entrada += ["-i", t["logo_arq"]]
        lw = int(w * 0.20)
        filtro = f"{vf}[b];[1:v]scale={lw}:-1,format=rgba[l];[b][l]overlay=W-w-{int(w*0.06)}:H-h-{int(h*0.05)}:format=auto,format=yuv420p[v]"
    else:
        filtro = vf + "[v]"
    # fade curto no começo de cada cena
    if n == 0:
        filtro = filtro.replace("[v]", ",fade=t=in:st=0:d=0.25[v]") if filtro.endswith("[v]") else filtro
    ff(*entrada, "-filter_complex", filtro, "-map", "[v]", "-an", "-t", str(dur), "-r", str(fps),
       "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-pix_fmt", "yuv420p", saida)
    return saida


def trilha(clima=""):
    """música da pasta trilhas/, de preferência do mesmo clima (nome começa pelo clima)."""
    if not os.path.isdir(TRILHAS):
        return None
    ops = [f for f in os.listdir(TRILHAS) if f.lower().endswith((".mp3", ".m4a", ".wav"))]
    mesmo = [f for f in ops if clima and f.lower().startswith(clima.lower())]
    escolha = mesmo or ops
    return os.path.join(TRILHAS, random.choice(escolha)) if escolha else None


TRANS = ["fade", "slideleft", "smoothup", "circleopen", "slideup", "fadeblack", "smoothleft", "zoomin"]
XF = 0.35


def sondar(arq):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", arq], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def filtros_legenda(legs, pasta, w, h):
    """legenda da fala, bloco a bloco, com entrada em 'pop' (estilo reels)."""
    out = []
    for i, l in enumerate(legs):
        txt = " ".join(str(l.get("t", "")).split())
        if not txt:
            continue
        arq = os.path.join(pasta, f"leg{i}.txt")
        with open(arq, "w", encoding="utf-8") as f:
            f.write(txt.upper())
        a, b = float(l["a"]), float(l["b"])
        tam = 78 if len(txt) <= 14 else 66
        out.append(
            f"drawtext=fontfile='{FONTE}':textfile='{arq}':fontcolor=white:fontsize='{tam}*(1+0.14*max(0\\,1-(t-{a:.2f})/0.12))'"
            f":x=(w-text_w)/2:y={int(h*0.68)}-text_h/2:borderw=7:bordercolor=0x2a1640"
            f":shadowcolor=0x000000@0.5:shadowx=0:shadowy=5:enable='between(t\\,{a:.2f}\\,{b:.2f})'"
        )
    return out


def montar(t, pasta):
    clipes = {}
    for s in t["cenas"]:
        if s["tipo"] in ("video", "imagem") and s.get("url") and s.get("arquivo", s.get("img")) not in clipes:
            chave = s.get("arquivo") or s.get("img")
            dest = os.path.join(pasta, f"bruto_{len(clipes)}" + (".jpg" if s["tipo"] == "imagem" else ""))
            log("  baixando", s["tipo"], len(clipes) + 1)
            baixar(s["url"], dest)
            clipes[chave] = dest
            s["arquivo"] = chave
    voz = None
    if t.get("voz"):
        voz = os.path.join(pasta, "voz.mp3")
        baixar(t["voz"], voz)
    if t.get("logo"):
        try:
            dest = os.path.join(pasta, "logo" + os.path.splitext(t["logo"])[1])
            baixar(t["logo"], dest)
            png = os.path.join(pasta, "logo.png")
            ff("-i", dest, png)
            t["logo_arq"] = png
        except Exception as e:  # noqa: BLE001
            log("  sem logo:", e)
    # a voz manda no tempo: se sobrar ou faltar, a última cena ajusta
    cenas = t["cenas"]
    alvo = (sondar(voz) + 0.8) if voz else 0
    if alvo:
        sobra = alvo - (sum(float(s["dur"]) for s in cenas) - XF * (len(cenas) - 1))
        cenas[-1]["dur"] = max(1.6, float(cenas[-1]["dur"]) + sobra)
    # cada cena (menos a última) ganha o tempo da transição
    for i, s in enumerate(cenas):
        s["_dur"] = float(s["dur"]) + (XF if i < len(cenas) - 1 else 0)
    partes = []
    for i, s in enumerate(cenas):
        s2 = dict(s, dur=s["_dur"])
        partes.append(cena(t, s2, i, pasta, clipes))
    # junta com transições
    junto = os.path.join(pasta, "junto.mp4")
    if len(partes) == 1:
        shutil.copy(partes[0], junto)
        total = cenas[0]["_dur"]
    else:
        ent, fc, off, ant = [], [], 0.0, "[0:v]"
        for p in partes:
            ent += ["-i", p]
        for i in range(1, len(partes)):
            off += cenas[i - 1]["_dur"] - XF
            tr = TRANS[(i - 1) % len(TRANS)]
            saida = f"[x{i}]" if i < len(partes) - 1 else "[v]"
            fc.append(f"{ant}[{i}:v]xfade=transition={tr}:duration={XF}:offset={off:.3f}{saida}")
            ant = saida
        total = off + cenas[-1]["_dur"]
        ff(*ent, "-filter_complex", ";".join(fc), "-map", "[v]", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", "-r", str(t["fps"]), junto)
    # legenda da fala por cima do vídeo inteiro
    if t.get("legendas"):
        leg = os.path.join(pasta, "leg.mp4")
        vf = ",".join(filtros_legenda(t["legendas"], pasta, t["w"], t["h"])) or "null"
        ff("-i", junto, "-vf", vf, "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", leg)
        junto = leg
    # áudio: voz na frente, trilha embaixo e abaixando quando a voz fala
    mus = None
    if t.get("trilha"):
        try:
            mus = os.path.join(pasta, "trilha_drive")
            baixar(t["trilha"], mus)
        except Exception as e:  # noqa: BLE001
            log("  trilha do Drive falhou:", e)
            mus = None
    if not mus:
        mus = trilha(t.get("clima", ""))
        if mus:
            log("  trilha da pasta:", os.path.basename(mus))
    if not mus and musica:
        try:
            mus = musica.salvar(os.path.join(pasta, "trilha.wav"), total + 0.5, t.get("clima", "inspirador"))
            log("  trilha composta:", t.get("clima", "inspirador"))
        except Exception as e:  # noqa: BLE001
            log("  sem trilha:", e)
            mus = None
    final = os.path.join(pasta, "reels.mp4")
    fim = f"afade=t=out:st={max(0, total-1.4):.2f}:d=1.4"
    if voz and mus:
        fc = (f"[1:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=1.6,adelay=250|250,apad[vz];"
              f"[2:a]aformat=sample_rates=44100:channel_layouts=stereo,volume=0.42,afade=t=in:d=0.8[mu];"
              f"[vz]asplit=2[vz1][vz2];[mu][vz1]sidechaincompress=threshold=0.04:ratio=8:attack=20:release=350[duck];"
              f"[duck][vz2]amix=inputs=2:duration=first:normalize=0,{fim},loudnorm=I=-14:TP=-1.5:LRA=9[a]")
        ff("-i", junto, "-i", voz, "-stream_loop", "-1", "-i", mus, "-filter_complex", fc, "-map", "0:v", "-map", "[a]",
           "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "44100", "-movflags", "+faststart", final)
    elif voz:
        ff("-i", junto, "-i", voz, "-filter_complex", f"[1:a]adelay=250|250,apad,{fim},loudnorm=I=-14:TP=-1.5[a]", "-map", "0:v", "-map", "[a]",
           "-t", f"{total:.2f}", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", final)
    elif mus:
        ff("-i", junto, "-stream_loop", "-1", "-i", mus, "-map", "0:v", "-map", "1:a", "-t", f"{total:.2f}",
           "-af", f"volume=0.8,afade=t=in:d=0.6,{fim},loudnorm=I=-14:TP=-1.5",
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
