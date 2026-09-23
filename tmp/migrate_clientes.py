"""One-shot migration helper for clientes.html -> clientes.js extraction."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "aicentralv2/templates/clientes.html"
OUT_JS = ROOT / "aicentralv2/static/js/clientes.js"

INPUT_CLASS = 'class="w-full px-1.5 py-0.5 text-xs border border-gray-300 rounded focus:outline-none focus:border-gray-400"'
SELECT_CLASS = INPUT_CLASS + ' bg-white'
CX_INPUT = 'class="cx-input cx-input-sm w-full"'
CX_SELECT = 'class="cx-select cx-select-sm w-full"'


def extract_scripts(html: str) -> tuple[str, str, str]:
    """Return (html_without_scripts, script1, script2), preserving modal markup."""
    first_open = html.find("<script>\n")
    if first_open == -1:
        raise RuntimeError("First inline script block not found")
    first_close = html.find("</script>", first_open)
    script1 = html[first_open + len("<script>\n"):first_close]

    ext_marker = "agencias_vinculadas_form.js"
    ext_idx = html.find(ext_marker, first_close)
    if ext_idx == -1:
        raise RuntimeError("External agencias_vinculadas_form.js tag not found")
    second_open = html.find("<script>", ext_idx)
    second_close = html.find("</script>", second_open)
    script2 = html[second_open + len("<script>\n"):second_close]

    html_without = html[:first_open] + html[first_close + len("</script>"):second_open] + html[second_close + len("</script>"):]
    return html_without, script1.strip(), script2.strip()


def main() -> None:
    html = TEMPLATE.read_text(encoding="utf-8")

    if "{% from 'macros/cx_ui.html' import flash_messages %}" not in html:
        html = html.replace(
            "{% extends 'base_erp.html' %}",
            "{% extends 'base_erp.html' %}\n{% from 'macros/cx_ui.html' import flash_messages %}",
            1,
        )

    html = html.replace(
        """  {% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
      <div class="mb-4 space-y-2">
        {% for category, message in messages %}
          <div class="cx-alert {% if category == 'error' %}alert-error{% elif category == 'success' %}alert-success{% elif category == 'warning' %}alert-warning{% else %}alert-info{% endif %}">
            <span>{{ message }}</span>
          </div>
        {% endfor %}
      </div>
    {% endif %}
  {% endwith %}""",
        """  {% with messages = get_flashed_messages(with_categories=true) %}
    {{ flash_messages(messages) }}
  {% endwith %}""",
    )

    html = html.replace(
        """        <div class="clientes-search-box">
          <i class="fa-solid fa-magnifying-glass" aria-hidden="true"></i>
          <input id="clientes-search" type="search" name="search" value="{{ filtros.get('search', '') }}" placeholder="Nome, razão social ou documento" class="cx-input">
        </div>""",
        """        <div class="cx-drawer-input-wrap">
          <i class="fa-solid fa-magnifying-glass cx-drawer-input-icon" aria-hidden="true"></i>
          <input id="clientes-search" type="search" name="search" value="{{ filtros.get('search', '') }}" placeholder="Nome, razão social ou documento" class="cx-input cx-input-sm w-full">
        </div>""",
    )

    html = html.replace("**filtros", "**query_params")

    html = html.replace(SELECT_CLASS, CX_SELECT)
    html = html.replace(INPUT_CLASS, CX_INPUT)

    html = html.replace('class="text-xs font-medium text-gray-500"', 'class="cx-label"')
    html = html.replace(
        'class="flex-1 min-w-[8rem] px-1.5 py-0.5 text-xs border border-gray-300 rounded bg-white"',
        'class="cx-select cx-select-sm flex-1 min-w-[8rem]"',
    )
    html = html.replace(
        'class="px-1.5 py-0.5 text-xs bg-gray-700 text-white rounded hover:bg-gray-600"',
        'class="cx-btn cx-btn-secondary cx-btn-xs"',
    )

    status_toggle_old = """          <div id="status_toggle_container" class="cx-field col-span-1" style="display:none;">
            <label class="cx-label">Status</label>
            <div class="flex">
              <label id="label_status_ativo" class="status-toggle-btn cursor-pointer flex items-center justify-center px-1.5 py-0.5 border rounded-l text-xs font-medium border-green-500 bg-green-50 text-green-700" onclick="toggleStatusField(true)">
                <input type="radio" name="status" value="1" class="hidden" checked><span>On</span>
              </label>
              <label id="label_status_inativo" class="status-toggle-btn cursor-pointer flex items-center justify-center px-1.5 py-0.5 border rounded-r text-xs font-medium border-gray-300 bg-white text-gray-400" onclick="toggleStatusField(false)">
                <input type="radio" name="status" value="0" class="hidden"><span>Off</span>
              </label>
            </div>
          </div>"""

    status_toggle_new = """          <div id="status_toggle_container" class="cx-field col-span-1" style="display:none;">
            <span class="cx-label">Status</span>
            <div class="clientes-segmented clientes-segmented--radio" role="group" aria-label="Status do cliente">
              <label id="label_status_ativo" class="is-active" onclick="toggleStatusField(true)">
                <input type="radio" name="status" value="1" class="sr-only" checked><span>Ativo</span>
              </label>
              <label id="label_status_inativo" onclick="toggleStatusField(false)">
                <input type="radio" name="status" value="0" class="sr-only"><span>Inativo</span>
              </label>
            </div>
          </div>"""

    if status_toggle_old in html:
        html = html.replace(status_toggle_old, status_toggle_new)

    pessoa_toggle_old = """          <div class="cx-field col-span-1">
            <label class="cx-label">Pessoa*</label>
            <div class="flex pessoa-toggle-group">
              <label id="label_pessoa_j" class="pessoa-toggle-btn cursor-pointer flex items-center justify-center px-1.5 py-0.5 border rounded-l text-xs font-medium border-green-500 bg-green-50 text-green-700">
                <input type="radio" name="pessoa" value="J" class="hidden" required checked><span>PJ</span>
              </label>
              <label id="label_pessoa_f" class="pessoa-toggle-btn cursor-pointer flex items-center justify-center px-1.5 py-0.5 border rounded-r text-xs font-medium border-gray-300 bg-white text-gray-400">
                <input type="radio" name="pessoa" value="F" class="hidden" required><span>PF</span>
              </label>
            </div>
          </div>"""

    pessoa_toggle_new = """          <div class="cx-field col-span-1">
            <span class="cx-label">Pessoa*</span>
            <div class="clientes-segmented clientes-segmented--radio pessoa-toggle-group" role="group" aria-label="Tipo de pessoa">
              <label id="label_pessoa_j" class="is-active">
                <input type="radio" name="pessoa" value="J" class="sr-only" required checked><span>PJ</span>
              </label>
              <label id="label_pessoa_f">
                <input type="radio" name="pessoa" value="F" class="sr-only" required><span>PF</span>
              </label>
            </div>
          </div>"""

    if pessoa_toggle_old in html:
        html = html.replace(pessoa_toggle_old, pessoa_toggle_new)

    tabs_old = """    <div id="tabs_container" class="modal-cliente-tabs" role="tablist" aria-label="Seções do cliente" style="display:none;">
      <button type="button" class="tab-btn tab-active" role="tab" aria-selected="true" data-tab="editar" onclick="trocarAba('editar')">
        <i class="fas fa-edit mr-1" aria-hidden="true"></i>Editar
      </button>
      <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="detalhes" onclick="trocarAba('detalhes')">
        <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>Detalhes
      </button>
      <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="contatos" onclick="trocarAba('contatos')">
        <i class="fas fa-address-book mr-1" aria-hidden="true"></i>Contatos
      </button>
      <button type="button" class="tab-btn" role="tab" aria-selected="false" data-tab="contratos" onclick="trocarAba('contratos')">
        <i class="fas fa-file-contract mr-1" aria-hidden="true"></i>Assinaturas
      </button>
    </div>"""

    tabs_new = """    <div id="tabs_container" class="cx-tabs modal-cliente-tabs" role="tablist" data-cx-tab-scope aria-label="Seções do cliente" style="display:none;">
      <button type="button" class="cx-tab cx-tab-active" role="tab" aria-selected="true" data-tab="editar" onclick="trocarAba('editar')">
        <i class="fas fa-edit mr-1" aria-hidden="true"></i>Editar
      </button>
      <button type="button" class="cx-tab" role="tab" aria-selected="false" data-tab="detalhes" onclick="trocarAba('detalhes')">
        <i class="fas fa-info-circle mr-1" aria-hidden="true"></i>Detalhes
      </button>
      <button type="button" class="cx-tab" role="tab" aria-selected="false" data-tab="contatos" onclick="trocarAba('contatos')">
        <i class="fas fa-address-book mr-1" aria-hidden="true"></i>Contatos
      </button>
      <button type="button" class="cx-tab" role="tab" aria-selected="false" data-tab="contratos" onclick="trocarAba('contratos')">
        <i class="fas fa-file-contract mr-1" aria-hidden="true"></i>Assinaturas
      </button>
    </div>"""

    if tabs_old in html:
        html = html.replace(tabs_old, tabs_new)

    modal_detalhes = re.search(
        r"\n<!-- Modal de Detalhes do Cliente -->.*?</dialog>\n",
        html,
        flags=re.S,
    )
    if modal_detalhes:
        html = html.replace(modal_detalhes.group(0), "\n")

    html_without_scripts, script1, script2 = extract_scripts(html)

    script2 = script2.replace(
        "const LOGGED_USER_ID = {{ session.get('user_id', 0) }};",
        "const LOGGED_USER_ID = window.__CLIENTES_CONFIG?.loggedUserId ?? 0;",
    )

    script1 = script1.replace(
        "'{{ url_for(\"clientes\") }}'",
        "window.__CLIENTES_CONFIG.clientesUrl",
    )

    combined_js = script1 + "\n\n" + script2

    combined_js = combined_js.replace(
        """async function abrirModalDetalhes(clienteId) {
  clienteIdAtual = clienteId;
  try {
    // Buscar dados do cliente
    const response = await fetch(`/api/cliente/${clienteId}`);
    const cliente = await response.json();

    // Buscar contatos do cliente
    const contatosResponse = await fetch(`/api/cliente/${clienteId}/contatos`);
    const contatos = await contatosResponse.json();

    // Preencher título
    document.getElementById('detalhes_title').textContent = `Detalhes: ${cliente.nome_fantasia || cliente.razao_social}`;

    // Preencher informações principais
    const infoPrincipais = document.getElementById('info_principais');
    infoPrincipais.innerHTML = `
      <div class="flex"><span class="font-semibold text-slate-600 w-40">ID:</span><span>#${cliente.id_cliente}</span></div>
      <div class="flex"><span class="font-semibold text-slate-600 w-40">Status:</span>
        <span class="cx-badge ${cliente.status ? 'cx-badge-success' : 'cx-badge-danger'}">${cliente.status ? 'Ativo' : 'Inativo'}</span>
      </div>
      ${cliente.pessoa !== 'F' ? `<div class="flex"><span class="font-semibold text-slate-600 w-40">Razão Social:</span><span>${cliente.razao_social || '—'}</span></div>` : ''}
      <div class="flex"><span class="font-semibold text-slate-600 w-40">${cliente.pessoa === 'F' ? 'Nome Completo' : 'Nome Fantasia'}:</span><span>${cliente.nome_fantasia || '—'}</span></div>
      <div class="flex"><span class="font-semibold text-slate-600 w-40">${cliente.pessoa === 'F' ? 'CPF' : 'CNPJ'}:</span><span>${cliente.cnpj || 'Não informado'}</span></div>
      <div class="flex"><span class="font-semibold text-slate-600 w-40">Tipo:</span><span>${cliente.tipo_cliente_display || 'Não informado'}</span></div>
      ${cliente.pessoa !== 'F' ? `
        <div class="flex"><span class="font-semibold text-slate-600 w-40">Insc. Estadual:</span><span>${cliente.inscricao_estadual || '—'}</span></div>
        <div class="flex"><span class="font-semibold text-slate-600 w-40">Insc. Municipal:</span><span>${cliente.inscricao_municipal || '—'}</span></div>
      ` : ''}
    `;

    // Preencher endereço se existir
    const enderecoSection = document.getElementById('endereco_section');
    const infoEndereco = document.getElementById('info_endereco');
    if (cliente.cep || cliente.logradouro || cliente.cidade) {
      enderecoSection.style.display = '';
      infoEndereco.innerHTML = `
        <div class="flex"><span class="font-semibold text-slate-600 w-40">CEP:</span><span>${cliente.cep || '—'}</span></div>
        <div class="flex"><span class="font-semibold text-slate-600 w-40">Estado:</span><span>${cliente.estado_nome || '—'}</span></div>
        <div class="flex"><span class="font-semibold text-slate-600 w-40">Cidade:</span><span>${cliente.cidade || '—'}</span></div>
        <div class="flex"><span class="font-semibold text-slate-600 w-40">Bairro:</span><span>${cliente.bairro || '—'}</span></div>
        <div class="flex md:col-span-2"><span class="font-semibold text-slate-600 w-40">Logradouro:</span><span>${cliente.logradouro || '—'}${cliente.numero ? ', ' + cliente.numero : ''}</span></div>
        ${cliente.complemento ? `<div class="flex md:col-span-2"><span class="font-semibold text-slate-600 w-40">Complemento:</span><span>${cliente.complemento}</span></div>` : ''}
      `;
    } else {
      enderecoSection.style.display = 'none';
    }

    renderAgenciasVinculadasDetalhes(cliente, 'agencias_vinculadas_lista', 'agencias_vinculadas_section');

    // Preencher contatos
    const listaContatos = document.getElementById('lista_contatos');
    if (contatos && contatos.length > 0) {
      listaContatos.innerHTML = `
        <div class="overflow-x-auto">
          <table class="cx-table cx-table-dense w-full">
            <thead class="bg-[#1e4d4f] text-white">
              <tr>
                <th>Nome</th>
                <th>Email</th>
                <th>Telefone</th>
                <th>Setor</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${contatos.map(c => `
                <tr class="hover">
                  <td class="font-semibold">${c.nome_completo}</td>
                  <td>${c.email || '—'}</td>
                  <td>
                    ${c.telefone || '—'}
                    ${c.telefone_secundario ? `<div class="text-xs opacity-70">${c.telefone_secundario}</div>` : ''}
                  </td>
                  <td>${c.setor || '—'}</td>
                  <td><span class="cx-badge ${c.status ? 'cx-badge-success' : 'cx-badge-danger'}">${c.status ? 'Ativo' : 'Inativo'}</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    } else {
      listaContatos.innerHTML = '<p class="text-center text-slate-500 text-sm py-4">Nenhum contato vinculado</p>';
    }

    // Abrir modal
    modal_detalhes.showModal();
  } catch (error) {
    console.error('Erro ao carregar detalhes:', error);
    showToast('Erro ao carregar dados do cliente.', 'error');
  }
}

function editarClienteDoModal() {
  if (clienteIdAtual) {
    modal_detalhes.close();
    abrirModalEditar(clienteIdAtual);
  }
}""",
        """async function abrirModalDetalhes(clienteId) {
  clienteIdAtual = clienteId;
  await abrirModalEditar(clienteId);
  trocarAba('detalhes');
}""",
    )

    combined_js = combined_js.replace("modal_detalhes.close();", "modal_cliente.close();")

    combined_js = combined_js.replace(
        "#tabs_container .tab-btn",
        "#tabs_container .cx-tab",
    )
    combined_js = combined_js.replace(
        "btn.classList.toggle('tab-active', isActive);",
        "btn.classList.toggle('cx-tab-active', isActive);",
    )

    combined_js = re.sub(
        r"function togglePessoaFieldsModal\(\) \{[\s\S]*?  // Atualizar estilos dos toggle buttons[\s\S]*?  \}\n\n  // Campos específicos de PJ",
        "function togglePessoaFieldsModal() {\n  const pessoa = document.querySelector('#form_cliente input[name=\"pessoa\"]:checked')?.value || 'J';\n\n  const labelJ = document.getElementById('label_pessoa_j');\n  const labelF = document.getElementById('label_pessoa_f');\n  labelJ?.classList.toggle('is-active', pessoa === 'J');\n  labelF?.classList.toggle('is-active', pessoa === 'F');\n\n  // Campos específicos de PJ",
        combined_js,
        count=1,
    )

    combined_js = re.sub(
        r"function toggleStatusField\(ativo\) \{[\s\S]*?\n\}",
        """function toggleStatusField(ativo) {
  const labelAtivo = document.getElementById('label_status_ativo');
  const labelInativo = document.getElementById('label_status_inativo');

  if (ativo) {
    labelAtivo.querySelector('input').checked = true;
    labelAtivo.classList.add('is-active');
    labelInativo.classList.remove('is-active', 'is-danger');
  } else {
    labelInativo.querySelector('input').checked = true;
    labelInativo.classList.add('is-active', 'is-danger');
    labelAtivo.classList.remove('is-active');
  }
}""",
        combined_js,
        count=1,
    )

    contato_helper = """
function contatoInviteBadgeClass(status) {
  if (status === 'accepted') return 'cx-badge-success';
  if (status === 'pending') return 'cx-badge-warning';
  return 'cx-badge-muted';
}

function contatoInviteLabel(status) {
  if (status === 'accepted') return 'Aceito';
  if (status === 'pending') return 'Pendente';
  return 'Sem convite';
}

function renderContatoRowHtml(c, clienteId) {
  const nomeEsc = (c.nome_completo || '').replace(/'/g, "\\\\'");
  const statusClass = c.status ? 'cx-badge-success' : 'cx-badge-danger';
  const inviteClass = contatoInviteBadgeClass(c.invite_status);
  const inviteLabel = contatoInviteLabel(c.invite_status);
  return `<div class="cliente-contato-row" data-contato-id="${c.id_contato_cliente}">
    <button type="button" class="cliente-contato-main" onclick="abrirModalEditarContato(${c.id_contato_cliente})">
      <span class="cliente-contato-nome">${escapeHtml(c.nome_completo)}</span>
      <span class="cliente-contato-email">${escapeHtml(c.email || '—')}</span>
    </button>
    <div class="cliente-contato-actions">
      <button type="button" class="cx-badge ${statusClass} cliente-contato-status" onclick="toggleContatoStatus(${c.id_contato_cliente}, ${clienteId}, this, ${c.status})">${c.status ? 'Ativo' : 'Inativo'}</button>
      <span class="cx-badge ${inviteClass}">${inviteLabel}</span>
      ${contatoInviteBtnHtml(c)}
      <button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs cliente-contato-delete" title="Excluir contato" onclick="deletarContato(${c.id_contato_cliente}, ${clienteId}, '${nomeEsc}')"><i class="fas fa-trash" aria-hidden="true"></i></button>
    </div>
  </div>`;
}

"""

    if "function renderContatoRowHtml" not in combined_js:
        combined_js = combined_js.replace(
            "// Avatar do contato:",
            contato_helper + "// Avatar do contato:",
        )

    combined_js = re.sub(
        r"listaContatos\.innerHTML = contatos\.map\(c => \{[\s\S]*?\}\)\.join\(''\);",
        "listaContatos.innerHTML = contatos.map(c => renderContatoRowHtml(c, cliente.id_cliente)).join('');",
        combined_js,
        count=1,
    )

    combined_js = re.sub(
        r"listaContatos\.innerHTML = contatos\.map\(c => \{[\s\S]*?\}\)\.join\(''\);",
        "listaContatos.innerHTML = contatos.map(c => renderContatoRowHtml(c, clienteId)).join('');",
        combined_js,
        count=1,
    )

    combined_js = combined_js.replace(
        "listaContatos.innerHTML = '<p style=\"text-align:center;color:#9ca3af;padding:12px;font-size:10px;\">Nenhum contato vinculado</p>';",
        "listaContatos.innerHTML = '<p class=\"cliente-contato-empty\">Nenhum contato vinculado</p>';",
    )
    combined_js = combined_js.replace(
        "listaContatos.innerHTML = '<p style=\"text-align:center;color:#ef4444;padding:12px;font-size:10px;\">Erro ao carregar</p>';",
        "listaContatos.innerHTML = '<p class=\"cliente-contato-empty cliente-contato-empty--error\">Erro ao carregar contatos</p>';",
    )

    combined_js = combined_js.replace(
        """function contatoInviteBtnHtml(c) {
  const emailEsc = (c.email || '').replace(/'/g, "\\\\'");
  const nomeEsc = (c.nome_completo || '').replace(/'/g, "\\\\'");
  if (c.email && c.status) {
    return `<i class="fas fa-paper-plane" style="color:#22c55e;cursor:pointer;font-size:9px;" title="Enviar convite" onclick="event.stopPropagation();enviarConviteContato(${c.id_contato_cliente}, '${emailEsc}', '${nomeEsc}')"></i>`;
  }
  const title = !c.email ? 'Sem email cadastrado' : 'Contato inativo';
  return `<i class="fas fa-paper-plane" style="color:#d1d5db;font-size:9px;cursor:default;" title="${title}"></i>`;
}""",
        """function contatoInviteBtnHtml(c) {
  const emailEsc = (c.email || '').replace(/'/g, "\\\\'");
  const nomeEsc = (c.nome_completo || '').replace(/'/g, "\\\\'");
  if (c.email && c.status) {
    return `<button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs" title="Enviar convite" onclick="event.stopPropagation();enviarConviteContato(${c.id_contato_cliente}, '${emailEsc}', '${nomeEsc}')"><i class="fas fa-paper-plane text-emerald-600" aria-hidden="true"></i></button>`;
  }
  const title = !c.email ? 'Sem email cadastrado' : 'Contato inativo';
  return `<button type="button" class="cx-btn cx-btn-icon cx-btn-ghost cx-btn-xs" disabled title="${title}"><i class="fas fa-paper-plane text-slate-300" aria-hidden="true"></i></button>`;
}""",
    )

    combined_js = combined_js.replace(
        """// Abrir modal automaticamente via URL params
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  const clienteId = urlParams.get('open');
  const tab = urlParams.get('tab');

  if (clienteId) {
    abrirModalEditar(parseInt(clienteId)).then(() => {
      if (tab === 'contratos') {
        // Aguardar modal abrir e clicar na aba contratos
        setTimeout(() => {
          const contratosTab = document.getElementById('tab_contratos');
          if (contratosTab) {
            contratosTab.click();
          }
        }, 500);
      }
    });

    // Limpar URL sem recarregar página
    window.history.replaceState({}, document.title, window.location.pathname);
  }
});""",
        """// Abrir modal automaticamente via URL params (?open=&tab=)
document.addEventListener('DOMContentLoaded', function() {
  const urlParams = new URLSearchParams(window.location.search);
  const clienteId = urlParams.get('open');
  const tab = urlParams.get('tab');

  if (!clienteId) return;

  const id = parseInt(clienteId, 10);
  const openPromise = tab === 'detalhes'
    ? abrirModalDetalhes(id)
    : abrirModalEditar(id);

  openPromise.then(() => {
    if (tab && tab !== 'editar' && tab !== 'detalhes') {
      trocarAba(tab);
    }
  });
});""",
    )

    OUT_JS.write_text(combined_js + "\n", encoding="utf-8")

    assets_block = """
<script type="application/json" id="clientes-config">{{ {
  'clientesUrl': url_for('clientes'),
  'loggedUserId': session.get('user_id', 0)
}|tojson }}</script>
<script>
  window.__CLIENTES_CONFIG = JSON.parse(document.getElementById('clientes-config').textContent);
</script>
<script src="{{ url_for('static', filename='js/agencias_vinculadas_form.js') }}"></script>
<script src="{{ url_for('static', filename='js/clientes.js') }}?v=2"></script>
"""

    if "<script src=\"{{ url_for('static', filename='js/agencias_vinculadas_form.js') }}\"></script>" in html_without_scripts:
        html_without_scripts = re.sub(
            r"<script src=\"\{\{ url_for\('static', filename='js/agencias_vinculadas_form\.js'\) \}\}\"></script>\s*",
            assets_block,
            html_without_scripts,
            count=1,
        )

    TEMPLATE.write_text(html_without_scripts, encoding="utf-8")
    print(f"Wrote {OUT_JS} ({OUT_JS.stat().st_size} bytes)")
    print(f"Updated {TEMPLATE} ({TEMPLATE.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
