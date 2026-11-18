#!/usr/bin/env python3
"""Estúdio RCA (17/11/2026): montador novo dos Reels, no Remotion.

Mesmo contrato do montar.py com o admin (reels.php: fila, parte, falha), mas a montagem
sai do estudio/ (React + Remotion): legenda palavra por palavra sincronizada com a voz,
gancho animado, transições, movimento de câmera por cena, logo, trilha que abaixa
sozinha quando a voz entra, efeito sonoro nos cortes, barra de progresso e capa 3:4.
O tempo de cada palavra vem da própria voz (faster-whisper no runner); sem ele,
usa o tempo que o admin mandou.
"""
import difflib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

import montar as m  # pedir, baixar, conferir, entregar, log, sondar

AQUI = os.path.dirname(os.path.abspath(__file__))
EST = os.path.join(AQUI, "estudio")
PUB = os.path.join(EST, "public")
VERSAO = "estudio-1.0"


def norm(w):
    return re.sub(r"[^\wà-ú]", "", w.lower())


def palavras_do_admin(legs):
    """o admin manda blocos {t,a,b}; vira palavra a palavra, tempo proporcional ao tamanho."""
    out = []
    for l in legs or []:
        if "p" in l:
            out.append({"p": l["p"], "a": float(l["a"]), "b": float(l["b"])})
            continue
        ws = str(l.get("t", "")).split()
        if not ws:
            continue
        a, b = float(l["a"]), float(l["b"])
        peso = [max(2, len(w)) for w in ws]
        tot, t = sum(peso), a
        for w, p in zip(ws, peso):
            d = (b - a) * p / tot
            out.append({"p": w, "a": round(t, 3), "b": round(t + d * 0.92, 3)})
            t += d
    return out


def alinhar(voz, roteiro):
    """tempo real de cada palavra, ouvindo a voz; o texto fica o do roteiro (sem erro de transcrição)."""
    try:
        from faster_whisper import WhisperModel
    except Exception:  # noqa: BLE001
        return None
    try:
        mod = WhisperModel(os.environ.get("WHISPER_MODELO", "small"), device="cpu", compute_type="int8")
        segs, _ = mod.transcribe(voz, language="pt", word_timestamps=True, vad_filter=False)
        ouvidas = [{"p": w.word.strip(), "a": float(w.start), "b": float(w.end)} for s in segs for w in (s.words or [])]
    except Exception as e:  # noqa: BLE001
        m.log("  alinhamento falhou:", e)
        return None
    if not ouvidas:
        return None
    ref = [w["p"] for w in roteiro] if roteiro else [w["p"] for w in ouvidas]
    if not roteiro:
        return ouvidas
    sm = difflib.SequenceMatcher(a=[norm(x) for x in ref], b=[norm(w["p"]) for w in ouvidas], autojunk=False)
    tempos = [None] * len(ref)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                tempos[i1 + k] = (ouvidas[j1 + k]["a"], ouvidas[j1 + k]["b"])
        elif j2 > j1:
            a, b = ouvidas[j1]["a"], ouvidas[j2 - 1]["b"]
            n = i2 - i1
            for k in range(n):
                tempos[i1 + k] = (a + (b - a) * k / max(1, n), a + (b - a) * (k + 1) / max(1, n))
    # preenche buracos pelo vizinho
    for i, x in enumerate(tempos):
        if x is None:
            ant = tempos[i - 1][1] if i and tempos[i - 1] else 0.0
            tempos[i] = (ant, ant + 0.25)
    return [{"p": w, "a": round(a, 3), "b": round(b, 3)} for w, (a, b) in zip(ref, tempos)]


def frase(texto, fim=True):
    fr = [x.strip() for x in re.split(r"(?<=[.!?])\s+", " ".join(texto.split())) if x.strip()]
    if not fr:
        return ""
    f = fr[-1] if fim else fr[0]
    return f if len(f.split()) <= 9 else ""


