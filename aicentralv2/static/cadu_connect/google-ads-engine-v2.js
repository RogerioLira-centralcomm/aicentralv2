/**
 * Cadu Reports · Motor Google Ads v2
 *
 * Instale em Ferramentas > Scripts na conta Google Ads ou na MCC e agende diariamente.
 * O script SOMENTE LÊ dados da conta e os envia ao espaço Reports da agência. Nunca altera nada no Google Ads.
 *
 * Arquitetura (de cima para baixo):
 *   CADU          configuração (os três marcadores __CADU_*__ são preenchidos pelo Reports)
 *   Util          funções puras de apoio
 *   Gaql          leitura de consultas GAQL com limite de linhas
 *   Transport     envio HTTP com retentativa e classificação de falhas
 *   COLLECTORS    um coletor por conjunto de dados; cada um devolve registros prontos para envio
 *   Engine        orquestra contas, janela de datas, envio em lotes, tempo limite e resumo da execução
 *
 * Princípios:
 *   - Um conjunto de dados que falha não derruba os demais; o erro vai para o resumo e para o Registro.
 *   - Todo envio é idempotente: reexecutar a mesma janela só atualiza, nunca duplica.
 *   - Toda execução envia um resumo (heartbeat), mesmo sem linhas, para o Reports saber que a conexão está viva.
 */
var CADU = {
  endpoint: '__CADU_INGEST_URL__',
  apiKey: '__CADU_API_KEY__',
  accountIds: __CADU_ACCOUNT_IDS__, // Obrigatório em MCC; emitido para este cliente.

  engineVersion: '2.1.1',
  schemaVersion: 2,
  windowDays: 14,                   // Janela recente quando o Reports não responde ao plano (conversões chegam atrasadas).
  // O Reports devolve o plano de datas: a janela recente + a próxima fatia do histórico (até 13 meses), uma por execução.
  chunkSize: 300,                   // Registros por requisição (limite do servidor: 500).
  maxRuntimeMs: 25 * 60 * 1000,     // Folga sobre o limite de 30 minutos do Google Ads Scripts.
  maxAttempts: 3,
  dryRun: false,                    // true: coleta e registra contagens, sem enviar nada.

  // Ordem = prioridade (se o tempo acabar, os últimos são pulados). maxRows corta pelos de maior custo.
  datasets: {
    campaign_metrics:    {enabled: true},
    campaign_settings:   {enabled: true},
    ad_group_metrics:    {enabled: true, maxRows: 20000},
    device_metrics:      {enabled: true, maxRows: 20000},
    landing_page_metrics:{enabled: true, maxRows: 20000},
    keyword_metrics:     {enabled: true, maxRows: 20000},
    search_term_metrics: {enabled: true, maxRows: 30000},
    negative_keywords:   {enabled: true, maxRows: 30000}
  }
};

/* ------------------------------------------------------------------ Util */
var Util = {
  get: function (object, path) {
    var cursor = object;
    var parts = path.split('.');
    for (var i = 0; i < parts.length; i++) {
      if (cursor === null || cursor === undefined) return null;
      cursor = cursor[parts[i]];
    }
    return cursor === undefined ? null : cursor;
  },
  number: function (value) {
    var parsed = Number(value);
    return isFinite(parsed) ? parsed : 0;
  },
  // Valor monetário em moeda -> micros inteiros (a API já devolve custo em micros).
  toMicros: function (value) {
    return Math.round(Util.number(value) * 1000000);
  },
  text: function (value) {
    return value === null || value === undefined ? '' : String(value);
  },
  day: function (date, timeZone) {
    return Utilities.formatDate(date, timeZone, 'yyyy-MM-dd');
  },
  chunk: function (list, size) {
    var parts = [];
    for (var offset = 0; offset < list.length; offset += size) parts.push(list.slice(offset, offset + size));
    return parts;
  },
  seconds: function (startedAt) {
    return ((Date.now() - startedAt) / 1000).toFixed(1) + 's';
  },
  // Métricas comuns a todos os conjuntos diários.
  metrics: function (row) {
    return {
      impressions: Util.number(Util.get(row, 'metrics.impressions')),
      clicks: Util.number(Util.get(row, 'metrics.clicks')),
      cost_micros: Util.number(Util.get(row, 'metrics.costMicros')),
      conversions: Util.number(Util.get(row, 'metrics.conversions')),
      conversion_value_micros: Util.toMicros(Util.get(row, 'metrics.conversionsValue'))
    };
  }
};

