(function (root, factory) {
  if (typeof module === 'object' && module.exports) {
    module.exports = factory();
  } else {
    root.McDsaWriteQueue = factory();
  }
})(typeof self !== 'undefined' ? self : this, function () {
  const BRAND_CONFLICT = 'A marca mudou. Recarregue.';
  const DISCARDED_EDIT = 'Edição pendente descartada. A marca mudou.';
  const DISCARDED_STALE_LOCAL =
    'O ajuste anterior foi gravado. Este pedido usava o estado antigo e não foi reenviado.';

  function emptyPatch() {
    return { tokens: {}, adCopy: {}, dna: {} };
  }

  function mergePatch(current, incoming) {
    const next = {
      tokens: Object.assign({}, (current && current.tokens) || {}),
      adCopy: Object.assign({}, (current && current.adCopy) || {}),
      dna: Object.assign({}, (current && current.dna) || {}),
    };
    const extra = incoming || {};
    if (extra.tokens) Object.assign(next.tokens, extra.tokens);
    if (extra.adCopy) Object.assign(next.adCopy, extra.adCopy);
    if (extra.dna) Object.assign(next.dna, extra.dna);
    return next;
  }

  function patchIsEmpty(payload) {
    const data = payload || emptyPatch();
    return (
      Object.keys(data.tokens || {}).length === 0 &&
      Object.keys(data.adCopy || {}).length === 0 &&
      Object.keys(data.dna || {}).length === 0
    );
  }

  function queuedWriteReason(jobRevision, currentRevision, jobEpoch, epoch, localSuccess) {
    if (Number(jobEpoch) !== Number(epoch)) return 'conflict';
    if (Number(jobRevision) !== Number(currentRevision)) {
      return localSuccess ? 'stale_after_local' : 'stale';
    }
    return null;
  }

  function messageFor(reason) {
    if (reason === 'stale_after_local') return DISCARDED_STALE_LOCAL;
    if (reason === 'conflict' || reason === 'stale') return DISCARDED_EDIT;
    return '';
  }

  function revisionBody(extra, revision) {
    return Object.assign({}, extra || {}, { expected_revision: revision });
  }

  function relabelJob(job, newRevision) {
    throw new Error('Não reetiquete payload antigo com revisão nova.');
  }

  async function runQueuedWrites(jobs, current, send) {
    const state = {
      revision: Number(current.revision),
      epoch: Number(current.epoch || 0),
      localSuccess: false,
    };
    const results = [];
    for (const job of jobs) {
      const reason = queuedWriteReason(
        job.revision,
        state.revision,
        job.epoch,
        state.epoch,
        state.localSuccess
      );
      if (reason) {
        results.push({
          discarded: reason,
          message: messageFor(reason),
          extra: job.extra,
          revision: job.revision,
        });
        continue;
      }
      const body = revisionBody(job.extra, job.revision);
      await send(body);
      state.revision += 1;
      state.localSuccess = true;
      results.push({ ok: true, extra: job.extra, sentRevision: job.revision, body: body });
    }
    return results;
  }

  return {
    BRAND_CONFLICT,
    DISCARDED_EDIT,
    DISCARDED_STALE_LOCAL,
    emptyPatch,
    mergePatch,
    patchIsEmpty,
    queuedWriteReason,
    messageFor,
    revisionBody,
    relabelJob,
    runQueuedWrites,
  };
});
