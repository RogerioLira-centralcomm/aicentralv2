import assert from 'node:assert/strict';
import test from 'node:test';
import {
  DEFAULT_FACILITATOR_PROFILE, FACILITATOR_PROFILES, MAX_FACILITATOR_SUGGESTIONS,
  asksCapabilities, facilitatorSuggestions, loadFacilitatorProfile, normalizeFacilitatorProfile, saveFacilitatorProfile,
} from '../../frontend/cadu-design-system/lib/facilitator.mjs';

test('every profile gets a full list of suggestions inside a project', () => {
  for (const profile of FACILITATOR_PROFILES) {
    const items = facilitatorSuggestions({profile: profile.id, projectName: 'Clínica Sorriso', hasProject: true});
    assert.ok(items.length >= 3 && items.length <= MAX_FACILITATOR_SUGGESTIONS, `${profile.id}: ${items.length}`);
    assert.equal(new Set(items.map(item => item.id)).size, items.length);
  }
});

test('suggestions are plain sentences in the user voice, with the project name', () => {
  const items = facilitatorSuggestions({profile: 'midia', projectName: 'Clínica Sorriso', hasProject: true});
  assert.ok(items.every(item => item.text.endsWith('.') && !/Reports|Planner|Studio|Radar/.test(item.text)));
  assert.ok(items.some(item => item.text.includes('Clínica Sorriso')));
});

test('without a project only suggestions that do not depend on it are offered', () => {
  for (const profile of FACILITATOR_PROFILES) {
    const items = facilitatorSuggestions({profile: profile.id, hasProject: false});
    assert.ok(items.every(item => !/este projeto/.test(item.text)));
  }
  assert.ok(facilitatorSuggestions({profile: 'planejamento', hasProject: false}).length > 0);
});

test('no suggestion produces a broken preposition, with or without a project name', () => {
  for (const profile of FACILITATOR_PROFILES) {
    for (const args of [{projectName: 'Clínica Sorriso', hasProject: true}, {hasProject: true}, {hasProject: false}]) {
      for (const item of facilitatorSuggestions({profile: profile.id, ...args})) {
        assert.ok(!/\b(de|em) (este|esta|a|o) /i.test(item.text), item.text);
      }
    }
  }
});

test('unknown profiles fall back to the default and storage failures are harmless', () => {
  assert.equal(normalizeFacilitatorProfile('zzz'), DEFAULT_FACILITATOR_PROFILE);
  const memory = new Map();
  const storage = {getItem: key => memory.get(key) ?? null, setItem: (key, value) => memory.set(key, value)};
  saveFacilitatorProfile('diretor', storage);
  assert.equal(loadFacilitatorProfile(storage), 'diretor');
  const broken = {getItem() { throw new Error('blocked'); }, setItem() { throw new Error('blocked'); }};
  assert.equal(loadFacilitatorProfile(broken), DEFAULT_FACILITATOR_PROFILE);
  assert.doesNotThrow(() => saveFacilitatorProfile('gestor', broken));
});

test('open "what can you do" questions are detected, ordinary requests are not', () => {
  for (const text of ['E ai vamos construir o que por aqui? o que vc pode me ajudar?', 'O que você pode fazer por mim?', 'como voce pode me ajudar neste projeto', 'Por onde começamos?', 'você pode me ajudar?']) {
    assert.equal(asksCapabilities(text), true, text);
  }
  for (const text of ['Monte um plano de mídia de 30 dias.', 'Analise a campanha de leads da Clínica Sorriso', 'Quanto gastamos ontem?', 'Vamos criar a campanha de março hoje', 'Você pode me ajudar a montar um plano de mídia?', '', undefined]) {
    assert.equal(asksCapabilities(text), false, String(text));
  }
});