var METRIC_FIELDS = 'metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions, metrics.conversions_value';

/* ------------------------------------------------------------------ Gaql */
var Gaql = {
  /** Executa a consulta e chama visit(row) por linha. Devolve {rows, truncated}. */
  each: function (query, maxRows, visit) {
    var iterator = AdsApp.search(query);
    var count = 0;
    while (iterator.hasNext()) {
      if (maxRows && count >= maxRows) return {rows: count, truncated: true};
      visit(iterator.next());
      count++;
    }
    return {rows: count, truncated: false};
  },
  between: function (ctx) {
    return 'segments.date BETWEEN "' + ctx.since + '" AND "' + ctx.until + '"';
  }
};

/* ------------------------------------------------------------- Transport */
var Transport = {
  /** Envia um lote. Falhas 401/403 são fatais (chave ou conta inválidas); 4xx são do conjunto; 429/5xx tentam de novo. */
  send: function (body) {
    var payload = JSON.stringify(body);
    var lastError = 'sem resposta';
    for (var attempt = 1; attempt <= CADU.maxAttempts; attempt++) {
      var response = null;
      try {
        response = UrlFetchApp.fetch(CADU.endpoint, {
          method: 'post',
          contentType: 'application/json',
          headers: {Authorization: 'Bearer ' + CADU.apiKey},
          payload: payload,
          muteHttpExceptions: true
        });
      } catch (networkError) {
        lastError = 'rede: ' + networkError;
      }
      if (response) {
        var code = response.getResponseCode();
        if (code >= 200 && code < 300) return;
        var detail = response.getContentText().slice(0, 300);
        if (code === 401 || code === 403) throw Transport.fail('Reports recusou a chave ou a conta (HTTP ' + code + '): ' + detail, true);
        if (code !== 429 && code < 500) throw Transport.fail('Reports HTTP ' + code + ': ' + detail, false);
        lastError = 'HTTP ' + code;
      }
      if (attempt < CADU.maxAttempts) Utilities.sleep(attempt * 5000);
    }
    throw Transport.fail('Reports indisponível após ' + CADU.maxAttempts + ' tentativas (' + lastError + ').', false);
  },
  fail: function (message, fatal) {
    var error = new Error(message);
    error.fatal = fatal;
    return error;
  }
};

/* ------------------------------------------------------------ COLLECTORS */
/**
 * Contrato de um coletor:
 *   kind:    'daily' (métricas por dia, só envia se houver linhas) ou
 *            'snapshot' (estado atual; envia sempre, inclusive vazio, para o Reports detectar remoções).
 *   collect: function (ctx, cfg) -> {records: [...], truncated: bool}
 */
