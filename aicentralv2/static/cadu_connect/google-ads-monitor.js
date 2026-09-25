/** Cadu Reports · Monitoramento Google Ads V1
 * Instale em Ferramentas > Scripts na conta Google Ads ou MCC.
 * O script somente lê métricas de ontem e envia ao espaço Reports da agência.
 * Agende diariamente após a atualização dos dados da conta.
 */
var CADU = {
  endpoint: '__CADU_INGEST_URL__',
  apiKey: '__CADU_API_KEY__',
  accountIds: __CADU_ACCOUNT_IDS__, // Obrigatório em MCC; emitido para este client_id.
  batchSize: 200
};

function main() {
  var managerId = null;
  if (typeof AdsManagerApp !== 'undefined') {
    if (!CADU.accountIds.length) throw new Error('Informe as contas autorizadas antes de instalar este script em uma MCC.');
    managerId = AdsApp.currentAccount().getCustomerId();
    var selector = AdsManagerApp.accounts().withIds(CADU.accountIds);
    var accounts = selector.get();
    while (accounts.hasNext()) {
      AdsManagerApp.select(accounts.next());
      collectAndSend(managerId);
    }
  } else {
    collectAndSend(null);
  }
}

function collectAndSend(managerId) {
  var account = AdsApp.currentAccount();
  var query = 'SELECT campaign.id, campaign.name, segments.date, ' +
    'metrics.impressions, metrics.clicks, metrics.cost_micros, ' +
    'metrics.conversions, metrics.conversions_value ' +
    'FROM campaign WHERE segments.date DURING YESTERDAY';
  var rows = AdsApp.search(query);
  var records = [];
  while (rows.hasNext()) {
    var row = rows.next();
    records.push({
      account_id: account.getCustomerId(),
      account_name: account.getName(),
      currency: account.getCurrencyCode(),
      campaign_id: String(row.campaign.id),
      campaign_name: row.campaign.name,
      date: row.segments.date,
      impressions: Number(row.metrics.impressions || 0),
      clicks: Number(row.metrics.clicks || 0),
      cost_micros: Number(row.metrics.costMicros || 0),
      conversions: Number(row.metrics.conversions || 0),
      conversion_value_micros: Math.round(Number(row.metrics.conversionsValue || 0) * 1000000)
    });
  }
  for (var offset = 0; offset < records.length; offset += CADU.batchSize) {
    var batch = records.slice(offset, offset + CADU.batchSize);
    var body = {
      run_key: Utilities.getUuid(),
      manager_account_id: managerId,
      records: batch
    };
    sendBatch(body);
  }
  Logger.log(account.getCustomerId() + ': ' + records.length + ' linhas enviadas ao Cadu Reports.');
}

function sendBatch(body) {
  var payload = JSON.stringify(body);
  for (var attempt = 0; attempt < 3; attempt++) {
    var response = UrlFetchApp.fetch(CADU.endpoint, {
      method: 'post',
      contentType: 'application/json',
      headers: {Authorization: 'Bearer ' + CADU.apiKey},
      payload: payload,
      muteHttpExceptions: true
    });
    var code = response.getResponseCode();
    if (code >= 200 && code < 300) return;
    if (code !== 429 && code < 500) throw new Error('Cadu Reports HTTP ' + code + ': ' + response.getContentText().slice(0, 300));
    Utilities.sleep((attempt + 1) * 5000);
  }
  throw new Error('Cadu Reports indisponível após três tentativas.');
}
