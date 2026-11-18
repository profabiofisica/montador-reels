import React from 'react';
import {AbsoluteFill, Img, interpolate, OffthreadVideo, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {FONTE} from './fontes';
import {Cena as TCena, Props, res} from './tipos';

/* movimento de câmera por cena (biblioteca nomeada; o roteiro escolhe, senão alterna) */
const CAMERAS = ['empurra', 'afasta', 'passa_esq', 'passa_dir', 'sobe', 'orbita'] as const;
const mov = (nome: string, p: number) => {
	const e = Easing.bezier(0.33, 0, 0.2, 1)(p);
	switch (nome) {
		case 'afasta':
			return {s: interpolate(e, [0, 1], [1.2, 1.04]), x: 0, y: 0, r: 0};
		case 'passa_esq':
			return {s: 1.14, x: interpolate(e, [0, 1], [50, -50]), y: 0, r: 0};
		case 'passa_dir':
			return {s: 1.14, x: interpolate(e, [0, 1], [-50, 50]), y: 0, r: 0};
		case 'sobe':
			return {s: 1.14, x: 0, y: interpolate(e, [0, 1], [60, -60]), r: 0};
		case 'orbita':
			return {s: interpolate(e, [0, 1], [1.12, 1.2]), x: interpolate(e, [0, 1], [-30, 30]), y: 0, r: interpolate(e, [0, 1], [-1.2, 1.2])};
		default:
			return {s: interpolate(e, [0, 1], [1.04, 1.2]), x: 0, y: 0, r: 0};
	}
};

export const CenaView: React.FC<{c: TCena; i: number; p: Props; durF: number}> = ({c, i, p, durF}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const prog = Math.min(1, frame / Math.max(1, durF));
	const cam = c.camera && (CAMERAS as readonly string[]).includes(c.camera) ? c.camera : CAMERAS[i % CAMERAS.length];
	const m = mov(cam, prog);
	const filtro = 'contrast(1.05) saturate(1.08)';
	if (c.tipo === 'texto') {
		const ent = interpolate(frame, [0, 0.5 * fps], [0, 1], {extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic)});
		return (
			<AbsoluteFill
				style={{
					background: `radial-gradient(120% 90% at ${30 + 40 * prog}% 20%, ${p.cores.cor2} 0%, ${p.cores.cor1} 55%, ${p.cores.cor3} 100%)`,
					justifyContent: 'center',
					alignItems: 'center',
					padding: '0 110px',
				}}
			>
				<div
					style={{
						fontFamily: FONTE,
						fontWeight: 800,
						fontSize: 108,
						lineHeight: 1.05,
						letterSpacing: -2,
						color: p.cores.texto || '#FFFFFF',
						textAlign: 'center',
						opacity: ent,
						transform: `translateY(${(1 - ent) * 40}px)`,
					}}
				>
					{c.texto}
				</div>
			</AbsoluteFill>
		);
	}
	/* cena longa ganha um punch-in no meio (outro enquadramento do mesmo plano): mais um corte sem gastar geração */
	const corteMeio = durF > 2.4 * fps ? Math.round(durF * 0.55) : Infinity;
	const depois = frame >= corteMeio;
	const soco = depois ? {s: 1.17, ox: i % 2 ? '38%' : '62%', oy: '40%'} : {s: 1, ox: '50%', oy: '50%'};
	const t = `translate(${m.x}px, ${m.y}px) scale(${m.s * soco.s}) rotate(${m.r}deg)`;
	return (
		<AbsoluteFill style={{backgroundColor: '#100818', overflow: 'hidden'}}>
			{c.tipo === 'video' && c.src ? (
				<OffthreadVideo
					src={res(c.src)!}
					startFrom={Math.round((c.inicio || 0) * fps)}
					volume={p.voz ? 0.18 : 0.35}
					style={{width: '100%', height: '100%', objectFit: 'cover', transform: `scale(${interpolate(prog, [0, 1], [1.0, 1.06]) * soco.s})`, transformOrigin: `${soco.ox} ${soco.oy}`, filter: filtro}}
				/>
			) : c.src ? (
				<Img src={res(c.src)!} style={{width: '100%', height: '100%', objectFit: 'cover', transform: t, transformOrigin: `${soco.ox} ${soco.oy}`, filter: filtro}} />
			) : null}
			{/* vinheta e escurecimento suave onde entra a legenda */}
			<AbsoluteFill
				style={{
					background:
						'radial-gradient(130% 90% at 50% 45%, rgba(0,0,0,0) 55%, rgba(0,0,0,0.38) 100%), linear-gradient(180deg, rgba(0,0,0,0.25) 0%, rgba(0,0,0,0) 18%, rgba(0,0,0,0) 48%, rgba(0,0,0,0.42) 100%)',
				}}
			/>
		</AbsoluteFill>
	);
};