var COLLECTORS = {
  campaign_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, campaign.status, campaign.advertising_channel_type, segments.date, ' +
        METRIC_FIELDS + ' FROM campaign WHERE ' + Gaql.between(ctx);
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var record = Util.metrics(row);
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.campaign_status = row.campaign.status;
        record.channel_type = row.campaign.advertisingChannelType;
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  campaign_settings: {
    kind: 'snapshot',
    collect: function (ctx, cfg) {
      var base = 'SELECT campaign.id, campaign.name, campaign.status, campaign.serving_status, ' +
        'campaign.advertising_channel_type, campaign.bidding_strategy_type, ' +
        'campaign_budget.amount_micros, campaign_budget.explicitly_shared';
      // Metas de lance (tCPA/tROAS); se a versão da API recusar algum campo, cai para a consulta básica.
      var targets = ', campaign.target_cpa.target_cpa_micros, campaign.maximize_conversions.target_cpa_micros, ' +
        'campaign.target_roas.target_roas, campaign.maximize_conversion_value.target_roas';
      var where = ' FROM campaign WHERE campaign.status != "REMOVED"';
      var read = function (query) {
        var records = [];
        var result = Gaql.each(query, cfg.maxRows, function (row) {
          var tcpa = Util.get(row, 'campaign.targetCpa.targetCpaMicros') || Util.get(row, 'campaign.maximizeConversions.targetCpaMicros');
          var troas = Util.get(row, 'campaign.targetRoas.targetRoas') || Util.get(row, 'campaign.maximizeConversionValue.targetRoas');
          records.push({
            campaign_id: String(row.campaign.id),
            campaign_name: row.campaign.name,
            status: row.campaign.status,
            serving_status: Util.get(row, 'campaign.servingStatus'),
            channel_type: Util.get(row, 'campaign.advertisingChannelType'),
            bidding_strategy_type: Util.get(row, 'campaign.biddingStrategyType'),
            budget_micros: Util.get(row, 'campaignBudget.amountMicros') === null ? null : Util.number(row.campaignBudget.amountMicros),
            budget_shared: Util.get(row, 'campaignBudget.explicitlyShared') === null ? null : row.campaignBudget.explicitlyShared === true,
            target_cpa_micros: tcpa ? Util.number(tcpa) : null,
            target_roas: troas ? Util.number(troas) : null
          });
        });
        return {records: records, truncated: result.truncated};
      };
      try {
        return read(base + targets + where);
      } catch (error) {
        Logger.log(ctx.account.id + ' · campaign_settings: metas de lance indisponíveis nesta versão da API (' + String(error).slice(0, 120) + ')');
        return read(base + where);
      }
    }
  },

  ad_group_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group.status, segments.date, ' +
        METRIC_FIELDS + ' FROM ad_group WHERE ' + Gaql.between(ctx) + ' ORDER BY metrics.cost_micros DESC';
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var record = Util.metrics(row);
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.ad_group_id = String(row.adGroup.id);
        record.ad_group_name = row.adGroup.name;
        record.ad_group_status = row.adGroup.status;
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  device_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, segments.device, segments.date, ' +
        METRIC_FIELDS + ' FROM campaign WHERE ' + Gaql.between(ctx);
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var record = Util.metrics(row);
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.device = row.segments.device;
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  /** Páginas de destino dos anúncios: a ponte entre o custo no Google Ads e as páginas monitoradas pela Super Tag. */
  landing_page_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, landing_page_view.unexpanded_final_url, segments.date, ' +
        METRIC_FIELDS + ' FROM landing_page_view WHERE ' + Gaql.between(ctx) + ' ORDER BY metrics.cost_micros DESC';
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var url = Util.text(row.landingPageView.unexpandedFinalUrl);
        if (!/^https?:\/\/[^\s]+$/i.test(url) || url.length > 2000) return; // modelos como {lpurl} e deep links não são páginas web
        var record = Util.metrics(row);
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.final_url = url;
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  keyword_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group_criterion.criterion_id, ' +
        'ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, ad_group_criterion.status, ' +
        'ad_group_criterion.quality_info.quality_score, segments.date, ' + METRIC_FIELDS +
        ' FROM keyword_view WHERE ' + Gaql.between(ctx) + ' AND ad_group_criterion.negative = FALSE' +
        ' ORDER BY metrics.cost_micros DESC';
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var record = Util.metrics(row);
        var quality = Util.get(row, 'adGroupCriterion.qualityInfo.qualityScore');
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.ad_group_id = String(row.adGroup.id);
        record.ad_group_name = row.adGroup.name;
        record.criterion_id = String(row.adGroupCriterion.criterionId);
        record.keyword_text = row.adGroupCriterion.keyword.text;
        record.match_type = row.adGroupCriterion.keyword.matchType;
        record.keyword_status = row.adGroupCriterion.status;
        record.quality_score = quality === null ? null : Util.number(quality);
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  search_term_metrics: {
    kind: 'daily',
    collect: function (ctx, cfg) {
      var records = [];
      var query = 'SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, search_term_view.search_term, ' +
        'search_term_view.status, segments.date, ' + METRIC_FIELDS +
        ' FROM search_term_view WHERE ' + Gaql.between(ctx) + ' ORDER BY metrics.cost_micros DESC';
      var result = Gaql.each(query, cfg.maxRows, function (row) {
        var record = Util.metrics(row);
        record.campaign_id = String(row.campaign.id);
        record.campaign_name = row.campaign.name;
        record.ad_group_id = String(row.adGroup.id);
        record.ad_group_name = row.adGroup.name;
        record.search_term = row.searchTermView.searchTerm;
        record.term_status = row.searchTermView.status;
        record.date = row.segments.date;
        records.push(record);
      });
      return {records: records, truncated: result.truncated};
    }
  },

  /** Negativas de campanha, de grupo de anúncios e de listas compartilhadas (com as campanhas vinculadas). */
  negative_keywords: {
    kind: 'snapshot',
    collect: function (ctx, cfg) {
      var records = [];
      var truncated = false;
      var note = function (result) { truncated = truncated || result.truncated; };
      // Limite compartilhado entre as três consultas; sem maxRows não há limite.
      var capped = function (query, visit) {
        var room = cfg.maxRows ? cfg.maxRows - records.length : 0;
        if (cfg.maxRows && room <= 0) { truncated = true; return; }
        note(Gaql.each(query, room, visit));
      };

      capped(
        'SELECT campaign.id, campaign.name, campaign_criterion.criterion_id, campaign_criterion.keyword.text, ' +
        'campaign_criterion.keyword.match_type FROM campaign_criterion ' +
        'WHERE campaign_criterion.negative = TRUE AND campaign_criterion.type = "KEYWORD" ' +
        'AND campaign_criterion.status != "REMOVED" AND campaign.status != "REMOVED"',
        function (row) {
          records.push({
            level: 'campaign',
            campaign_id: String(row.campaign.id), campaign_name: row.campaign.name,
            keyword_text: row.campaignCriterion.keyword.text, match_type: row.campaignCriterion.keyword.matchType
          });
        });

      capped(
        'SELECT campaign.id, campaign.name, ad_group.id, ad_group.name, ad_group_criterion.criterion_id, ' +
        'ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type FROM ad_group_criterion ' +
        'WHERE ad_group_criterion.negative = TRUE AND ad_group_criterion.type = "KEYWORD" ' +
        'AND ad_group_criterion.status != "REMOVED" AND ad_group.status != "REMOVED" AND campaign.status != "REMOVED"',
        function (row) {
          records.push({
            level: 'ad_group',
            campaign_id: String(row.campaign.id), campaign_name: row.campaign.name,
            ad_group_id: String(row.adGroup.id), ad_group_name: row.adGroup.name,
            keyword_text: row.adGroupCriterion.keyword.text, match_type: row.adGroupCriterion.keyword.matchType
          });
        });

      // Listas compartilhadas: quais campanhas usam cada lista.
      var attachments = {};
      Gaql.each(
        'SELECT campaign.id, shared_set.id FROM campaign_shared_set ' +
        'WHERE shared_set.type = "NEGATIVE_KEYWORDS" AND campaign_shared_set.status = "ENABLED"',
        0, function (row) {
          var setId = String(row.sharedSet.id);
          (attachments[setId] = attachments[setId] || []).push(String(row.campaign.id));
        });
      capped(
        'SELECT shared_set.id, shared_set.name, shared_criterion.criterion_id, shared_criterion.keyword.text, ' +
        'shared_criterion.keyword.match_type FROM shared_criterion ' +
        'WHERE shared_set.type = "NEGATIVE_KEYWORDS" AND shared_set.status = "ENABLED" AND shared_criterion.type = "KEYWORD"',
        function (row) {
          var setId = String(row.sharedSet.id);
          records.push({
            level: 'shared_list',
            shared_set_id: setId, shared_set_name: row.sharedSet.name,
            attached_campaign_ids: attachments[setId] || [],
            keyword_text: row.sharedCriterion.keyword.text, match_type: row.sharedCriterion.keyword.matchType
          });
        });

      return {records: records, truncated: truncated};
    }
  }
};

