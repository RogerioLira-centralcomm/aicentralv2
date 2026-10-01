// Runs the Google Ads engine v2 against a fake Google Ads Scripts runtime and prints the HTTP calls it made.
const fs = require('fs');
const vm = require('vm');
const path = require('path');

const scenario = process.argv[2];
let source = fs.readFileSync(path.join(__dirname, '../../aicentralv2/static/cadu_connect/google-ads-engine-v2.js'), 'utf8');
source = source.replace('__CADU_INGEST_URL__', 'https://example.test/v2').replace('__CADU_API_KEY__', 'secret').replace('__CADU_ACCOUNT_IDS__', '[]');

const calls = [];
const logs = [];
const day = '2026-10-01';
const metrics = {impressions: '5', clicks: '1', costMicros: '2000000', conversions: 1, conversionsValue: 10};

function iterator(rows) { let i = 0; return {hasNext: () => i < rows.length, next: () => rows[i++]}; }
const failingDataset = scenario === 'dataset_error' ? 'keyword_view' : null;
const manyTerms = scenario === 'chunking';
function search(query) {
  if (failingDataset && query.includes(failingDataset)) throw new Error('Field not valid');
  if (query.includes('FROM landing_page_view')) return iterator([{campaign: {id: 1, name: 'C'},
    landingPageView: {unexpandedFinalUrl: 'https://exemplo.com.br/lp/verao/?utm_campaign=x'}, segments: {date: day}, metrics}]);
  if (query.includes('FROM keyword_view')) return iterator([]);
  if (query.includes('FROM search_term_view')) {
    const n = manyTerms ? 650 : 1;
    return iterator(Array.from({length: n}, (_, i) => ({campaign: {id: 1, name: 'C'}, adGroup: {id: 2, name: 'G'},
      searchTermView: {searchTerm: 'termo ' + i, status: 'NONE'}, segments: {date: day}, metrics})));
  }
  if (query.includes('FROM ad_group_criterion')) return iterator([{campaign: {id: 1, name: 'C'}, adGroup: {id: 2, name: 'G'},
    adGroupCriterion: {keyword: {text: 'grátis', matchType: 'PHRASE'}}}]);
  if (query.includes('FROM campaign_criterion')) return iterator([]);
  if (query.includes('FROM campaign_shared_set')) return iterator([{campaign: {id: 1}, sharedSet: {id: 9}}]);
  if (query.includes('FROM shared_criterion')) return iterator([{sharedSet: {id: 9, name: 'Lista'},
    sharedCriterion: {keyword: {text: 'vagas', matchType: 'BROAD'}}}]);
  if (query.includes('FROM ad_group ')) return iterator([]);
  if (query.includes('campaign_budget')) return iterator([{campaign: {id: 1, name: 'C', status: 'ENABLED', servingStatus: 'SERVING',
    advertisingChannelType: 'SEARCH', biddingStrategyType: 'MAXIMIZE_CONVERSIONS'}, campaignBudget: {amountMicros: '50000000', explicitlyShared: false}}]);
  if (query.includes('segments.device')) return iterator([{campaign: {id: 1, name: 'C'}, segments: {device: 'MOBILE', date: day}, metrics}]);
  if (query.includes('FROM campaign WHERE segments.date')) return iterator([{campaign: {id: 1, name: 'C', status: 'ENABLED', advertisingChannelType: 'SEARCH'}, segments: {date: day}, metrics}]);
  throw new Error('unexpected query ' + query);
}

const status = scenario === 'unauthorized' ? 403 : 200;
const sandbox = {
  Logger: {log: line => logs.push(line)},
  Utilities: {getUuid: () => 'uuid-1', sleep: () => {}, formatDate: (d, tz, fmt) => day},
  UrlFetchApp: {fetch: (url, options) => {
    calls.push(JSON.parse(options.payload));
    return {getResponseCode: () => status, getContentText: () => 'resposta'};
  }},
  AdsApp: {search, currentAccount: () => ({getCustomerId: () => '655-001-2913', getName: () => 'Conta', getCurrencyCode: () => 'BRL', getTimeZone: () => 'America/Sao_Paulo'})},
  Date, JSON, Object, Math, Number, String, isFinite, Array, Error,
};
vm.createContext(sandbox);
vm.runInContext(source, sandbox);
if (scenario === 'dry_run') vm.runInContext('CADU.dryRun = true', sandbox);
let thrown = null;
try { vm.runInContext('main()', sandbox); } catch (error) { thrown = error.message; }
console.log(JSON.stringify({calls, logs, thrown}));
