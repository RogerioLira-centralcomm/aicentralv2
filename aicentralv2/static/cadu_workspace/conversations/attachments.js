/* Local staging only. Provider upload occurs after explicit message submission. */
(() => {
  'use strict';
  class Attachments {
    constructor(panel, status) {
      this.items = []; this.enabled = false; this.busy = false; this.status = status;
      this.list = panel.querySelector('#conversation-attachments');
      this.input = panel.querySelector('#conversation-file-input');
      this.button = panel.querySelector('#conversation-attach');
      this.composer = panel.querySelector('#conversation-editor') || panel.querySelector('#conversation-message');
      this.shell = panel.querySelector('.conversation-composer-shell');
      this.button?.addEventListener('click', () => this.input?.click());
      this.input.addEventListener('change', () => { this.add(this.input.files); this.input.value = ''; });
      this.composer.addEventListener('paste', event => {
        const files = [...(event.clipboardData?.files || [])];
        if (files.length) { event.preventDefault(); this.add(files); }
      });
      const hasFiles = event => Array.from(event.dataTransfer?.types || []).includes('Files');
      this.shell?.addEventListener('dragenter', event => { if (!hasFiles(event) || !this.enabled || this.busy) return; event.preventDefault(); this.shell.classList.add('is-dragging'); });
      this.shell?.addEventListener('dragover', event => { if (!hasFiles(event)) return; event.preventDefault(); event.dataTransfer.dropEffect = 'copy'; });
      this.shell?.addEventListener('dragleave', event => { if (!this.shell.contains(event.relatedTarget)) this.shell.classList.remove('is-dragging'); });
      this.shell?.addEventListener('drop', event => { if (!hasFiles(event)) return; event.preventDefault(); this.shell.classList.remove('is-dragging'); this.add(event.dataTransfer.files); });
      window.addEventListener('beforeunload', event => {
        if (this.items.length) { event.preventDefault(); event.returnValue = ''; }
      });
    }
    configure(capabilities) { this.enabled = capabilities.attachments === true; if (this.button) this.button.disabled = !this.enabled || this.busy; }
    lock(value) { this.busy = value; if (this.button) this.button.disabled = !this.enabled || value; this.render(); }
    add(files) {
      if (!this.enabled || this.busy) { this.status.textContent = 'Anexos não estão disponíveis neste momento.'; return; }
      for (const file of files) {
        if (this.items.length >= 3) { this.status.textContent = 'Anexe no máximo três arquivos.'; break; }
        if (!file.size || file.size > 15 * 1024 * 1024) { this.status.textContent = 'Cada arquivo deve ter entre 1 byte e 15 MB.'; continue; }
        if (!/\.(png|jpe?g|webp|gif|pdf|txt|csv|md|json|docx|xlsx|pptx)$/i.test(file.name)) { this.status.textContent = 'Formato ainda não disponível. Use imagem, PDF, texto ou Office.'; continue; }
        const preview = /^image\/(png|jpeg|webp|gif)$/.test(file.type) ? URL.createObjectURL(file) : null;
        this.items.push({file, preview, id:null, state:'Pronto para enviar', progress:null});
      }
      this.render();
    }
    render() {
      this.list.replaceChildren(); this.list.hidden = !this.items.length;
      this.items.forEach((item, index) => {
        const row = document.createElement('div'); row.className = 'conversation-file';
        if (item.preview) { const image = document.createElement('img'); image.src = item.preview; image.alt = ''; row.append(image); }
        const label = document.createElement('span'); label.textContent = item.file.name;
        const meta = document.createElement('small'); meta.textContent = `${Math.ceil(item.file.size / 1024)} KB · ${item.state}`;
        label.append(meta);
        const remove = document.createElement('button'); remove.type = 'button'; remove.textContent = 'Remover'; remove.disabled = this.busy;
        remove.setAttribute('aria-label', `Remover ${item.file.name}`);
        remove.addEventListener('click', () => { if (item.preview) URL.revokeObjectURL(item.preview); this.items.splice(index, 1); this.render(); this.button?.focus(); });
        row.append(label);
        if (item.state === 'Falha no envio') {
          const retry = document.createElement('button'); retry.type = 'button'; retry.textContent = 'Tentar novamente'; retry.disabled = this.busy;
          retry.addEventListener('click', async () => {
            if (this.busy) return;
            this.busy = true; this.render();
            try { await this.uploadItem(item); this.status.textContent = 'Arquivo anexado. Você pode enviar a mensagem.'; }
            catch (error) { this.status.textContent = error.message || 'Não foi possível anexar o arquivo.'; }
            finally { this.busy = false; this.configure({attachments:this.enabled}); this.render(); }
          });
          row.append(retry);
        }
        row.append(remove); this.list.append(row);
      });
      this.list.dispatchEvent(new CustomEvent('attachmentschange', {bubbles:true}));
    }
    async upload(signal) {
      for (const item of this.items) {
        if (item.id) continue;
        await this.uploadItem(item, signal);
      }
      return this.items.map(item => item.id);
    }
    uploadItem(item, signal) {
      item.state = 'Enviando… 0%'; item.progress = 0; this.render();
      return new Promise((resolve, reject) => {
        const xhr = new XMLHttpRequest(), body = new FormData(); body.append('file', item.file);
        const abort = () => xhr.abort();
        if (signal?.aborted) { abort(); reject(new DOMException('Envio interrompido', 'AbortError')); return; }
        signal?.addEventListener('abort', abort, {once:true});
        xhr.open('POST', '/familia/api/conversations/uploads'); xhr.withCredentials = true;
        const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
        if (csrf) xhr.setRequestHeader('X-CSRF-Token', csrf);
        xhr.upload.onprogress = event => {
          if (!event.lengthComputable) return;
          item.progress = Math.max(0, Math.min(100, Math.round(event.loaded / event.total * 100)));
          item.state = 'Enviando… ' + item.progress + '%'; this.render();
        };
        xhr.onload = () => {
          signal?.removeEventListener('abort', abort);
          let data = {}; try { data = JSON.parse(xhr.responseText || '{}'); } catch (_) { /* Keep the safe fallback below. */ }
          if (xhr.status < 200 || xhr.status >= 300 || !data.file?.id) {
            item.state = 'Falha no envio'; item.progress = null; this.render();
            reject(new Error(data.error || 'Não foi possível anexar o arquivo.')); return;
          }
          item.id = data.file.id; item.state = 'Anexado'; item.progress = 100; this.render(); resolve();
        };
        xhr.onerror = () => { signal?.removeEventListener('abort', abort); item.state = 'Falha no envio'; item.progress = null; this.render(); reject(new Error('A conexão falhou durante o envio.')); };
        xhr.onabort = () => { signal?.removeEventListener('abort', abort); item.state = 'Falha no envio'; item.progress = null; this.render(); reject(new DOMException('Envio interrompido', 'AbortError')); };
        xhr.send(body);
      });
    }
    clear() { this.items.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview); }); this.items = []; this.render(); }
  }
  globalThis.CaduAttachments = Attachments;
})();
