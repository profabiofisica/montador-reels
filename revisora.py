#!/usr/bin/env python3
"""Revisora de artes da Agência RCA (05/11/2026).

Segunda revisão, sem IA e sem custo, de toda arte que a Criative manda pelo
arte-envio.php, antes de a arte chegar à diretoria. Roda no GitHub Actions a
cada 20 minutos (ou na mão). Pergunta ao admin a fila, baixa cada peça, mede e
lê o texto com OCR (tesseract, português) e devolve passou ou reprovou com o
motivo de cada furo.

Conferências (todas exatas, com número):
  1. tamanho da peça pelo canal (feed, Stories, GMN);
  2. texto: o que está escrito na arte tem que estar no briefing, palavra por
     palavra (letra encavalada, cortada ou palavra inventada aparece aqui) e o
     texto do briefing tem que estar na arte;
  3. leitura: altura mínima da letra e contraste do texto com o fundo;
  4. margens: texto encostado na borda e fora da área segura do Stories.

Variáveis: RCA_REELS_TOKEN (a mesma senha do montador) e RCA_BASE.
Só usa a biblioteca padrão, o Pillow e o tesseract.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
import urllib.error
import urllib.request

from PIL import Image, ImageOps

VERSAO = "1.0"
BASE = os.environ.get("RCA_BASE", "https://agenciarca.com.br").rstrip("/")
TOKEN = os.environ.get("RCA_REELS_TOKEN", "")
API = "/portal-admin/api/arte-revisora.php"

TAMANHOS = {
    "feed": [(1080, 1350), (1080, 1320)],
    "lamina": [(1080, 1350), (1080, 1320), (5400, 1350)],
    "stories": [(1080, 1920)],
    "gmn": [(1200, 900), (1080, 1080), (720, 720)],
}
ALTURA_MIN = {"feed": 18, "lamina": 18, "stories": 24, "gmn": 16}   # px da caixa da palavra, em 1080 de largura
CONTRASTE_MIN = 3.0
BORDA = 12
SEGURA_STORIES = 250


def log(*a):
    print(time.strftime("%H:%M:%S"), *a, flush=True)


def pedir(caminho, metodo="GET", corpo=None):
    url = BASE + API + caminho
    for i in range(3):
        req = urllib.request.Request(url, data=corpo, method=metodo)
        req.add_header("X-Reels-Token", TOKEN)
        req.add_header("User-Agent", "rca-revisora/" + VERSAO)
        if corpo is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode("utf-8") or "{}")
        except urllib.error.HTTPError as e:
            if e.code < 500 or i == 2:
                raise RuntimeError(f"{e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
        except (urllib.error.URLError, TimeoutError) as e:
            if i == 2:
                raise RuntimeError(f"sem conexão: {e}")
        time.sleep(4 * (i + 1))


def baixar(url, destino):
    url = url if url.startswith("http") else BASE + url
    req = urllib.request.Request(url, headers={"User-Agent": "rca-revisora/" + VERSAO})
    with urllib.request.urlopen(req, timeout=120) as r, open(destino, "wb") as f:
        f.write(r.read())


def norm(p):
    p = unicodedata.normalize("NFD", p.lower())
    p = "".join(c for c in p if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9@.]", "", p).strip(".")


def palavras(texto):
    return [w for w in (norm(x) for x in re.split(r"[\s/|•·–—\-]+", texto or "")) if w]


# ---------- texto esperado de cada peça, tirado do briefing ----------
ROTULO = re.compile(r"^\s*(L[ÂA]MINA|TELA|STORY|STORIES|CAPA)\s*(\d+)?", re.I)


def blocos_laminas(briefing):
    """LÂMINA 1 ... LÂMINA 2 ...: texto de cada lâmina (sem a linha do rótulo)."""
    out, atual = [], None
    for linha in (briefing or "").splitlines():
        m = re.match(r"^\s*L[ÂA]MINA\s*(\d+)", linha, re.I)
        if m:
            atual = []
            out.append(atual)
            resto = re.sub(r"^\s*L[ÂA]MINA\s*\d+\s*[—–:\-]*\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ ]*$", "", linha.strip())
            if resto and resto != linha.strip():
                atual.append(resto)
            continue
        if atual is None:
            continue
        if re.match(r"^\s*[A-ZÁÉÍÓÚÂÊÔÃÕÇ ]{6,}[:—–]", linha) and not re.match(r"^\s*L[ÂA]MINA", linha, re.I):
            atual = None          # DIREÇÃO VISUAL:, LEGENDA: ... fim do bloco
            continue
        if linha.strip():
            atual.append(linha.strip())
    return [" ".join(b) for b in out]


def citacoes(briefing):
    """Textos entre aspas “...” ou "..." (o padrão TEXTO FINAL EXATO)."""
    return [t for t in re.findall(r"[“\"]([^”\"]{3,300})[”\"]", briefing or "")]


def esperado_da_peca(briefing, canal, indice, n_feed):
    lam = blocos_laminas(briefing)
    if canal in ("lamina", "feed") and lam and len(lam) >= n_feed and indice < len(lam):
        return lam[indice]
    cits = citacoes(briefing)
    if cits:
        return " ".join(cits)
    return ""


# ---------- OCR ----------
def ocr(caminho):
    """Lê a peça normal e invertida (texto claro em fundo escuro) e junta as palavras."""
    im = Image.open(caminho).convert("L")
    pal = []
    with tempfile.TemporaryDirectory() as tmp:
        for k, img in enumerate([im, ImageOps.invert(im)]):
            arq = os.path.join(tmp, f"o{k}.png")
            img.save(arq)
            r = subprocess.run(["tesseract", arq, "stdout", "-l", "por", "--psm", "11", "tsv"],
                               capture_output=True, text=True)
            for linha in r.stdout.splitlines()[1:]:
                c = linha.split("\t")
                if len(c) < 12 or not c[11].strip():
                    continue
                try:
                    conf = float(c[10])
                except ValueError:
                    continue
                if conf < 0:
                    continue
                x, y, w, h = (int(c[6]), int(c[7]), int(c[8]), int(c[9]))
                pal.append({"txt": c[11].strip(), "n": norm(c[11]), "conf": conf, "x": x, "y": y, "w": w, "h": h})
    # tira duplicadas (mesma caixa nas duas leituras): fica a de maior confiança
    pal.sort(key=lambda p: -p["conf"])
    fica = []
    for p in pal:
        if any(abs(p["x"] - q["x"]) < 8 and abs(p["y"] - q["y"]) < 8 for q in fica):
            continue
        fica.append(p)
    return fica


def lum(v):
    v = v / 255.0
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def colunas_de_letra(im_rgb, p):
    """Quantos blocos de letra separados por espaço vertical há na palavra. Letra encavalada
    (espaçamento negativo) junta tudo num bloco só: 'histórico' com 9 letras dá 1 bloco."""
    c = im_rgb.crop((p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])).convert("L")
    w, h = c.size
    px = list(c.tobytes())
    s = sorted(px)
    thr = (s[int(len(s) * 0.1)] + s[int(len(s) * 0.9)]) / 2
    texto_escuro = sum(1 for v in px if v < thr) < len(px) / 2
    n, antes = 0, False
    for x in range(w):
        tem = any(((px[y * w + x] < thr) == texto_escuro) for y in range(h))
        if tem and not antes:
            n += 1
        antes = tem
    return n


def contraste(im_rgb, p):
    caixa = im_rgb.crop((p["x"], p["y"], p["x"] + p["w"], p["y"] + p["h"])).convert("L")
    px = sorted(caixa.tobytes())
    if len(px) < 20:
        return 99.0
    a, b = lum(px[int(len(px) * 0.08)]), lum(px[int(len(px) * 0.92)])
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


# ---------- revisão de uma peça ----------
def revisar_peca(caminho, canal, esperado, vocab, livres):
    furos = []
    im = Image.open(caminho).convert("RGB")
    w, h = im.size
    ok_tam = TAMANHOS.get(canal)
    # exportação em 2x (2160x2700) vale: mesma proporção e pelo menos a largura pedida
    if ok_tam and not any(w >= a and abs(w / h - a / b) < 0.005 for a, b in ok_tam):
        furos.append(f"tamanho {w}x{h}; o {canal} pede " + " ou ".join(f"{a}x{b}" for a, b in ok_tam))
    pal = [p for p in ocr(caminho) if len(p["n"]) >= 2]
    escala = w / 1080.0
    lidas = [p for p in pal if p["conf"] >= 55]
    # 2a. palavra na arte que não existe no briefing (encavalada, cortada ou inventada)
    estranhas = []
    for p in lidas:
        n = p["n"]
        if len(n) < 4 or n in vocab or n in livres or any(n in v or v in n for v in vocab if len(v) >= 5 and len(n) >= 5):
            continue
        if re.fullmatch(r"[0-9.@]+", n):
            continue
        estranhas.append(p["txt"])
    # leitura com confiança baixa onde deveria haver texto do briefing = letra embaralhada
    ruins = [p["txt"] for p in pal if 0 <= p["conf"] < 45 and len(p["n"]) >= 4 and p["n"] not in livres]
    if len(estranhas) >= 2:
        furos.append("texto que não está no briefing ou ilegível na arte: " + ", ".join(estranhas[:8]))
    # 2c. letras encavaladas (espaçamento negativo no título): blocos de letra << número de letras
    grudadas = [p["txt"] for p in lidas if len(p["n"]) >= 5 and p["h"] >= 30 * escala
                and colunas_de_letra(im, p) < 0.6 * len(p["n"])]
    avisos = []
    if len(grudadas) >= 2:     # só aviso: em foto e faixa colorida a medida ainda erra
        avisos.append("conferir espaçamento entre letras: " + ", ".join(grudadas[:6]))
    # 2d. palavras grudadas sem espaço ("Temsite" = tem + site): espaçamento negativo entre palavras
    juntas = []
    for p in lidas:
        n = p["n"]
        if n in vocab or len(n) < 6:
            continue
        for i in range(2, len(n) - 1):
            a, b = n[:i], n[i:]
            if a in vocab and b in vocab and len(b) >= 2:
                juntas.append(f"{p['txt']} ({a} {b})")
                break
    if juntas:
        furos.append("palavras grudadas, sem espaço entre elas: " + ", ".join(juntas[:6]))
    if len(ruins) >= 3:
        furos.append("letras difíceis de ler (encavaladas, cortadas ou sem contraste): " + ", ".join(ruins[:8]))
    # 2b. texto do briefing que não apareceu na arte
    exp = [x for x in palavras(esperado) if len(x) >= 4]
    if exp:
        achadas = {p["n"] for p in pal}
        faltam = [x for x in exp if x not in achadas and not any(x in a or a in x for a in achadas if len(a) >= 4)]
        cobertura = 1 - len(faltam) / len(exp)
        minimo = 0.6 if canal == "stories" else 0.8
        if cobertura < minimo:
            furos.append(f"texto do briefing faltando ou ilegível ({int(cobertura * 100)}% lido; faltou: {', '.join(faltam[:8])})")
    # 3. leitura: letra pequena e contraste
    corpo = [p for p in lidas if p["n"] in vocab and p["n"] not in livres and len(p["n"]) >= 3]
    alt_min = ALTURA_MIN.get(canal, 20) * escala
    pequenas = [p for p in corpo if p["h"] < alt_min]
    if len(pequenas) >= 4:
        furos.append(f"texto pequeno demais para o celular: {len(pequenas)} palavras com menos de {int(alt_min)} px de altura (ex.: {', '.join(p['txt'] for p in pequenas[:5])})")
    baixas = [p["txt"] for p in corpo if contraste(im, p) < CONTRASTE_MIN]
    if len(baixas) >= 3:
        furos.append(f"contraste baixo entre texto e fundo (menor que {CONTRASTE_MIN}:1): " + ", ".join(baixas[:6]))
    # 4. margens
    borda = int(BORDA * escala)
    na_borda = [p["txt"] for p in corpo if p["x"] < borda or p["y"] < borda or p["x"] + p["w"] > w - borda or p["y"] + p["h"] > h - borda]
    if na_borda:
        furos.append("texto encostado ou cortado na borda: " + ", ".join(na_borda[:6]))
    if canal == "stories":
        fora = [p["txt"] for p in corpo if p["y"] < SEGURA_STORIES or p["y"] + p["h"] > h - SEGURA_STORIES]
        if fora:
            furos.append(f"texto fora da área segura do Stories ({SEGURA_STORIES} px de cima e de baixo): " + ", ".join(fora[:6]))
    return furos, {"tamanho": f"{w}x{h}", "palavras_lidas": len(lidas), "avisos": avisos}


def revisar(t, tmp):
    briefing = t.get("briefing") or ""
    vocab = set(palavras(briefing + " " + (t.get("titulo") or "") + " " + " ".join(t.get("textos_extra") or [])))
    # texto fixo do molde e da marca (assinatura, "link na bio", "loja física e online") vem do contexto aprovado do cliente
    vocab |= set(palavras(t.get("vocab_contexto") or ""))
    livres = set(palavras(" ".join(t.get("livres") or [])))
    pecas = t.get("pecas") or []
    n_feed = sum(1 for p in pecas if p.get("canal") in ("lamina", "feed"))
    furos, det, i_feed = [], [], 0
    for k, p in enumerate(pecas):
        arq = os.path.join(tmp, f"{t['id']}_{k}.img")
        try:
            baixar(p["url"], arq)
        except Exception as e:  # noqa: BLE001
            furos.append(f"peça {k + 1}: não baixei a arte ({e})")
            continue
        canal = p.get("canal") or "feed"
        try:
            lw, lh = Image.open(arq).size
            if canal in ("feed", "lamina") and abs(lw / lh - 9 / 16) < 0.01:
                canal = "stories"      # arte vertical sem canal marcado
        except Exception:  # noqa: BLE001
            pass
        esp = p.get("esperado") or esperado_da_peca(briefing, canal, i_feed if canal in ("lamina", "feed") else 0, n_feed)
        if canal in ("lamina", "feed"):
            i_feed += 1
        fs, d = revisar_peca(arq, canal, esp, vocab, livres)
        nome = f"peça {k + 1} ({'lâmina ' + str(i_feed) if canal == 'lamina' else canal})"
        furos += [f"{nome}: {f}" for f in fs]
        det.append({"peca": k + 1, "canal": canal, **d, "furos": len(fs)})
    return furos, det


def main():
    if not TOKEN:
        log("sem RCA_REELS_TOKEN")
        sys.exit(1)
    fila = pedir("?acao=fila&v=" + VERSAO).get("trabalhos") or []
    log(f"{len(fila)} arte(s) para revisar")
    with tempfile.TemporaryDirectory() as tmp:
        for t in fila:
            try:
                furos, det = revisar(t, tmp)
            except Exception as e:  # noqa: BLE001
                log(f"post {t.get('id')}: erro {e}")
                pedir("?acao=resultado", "POST", json.dumps({"id": t["id"], "erro": str(e)[:300]}).encode())
                continue
            r = pedir("?acao=resultado", "POST", json.dumps({"id": t["id"], "ok": not furos, "furos": furos, "detalhes": det}, ensure_ascii=False).encode("utf-8"))
            log(f"post {t['id']}: {'passou' if not furos else 'reprovou (' + str(len(furos)) + ')'} -> {r.get('mensagem', '')}")
            for f in furos:
                log("   ", f)


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--local":
        # teste local: revisora.py --local trabalho.json
        t = json.load(open(sys.argv[2], encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            f, d = revisar(t, tmp)
        print(json.dumps({"ok": not f, "furos": f, "detalhes": d}, ensure_ascii=False, indent=1))
    else:
        main()
