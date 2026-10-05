// Beats seguem a cena pelo ID: reordenar, remover e trocar a imagem não podem mover falas de lugar.
import assert from 'node:assert/strict';

globalThis.window = globalThis;
globalThis.document = { getElementById: () => null, querySelector: () => null, addEventListener() {} };
const { state, alignBeatsToScenes, beatFor } = await import('../../aicentralv2/static/js/cadu-video/state.js');

const [a, b, c] = [{ id: 'a', name: 'A' }, { id: 'b', name: 'B' }, { id: 'c', name: 'C' }];
state.script = { beats: [{ id: 'a', spoken: 'fala A' }, { id: 'b', spoken: 'fala B' }, { id: 'c', spoken: 'fala C' }] };

state.scenes = [c, a, b];
alignBeatsToScenes();
assert.deepEqual(state.script.beats.map((beat) => beat.spoken), ['fala C', 'fala A', 'fala B']);

state.scenes = state.scenes.filter((scene) => scene.id !== 'a');
alignBeatsToScenes();
assert.equal(beatFor('b').spoken, 'fala B');
assert.equal(state.script.beats.length, 2);

console.log('PASS beats acompanham a cena por ID');
