# Montador de reels da Agência RCA

Monta os reels automáticos do admin da RCA (ffmpeg no GitHub Actions, a cada hora).
Precisa do segredo RCA_REELS_TOKEN (senha do montador, na aba IA do admin).

## Revisora de artes

`revisora.py` (workflow "Revisar artes", a cada 20 min): segunda revisão, sem IA e sem custo,
de toda arte que a Criative manda ao admin. Confere tamanho, texto igual ao briefing (OCR em
português), palavras grudadas, letra pequena, contraste e margens. Passou, a arte segue para a
diretoria; reprovou, volta para a Criative com o motivo. Usa o mesmo segredo RCA_REELS_TOKEN.
Teste local: `python3 revisora.py --local trabalho.json`.
