(function () {
  const app = document.getElementById("studioCreate");
  if (!app) return;
  const apiRoot = String(app.dataset.apiRoot || "/parametros/api").replace(/\/$/, "");
  const projectSelect = document.getElementById("mcCaduProject");
  const projectName = document.getElementById("studioCreateProject");
  const projectBrand = document.getElementById("studioCreateBrand");
  const path = document.getElementById("studioCreatePath");
  const agentContext = document.getElementById("studioCreateAgentContext");
  const references = document.getElementById("studioCreateReferences");
  const referenceHint = document.getElementById("studioCreateReferenceHint");
  const referenceCount = document.getElementById("studioCreateReferenceCount");
  const prompt = document.getElementById("studioCreatePrompt");
  const directions = document.getElementById("studioCreateDirections");
  const canvas = document.getElementById("studioCreateCanvas");
  const continueButton = document.getElementById("studioCreateContinue");
  const editor = document.getElementById("studioCreateEditor");
  const format = document.getElementById("studioCreateFormat");
  const intensity = document.getElementById("studioCreateIntensity");
  const range = document.getElementById("studioCreateRange");
  const historyPanel = document.getElementById("studioCreateHistory");
  let clientId = "";
  let projectId = "";
  let selectedReferences = [];
  let library = [];
  let selectedImage = "";
  let projectDocument = {};
  let projectReady = false;

  function escapeHtml(value) {
    return String(value || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function get(url) {
    return fetch(url, { credentials: "same-origin", headers: { Accept: "application/json" } }).then(async (response) => {
      const payload = await response.json().catch(() => ({}));
      if (!response.ok || payload.success === false) throw new Error(payload.error || "Não foi possível carregar.");
      return payload.data !== undefined ? payload.data : payload;
    });
  }
  function selectedRatio() {
    return document.querySelector('input[name="ratio"]:checked')?.value || "9:16";
  }
  function selectedPurpose() {
    return document.querySelector('select[name="purpose"]')?.value || "alcance";
  }
  function formatLabel() {
    const ratio = selectedRatio();
    return `${ratio} · ${{"1:1":"Quadrado","4:5":"Retrato","9:16":"Story","16:9":"Paisagem"}[ratio] || "Peça"}`;
  }
  function updateFormat() { format.textContent = formatLabel(); }
  function selectedCount() { return Number(document.querySelector('input[name="directionCount"]:checked')?.value || 5); }
  function imageUrl(item) { return String(item?.thumbnail_url || item?.url || item?.image_url || item?.preview_url || ""); }
  function renderReferences() {
    referenceCount.textContent = `${selectedReferences.length} de 2`;
    if (!library.length) {
      references.innerHTML = "";
      referenceHint.textContent = "Ainda não há imagens na biblioteca deste projeto.";
      return;
    }
    referenceHint.textContent = "Escolha até duas referências para o agente ou coloque uma imagem no palco.";
    references.innerHTML = library.slice(0, 6).map((item, index) => {
      const url = imageUrl(item);
      const active = selectedReferences.includes(index);
      return `<div class="studio-create__reference">${url ? `<img src="${escapeHtml(url)}" alt="Imagem ${index + 1} da biblioteca">` : ""}<button class="studio-create__stage-image" type="button" data-stage-image="${index}">Usar no palco</button><button class="studio-create__reference-toggle" type="button" data-reference="${index}" aria-label="${active ? "Remover referência" : "Adicionar como referência"}" aria-pressed="${active}">${active ? "✓" : "+"}</button></div>`;
    }).join("");
    references.querySelectorAll("button[data-stage-image]").forEach((button) => button.addEventListener("click", () => {
      const item = library[Number(button.dataset.stageImage)];
      if (item) setCanvas(item);
    }));
    references.querySelectorAll("button[data-reference]").forEach((button) => button.addEventListener("click", () => {
      const index = Number(button.dataset.reference);
      if (selectedReferences.includes(index)) selectedReferences = selectedReferences.filter((value) => value !== index);
      else if (selectedReferences.length < 2) selectedReferences = [...selectedReferences, index];
      renderReferences();
    }));
  }
  function setCanvas(item) {
    const url = typeof item === "string" ? item : imageUrl(item);
    if (!url) return;
    selectedImage = url;
    canvas.innerHTML = `<div class="studio-create__artwork"><img src="${escapeHtml(url)}" alt="Peça no palco"></div>`;
    continueButton.disabled = false;
    editor.classList.remove("is-disabled");
    editor.removeAttribute("aria-disabled");
    editor.href = `${editor.href.split("?")[0]}?creative_client_id=${encodeURIComponent(clientId)}&project_id=${encodeURIComponent(projectId)}&source=${encodeURIComponent(url)}`;
  }
  function clearCanvas() {
    selectedImage = "";
    canvas.innerHTML = '<div class="studio-create__empty"><strong>Descreva o que a peça precisa comunicar</strong><span>Use o agente para informar objetivo, público e mensagem.</span></div>';
    continueButton.disabled = true;
    editor.classList.add("is-disabled");
    editor.setAttribute("aria-disabled", "true");
    editor.href = editor.href.split("?")[0];
  }
  async function saveStageAsset() {
    if (!selectedImage || !clientId || !projectId) return;
    const csrf = document.querySelector('meta[name="trocr-csrf-token"]')?.content || "";
    const response = await fetch(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(projectId)}/items`, {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json", Accept:"application/json", ...(csrf ? {"X-Trocr-CSRF-Token":csrf} : {})}, body:JSON.stringify({client_id:clientId, kind:"image", title:projectName.textContent || "Imagem em edição", asset_url:selectedImage, metadata:{ratio:selectedRatio(), stage:"create"}})});
    if (!response.ok) throw new Error("Não foi possível vincular a imagem ao projeto.");
  }
  function renderHistory(history) {
    if (!historyPanel) return;
    const runs = Array.isArray(history?.runs) ? history.runs : [];
    if (!runs.length) { historyPanel.innerHTML = "<p>Nenhuma direção criada neste projeto ainda.</p>"; return; }
    historyPanel.innerHTML = `<div class="studio-create__history-list">${runs.slice(0, 4).map((run) => {
      const direction = Array.isArray(run.directions) ? run.directions[0] : null;
      const title = direction?.title || run.prompt || "Direção criativa";
      const label = run.status === "failed" ? "Não concluída" : `${run.returned_count || 0} direção(ões)`;
      return `<article class="studio-create__history-entry ${run.status === "failed" ? "is-failed" : ""}"><i></i><div><strong>${escapeHtml(title)}</strong><span>${escapeHtml(label)}</span></div>${direction?.prompt ? `<button type="button" data-history-prompt="${escapeHtml(direction.prompt)}">Reusar</button>` : ""}</article>`;
    }).join("")}</div>`;
    historyPanel.querySelectorAll("button[data-history-prompt]").forEach((button) => button.addEventListener("click", () => { prompt.value = button.dataset.historyPrompt || ""; prompt.focus(); }));
  }
  async function loadHistory() {
    if (!clientId || !projectId || !historyPanel) return;
    try { renderHistory(await get(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(projectId)}/creation-history?client_id=${encodeURIComponent(clientId)}&limit=4`)); }
    catch (_error) { historyPanel.innerHTML = "<p>O histórico fica disponível após salvar a primeira direção.</p>"; }
  }
  async function loadProject(context = {}) {
    projectId = String(projectSelect?.value || "");
    projectReady = false;
    // A project change starts a new creation.  Existing library assets remain
    // available as optional references; none is silently placed on the stage.
    clearCanvas();
    if (!clientId || !projectId) return;
    projectName.textContent = "Carregando projeto…";
    try {
      const project = await get(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(projectId)}?client_id=${encodeURIComponent(clientId)}`);
      const document = project?.document || {};
      projectDocument = document;
      const name = String(document.name || project?.name || projectSelect.selectedOptions?.[0]?.textContent || "Projeto selecionado");
      const brand = String(document.brand_name || document.brand || document.client_name || "Marca vinculada ao projeto");
      const brief = String(document.brief || document.objective || document.description || "Use o contexto do projeto para orientar a peça.");
      projectName.textContent = name;
      projectBrand.textContent = `${brand} · ${brief}`;
      path.textContent = name;
      agentContext.textContent = `${brand} e o briefing do projeto já estão incluídos no contexto.`;
      updateSuggestions(document);
      projectReady = true;
      refreshCreditHint();
    } catch (_error) {
      projectId = "";
      projectName.textContent = projectSelect.selectedOptions?.[0]?.textContent || "Projeto selecionado";
      const brandName = String(context.brandName || projectSelect?.selectedOptions?.[0]?.dataset.brandName || "Marca vinculada");
      projectBrand.textContent = `${brandName} · Escolha um projeto disponível nesta marca.`;
      agentContext.textContent = "Esse projeto não está disponível para a marca atual. Escolha outro projeto para continuar.";
      directions.innerHTML = "<p>Escolha um projeto disponível nesta marca antes de gerar direções.</p>";
    }
    await loadLibrary();
    await loadHistory();
  }
  function updateSuggestions(project) {
    const subject = String(project?.objective || project?.brief || project?.name || "a campanha").replace(/\s+/g, " ").trim().slice(0, 72);
    const audience = String(project?.audience || project?.publico || subject).replace(/\s+/g, " ").trim().slice(0, 64);
    const values = [`Lançamento de ${subject}`, `Peça para portal com foco em ${audience}`, `Criativo de CTV para ${subject}`];
    document.querySelectorAll("[data-suggestion]").forEach((button, index) => {
      button.dataset.suggestion = values[index] || subject;
      button.textContent = values[index] || subject;
    });
  }
  async function loadLibrary() {
    library = [];
    selectedReferences = [];
    renderReferences();
    try {
      const data = await get(`${apiRoot}/format-lab/swap/library?client_id=${encodeURIComponent(clientId)}&media=still`);
      library = Array.isArray(data?.items) ? data.items : [];
      renderReferences();
    } catch (_error) {
      renderReferences();
    }
  }
  function renderDirections(items) {
    if (Array.isArray(items)) {
      directions.innerHTML = items.map((item, index) => `<article class="studio-create__direction">${selectedImage ? `<img src="${escapeHtml(selectedImage)}" alt="Imagem atualmente no palco">` : "<img alt=\"\">"}<div><strong>${index + 1}. ${escapeHtml(item.title)}</strong><span>${escapeHtml(item.summary || item.prompt)}</span></div><button type="button" data-use-direction="${index}">Aplicar direção</button></article>`).join("");
      directions.querySelectorAll("button[data-use-direction]").forEach((button) => button.addEventListener("click", async () => {
        const index = Number(button.dataset.useDirection); const item = items[index] || {};
        prompt.value = item.prompt || "";
        if (item.id && clientId && projectId) {
          try {
            const csrf = document.querySelector('meta[name="trocr-csrf-token"]')?.content || "";
            await fetch(`${apiRoot}/format-lab/studio/projects/${encodeURIComponent(projectId)}/directions/${encodeURIComponent(item.id)}/select`, {method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json", Accept:"application/json", ...(csrf ? {"X-Trocr-CSRF-Token":csrf} : {})}, body:JSON.stringify({client_id:clientId})});
            await loadHistory();
          } catch (_error) { /* The direction remains usable even if its timeline update is unavailable. */ }
        }
      }));
      return;
    }
    const base = prompt.value.trim() || ({ alcance: "Direção para ampliar alcance", reconhecimento: "Direção para reconhecimento de marca", conversao: "Direção para conversão" }[selectedPurpose()] || "Direção de campanha");
    const endings = ["com foco no momento de uso", "com leitura rápida e memorável", "com produto em contexto", "com linguagem direta", "com presença de marca"];
    directions.innerHTML = endings.map((ending, index) => `<article class="studio-create__direction">${selectedImage ? `<img src="${escapeHtml(selectedImage)}" alt="Imagem atualmente no palco">` : "<img alt=\"\">"}<div><strong>${index + 1}. ${escapeHtml(base)}</strong><span>${escapeHtml(ending)} · ${escapeHtml(formatLabel())}</span></div><button type="button" data-use-direction="${index}">Aplicar direção</button></article>`).join("");
    directions.querySelectorAll("button[data-use-direction]").forEach((button) => button.addEventListener("click", () => {
      const index = Number(button.dataset.useDirection);
      prompt.value = `${base}: ${endings[index]}.`;
    }));
  }
  document.querySelectorAll("[data-suggestion]").forEach((button) => button.addEventListener("click", () => {
    prompt.value = button.dataset.suggestion || "";
    prompt.focus();
  }));
  async function refreshCreditHint() {
    const hint = document.getElementById("studioCreateCreditHint");
    if (!hint || !clientId) return;
    try {
      const balance = await get(`${apiRoot}/image-credits?client_id=${encodeURIComponent(clientId)}`);
      hint.textContent = `${Number(balance?.remaining || 0).toLocaleString("pt-BR")} créditos disponíveis`;
      hint.dataset.state = "ready";
      return true;
    } catch (_error) {
      hint.textContent = "Saldo confirmado ao gerar";
      hint.dataset.state = "unavailable";
      return false;
    }
  }
  document.getElementById("studioCreateGenerate")?.addEventListener("click", async (event) => {
    const button = event.currentTarget;
    if (!clientId || !projectId || !projectReady) { directions.innerHTML = "<p>Escolha um projeto disponível nesta marca antes de gerar direções.</p>"; return; }
    const count = selectedCount();
    button.disabled = true; button.textContent = "Verificando créditos…";
    try {
      await refreshCreditHint();
      button.textContent = `Gerando ${count} ${count === 1 ? "direção" : "direções"}…`;
      const csrf = document.querySelector('meta[name="trocr-csrf-token"]')?.content || "";
      const channels = Array.from(document.querySelectorAll('input[name="channel"]:checked')).map((input) => input.value);
      const formats = Array.from(document.querySelectorAll(".studio-create__iab button.is-selected")).map((item) => item.textContent.trim());
      const selectedReferencePayload = selectedReferences.map((index) => library[index]).filter(Boolean).map((item) => ({id:item.id || item.public_id || "", name:item.name || item.title || "Referência visual", url:imageUrl(item)})).filter((item) => item.url).slice(0, 2);
      const data = await fetch(`${apiRoot}/format-lab/studio/create/directions`, { method:"POST", credentials:"same-origin", headers:{"Content-Type":"application/json", Accept:"application/json", ...(csrf ? {"X-Trocr-CSRF-Token":csrf} : {})}, body:JSON.stringify({client_id:clientId, project_id:projectId, count, prompt:prompt.value, references:selectedReferencePayload, context:{project_name:projectName.textContent, brand:projectDocument.brand_name || projectDocument.brand || "", brief:projectDocument.brief || projectDocument.description || "", objective:projectDocument.objective || "", audience:projectDocument.audience || projectDocument.publico || "", purpose:selectedPurpose(), channels, format:selectedRatio(), formats, direction_intensity:Number(range.value), references:selectedReferencePayload}}) });
      const payload = await data.json().catch(() => ({}));
      if (!data.ok || payload.success === false) throw new Error(payload.error || "Não foi possível gerar direções.");
      const result = payload.data !== undefined ? payload.data : payload;
      renderDirections(result.directions || []);
      await loadHistory();
      const hint = document.getElementById("studioCreateCreditHint");
      if (hint) hint.textContent = `${Number(result.remaining_credits || 0).toLocaleString("pt-BR")} créditos disponíveis`;
      document.dispatchEvent(new CustomEvent("cadu:credits-refresh", {detail:{clientId}}));
    } catch (error) { directions.innerHTML = `<p>${escapeHtml(error.message || "Não foi possível gerar direções.")}</p>`; }
    finally { button.disabled = false; button.textContent = `Gerar ${selectedCount()} ${selectedCount() === 1 ? "direção" : "direções"}`; }
  });
  document.querySelectorAll('input[name="directionCount"]').forEach((input) => input.addEventListener("change", () => { const button = document.getElementById("studioCreateGenerate"); if (button) button.textContent = `Gerar ${selectedCount()} ${selectedCount() === 1 ? "direção" : "direções"}`; }));
  continueButton?.addEventListener("click", async () => { try { await saveStageAsset(); await loadHistory(); } catch (_error) { /* The canvas remains usable; saving is retried when opening the editor. */ } });
  editor?.addEventListener("click", async (event) => { if (editor.classList.contains("is-disabled")) return; event.preventDefault(); try { await saveStageAsset(); } catch (_error) { /* Do not block a user from opening the editor because a timeline write failed. */ } window.location.assign(editor.href); });
  document.querySelectorAll('input[name="ratio"]').forEach((input) => input.addEventListener("change", updateFormat));
  document.querySelectorAll(".studio-create__iab button").forEach((button) => button.addEventListener("click", () => button.classList.toggle("is-selected")));
  range?.addEventListener("input", () => { intensity.textContent = `${range.value}%`; });
  document.addEventListener("cadu:project-ready", (event) => {
    clientId = String(event.detail?.clientId || "");
    if (projectSelect && !projectSelect.disabled && projectSelect.value) loadProject(event.detail || {});
  });
  document.addEventListener("cadu:project-change", (event) => {
    clientId = String(event.detail?.clientId || clientId || "");
    loadProject(event.detail || {});
  });
  if (projectSelect?.value) loadProject();
  updateFormat();
})();
