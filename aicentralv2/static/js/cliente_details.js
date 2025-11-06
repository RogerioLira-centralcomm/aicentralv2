// Client Details Sidebar Management
class ClientDetailsSidebar {
    constructor() {
        this.sidebar = document.getElementById('clientDetailsSidebar');
        this.setupEventListeners();
        this.activeTab = 'cadu';
        this.currentClientId = null;
    }

    setupEventListeners() {
        // Tab switching
        document.querySelectorAll('[role="tab"]').forEach(tab => {
            tab.addEventListener('click', (e) => this.switchTab(e.currentTarget.dataset.tab));
        });

        // Close sidebar on overlay click
        document.addEventListener('click', (e) => {
            if (e.target.id === 'clientDetailsSidebar-overlay') {
                this.close();
            }
        });
    }

    async open(clientId) {
        if (this.currentClientId === clientId) return;
        this.currentClientId = clientId;

        // Show loading state
        this.sidebar.classList.remove('hidden');
        this.sidebar.classList.remove('translate-x-full');
        this.showLoading();

        try {
            const response = await fetch(`/api/cliente/${clientId}/details`);
            const data = await response.json();
            this.updateContent(data);
        } catch (error) {
            console.error('Error fetching client details:', error);
            this.showError();
        }
    }

    close() {
        this.sidebar.classList.add('translate-x-full');
        setTimeout(() => {
            this.sidebar.classList.add('hidden');
            this.currentClientId = null;
        }, 300);
    }

    switchTab(tabId) {
        if (this.activeTab === tabId) return;

        // Update tab UI
        document.querySelectorAll('[role="tab"]').forEach(tab => {
            const isActive = tab.dataset.tab === tabId;
            tab.classList.toggle('text-primary', isActive);
            tab.classList.toggle('border-primary', isActive);
            tab.classList.toggle('text-gray-500', !isActive);
            tab.classList.toggle('border-transparent', !isActive);
        });

        // Update content visibility
        document.querySelectorAll('[role="tabpanel"]').forEach(panel => {
            panel.classList.toggle('hidden', panel.id !== `tab-${tabId}`);
        });

        this.activeTab = tabId;
        if (this.currentClientId) {
            this.loadTabContent(tabId, this.currentClientId);
        }
    }

    async loadTabContent(tabId, clientId) {
        const tabPanel = document.getElementById(`tab-${tabId}`);
        tabPanel.innerHTML = this.getLoadingHTML();

        try {
            const response = await fetch(`/api/cliente/${clientId}/${tabId}`);
            const data = await response.json();
            this.updateTabContent(tabId, data);
        } catch (error) {
            console.error(`Error loading ${tabId} content:`, error);
            tabPanel.innerHTML = this.getErrorHTML();
        }
    }

    updateContent(data) {
        // Update client header
        document.getElementById('clientName').textContent = data.nome_fantasia || data.razao_social;
        document.getElementById('clientId').textContent = `#${data.id_cliente}`;
        
        // Update type icon
        const iconContainer = document.getElementById('clientTypeIcon');
        iconContainer.className = `w-10 h-10 rounded-lg flex items-center justify-center mr-3 ${
            data.tipo_pessoa === 'PJ' ? 'bg-primary/10' : 'bg-accent-yellow/10'
        }`;
        iconContainer.innerHTML = `<i class="fas fa-${data.tipo_pessoa === 'PJ' ? 'building' : 'user'} ${
            data.tipo_pessoa === 'PJ' ? 'text-primary' : 'text-accent-yellow'
        }"></i>`;

        // Load initial tab content
        this.loadTabContent(this.activeTab, data.id_cliente);
    }

    updateTabContent(tabId, data) {
        const tabPanel = document.getElementById(`tab-${tabId}`);
        
        switch (tabId) {
            case 'cadu':
                tabPanel.innerHTML = this.renderCaduTab(data);
                break;
            case 'cotacoes':
                tabPanel.innerHTML = this.renderCotacoesTab(data);
                break;
            case 'operacao':
                tabPanel.innerHTML = this.renderOperacaoTab(data);
                break;
            case 'financeiro':
                tabPanel.innerHTML = this.renderFinanceiroTab(data);
                break;
        }
    }

