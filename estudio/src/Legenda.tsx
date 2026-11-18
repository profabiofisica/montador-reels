import React from 'react';
import {interpolate, spring, useCurrentFrame, useVideoConfig} from 'remotion';
import {FONTE} from './fontes';
import {Palavra} from './tipos';

/* páginas de até 3 palavras (ou 18 letras), quebrando na pontuação, como as legendas que performam no Reels */
export const paginar = (ps: Palavra[]) => {
	const out: Palavra[][] = [];
	let atual: Palavra[] = [];
	for (const w of ps) {
		const tx = [...atual, w].map((x) => x.p).join(' ');
		if (atual.length && (atual.length >= 3 || tx.length > 18)) {
			out.push(atual);
			atual = [];
		}
		atual.push(w);
		if (/[.!?,;:]$/.test(w.p)) {
			out.push(atual);
			atual = [];
		}
	}
	if (atual.length) out.push(atual);
	return out;
};

export const Legenda: React.FC<{palavras: Palavra[]; destaque: string; y: number; desde?: number}> = ({palavras, destaque, y, desde = 0}) => {
	const frame = useCurrentFrame();
	const {fps, width} = useVideoConfig();
	const t = frame / fps;
	const paginas = React.useMemo(() => paginar(palavras), [palavras]);
	const pg = paginas.find((g, i) => {
		const fim = Math.min(g[g.length - 1].b + 0.25, paginas[i + 1]?.[0].a ?? Infinity);
		return t >= g[0].a - 0.05 && t < fim;
	});
	if (!pg || t < desde) return null;
	const entrada = spring({frame: frame - Math.round(pg[0].a * fps), fps, config: {damping: 14, stiffness: 220, mass: 0.6}});
	const len = pg.map((x) => x.p).join(' ').length;
	const tam = len <= 10 ? 104 : len <= 15 ? 90 : 78;
	return (
		<div
			style={{
				position: 'absolute',
				left: 70,
				right: 150,
				top: y,
				transform: `translateY(-50%) scale(${interpolate(entrada, [0, 1], [0.86, 1])})`,
				opacity: interpolate(entrada, [0, 1], [0, 1]),
				display: 'flex',
				flexWrap: 'wrap',
				justifyContent: 'center',
				columnGap: '0.42em',
				rowGap: 4,
				fontFamily: FONTE,
				fontWeight: 800,
				fontSize: tam,
				lineHeight: 1.08,
				letterSpacing: -1,
				color: '#FFFFFF',
				textTransform: 'uppercase',
				paintOrder: 'stroke fill',
				WebkitTextStroke: '14px rgba(20,10,35,0.92)',
				textShadow: '0 8px 24px rgba(0,0,0,0.45)',
				maxWidth: width - 220,
				marginLeft: 'auto',
				marginRight: 'auto',
			}}
		>
			{pg.map((w, i) => {
				const ativo = t >= w.a - 0.04 && t < (pg[i + 1] ? pg[i + 1].a - 0.04 : w.b + 0.3);
				const s = spring({frame: frame - Math.round(w.a * fps), fps, config: {damping: 12, stiffness: 260}});
				return (
					<span
						key={i}
						style={{
							display: 'inline-block',
							color: ativo ? destaque : '#FFFFFF',
							transform: `translateY(${ativo ? interpolate(s, [0, 1], [-14, -4]) : 0}px)`,
						}}
					>
						{w.p.replace(/[,;:]$/, '')}
					</span>
				);
			})}
		</div>
	);
};