def montar_estudio(t, pasta):
    trab = os.path.join(PUB, "trab", str(t["id"]))
    shutil.rmtree(trab, ignore_errors=True)
    os.makedirs(trab)
    loc = lambda nome: "local:trab/%s/%s" % (t["id"], nome)  # noqa: E731
    cenas, baixados = [], {}
    for i, s in enumerate(t["cenas"]):
        c = {"tipo": s["tipo"], "dur": float(s["dur"]), "texto": s.get("texto", ""), "camera": s.get("camera", "")}
        if s["tipo"] in ("video", "imagem") and s.get("url"):
            if s["url"] not in baixados:
                ext = ".mp4" if s["tipo"] == "video" else ".jpg"
                nome = f"c{len(baixados)}{ext}"
                m.log("  baixando", s["tipo"], len(baixados) + 1)
                m.baixar(s["url"], os.path.join(trab, nome))
                baixados[s["url"]] = nome
            c["src"] = loc(baixados[s["url"]])
            c["inicio"] = float(s.get("inicio") or 0)
        elif s["tipo"] in ("video", "imagem"):
            c["tipo"] = "texto"
        cenas.append(c)
    props = {"w": int(t["w"]), "h": int(t["h"]), "fps": int(t["fps"]), "cenas": cenas, "transicao": 0.4,
             "cores": {"cor1": t["cores"].get("cor1", "#542E81"), "cor2": t["cores"].get("cor2", "#A52E78"),
                       "cor3": t["cores"].get("cor3", "#2A1748"), "destaque": t["cores"].get("destaque", "#EF773B")},
             "sfx": "local:sfx/whoosh.wav"}
    if t.get("logo"):
        try:
            ext = os.path.splitext(t["logo"].split("?")[0])[1] or ".png"
            m.baixar(t["logo"], os.path.join(trab, "logo" + ext))
            props["logo"] = loc("logo" + ext)
        except Exception as e:  # noqa: BLE001
            m.log("  sem logo:", e)
    voz = None
    if t.get("voz"):
        voz = os.path.join(trab, "voz.mp3")
        m.baixar(t["voz"], voz)
        props["voz"] = loc("voz.mp3")
    mus = None
    if t.get("trilha"):
        try:
            mus = os.path.join(trab, "trilha.mp3")
            m.baixar(t["trilha"], mus)
        except Exception as e:  # noqa: BLE001
            m.log("  trilha do Drive falhou:", e)
            mus = None
    if not mus:
        p = m.trilha(t.get("clima", ""))
        if p:
            mus = os.path.join(trab, "trilha" + os.path.splitext(p)[1])
            shutil.copy(p, mus)
    if mus:
        props["trilha"] = loc(os.path.basename(mus))
    t["_trilha"], t["_voz"] = bool(mus), bool(voz)
    roteiro = palavras_do_admin(t.get("legendas"))
    leg = alinhar(voz, roteiro) if voz else None
    if leg:
        m.log(f"  legenda alinhada pela voz ({len(leg)} palavras)")
        # a voz entra 0,25 s depois (Sequence from)
        leg = [dict(w, a=w["a"] + 0.25, b=w["b"] + 0.25) for w in leg]
    props["legendas"] = leg or roteiro
    fala = " ".join(w["p"] for w in props["legendas"])
    props["gancho"] = t.get("gancho") or t.get("capa_texto") or t.get("capa") or frase(fala, fim=False)
    props["cta"] = t.get("cta") or frase(fala, fim=True)
    # a voz manda no tempo: a última cena estica ou encolhe
    xf = props["transicao"]
    if voz:
        alvo = m.sondar(voz) + 0.25 + 1.0
        soma = sum(c["dur"] for c in cenas) - xf * (len(cenas) - 1)
        cenas[-1]["dur"] = max(1.8, cenas[-1]["dur"] + alvo - soma)
    t["_total"] = sum(c["dur"] for c in cenas) - xf * (len(cenas) - 1)
    arq_job = os.path.join(pasta, "job.json")
    with open(arq_job, "w", encoding="utf-8") as f:
        json.dump(props, f, ensure_ascii=False)
    final = os.path.join(pasta, "reels.mp4")
    capa = os.path.join(pasta, "capa.jpg")
    r = subprocess.run(["node", "render.mjs", arq_job, final, capa], cwd=EST, capture_output=True, text=True, timeout=1800)
    saida = "\n".join(l for l in (r.stdout + r.stderr).splitlines() if "emory" not in l and "docker" not in l)
    if r.returncode != 0 or not os.path.exists(final):
        raise RuntimeError("estúdio: " + saida[-400:])
    m.log("  renderizado", f"{os.path.getsize(final) // 1024} KB")
    shutil.rmtree(trab, ignore_errors=True)
    return final, capa


def main():
    if not m.TOKEN:
        sys.exit("Falta o segredo RCA_REELS_TOKEN.")
    fila = m.pedir(f"/portal-admin/api/reels.php?acao=fila&v={VERSAO}")
    trabalhos = fila.get("trabalhos") or []
    m.log(f"{len(trabalhos)} reels na fila")
    falhas = 0
    for t in trabalhos:
        m.log(f"estúdio #{t['id']} {t.get('cliente', '')}: {t.get('titulo', '')} ({len(t['cenas'])} cenas)")
        pasta = tempfile.mkdtemp(prefix=f"est{t['id']}_")
        try:
            arq, _capa = montar_estudio(t, pasta)
            m.conferir(t, arq)
            r = m.entregar(t, arq)
            m.log("  ", r.get("mensagem", "entregue"))
        except Exception as e:  # noqa: BLE001
            falhas += 1
            m.log("  falhou:", e)
            try:
                m.pedir(f"/portal-admin/api/reels.php?acao=falha&post={t['id']}", "POST",
                        json.dumps({"erro": str(e)[:280]}).encode(), "application/json")
            except Exception as e2:  # noqa: BLE001
                m.log("  nem consegui avisar:", e2)
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--teste":
        # teste local: python3 estudio.py --teste trabalho.json (gera /tmp/estudio-teste.mp4)
        t = json.load(open(sys.argv[2], encoding="utf-8"))
        p = tempfile.mkdtemp()
        a, c = montar_estudio(t, p)
        m.conferir(t, a)
        shutil.copy(a, "/tmp/estudio-teste.mp4")
        shutil.copy(c, "/tmp/estudio-capa.jpg")
        print("ok")
    else:
        main()
