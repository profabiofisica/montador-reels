#!/usr/bin/env python3
"""Trilha original feita na hora (22/10/2026).

Quando a pasta de trilhas do Drive não tem música, o montador compõe uma
trilha curta no clima do reels: acordes, baixo, arpejo e bateria leve.
Cada reels sai com uma música diferente (tom, progressão e padrão sorteados).
Só usa numpy. Gera WAV estéreo 44,1 kHz.
"""
import random
import wave

import numpy as np

SR = 44100

CLIMAS = {
    #            bpm        bateria   arpejo  brilho
    "animado":   ((112, 122), "cheia",  True,  0.55),
    "inspirador": ((92, 102), "leve",   True,  0.42),
    "calmo":     ((78, 88),   "nenhuma", True, 0.30),
    "intenso":   ((124, 132), "cheia",  False, 0.65),
}

MAIOR = [0, 2, 4, 5, 7, 9, 11]
MENOR = [0, 2, 3, 5, 7, 8, 10]
PROG_MAIOR = [[0, 4, 5, 3], [0, 5, 3, 4], [3, 0, 4, 5], [0, 3, 5, 4]]
PROG_MENOR = [[0, 5, 2, 6], [0, 3, 5, 4], [0, 6, 5, 4]]


def hz(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)




def lp_rapido(x, corte):
    """passa-baixa por FFT (rápido para sinais longos)."""
    n = len(x)
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    f *= 1 / (1 + (fr / corte) ** 4)
    return np.fft.irfft(f, n)


def hp_rapido(x, corte):
    n = len(x)
    f = np.fft.rfft(x)
    fr = np.fft.rfftfreq(n, 1 / SR)
    f *= 1 - 1 / (1 + (fr / corte) ** 4)
    return np.fft.irfft(f, n)


def serra(freq, t, harm=14):
    out = np.zeros_like(t)
    for k in range(1, harm + 1):
        if freq * k > 12000:
            break
        out += np.sin(2 * np.pi * freq * k * t) / k
    return out * 0.6


def env_adsr(n, a, d, s, r):
    a, d, r = int(a * SR), int(d * SR), int(r * SR)
    e = np.full(n, s, dtype=np.float64)
    a = min(a, n)
    if a:
        e[:a] = np.linspace(0, 1, a, endpoint=False)
    d2 = min(d, max(0, n - a))
    if d2:
        e[a:a + d2] = np.linspace(1, s, d2, endpoint=False)
    r2 = min(r, n)
    if r2:
        e[n - r2:] *= np.linspace(1, 0, r2)
    return e


def kick(n):
    t = np.arange(n) / SR
    f = 45 + 85 * np.exp(-t * 28)
    fase = 2 * np.pi * np.cumsum(f) / SR
    return np.sin(fase) * np.exp(-t * 7.5) * 0.95


def clap(n, rng):
    t = np.arange(n) / SR
    ruido = rng.standard_normal(n)
    base = hp_rapido(ruido, 1000)
    corpo = base * np.exp(-t * 16)
    for atraso in (0.009, 0.018):
        k = int(atraso * SR)
        corpo[k:] += base[:n - k] * np.exp(-t[:n - k] * 22) * 0.5
    return corpo * 0.33


def hat(n, rng, aberto=False):
    t = np.arange(n) / SR
    return hp_rapido(rng.standard_normal(n), 7000) * np.exp(-t * (14 if aberto else 55)) * 0.16


