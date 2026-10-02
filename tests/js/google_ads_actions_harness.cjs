// Runs the Google Ads "Ações" script against a fake Google Ads Scripts runtime and prints what it did.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const scenario = process.argv[2];
let source = fs.readFileSync(path.join(__dirname, '../../aicentralv2/static/cadu_connect/google-ads-actions.js'), 'utf8');
source = source.replace('__CADU_INGEST_URL__', 'https://example.test/gads').replace('__CADU_API_KEY__', 'secret')
  .replace('__CADU_ACCOUNT_IDS__', '[]').replace('__CADU_MAX_BUDGET_PCT__', '30').replace('__CADU_MAX_CPC_PCT__', '30')
  .replace('__CADU_SCRIPT_TITLE__', 'teste');

const changes = [];
function iterator(rows) { let i = 0; return {hasNext: () => i < rows.length, next: () => rows[i++]}; }
function entity(kind, id, state) {
  return {
    id, state,
    isEnabled() { return this.state === 'ENABLED'; }, isPaused() { return this.state === 'PAUSED'; },
    pause() { this.state = 'PAUSED'; changes.push([kind, id, 'pause']); },
    enable() { this.state = 'ENABLED'; changes.push([kind, id, 'enable']); },
  };
}
const negatives = {campaign: [{text: '[grátis]', match: 'EXACT'}]};
function negativeOwner(kind, id) {
  return {
    negativeKeywords: () => ({get: () => iterator((negatives[kind] || []).map(item => ({
      getText: () => item.text, getMatchType: () => item.match,
      remove: () => { negatives[kind] = negatives[kind].filter(other => other !== item); changes.push([kind, id, 'remove_negative', item.text]); },
    })))}),
    createNegativeKeyword: text => changes.push([kind, id, 'add_negative', text]),
    addNegativeKeyword: text => changes.push([kind, id, 'add_negative', text]),
  };
}
const campaign = Object.assign(entity('campaign', 1, 'ENABLED'), negativeOwner('campaign', 1), {
  getBudget: () => ({isExplicitlyShared: () => false, getAmount: () => 100, setAmount: value => changes.push(['budget', 1, value])}),
});
const adGroup = Object.assign(entity('ad_group', 2, 'ENABLED'), negativeOwner('ad_group', 2), {
  newKeywordBuilder: () => ({withText: text => ({build: () => { changes.push(['ad_group', 2, 'add_keyword', text]);
    return {isSuccessful: () => true, getResult: () => ({getId: () => 99}), getErrors: () => []}; }})}),
});
const keyword = entity('keyword', 3, 'PAUSED');
const selector = found => () => ({withIds: () => ({get: () => iterator(found ? [found] : [])})});

const queue = {
  happy: [
    {id: 'a', op: 'campaign.pause', target: {campaign_id: '1'}, expect: {status: 'ENABLED'}, label: 'Pausar C'},
    {id: 'b', op: 'keyword.pause', target: {ad_group_id: '2', keyword_id: '3'}, label: 'Pausar K'},
    {id: 'c', op: 'negative.add', target: {level: 'campaign', campaign_id: '1'}, params: {text: 'vagas', match_type: 'PHRASE'}, label: 'Negativar'},
    {id: 'd', op: 'negative.add', target: {level: 'campaign', campaign_id: '1'}, params: {text: 'grátis', match_type: 'EXACT'}, label: 'Já existe'},
    {id: 'e', op: 'campaign.set_budget', target: {campaign_id: '1'}, params: {amount_micros: 200000000}, expect: {budget_micros: 100000000}, label: 'Dobrar'},
    {id: 'f', op: 'campaign.set_budget', target: {campaign_id: '1'}, params: {amount_micros: 120000000}, expect: {budget_micros: 100000000}, label: '+20%'},
    {id: 'g', op: 'keyword.add', target: {ad_group_id: '2'}, params: {text: 'tênis', match_type: 'EXACT'}, label: 'Adicionar'},
    {id: 'h', op: 'account.delete', target: {}, label: 'Fora da lista'},
    {id: 'i', op: 'campaign.enable', target: {campaign_id: '404'}, label: 'Inexistente'},
    {id: 'j', op: 'negative.remove', target: {level: 'campaign', campaign_id: '1'}, params: {text: 'grátis', match_type: 'EXACT'}, label: 'Remover'},
  ],
};
const commands = scenario === 'limit' ? Array.from({length: 52}, (_, i) => ({id: 'n' + i, op: 'campaign.enable', target: {campaign_id: '1'}}))
  : (queue[scenario] || queue.happy);

const calls = [];
const logs = [];
const sandbox = {
  Logger: {log: line => logs.push(line)},
  Utilities: {sleep: () => {}},
  UrlFetchApp: {fetch: (url, options) => {
    const body = JSON.parse(options.payload);
    calls.push({path: url.replace('https://example.test/gads', ''), body});
    const reply = url.endsWith('/actions/next') ? {commands} : {recorded: 1};
    return {getResponseCode: () => 200, getContentText: () => JSON.stringify(reply)};
  }},
  AdsApp: {
    getExecutionInfo: () => ({isPreview: () => scenario === 'preview'}),
    currentAccount: () => ({getCustomerId: () => '655-001-2913'}),
    campaigns: () => ({withIds: ids => ({get: () => iterator(ids[0] === 1 ? [campaign] : [])})}),
    performanceMaxCampaigns: selector(null),
    adGroups: selector(adGroup),
    keywords: selector(keyword),
    negativeKeywordLists: selector(null),
    search: () => iterator([]),
  },
  Date, JSON, Object, Math, Number, String, isFinite, Array, Error,
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
if (scenario === 'writes_off') vm.runInContext('CADU.allowWrites = false', sandbox);
let thrown = null;
try { vm.runInContext('main()', sandbox); } catch (error) { thrown = error.message; }
console.log(JSON.stringify({calls, changes, logs, thrown}));
