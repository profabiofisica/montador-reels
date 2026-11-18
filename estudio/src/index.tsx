import React from 'react';
import {Composition, registerRoot, Still} from 'remotion';
import {Capa, Reels} from './Reels';
import {Props, duracaoTotal} from './tipos';

const exemplo: Props = {
	w: 1080,
	h: 1920,
	fps: 30,
	cores: {cor1: '#542E81', cor2: '#A52E78', cor3: '#2A1748', destaque: '#EF773B'},
	cenas: [{tipo: 'texto', dur: 3, texto: 'Exemplo'}],
	legendas: [],
};

const Raiz: React.FC = () => (
	<>
		<Composition
			id="Reels"
			component={Reels as never}
			width={1080}
			height={1920}
			fps={30}
			durationInFrames={90}
			defaultProps={exemplo}
			calculateMetadata={({props}) => {
				const p = props as unknown as Props;
				return {durationInFrames: Math.round(duracaoTotal(p) * p.fps), fps: p.fps, width: p.w, height: p.h};
			}}
		/>
		<Still id="Capa" component={Capa as never} width={1080} height={1920} defaultProps={exemplo} />
	</>
);

registerRoot(Raiz);