    renderCaduTab(data) {
        return `
            <div class="space-y-6">
                <!-- Informações Básicas -->
                <div class="p-4 bg-gray-50 rounded-lg">
                    <h4 class="text-sm font-semibold text-gray-900 mb-3">Informações Básicas</h4>
                    <div class="space-y-2">
                        <div class="flex justify-between">
                            <span class="text-sm text-gray-500">CNPJ/CPF</span>
                            <span class="text-sm font-medium">${data.cnpj || data.cpf || '-'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-sm text-gray-500">Tipo</span>
                            <span class="text-sm font-medium">${data.tipo_pessoa === 'PJ' ? 'Pessoa Jurídica' : 'Pessoa Física'}</span>
                        </div>
                        <div class="flex justify-between">
                            <span class="text-sm text-gray-500">Status</span>
                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                data.status ? 'bg-success/10 text-success' : 'bg-error/10 text-error'
                            }">
                                ${data.status ? 'Ativo' : 'Inativo'}
                            </span>
                        </div>
                    </div>
                </div>

                <!-- Contatos -->
                <div class="border rounded-lg divide-y">
                    <div class="p-4">
                        <h4 class="text-sm font-semibold text-gray-900 mb-1">Contatos</h4>
                        <p class="text-xs text-gray-500">Lista de contatos vinculados</p>
                    </div>
                    ${data.contatos.map(contato => `
                        <div class="p-4 hover:bg-gray-50">
                            <div class="flex items-center justify-between">
                                <div class="min-w-0">
                                    <h5 class="text-sm font-medium text-gray-900 truncate">${contato.nome_completo}</h5>
                                    <p class="text-xs text-gray-500">${contato.cargo || 'Cargo não definido'}</p>
                                </div>
                                <a href="#" class="text-primary hover:text-primary-dark">
                                    <i class="fas fa-chevron-right"></i>
                                </a>
                            </div>
                        </div>
                    `).join('')}
                </div>

                <!-- Executivo Responsável -->
                <div class="p-4 border rounded-lg">
                    <h4 class="text-sm font-semibold text-gray-900 mb-3">Executivo Responsável</h4>
                    ${data.executivo ? `
                        <div class="flex items-center">
                            <div class="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                                <span class="text-sm font-medium text-primary">
                                    ${data.executivo.nome_completo.split(' ').map(n => n[0]).join('')}
                                </span>
                            </div>
                            <div class="ml-3">
                                <h5 class="text-sm font-medium text-gray-900">${data.executivo.nome_completo}</h5>
                                <p class="text-xs text-gray-500">Vendas CentralComm</p>
                            </div>
                        </div>
                    ` : `
                        <p class="text-sm text-gray-500">Nenhum executivo atribuído</p>
                    `}
                </div>
            </div>
        `;
    }

