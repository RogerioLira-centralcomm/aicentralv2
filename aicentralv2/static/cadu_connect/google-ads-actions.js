/**
 * Cadu Reports · Google Ads · Ações
 * __CADU_SCRIPT_TITLE__
 *
 * Instale em Ferramentas > Scripts na conta Google Ads ou na MCC e agende DE HORA EM HORA.
 * Este script aplica na conta as mudanças APROVADAS no Reports (pausar, ativar, negativar, adicionar palavra-chave,
 * ajustar lance e orçamento). Ele não lê relatórios: isso é trabalho do script de Leitura, instalado à parte.
 *
 * Travas que valem aqui, no código colado, independentemente do que o Reports pedir:
 *   - allowWrites:  false desliga toda escrita (o script só informa o que faria).
 *   - allowedOps:   só estas operações são aceitas; qualquer outra é recusada.
 *   - limits:       teto de mudanças por execução e de variação de lance e orçamento.
 *   - Cada comando traz o estado esperado; se a conta mudou desde a aprovação, ele é ignorado e o estado real volta.
 *   - Em "Visualizar" (prévia do Google Ads) nada é gravado e os comandos continuam na fila.
 */
var CADU = {
  endpoint: '__CADU_INGEST_URL__',
  apiKey: '__CADU_API_KEY__',
  accountIds: __CADU_ACCOUNT_IDS__, // Obrigatório em MCC; emitido para este cliente.

  engineVersion: '1.0.0',
  allowWrites: true,
  limits: {
    maxChangesPerRun: 50,
    maxBudgetChangePct: __CADU_MAX_BUDGET_PCT__,  // Variação máxima do orçamento diário por comando.
    maxCpcChangePct: __CADU_MAX_CPC_PCT__         // Variação máxima do CPC máximo por comando.
  },
  allowedOps: ['campaign.pause', 'campaign.enable', 'ad_group.pause', 'ad_group.enable', 'keyword.pause', 'keyword.enable',
    'keyword.add', 'keyword.set_cpc', 'negative.add', 'negative.remove', 'campaign.set_budget'],
  maxAttempts: 3
};

