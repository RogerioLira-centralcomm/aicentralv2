const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const code = fs.readFileSync('aicentralv2/static/js/cadu-theme.js', 'utf8');
function boot({cookie='', force='', host='skills.centralcomm.media', domain='.centralcomm.media', dark=false, blocked=false}={}) {
  const events = {}, writes = [], root = {dataset:{},style:{}};
  const button = {hidden:true, setAttribute(key,value){this[key]=value;}};
  const document = {documentElement:root,currentScript:{dataset:{forceTheme:force,cookieDomain:domain}},
    querySelectorAll:() => [button],addEventListener:(name,fn) => events[name]=fn};
  Object.defineProperty(document,'cookie',{get(){if(blocked)throw Error('blocked');return cookie;},set(value){if(blocked)throw Error('blocked');writes.push(value);cookie=value;}});
  const location = {hostname:host,protocol:'https:'};
  vm.runInNewContext(code,{document,location,window:{location,matchMedia:()=>({matches:dark}),addEventListener:(name,fn)=>events[name]=fn}});
  return {root,button,writes,click:()=>events.click({target:{closest:()=>button}}),events};
}
test('explicit preference overrides system and is applied before DOM ready',()=>{
  const app=boot({cookie:'cadu-theme=light',dark:true});
  assert.equal(app.root.dataset.caduTheme,'light');
  assert.equal(app.writes.length,0);
});
test('theme click writes a secure shared cookie and updates accessible state',()=>{
  const app=boot({cookie:'cadu-theme=light'});app.click();
  assert.equal(app.root.dataset.caduTheme,'dark');
  assert.equal(app.button['aria-pressed'],'true');
  assert.match(app.writes[0],/Domain=centralcomm.media; Secure/);
});
test('Studio stays dark without touching the saved light preference',()=>{
  const app=boot({cookie:'cadu-theme=light',force:'dark'});app.click();app.events.pageshow();
  assert.equal(app.root.dataset.caduTheme,'dark');
  assert.equal(app.button.hidden,true);
  assert.deepEqual(app.writes,[]);
});
test('local preview never sets production cookie domain',()=>{
  const app=boot({host:'127.0.0.1'});app.click();assert.doesNotMatch(app.writes[0],/Domain=/);
});
test('blocked cookies do not break the toggle',()=>{
  const app=boot({blocked:true});app.click();assert.equal(app.root.dataset.caduTheme,'dark');
});
test('invalid preferences use system default',()=>{
  assert.equal(boot({cookie:'cadu-theme=invalid',dark:true}).root.dataset.caduTheme,'dark');
});
