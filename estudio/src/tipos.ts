export type Palavra = {p: string; a: number; b: number};
export type Cena = {
	tipo: 'video' | 'imagem' | 'texto';
	src?: string;
	inicio?: number;
	dur: number;
	texto?: string;
	camera?: string;
};
export type Props = {
	w: number;
	h: number;
	fps: number;
	cores: {cor1: string; cor2: string; cor3: string; destaque?: string; texto?: string};
	logo?: string;
	cenas: Cena[];
	voz?: string;
	trilha?: string;
	legendas: Palavra[];
	gancho?: string;
	cta?: string;
	transicao?: number;
	sfx?: string;
};

export const XF = 0.4; // segundos de transição

export const duracaoTotal = (p: Props) => {
	const xf = p.transicao ?? XF;
	const soma = p.cenas.reduce((s, c) => s + c.dur, 0);
	return Math.max(1, soma - xf * Math.max(0, p.cenas.length - 1));
};

import {staticFile} from 'remotion';
/* arquivo baixado para public/ vem como "local:caminho"; endereço http passa direto */
export const res = (s?: string) => (s && s.startsWith('local:') ? staticFile(s.slice(6)) : s);