/* ------------------------------------------------------------------ Util */
var Util = {
  /** Texto da palavra-chave no formato que o Google Ads Scripts entende para cada correspondência. */
  keywordText: function (text, matchType) {
    if (matchType === 'EXACT') return '[' + text + ']';
    if (matchType === 'PHRASE') return '"' + text + '"';
    return text;
  },
  /** Texto sem os marcadores de correspondência, em minúsculas e com espaços simples. */
  bare: function (text) {
    return String(text || '').replace(/^[\[\"]|[\]\"]$/g, '').replace(/\s+/g, ' ').trim().toLowerCase();
  },
  gaqlString: function (value) {
    return '"' + String(value).replace(/\\/g, '\\\\').replace(/"/g, '\\"') + '"';
  },
  digits: function (value) {
    var text = String(value || '');
    if (!/^\d{1,20}$/.test(text)) throw Util.refuse('ID inválido: ' + text);
    return text;
  },
  refuse: function (message) {
    var error = new Error(message);
    error.refused = true;
    return error;
  },
  first: function (iterator) {
    return iterator.hasNext() ? iterator.next() : null;
  },
  /** Variação percentual entre o valor atual e o pedido. */
  changePct: function (current, wanted) {
    if (!current) return Infinity;
    return Math.abs(wanted - current) * 100 / current;
  }
};

/* ------------------------------------------------------------- Transport */
var Transport = {
  call: function (path, body) {
    var lastError = 'sem resposta';
    for (var attempt = 1; attempt <= CADU.maxAttempts; attempt++) {
      var response = null;
      try {
        response = UrlFetchApp.fetch(CADU.endpoint + path, {
          method: 'post', contentType: 'application/json', headers: {Authorization: 'Bearer ' + CADU.apiKey},
          payload: JSON.stringify(body), muteHttpExceptions: true
        });
      } catch (networkError) {
        lastError = 'rede: ' + networkError;
      }
      if (response) {
        var code = response.getResponseCode();
        if (code >= 200 && code < 300) return JSON.parse(response.getContentText() || '{}');
        var detail = response.getContentText().slice(0, 300);
        if (code !== 429 && code < 500) throw new Error('Reports recusou (HTTP ' + code + '): ' + detail);
        lastError = 'HTTP ' + code;
      }
      if (attempt < CADU.maxAttempts) Utilities.sleep(attempt * 5000);
    }
    throw new Error('Reports indisponível após ' + CADU.maxAttempts + ' tentativas (' + lastError + ').');
  }
};

/* ---------------------------------------------------------------- Finder */
var Finder = {
  /** Campanha de qualquer tipo (Pesquisa, Display, Performance Max, Shopping, Vídeo). */
  campaign: function (id) {
    var selectors = ['campaigns', 'performanceMaxCampaigns', 'shoppingCampaigns', 'videoCampaigns'];
    for (var i = 0; i < selectors.length; i++) {
      if (typeof AdsApp[selectors[i]] !== 'function') continue;
      var found = Util.first(AdsApp[selectors[i]]().withIds([Number(Util.digits(id))]).get());
      if (found) return found;
    }
    throw Util.refuse('Campanha ' + id + ' não encontrada.');
  },
  adGroup: function (id) {
    var selectors = ['adGroups', 'shoppingAdGroups', 'videoAdGroups'];
    for (var i = 0; i < selectors.length; i++) {
      if (typeof AdsApp[selectors[i]] !== 'function') continue;
      var found = Util.first(AdsApp[selectors[i]]().withIds([Number(Util.digits(id))]).get());
      if (found) return found;
    }
    throw Util.refuse('Grupo de anúncios ' + id + ' não encontrado.');
  },
  keyword: function (adGroupId, keywordId) {
    var found = Util.first(AdsApp.keywords().withIds([[Number(Util.digits(adGroupId)), Number(Util.digits(keywordId))]]).get());
    if (!found) throw Util.refuse('Palavra-chave ' + keywordId + ' não encontrada.');
    return found;
  },
  negativeList: function (id) {
    var found = Util.first(AdsApp.negativeKeywordLists().withIds([Number(Util.digits(id))]).get());
    if (!found) throw Util.refuse('Lista de negativas ' + id + ' não encontrada.');
    return found;
  },
  /** Onde a negativa mora: campanha, grupo ou lista compartilhada. */
  negativeOwner: function (target) {
    if (target.level === 'campaign') return Finder.campaign(target.campaign_id);
    if (target.level === 'ad_group') return Finder.adGroup(target.ad_group_id);
    if (target.level === 'shared_list') return Finder.negativeList(target.shared_set_id);
    throw Util.refuse('Nível de negativa inválido.');
  },
  /** Negativas existentes com o mesmo texto e correspondência. */
  negatives: function (owner, text, matchType) {
    var found = [];
    var iterator = owner.negativeKeywords().get();
    while (iterator.hasNext()) {
      var item = iterator.next();
      if (Util.bare(item.getText()) === Util.bare(text) && item.getMatchType() === matchType) found.push(item);
    }
    return found;
  }
};

function status(entity) {
  return entity.isEnabled() ? 'ENABLED' : entity.isPaused() ? 'PAUSED' : 'REMOVED';
}

/* ------------------------------------------------------------------- OPS */
/**
 * Contrato: apply(command, write) -> {status: 'applied' | 'skipped', message, observed}
 * write=false: confere tudo e informa o que faria, sem gravar (allowWrites desligado ou prévia).
 * Exceções com refused=true viram 'skipped'; as demais, 'failed'.
 */
function toggle(find, wanted) {
  return function (command, write) {
    var entity = find(command.target);
    var current = status(entity);
    if (current === wanted) return {status: 'skipped', message: 'Já estava ' + (wanted === 'PAUSED' ? 'pausada' : 'ativa') + '.', observed: {status: current}};
    if (command.expect.status && command.expect.status !== current) {
      return {status: 'skipped', message: 'Mudou desde a aprovação: está ' + current + '.', observed: {status: current}};
    }
    if (write) wanted === 'PAUSED' ? entity.pause() : entity.enable();
    return {status: 'applied', message: wanted === 'PAUSED' ? 'Pausada.' : 'Ativada.', observed: {status: wanted, previous_status: current}};
  };
}
var findCampaign = function (target) { return Finder.campaign(target.campaign_id); };
var findAdGroup = function (target) { return Finder.adGroup(target.ad_group_id); };
var findKeyword = function (target) { return Finder.keyword(target.ad_group_id, target.keyword_id); };

var OPS = {
  'campaign.pause': toggle(findCampaign, 'PAUSED'),
  'campaign.enable': toggle(findCampaign, 'ENABLED'),
  'ad_group.pause': toggle(findAdGroup, 'PAUSED'),
  'ad_group.enable': toggle(findAdGroup, 'ENABLED'),
  'keyword.pause': toggle(findKeyword, 'PAUSED'),
  'keyword.enable': toggle(findKeyword, 'ENABLED'),

  'keyword.add': function (command, write) {
    var adGroup = Finder.adGroup(command.target.ad_group_id);
    var text = command.params.text, matchType = command.params.match_type;
    var existing = AdsApp.search('SELECT ad_group_criterion.criterion_id FROM ad_group_criterion WHERE ad_group.id = ' +
      Util.digits(command.target.ad_group_id) + ' AND ad_group_criterion.type = KEYWORD AND ad_group_criterion.negative = FALSE' +
      ' AND ad_group_criterion.status != REMOVED AND ad_group_criterion.keyword.match_type = ' + matchType +
      ' AND ad_group_criterion.keyword.text = ' + Util.gaqlString(text));
    if (existing.hasNext()) {
      var id = String(existing.next().adGroupCriterion.criterionId);
      return {status: 'skipped', message: 'A palavra-chave já existe neste grupo.', observed: {keyword_id: id}};
    }
    if (!write) return {status: 'applied', message: 'Seria adicionada.', observed: {}};
    var operation = adGroup.newKeywordBuilder().withText(Util.keywordText(text, matchType)).build();
    if (!operation.isSuccessful()) throw new Error('Google Ads recusou: ' + operation.getErrors().join('; '));
    return {status: 'applied', message: 'Adicionada.', observed: {keyword_id: String(operation.getResult().getId())}};
  },

  'keyword.set_cpc': function (command, write) {
    var keyword = Finder.keyword(command.target.ad_group_id, command.target.keyword_id);
    var current = keyword.bidding().getCpc();
    var wanted = command.params.cpc_micros / 1e6;
    if (command.expect.cpc_micros && Math.abs(Math.round(current * 1e6) - command.expect.cpc_micros) > 10000) {
      return {status: 'skipped', message: 'O lance mudou desde a aprovação.', observed: {cpc_micros: Math.round(current * 1e6)}};
    }
    if (Util.changePct(current, wanted) > CADU.limits.maxCpcChangePct + 0.01) {
      throw Util.refuse('Variação de lance acima do limite de ' + CADU.limits.maxCpcChangePct + '%.');
    }
    if (write) keyword.bidding().setCpc(wanted);
    return {status: 'applied', message: 'Lance ajustado.', observed: {cpc_micros: command.params.cpc_micros, previous_cpc_micros: Math.round(current * 1e6)}};
  },

  'campaign.set_budget': function (command, write) {
    var campaign = Finder.campaign(command.target.campaign_id);
    var budget = campaign.getBudget();
    if (budget.isExplicitlyShared()) throw Util.refuse('Orçamento compartilhado: ajuste na Biblioteca compartilhada.');
    var current = budget.getAmount();
    var wanted = command.params.amount_micros / 1e6;
    if (command.expect.budget_micros && Math.abs(Math.round(current * 1e6) - command.expect.budget_micros) > 10000) {
      return {status: 'skipped', message: 'O orçamento mudou desde a aprovação.', observed: {budget_micros: Math.round(current * 1e6)}};
    }
    if (Util.changePct(current, wanted) > CADU.limits.maxBudgetChangePct + 0.01) {
      throw Util.refuse('Variação de orçamento acima do limite de ' + CADU.limits.maxBudgetChangePct + '%.');
    }
    if (write) budget.setAmount(wanted);
    return {status: 'applied', message: 'Orçamento ajustado.', observed: {budget_micros: command.params.amount_micros, previous_budget_micros: Math.round(current * 1e6)}};
  },

  'negative.add': function (command, write) {
    var owner = Finder.negativeOwner(command.target);
    var text = command.params.text, matchType = command.params.match_type;
    if (Finder.negatives(owner, text, matchType).length) return {status: 'skipped', message: 'A negativa já existe.', observed: {}};
    if (write) {
      var formatted = Util.keywordText(text, matchType);
      command.target.level === 'shared_list' ? owner.addNegativeKeyword(formatted) : owner.createNegativeKeyword(formatted);
    }
    return {status: 'applied', message: 'Negativa adicionada.', observed: {}};
  },

  'negative.remove': function (command, write) {
    var owner = Finder.negativeOwner(command.target);
    var found = Finder.negatives(owner, command.params.text, command.params.match_type);
    if (!found.length) return {status: 'skipped', message: 'A negativa já não existe.', observed: {}};
    if (write) found.forEach(function (item) { item.remove(); });
    return {status: 'applied', message: 'Negativa removida.', observed: {removed: found.length}};
  }
};

/* ---------------------------------------------------------------- Engine */
var Engine = {
  validateConfig: function () {
    if (!CADU.endpoint || CADU.endpoint.indexOf('__CADU_') === 0 || !CADU.apiKey || CADU.apiKey.indexOf('__CADU_') === 0) {
      throw new Error('Script não configurado: gere-o novamente em Reports > Mídia > Dados.');
    }
  },

  run: function () {
    Engine.validateConfig();
    var preview = AdsApp.getExecutionInfo().isPreview();
    var failures = [];
    if (typeof AdsManagerApp !== 'undefined') {
      if (!CADU.accountIds.length) throw new Error('Informe as contas autorizadas antes de instalar este script em uma MCC.');
      var managerId = AdsApp.currentAccount().getCustomerId();
      var accounts = AdsManagerApp.accounts().withIds(CADU.accountIds).get();
      while (accounts.hasNext()) {
        AdsManagerApp.select(accounts.next());
        Engine.runAccount(managerId, preview, failures);
      }
    } else {
      Engine.runAccount(null, preview, failures);
    }
    if (failures.length) throw new Error(failures.length + ' ação(ões) com erro: ' + failures.join(' | ').slice(0, 800));
  },

  runAccount: function (managerId, preview, failures) {
    var accountId = AdsApp.currentAccount().getCustomerId();
    var write = CADU.allowWrites && !preview;
    var envelope = {account_id: accountId, manager_account_id: managerId, engine_version: CADU.engineVersion,
      allow_writes: CADU.allowWrites, preview: preview, limits: CADU.limits};
    var queue = Transport.call('/actions/next', envelope);
    var commands = queue.commands || [];
    if (!commands.length) {
      Logger.log(accountId + ': nenhuma ação aprovada na fila.');
      return;
    }
    var results = [];
    for (var i = 0; i < commands.length; i++) {
      var command = commands[i];
      command.target = command.target || {};
      command.params = command.params || {};
      command.expect = command.expect || {};
      var outcome;
      try {
        if (i >= CADU.limits.maxChangesPerRun) {
          results.push({id: command.id, status: 'requeue', message: 'Limite de ' + CADU.limits.maxChangesPerRun + ' mudanças por execução; fica para a próxima.', observed: {}});
          continue;
        }
        if (CADU.allowedOps.indexOf(command.op) < 0 || !OPS[command.op]) throw Util.refuse('Operação não permitida neste script: ' + command.op);
        if (command.expires_at && Date.parse(command.expires_at) < Date.now()) throw Util.refuse('Aprovação vencida.');
        outcome = OPS[command.op](command, write);
      } catch (error) {
        outcome = {status: error.refused ? 'skipped' : 'failed', message: String(error.message || error).slice(0, 300), observed: {}};
        if (!error.refused) failures.push(command.label || command.op);
      }
      outcome.id = command.id;
      outcome.simulated = !write;
      results.push(outcome);
      Logger.log(accountId + ' · ' + (command.label || command.op) + ': ' + outcome.status + (write ? '' : ' (simulação)') + ' · ' + outcome.message);
    }
    Transport.call('/actions/result', {account_id: accountId, manager_account_id: managerId, engine_version: CADU.engineVersion,
      preview: preview, allow_writes: CADU.allowWrites, results: results});
  }
};

function main() {
  Engine.run();
}
