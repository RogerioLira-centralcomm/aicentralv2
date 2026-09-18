const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('aicentralv2/static/js/cadu-theme.js', 'utf8');

function boot({mode='light', stored='', blocked=false, defaultTheme='light'}={}) {
  const events = {}, writes = [], root = {dataset:{},style:{}};
  const button = {hidden:true, setAttribute(key,value){this[key]=value;}};
  const storage = {
    getItem(){if(blocked)throw Error('blocked');return stored || null;},
    setItem(key,value){if(blocked)throw Error('blocked');writes.push([key,value]);stored=value;},
  };
  const document = {
    documentElement:root,
    currentScript:{dataset:{themeMode:mode,themeScope:'workspace-conversations',themeDefault:defaultTheme}},
    querySelectorAll:() => [button],
    addEventListener:(name,fn) => events[name]=fn,
  };
  const window = {localStorage:storage,addEventListener:(name,fn)=>events[name]=fn};
  vm.runInNewContext(code,{document,window});
  return {root,button,writes,click:()=>events.click({target:{closest:()=>button}}),events};
}

test('regular Cadu environments stay light and hide the theme control',()=>{
  const app=boot({mode:'light',stored:'dark'});
  assert.equal(app.root.dataset.caduTheme,'light');
  assert.equal(app.button.hidden,true);
});

test('Workspace Conversations starts dark and exposes the preference control',()=>{
  const app=boot({mode:'preference',defaultTheme:'dark'});
  assert.equal(app.root.dataset.caduTheme,'dark');
  assert.equal(app.button.hidden,false);
  assert.equal(app.button['aria-pressed'],'true');
});

test('conversation preference is isolated and persisted in local storage',()=>{
  const app=boot({mode:'preference'});app.click();
  assert.equal(app.root.dataset.caduTheme,'dark');
  assert.equal(app.button['aria-pressed'],'true');
  assert.deepEqual(app.writes[0],['cadu-theme:workspace-conversations','dark']);
});

test('saved conversation preference is restored on entry and pageshow',()=>{
  const app=boot({mode:'preference',stored:'dark'});
  assert.equal(app.root.dataset.caduTheme,'dark');
  app.click();
  app.events.pageshow();
  assert.equal(app.root.dataset.caduTheme,'light');
});

test('Studio stays dark and does not expose or write a preference',()=>{
  const app=boot({mode:'dark',stored:'light'});app.click();app.events.pageshow();
  assert.equal(app.root.dataset.caduTheme,'dark');
  assert.equal(app.button.hidden,true);
  assert.deepEqual(app.writes,[]);
});

test('blocked local storage does not break the conversation toggle',()=>{
  const app=boot({mode:'preference',blocked:true});app.click();
  assert.equal(app.root.dataset.caduTheme,'dark');
});