/* ---------------------------------------------------------------- Engine */
var Engine = {
  startedAt: 0,
  runKey: '',

  validateConfig: function () {
    if (!CADU.endpoint || CADU.endpoint.indexOf('__CADU_') === 0 || !CADU.apiKey || CADU.apiKey.indexOf('__CADU_') === 0) {
      throw new Error('Script não configurado: gere-o novamente em Reports > Integrações (endpoint e chave ausentes).');
    }
  },

  outOfTime: function () {
    return Date.now() - Engine.startedAt > CADU.maxRuntimeMs;
  },

  run: function () {
    Engine.validateConfig();
    Engine.startedAt = Date.now();
    Engine.runKey = Utilities.getUuid();
    var failures = [];

    if (typeof AdsManagerApp !== 'undefined') {
      if (!CADU.accountIds.length) throw new Error('Informe as contas autorizadas antes de instalar este script em uma MCC.');
      var managerId = AdsApp.currentAccount().getCustomerId();
      var accounts = AdsManagerApp.accounts().withIds(CADU.accountIds).get();
      while (accounts.hasNext()) {
        AdsManagerApp.select(accounts.next());
        Engine.runAccount(managerId, failures);
      }
    } else {
      Engine.runAccount(null, failures);
    }

    Logger.log('Execução concluída em ' + Util.seconds(Engine.startedAt) + '.');
    // Falha visível no painel do Google quando algum conjunto não pôde ser enviado.
    if (failures.length) throw new Error(failures.length + ' conjunto(s) com erro: ' + failures.join(' | ').slice(0, 800));
  },

  runAccount: function (managerId, failures) {
    var account = AdsApp.currentAccount();
    var timeZone = account.getTimeZone();
    var accountInfo = {
      id: account.getCustomerId(), name: account.getName(),
      currency: account.getCurrencyCode(), time_zone: timeZone
    };
    var ctx = {
      account: accountInfo, managerId: managerId,
      since: Util.day(new Date(Date.now() - CADU.windowDays * 24 * 60 * 60 * 1000), timeZone),
      until: Util.day(new Date(), timeZone)
    };
    ctx.ranges = Engine.plan(ctx);
    ctx.since = ctx.ranges.reduce(function (min, range) { return range.since < min ? range.since : min; }, ctx.since);
    var accountStartedAt = Date.now();
    var results = [];
    var timedOut = false;

    var names = Object.keys(CADU.datasets);
    for (var i = 0; i < names.length; i++) {
      var name = names[i];
      var cfg = CADU.datasets[name];
      if (!cfg.enabled || !COLLECTORS[name]) continue;
      if (Engine.outOfTime()) {
        timedOut = true;
        results.push({name: name, status: 'skipped', rows: 0, error: 'tempo limite da execução'});
        continue;
      }
      var result = Engine.runDataset(ctx, name, cfg);
      results.push(result);
      if (result.status === 'error') failures.push(accountInfo.id + ' ' + name + ': ' + result.error);
      if (result.fatal) {
        // Chave ou conta recusada: os demais conjuntos falhariam do mesmo jeito.
        throw new Error(result.error);
      }
    }
    Engine.sendSummary(ctx, results, Date.now() - accountStartedAt, timedOut);
  },

  runDataset: function (ctx, name, cfg) {
    var startedAt = Date.now();
    var collector = COLLECTORS[name];
    var label = ctx.account.id + ' · ' + name;
    try {
      var collected;
      if (collector.kind === 'daily') {
        // Uma leitura por faixa de datas do plano; os lotes seguem numerados para não colidirem na mesma execução.
        collected = {records: [], truncated: false};
        var offset = 0;
        for (var r = 0; r < ctx.ranges.length; r++) {
          if (r > 0 && Engine.outOfTime()) { collected.truncated = true; break; }
          var part = collector.collect({account: ctx.account, managerId: ctx.managerId, since: ctx.ranges[r].since, until: ctx.ranges[r].until}, cfg);
          if (!CADU.dryRun) offset = Engine.sendDataset(ctx, name, collector.kind, part.records, !part.truncated, offset);
          collected.count = (collected.count || 0) + part.records.length;
          collected.truncated = collected.truncated || part.truncated;
        }
      } else {
        collected = collector.collect(ctx, cfg);
        if (!CADU.dryRun) Engine.sendDataset(ctx, name, collector.kind, collected.records, !collected.truncated, 0);
      }
      var records = collected.records;
      var rowCount = collected.count === undefined ? records.length : collected.count;
      var status = collected.truncated ? 'truncated' : (rowCount ? 'ok' : 'empty');
      Logger.log(label + ': ' + rowCount + ' linhas' + (CADU.dryRun ? ' (simulação, nada enviado)' : ' enviadas') +
        (collected.truncated ? ' [cortado em ' + cfg.maxRows + ']' : '') + ' em ' + Util.seconds(startedAt));
      return {name: name, status: status, rows: rowCount, error: null};
    } catch (error) {
      var message = String(error && error.message ? error.message : error).slice(0, 300);
      Logger.log(label + ': ERRO ' + message);
      return {name: name, status: 'error', rows: 0, error: message, fatal: !!(error && error.fatal)};
    }
  },

  envelope: function (ctx, dataset) {
    return {
      schema_version: CADU.schemaVersion,
      engine_version: CADU.engineVersion,
      run_key: Engine.runKey,
      manager_account_id: ctx.managerId,
      account: ctx.account,
      dataset: dataset
    };
  },

  /** complete=false (coleta cortada) impede o snapshot de marcar como removido o que ficou de fora. */
  sendDataset: function (ctx, name, kind, records, complete, offset) {
    offset = offset || 0;
    var snapshot = kind === 'snapshot';
    if (!records.length && !snapshot) return offset;
    // Snapshot vazio ainda é enviado: informa ao Reports que tudo o que existia foi removido.
    var chunks = records.length ? Util.chunk(records, CADU.chunkSize) : [[]];
    for (var index = 0; index < chunks.length; index++) {
      if (Engine.outOfTime()) throw new Error('tempo limite durante o envio de ' + name);
      var body = Engine.envelope(ctx, name);
      body.chunk = {index: offset + index, total: offset + chunks.length};
      if (snapshot) body.snapshot = {id: Engine.runKey + ':' + name, final: complete && index === chunks.length - 1};
      body.records = chunks[index];
      Transport.send(body);
    }
    return offset + chunks.length;
  },

  /** Plano de datas do Reports para esta conta; sem resposta, usa só a janela recente. */
  plan: function (ctx) {
    var fallback = [{since: ctx.since, until: ctx.until, kind: 'recent'}];
    try {
      var url = CADU.endpoint + '/plan?account_id=' + encodeURIComponent(ctx.account.id) +
        (ctx.managerId ? '&manager_account_id=' + encodeURIComponent(ctx.managerId) : '');
      var response = UrlFetchApp.fetch(url, {method: 'get', headers: {Authorization: 'Bearer ' + CADU.apiKey}, muteHttpExceptions: true});
      if (response.getResponseCode() !== 200) {
        Logger.log(ctx.account.id + ': plano recusado (HTTP ' + response.getResponseCode() + '), usando a janela recente · ' +
          response.getContentText().slice(0, 160));
        return fallback;
      }
      var plan = JSON.parse(response.getContentText());
      var ranges = (plan.ranges || []).filter(function (range) { return /^\d{4}-\d{2}-\d{2}$/.test(range.since) && /^\d{4}-\d{2}-\d{2}$/.test(range.until); });
      if (!ranges.length) return fallback;
      Logger.log(ctx.account.id + ': plano ' + ranges.map(function (range) { return range.kind + ' ' + range.since + '→' + range.until; }).join(', '));
      return ranges;
    } catch (error) {
      Logger.log(ctx.account.id + ': plano indisponível, usando a janela recente (' + String(error).slice(0, 120) + ')');
      return fallback;
    }
  },

  sendSummary: function (ctx, results, durationMs, timedOut) {
    if (CADU.dryRun) return;
    var body = Engine.envelope(ctx, 'run_summary');
    body.chunk = {index: 0, total: 1};
    body.summary = {
      window: {since: ctx.since, until: ctx.until},
      duration_ms: durationMs,
      timed_out: timedOut,
      datasets: results.map(function (item) {
        return {name: item.name, status: item.status, rows: item.rows, error: item.error};
      })
    };
    try {
      Transport.send(body);
    } catch (error) {
      // O resumo é diagnóstico: sua falha não invalida os dados já enviados.
      Logger.log(ctx.account.id + ': resumo não enviado: ' + error.message);
    }
  }
};

function main() {
  Engine.run();
}
