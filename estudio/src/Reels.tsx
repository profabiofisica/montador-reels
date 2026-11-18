import React from 'react';
import {AbsoluteFill, Audio, Img, interpolate, Sequence, spring, useCurrentFrame, useVideoConfig, Easing} from 'remotion';
import {TransitionSeries, linearTiming} from '@remotion/transitions';
import {fade} from '@remotion/transitions/fade';
import {slide} from '@remotion/transitions/slide';
import {wipe} from '@remotion/transitions/wipe';
import {carregaFontes, FONTE} from './fontes';
import {CenaView} from './Cena';
import {Legenda} from './Legenda';
import {Props, XF, duracaoTotal, res} from './tipos';

carregaFontes();

const TRANS = [
	() => slide({direction: 'from-right'}),
	() => fade(),
	() => wipe({direction: 'from-bottom-left'}),
	() => slide({direction: 'from-bottom'}),
	() => fade(),
	() => wipe({direction: 'from-right'}),
];

/* gancho: palavras entram uma a uma, a última em destaque (os 2,4 s que seguram o dedo) */
export const Gancho: React.FC<{texto: string; destaque: string; fixo?: boolean; y?: number}> = ({texto, destaque, fixo, y}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const ps = texto.split(/\s+/).filter(Boolean);
	const sai = fixo ? 1 : interpolate(frame, [2.2 * fps, 2.6 * fps], [1, 0], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'});
	const tam = texto.length <= 24 ? 118 : texto.length <= 40 ? 100 : 84;
	return (
		<div style={{position: 'absolute', left: 80, right: 150, top: y ?? 560, opacity: sai, fontFamily: FONTE, fontWeight: 900, fontSize: tam, lineHeight: 1.02, letterSpacing: -2.5, color: '#fff', paintOrder: 'stroke fill', WebkitTextStroke: '12px rgba(20,10,35,0.9)', textShadow: '0 10px 40px rgba(0,0,0,0.55)'}}>
			{ps.map((w, i) => {
				const s = fixo ? 1 : spring({frame: frame - i * 3, fps, config: {damping: 13, stiffness: 200}});
				const ultimo = i >= ps.length - Math.min(2, Math.ceil(ps.length / 3));
				return (
					<span key={i} style={{display: 'inline-block', marginRight: '0.22em', opacity: s, transform: `translateY(${(1 - s) * 50}px)`, color: ultimo ? destaque : '#fff'}}>
						{w}
					</span>
				);
			})}
		</div>
	);
};

const Logo: React.FC<{src: string; grande?: boolean}> = ({src, grande}) => (
	<Img
		src={src}
		style={
			grande
				? {position: 'absolute', width: 360, left: '50%', top: 1180, transform: 'translateX(-50%)', filter: 'drop-shadow(0 8px 24px rgba(0,0,0,0.4))'}
				: {position: 'absolute', width: 150, left: 70, top: 1920 - 420 - 90, filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.55))'}
		}
	/>
);

const Progresso: React.FC<{cor: string}> = ({cor}) => {
	const frame = useCurrentFrame();
	const {durationInFrames} = useVideoConfig();
	return <div style={{position: 'absolute', top: 0, left: 0, height: 8, width: `${(100 * frame) / durationInFrames}%`, background: cor, opacity: 0.9}} />;
};

const Cta: React.FC<{texto: string; destaque: string}> = ({texto, destaque}) => {
	const frame = useCurrentFrame();
	const {fps} = useVideoConfig();
	const s = spring({frame, fps, config: {damping: 14}});
	return (
		<div style={{position: 'absolute', left: 90, right: 90, top: 760, textAlign: 'center', fontFamily: FONTE, fontWeight: 800, fontSize: 92, lineHeight: 1.06, color: '#fff', opacity: s, transform: `scale(${interpolate(s, [0, 1], [0.9, 1])})`, textShadow: '0 10px 30px rgba(0,0,0,0.5)'}}>
			{texto}
			<div style={{margin: '36px auto 0', width: interpolate(s, [0, 1], [0, 220]), height: 10, background: destaque, borderRadius: 2}} />
		</div>
	);
};

