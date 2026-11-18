import {continueRender, delayRender, staticFile} from 'remotion';

const pesos: Array<[number, string]> = [
	[500, 'poppins-latin-500-normal.woff2'],
	[700, 'poppins-latin-700-normal.woff2'],
	[800, 'poppins-latin-800-normal.woff2'],
	[900, 'poppins-latin-900-normal.woff2'],
];

let carregado = false;
export const carregaFontes = () => {
	if (carregado || typeof document === 'undefined') return;
	carregado = true;
	const h = delayRender('fontes Poppins');
	Promise.all(
		pesos.map(([w, f]) => {
			const ff = new FontFace('Poppins', `url(${staticFile('fontes/' + f)}) format('woff2')`, {weight: String(w)});
			return ff.load().then((x) => {
				document.fonts.add(x);
			});
		})
	)
		.then(() => continueRender(h))
		.catch(() => continueRender(h));
};

export const FONTE = "Poppins, 'DejaVu Sans', sans-serif";
