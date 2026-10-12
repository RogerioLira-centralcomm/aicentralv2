import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..');
const load = name => import('data:text/javascript;base64,' + Buffer.from(fs.readFileSync(path.join(root, 'frontend/reports-v1', name), 'utf8')).toString('base64'));
const {applyDrag, findFreeSlot, edgePorts, FLOW_COORD_LIMIT} = await load('flowDrag.js');
const {funnelEdges} = await load('flowStages.js');

// Dragging is spatial only: the stage stays, edges stay, and the move keeps the grid.
const config = {nodes: [{id: 'a', type: 'page', stage: 'entry', x: 80, y: 100}, {id: 'b', type: 'form', stage: 'intent', x: 720, y: 100}], edges: [{id: 'ab', from: 'a', to: 'b', origin: 'manual'}]};
const dragged = applyDrag(config, new Map([['b', {x: 13, y: 207}]]));
const b = dragged.nodes.find(node => node.id === 'b');
assert.equal(b.stage, 'intent');
assert.deepEqual([b.x, b.y], [20, 200]);
assert.equal(dragged.edges, config.edges);
assert.equal(dragged.nodes[0], config.nodes[0], 'untouched cards keep their identity');

// The board has no wall at zero: negative positions are kept.
const left = applyDrag(config, new Map([['a', {x: -400, y: -220}]])).nodes[0];
assert.deepEqual([left.x, left.y], [-400, -220]);

// A selection pushed past the sanity limit moves back as one block, preserving spacing.
const far = applyDrag(config, new Map([['a', {x: FLOW_COORD_LIMIT + 100, y: 0}], ['b', {x: FLOW_COORD_LIMIT + 740, y: 0}]]));
assert.equal(far.nodes[1].x - far.nodes[0].x, 640);
assert(far.nodes[1].x <= FLOW_COORD_LIMIT);

// Members of a frame move with it.
const grouped = {groups: [{id: 'g', bounds: {x: 40, y: 40, width: 400, height: 300}, memberIds: ['a']}], nodes: [{id: 'a', type: 'page', x: 80, y: 100, groupId: 'g'}], edges: []};
const moved = applyDrag(grouped, new Map([['g', {x: 240, y: 40}]]));
assert.equal(moved.groups[0].bounds.x, 240);
assert.equal(moved.nodes[0].x, 280);

// Without grid snapping (Alt), the drop point is exact.
assert.equal(applyDrag(config, new Map([['a', {x: 13, y: 7}]]), {snap: false}).nodes[0].x, 13);

// New cards never land on top of another one.
const slot = findFreeSlot(config.nodes, {x: 80, y: 100});
assert(!config.nodes.some(node => Math.abs(node.x - slot.x) < 260 && Math.abs(node.y - slot.y) < 200));
assert.deepEqual(findFreeSlot([], {x: 93, y: 41}), {x: 100, y: 40});

// Connection sides follow the cards; explicit ports win.
assert.deepEqual(edgePorts({}, {x: 0, y: 0}, {x: 400, y: 0}), {sourceHandle: 'right-out', targetHandle: 'left-in'});
assert.deepEqual(edgePorts({}, {x: 0, y: 0}, {x: 20, y: 300}), {sourceHandle: 'bottom-out', targetHandle: 'top-in'});
assert.deepEqual(edgePorts({}, {x: 600, y: 0}, {x: 0, y: 0}), {sourceHandle: 'bottom-out', targetHandle: 'bottom-in'});
assert.deepEqual(edgePorts({from_port: 'bottom-out', to_port: 'left-in'}, {x: 0, y: 0}, {x: 400, y: 0}), {sourceHandle: 'bottom-out', targetHandle: 'left-in'});

// A connection drawn backwards by the person is never hidden; inferred back-links still wait for "Mostrar retornos".
const back = {nodes: [{id: 'a', stage: 'entry'}, {id: 'b', stage: 'intent'}], edges: [{id: 'manual', from: 'b', to: 'a', origin: 'manual'}, {id: 'inferred', from: 'b', to: 'a'}]};
assert.deepEqual(funnelEdges(back).map(edge => edge.id), ['manual']);
assert.equal(funnelEdges(back, {returns: true}).length, 2);

console.log('Fluxos: arraste espacial, mesa sem parede, vagas livres, lados das conexões e retornos desenhados aprovados');
