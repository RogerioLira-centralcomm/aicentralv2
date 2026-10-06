import test from 'node:test';
import assert from 'node:assert/strict';
import { coherenceIssues } from '../../aicentralv2/static/js/cadu-video/coherence.js';

const img = '/x.png';
const scene = (id, extra = {}) => ({ id, image_url: img, thumb_url: img, ...extra });
const run = (scenes, beats, extra = {}) => coherenceIssues({ scenes, beatFor: (id) => beats[id] || {}, duration: 12, ...extra });
const codes = (issues) => issues.map((issue) => issue.code);
const ok = { s1: { purpose: 'hook', visual: 'Abertura', spoken: 'Olá' }, s2: { purpose: 'beat', visual: 'Meio', spoken: 'Oferta boa' }, s3: { purpose: 'end', visual: 'Fecho', spoken: 'Venha' } };

test('sequência íntegra não tem problemas', () => {
  assert.deepEqual(run([scene('s1'), scene('s2'), scene('s3')], ok), []);
});

test('imagem indisponível bloqueia e aponta a cena', () => {
  const issues = run([scene('s1'), scene('s2', { broken: true }), scene('s3', { image_url: '', thumb_url: '' })], ok);
  const errors = issues.filter((issue) => issue.level === 'error');
  assert.deepEqual(errors.map((issue) => issue.sceneId), ['s2', 's3']);
  assert.equal(issues[0].level, 'error'); // erros vêm primeiro
});

test('cena sem visual nem movimento, visual repetido e rascunho pendente viram aviso', () => {
  const beats = { s1: { purpose: 'hook', visual: 'Mesmo plano' }, s2: { purpose: 'beat', visual: ' mesmo   PLANO ' }, s3: { purpose: 'end' } };
  const issues = run([scene('s1'), scene('s2'), scene('s3')], beats, { draftBeats: [{ id: 'd1' }, { id: 'd2' }] });
  assert.deepEqual(codes(issues).sort(), ['draft-pending', 'duplicate-visual', 'empty-beat'].sort());
  assert.match(issues.find((issue) => issue.code === 'draft-pending').message, /2 cenas do rascunho ainda estão sem imagem e não entram/);
  assert.equal(issues.find((issue) => issue.code === 'duplicate-visual').sceneId, 's2');
});

test('proporções diferentes entre imagens avisam; iguais não', () => {
  const scenes = [scene('s1'), scene('s2'), scene('s3')];
  assert.deepEqual(codes(run(scenes, ok, { aspects: { s1: '16:9', s2: '16:9', s3: '16:9' } })), []);
  const mixed = run(scenes, ok, { aspects: { s1: '16:9', s2: '9:16', s3: '' } });
  assert.deepEqual(codes(mixed), ['aspect-mix']);
  assert.match(mixed[0].message, /16:9, 9:16/);
});

test('fala que não cabe na cena e na duração total', () => {
  const longText = Array.from({ length: 40 }, () => "palavra").join(' ');
  const beats = { ...ok, s2: { ...ok.s2, spoken: longText } };
  const issues = run([scene('s1'), scene('s2'), scene('s3')], beats, { duration: 8 });
  assert.ok(codes(issues).includes('speech-scene'));
  assert.ok(codes(issues).includes('speech-total'));
  assert.equal(issues.find((issue) => issue.code === 'speech-scene').sceneId, 's2');
});

test('muitas cenas para pouca duração', () => {
  const scenes = Array.from({ length: 8 }, (_, i) => scene('s' + i));
  const beats = Object.fromEntries(scenes.map((s, i) => [s.id, { purpose: i === 0 ? 'hook' : i === 7 ? 'end' : 'beat', visual: 'Plano ' + i }]));
  assert.ok(codes(run(scenes, beats, { duration: 8 })).includes('too-short'));
});

test('arco: abertura e fechamento', () => {
  const beats = { s1: { purpose: 'beat', visual: 'a' }, s2: { purpose: 'beat', visual: 'b' }, s3: { purpose: 'beat', visual: 'c' } };
  assert.deepEqual(codes(run([scene('s1'), scene('s2'), scene('s3')], beats)).sort(), ['arc-end', 'arc-start']);
});

test('uma imagem só valida apenas a imagem escolhida', () => {
  assert.deepEqual(coherenceIssues({ scenes: [scene('a', { broken: true }), scene('b')], mode: 'single_image', selectedId: 'b' }), []);
  assert.equal(coherenceIssues({ scenes: [scene('a', { broken: true })], mode: 'single_image', selectedId: 'a' })[0].level, 'error');
});