    renderCotacoesTab(data) {
        return `
            <div class="space-y-6">
                <!-- Resumo -->
                <div class="grid grid-cols-3 gap-4">
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-2xl font-bold text-primary">${data.total_cotacoes || 0}</div>
                        <div class="text-xs text-gray-500">Total Cotações</div>
                    </div>
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-2xl font-bold text-success">${data.cotacoes_aprovadas || 0}</div>
                        <div class="text-xs text-gray-500">Aprovadas</div>
                    </div>
                    <div class="p-4 bg-gray-50 rounded-lg">
                        <div class="text-2xl font-bold text-error">${data.cotacoes_reprovadas || 0}</div>
                        <div class="text-xs text-gray-500">Reprovadas</div>
                    </div>
                </div>

                <!-- Lista de Cotações -->
                <div class="border rounded-lg">
                    <div class="p-4 border-b">
                        <h4 class="text-sm font-semibold text-gray-900">Últimas Cotações</h4>
                    </div>
                    ${data.cotacoes?.length ? data.cotacoes.map(cotacao => `
                        <div class="p-4 border-b last:border-0 hover:bg-gray-50">
                            <div class="flex items-center justify-between">
                                <div>
                                    <h5 class="text-sm font-medium text-gray-900">${cotacao.titulo}</h5>
                                    <p class="text-xs text-gray-500">${cotacao.data}</p>
                                </div>
                                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                    cotacao.status === 'aprovada' ? 'bg-success/10 text-success' :
                                    cotacao.status === 'reprovada' ? 'bg-error/10 text-error' :
                                    'bg-warning/10 text-warning'
                                }">
                                    ${cotacao.status}
                                </span>
                            </div>
                        </div>
                    `).join('') : `
                        <div class="p-8 text-center">
                            <p class="text-sm text-gray-500">Nenhuma cotação encontrada</p>
                        </div>
                    `}
                </div>
            </div>
        `;
    }

    renderOperacaoTab(data) {
        return `
            <div class="space-y-6">
                <!-- Status Atual -->
                <div class="p-4 bg-gray-50 rounded-lg">
                    <h4 class="text-sm font-semibold text-gray-900 mb-3">Status Operacional</h4>
                    <div class="flex items-center space-x-4">
                        <div class="flex-1">
                            <div class="h-2 bg-gray-200 rounded-full overflow-hidden">
                                <div class="h-full bg-primary" style="width: ${data.progresso || 0}%"></div>
                            </div>
                        </div>
                        <span class="text-sm font-medium text-gray-900">${data.progresso || 0}%</span>
                    </div>
                </div>

                <!-- Etapas -->
                <div class="border rounded-lg divide-y">
                    <div class="p-4">
                        <h4 class="text-sm font-semibold text-gray-900">Fluxo de Operação</h4>
                    </div>
                    ${data.etapas?.map((etapa, index) => `
                        <div class="p-4 flex items-start space-x-4">
                            <div class="flex-shrink-0 w-6 h-6 rounded-full ${
                                etapa.concluida ? 'bg-success' : 'bg-gray-200'
                            } flex items-center justify-center">
                                <i class="fas fa-check text-white text-xs"></i>
                            </div>
                            <div class="flex-1 min-w-0">
                                <h5 class="text-sm font-medium text-gray-900">${etapa.titulo}</h5>
                                <p class="text-xs text-gray-500">${etapa.descricao}</p>
                            </div>
                            ${etapa.data ? `
                                <span class="text-xs text-gray-500">${etapa.data}</span>
                            ` : ''}
                        </div>
                    `).join('') || `
                        <div class="p-8 text-center">
                            <p class="text-sm text-gray-500">Nenhuma etapa configurada</p>
                        </div>
                    `}
                </div>
            </div>
        `;
    }

    renderFinanceiroTab(data) {
        return `
            <div class="space-y-6">
                <!-- Resumo Financeiro -->
                <div class="grid grid-cols-2 gap-4">
                    <div class="p-4 bg-success/10 rounded-lg">
                        <div class="text-2xl font-bold text-success">
                            R$ ${(data.total_recebido || 0).toLocaleString('pt-BR')}
                        </div>
                        <div class="text-xs text-gray-500">Total Recebido</div>
                    </div>
                    <div class="p-4 bg-warning/10 rounded-lg">
                        <div class="text-2xl font-bold text-warning">
                            R$ ${(data.total_pendente || 0).toLocaleString('pt-BR')}
                        </div>
                        <div class="text-xs text-gray-500">Total Pendente</div>
                    </div>
                </div>

                <!-- Últimas Transações -->
                <div class="border rounded-lg">
                    <div class="p-4 border-b">
                        <h4 class="text-sm font-semibold text-gray-900">Últimas Transações</h4>
                    </div>
                    ${data.transacoes?.length ? data.transacoes.map(transacao => `
                        <div class="p-4 border-b last:border-0 hover:bg-gray-50">
                            <div class="flex items-center justify-between">
                                <div>
                                    <h5 class="text-sm font-medium text-gray-900">${transacao.descricao}</h5>
                                    <p class="text-xs text-gray-500">${transacao.data}</p>
                                </div>
                                <span class="text-sm font-medium ${
                                    transacao.tipo === 'entrada' ? 'text-success' : 'text-error'
                                }">
                                    ${transacao.tipo === 'entrada' ? '+' : '-'}
                                    R$ ${transacao.valor.toLocaleString('pt-BR')}
                                </span>
                            </div>
                        </div>
                    `).join('') : `
                        <div class="p-8 text-center">
                            <p class="text-sm text-gray-500">Nenhuma transação encontrada</p>
                        </div>
                    `}
                </div>

                <!-- Status de Pagamento -->
                <div class="p-4 border rounded-lg">
                    <h4 class="text-sm font-semibold text-gray-900 mb-3">Status de Pagamento</h4>
                    <div class="space-y-3">
                        <div class="flex justify-between items-center">
                            <span class="text-sm text-gray-500">Último Pagamento</span>
                            <span class="text-sm font-medium">${data.ultimo_pagamento || '-'}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-sm text-gray-500">Próximo Vencimento</span>
                            <span class="text-sm font-medium">${data.proximo_vencimento || '-'}</span>
                        </div>
                        <div class="flex justify-between items-center">
                            <span class="text-sm text-gray-500">Status</span>
                            <span class="inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                                data.status_pagamento === 'em_dia' ? 'bg-success/10 text-success' :
                                data.status_pagamento === 'atrasado' ? 'bg-error/10 text-error' :
                                'bg-warning/10 text-warning'
                            }">
                                ${data.status_pagamento === 'em_dia' ? 'Em dia' :
                                  data.status_pagamento === 'atrasado' ? 'Atrasado' : 'Pendente'}
                            </span>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }

    showLoading() {
        document.querySelectorAll('[role="tabpanel"]').forEach(panel => {
            panel.innerHTML = this.getLoadingHTML();
        });
    }

    showError() {
        document.querySelectorAll('[role="tabpanel"]').forEach(panel => {
            panel.innerHTML = this.getErrorHTML();
        });
    }

    getLoadingHTML() {
        return `
            <div class="flex items-center justify-center h-96">
                <div class="text-center">
                    <div class="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p class="text-sm text-gray-500">Carregando informações...</p>
                </div>
            </div>
        `;
    }

    getErrorHTML() {
        return `
            <div class="flex items-center justify-center h-96">
                <div class="text-center">
                    <i class="fas fa-exclamation-circle text-error text-2xl mb-4"></i>
                    <p class="text-sm text-gray-500">Erro ao carregar informações</p>
                    <button onclick="clientDetailsSidebar.retry()" class="mt-4 text-primary text-sm hover:underline">
                        Tentar novamente
                    </button>
                </div>
            </div>
        `;
    }

    retry() {
        if (this.currentClientId) {
            this.open(this.currentClientId);
        }
    }
}

// Initialize the sidebar
const clientDetailsSidebar = new ClientDetailsSidebar();

// Add click handlers to detail buttons
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('[data-client-details]').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            const clientId = e.currentTarget.dataset.clientDetails;
            clientDetailsSidebar.open(clientId);
        });
    });
});