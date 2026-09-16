/* Local staging only. Provider upload occurs after explicit message submission. */
(() => {
  'use strict';
  class Attachments {
    constructor(panel, status) {
      this.items = []; this.enabled = false; this.busy = false; this.status = status;
      this.list = panel.querySelector('#conversation-attachments');
      this.input = panel.querySelector('#conversation-file-input');
      this.button = panel.querySelector('#conversation-attach');
      this.composer = panel.querySelector('#conversation-message');
      this.button.addEventListener('click', () => this.input.click());
      this.input.addEventListener('change', () => { this.add(this.input.files); this.input.value = ''; });
      this.composer.addEventListener('paste', event => {
        const files = [...(event.clipboardData?.files || [])];
        if (files.length) { event.preventDefault(); this.add(files); }
      });
      this.composer.addEventListener('dragover', event => { event.preventDefault(); });
      this.composer.addEventListener('drop', event => { event.preventDefault(); this.add(event.dataTransfer.files); });
      window.addEventListener('beforeunload', event => {
        if (this.items.length) { event.preventDefault(); event.returnValue = ''; }
      });
    }
    configure(capabilities) { this.enabled = capabilities.attachments === true; this.button.disabled = !this.enabled || this.busy; }
    lock(value) { this.busy = value; this.button.disabled = !this.enabled || value; this.render(); }
    add(files) {
      if (!this.enabled || this.busy) { this.status.textContent = 'Anexos não estão disponíveis neste momento.'; return; }
      for (const file of files) {
        if (this.items.length >= 3) { this.status.textContent = 'Anexe no máximo três arquivos.'; break; }
        if (!file.size || file.size > 15 * 1024 * 1024) { this.status.textContent = 'Cada arquivo deve ter entre 1 byte e 15 MB.'; continue; }
        if (!/\.(png|jpe?g|webp|gif|pdf|txt|csv|md|json)$/i.test(file.name)) { this.status.textContent = 'Formato ainda não disponível. Use imagem, PDF ou texto.'; continue; }
        const preview = /^image\/(png|jpeg|webp|gif)$/.test(file.type) ? URL.createObjectURL(file) : null;
        this.items.push({file, preview, id:null, state:'Pronto para enviar'});
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
        remove.addEventListener('click', () => { if (item.preview) URL.revokeObjectURL(item.preview); this.items.splice(index, 1); this.render(); this.button.focus(); });
        row.append(label, remove); this.list.append(row);
      });
      this.list.dispatchEvent(new CustomEvent('attachmentschange', {bubbles:true}));
    }
    async upload(signal) {
      for (const item of this.items) {
        if (item.id) continue;
        item.state = 'Enviando…'; this.render();
        const body = new FormData(); body.append('file', item.file);
        try {
          const response = await fetch('/familia/api/conversations/uploads', {method:'POST', credentials:'same-origin', signal,
          headers:{...(document.querySelector('meta[name="csrf-token"]')?.content ? {'X-CSRF-Token':document.querySelector('meta[name="csrf-token"]').content} : {})}, body});
          const data = await response.json();
          if (!response.ok || !data.file?.id) throw new Error(data.error || 'Não foi possível anexar o arquivo.');
          item.id = data.file.id; item.state = 'Anexado'; this.render();
        } catch (error) { item.state = 'Falha no envio'; this.render(); throw error; }
      }
      return this.items.map(item => item.id);
    }
    clear() { this.items.forEach(item => { if (item.preview) URL.revokeObjectURL(item.preview); }); this.items = []; this.render(); }
  }
  globalThis.CaduAttachments = Attachments;
})();