def compor(duracao, clima="inspirador", semente=None):
    rng = np.random.default_rng(semente)
    random.seed(semente)
    (b0, b1), bateria, arpejo, brilho = CLIMAS.get(clima, CLIMAS["inspirador"])
    bpm = random.randint(b0, b1)
    menor = clima == "intenso" or random.random() < 0.35
    escala = MENOR if menor else MAIOR
    prog = random.choice(PROG_MENOR if menor else PROG_MAIOR)
    raiz = random.choice([57, 58, 60, 62, 64, 65]) - 12
    batida = 60.0 / bpm
    compasso = batida * 4
    n = int((duracao + 1.0) * SR)
    t_all = np.arange(n) / SR
    pad, baixo, arp, bat = np.zeros(n), np.zeros(n), np.zeros(n), np.zeros(n)

    def grau(g, oit=0):
        return raiz + 12 * oit + escala[g % 7] + 12 * (g // 7)

    n_comp = int(np.ceil(duracao / compasso)) + 1
    for c in range(n_comp):
        g = prog[c % len(prog)]
        i0 = int(c * compasso * SR)
        if i0 >= n:
            break
        tam = min(int(compasso * SR) + int(0.25 * SR), n - i0)
        t = np.arange(tam) / SR
        acorde = [grau(g, 1), grau(g + 2, 1), grau(g + 4, 1), grau(g, 2)]
        som = np.zeros(tam)
        for nota in acorde:
            f = hz(nota)
            for det in (-0.12, 0.0, 0.11):
                som += serra(f * 2 ** (det / 12), t + random.random(), harm=10)
        som *= env_adsr(tam, 0.35, 0.4, 0.75, 0.45) * 0.07
        pad[i0:i0 + tam] += som
        for b in range(8):
            j0 = i0 + int(b * batida / 2 * SR)
            if j0 >= n:
                break
            tb = min(int(batida / 2 * SR), n - j0)
            tt = np.arange(tb) / SR
            f = hz(grau(g, -1))
            vel = 1.0 if b % 2 == 0 else 0.6
            nota = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)) * env_adsr(tb, 0.005, 0.08, 0.6, 0.04)
            baixo[j0:j0 + tb] += nota * 0.32 * vel
        if arpejo:
            notas = [grau(g, 2), grau(g + 2, 2), grau(g + 4, 2), grau(g + 2, 2) + 12]
            passo = batida / (4 if clima in ("animado", "intenso") else 2)
            k = 0
            while k * passo < compasso:
                j0 = i0 + int(k * passo * SR)
                if j0 >= n:
                    break
                tb = min(int(0.32 * SR), n - j0)
                tt = np.arange(tb) / SR
                f = hz(notas[k % len(notas)])
                pl = (np.sin(2 * np.pi * f * tt) * 0.7 + np.sin(4 * np.pi * f * tt) * 0.12) * np.exp(-tt * 13)
                arp[j0:j0 + tb] += pl * 0.12 * (0.8 + 0.4 * random.random())
                k += 1
    if bateria != "nenhuma":
        kn, cn, hn = kick(int(0.45 * SR)), clap(int(0.3 * SR), rng), int(0.12 * SR)
        for b in range(int(duracao / batida) + 2):
            j0 = int(b * batida * SR)
            if j0 >= n:
                break
            if b >= 4 and (bateria == "cheia" or b % 2 == 0):
                kk = kn[:n - j0]
                bat[j0:j0 + len(kk)] += kk * (1.0 if bateria == "cheia" else 0.7)
            if b >= 4 and b % 4 in (1, 3):
                cc = cn[:n - j0] * (1.0 if bateria == "cheia" else 0.55)
                bat[j0:j0 + len(cc)] += cc
            for h in range(2):
                jh = j0 + int(h * batida / 2 * SR)
                if jh >= n:
                    break
                hh = hat(hn, rng, aberto=(h == 1 and b % 2 == 1))[:n - jh]
                bat[jh:jh + len(hh)] += hh * (0.7 if h == 0 else 1.0)
    pad = lp_rapido(pad, 900 + 2600 * brilho)
    pump = np.ones(n)
    if bateria != "nenhuma":
        fase = (t_all % batida) / batida
        pump = 0.55 + 0.45 * np.clip(fase * 3.2, 0, 1)
        pump[: int(4 * batida * SR)] = 1.0
    arp = lp_rapido(arp, 5200)
    eco = np.zeros(n)
    atraso = int(batida * 0.75 * SR)
    eco[atraso:] = arp[:-atraso] * 0.35
    mix = pad * pump + baixo * np.sqrt(pump) + arp + eco + bat * 0.9
    ent = np.clip(t_all / 1.2, 0, 1)
    sai = np.clip((duracao + 0.6 - t_all) / 1.8, 0, 1)
    mix *= ent * sai
    mix = np.tanh(mix * 1.6) / np.tanh(1.6)
    mix /= max(1e-6, np.max(np.abs(mix))) / 0.85
    esq = mix + 0.18 * (arp - eco)
    dir_ = mix - 0.18 * (arp - eco)
    st = np.stack([esq, dir_], axis=1)
    st /= max(1e-6, np.max(np.abs(st))) / 0.9
    return st[: int(duracao * SR)]


def salvar(destino, duracao, clima="inspirador", semente=None):
    st = compor(duracao, clima, semente)
    pcm = (np.clip(st, -1, 1) * 32767).astype("<i2")
    with wave.open(destino, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    return destino


if __name__ == "__main__":
    import sys
    salvar(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 25, sys.argv[3] if len(sys.argv) > 3 else "inspirador")