export const Reels: React.FC<Props> = (p0) => {
	const ult = p0.cenas[p0.cenas.length - 1];
	const p: Props = p0.cta && ult?.tipo === 'texto' ? {...p0, cenas: [...p0.cenas.slice(0, -1), {...ult, texto: p0.cta}]} : p0;
	const {fps, durationInFrames} = useVideoConfig();
	const xf = p.transicao ?? XF;
	const xfF = Math.round(xf * fps);
	const destaque = p.cores.destaque || '#EF773B';
	const durs = p.cenas.map((c) => Math.round(c.dur * fps));
	const inicioUltima = durs.slice(0, -1).reduce((s, d) => s + d - xfF, 0);
	const falando = React.useMemo(() => p.legendas.map((w) => [w.a, w.b] as [number, number]), [p.legendas]);
	const volTrilha = (f: number) => {
		const t = f / fps;
		let perto = 9;
		for (const [a, b] of falando) {
			if (t >= a && t <= b) {
				perto = 0;
				break;
			}
			perto = Math.min(perto, Math.abs(t - a), Math.abs(t - b));
		}
		const base = interpolate(perto, [0, 0.35], [0.11, 0.3], {extrapolateRight: 'clamp'});
		const fadeIn = interpolate(f, [0, 0.8 * fps], [0, 1], {extrapolateRight: 'clamp'});
		const fadeOut = interpolate(f, [durationInFrames - 1.4 * fps, durationInFrames], [1, 0], {extrapolateLeft: 'clamp'});
		return base * fadeIn * fadeOut;
	};
	let cursor = 0;
	return (
		<AbsoluteFill style={{backgroundColor: '#100818'}}>
			<TransitionSeries>
				{p.cenas.map((c, i) => {
					const el = (
						<TransitionSeries.Sequence key={'s' + i} durationInFrames={durs[i]}>
							<CenaView c={c} i={i} p={p} durF={durs[i]} />
						</TransitionSeries.Sequence>
					);
					if (i === p.cenas.length - 1) return el;
					return [
						el,
						<TransitionSeries.Transition key={'t' + i} presentation={TRANS[i % TRANS.length]() as never} timing={linearTiming({durationInFrames: xfF})} />,
					];
				})}
			</TransitionSeries>
			{p.gancho ? <Gancho texto={p.gancho} destaque={destaque} /> : null}
			<Legenda palavras={p.legendas} destaque={destaque} y={1190} desde={p.gancho ? 2.6 : 0} />
			{p.cta && p.cenas[p.cenas.length - 1].tipo !== 'texto' ? (
				<Sequence from={inicioUltima + Math.round(0.3 * fps)}>
					<Cta texto={p.cta} destaque={destaque} />
				</Sequence>
			) : null}
			{p.logo ? (
				<>
					<Sequence durationInFrames={inicioUltima + Math.round(0.2 * fps)}>
						<Logo src={res(p.logo)!} />
					</Sequence>
					<Sequence from={inicioUltima + Math.round(0.2 * fps)}>
						<Logo src={res(p.logo)!} grande />
					</Sequence>
				</>
			) : null}
			<Progresso cor={destaque} />
			{p.voz ? (
				<Sequence from={Math.round(0.25 * fps)}>
					<Audio src={res(p.voz)!} volume={1} />
				</Sequence>
			) : null}
			{p.trilha ? <Audio src={res(p.trilha)!} volume={volTrilha} loop /> : null}
			{p.sfx
				? durs.slice(0, -1).map((d, i) => {
						cursor += d - xfF;
						return (
							<Sequence key={'x' + i} from={Math.max(0, cursor - Math.round(0.12 * fps))} durationInFrames={Math.round(0.8 * fps)}>
								<Audio src={res(p.sfx)!} volume={0.28} />
							</Sequence>
						);
					})
				: null}
		</AbsoluteFill>
	);
};

/* capa: gancho dentro do corte 3:4 da grade (1080x1440 no centro), sobre o quadro da primeira cena */
export const Capa: React.FC<Props> = (p) => {
	const destaque = p.cores.destaque || '#EF773B';
	const c0 = p.cenas.find((c) => c.tipo === 'imagem') || p.cenas[0];
	return (
		<AbsoluteFill style={{backgroundColor: p.cores.cor1}}>
			{c0?.tipo === 'imagem' && c0.src ? <Img src={res(c0.src)!} style={{width: '100%', height: '100%', objectFit: 'cover', transform: 'scale(1.08)'}} /> : null}
			<AbsoluteFill style={{background: 'linear-gradient(180deg, rgba(16,8,24,0.15) 0%, rgba(16,8,24,0.55) 60%, rgba(16,8,24,0.75) 100%)'}} />
			{p.gancho ? <Gancho texto={p.gancho} destaque={destaque} fixo y={700} /> : null}
			{p.logo ? <Img src={res(p.logo)!} style={{position: 'absolute', width: 170, left: 80, top: 1530}} /> : null}
		</AbsoluteFill>
	);
};

export {duracaoTotal};
