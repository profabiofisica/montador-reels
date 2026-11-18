// Estúdio RCA: renderiza o Reels (e a capa) a partir do JSON do trabalho.
// uso: node render.mjs trabalho.json saida.mp4 [capa.jpg]
import {bundle} from '@remotion/bundler';
import {renderMedia, renderStill, selectComposition} from '@remotion/renderer';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const aqui = path.dirname(fileURLToPath(import.meta.url));
const [, , entrada, saida, capa] = process.argv;
const props = JSON.parse(fs.readFileSync(entrada, 'utf8'));

const serve = await bundle({entryPoint: path.join(aqui, 'src/index.tsx'), publicDir: path.join(aqui, 'public')});
const comp = await selectComposition({serveUrl: serve, id: 'Reels', inputProps: props});
console.log(`renderizando ${comp.durationInFrames} quadros (${(comp.durationInFrames / comp.fps).toFixed(1)} s)`);
let ult = -10;
await renderMedia({
	composition: comp,
	serveUrl: serve,
	codec: 'h264',
	crf: 18,
	pixelFormat: 'yuv420p',
	audioCodec: 'aac',
	audioBitrate: '192k',
	outputLocation: saida,
	inputProps: props,
	concurrency: Number(process.env.RENDER_CONC || 0) || null,
	onProgress: ({progress}) => {
		const p = Math.floor(progress * 100);
		if (p >= ult + 10) {
			ult = p;
			console.log(`  ${p}%`);
		}
	},
});
if (capa) {
	const st = await selectComposition({serveUrl: serve, id: 'Capa', inputProps: props});
	await renderStill({composition: st, serveUrl: serve, output: capa, inputProps: props, imageFormat: 'jpeg', jpegQuality: 92});
}
console.log('pronto:', saida);
