# Reports Design Audit & Improvement Plan

## Status de Cada Página

### ✅ 1. Dados de mídia (`monitor`) - CONCLUÍDO
- **Status**: ✓ Novo design implementado
- **Melhorias**: Hero section, sidebar com KPIs, layout responsivo
- **Commits**: 3e3cf24d, 0a4f40df

### 2. Visão geral (`overview`)
- **Estrutura**: Dashboard com cards, gráficos e tabela
- **Pontos fracos**: Layout denso, sem hero section, cards sem hierarquia
- **Propostas de melhoria**:
  - ✨ Adicionar hero section "Resultados da operação"
  - 📊 Melhorar grid de cards KPI (sessões, cliques, conversões)
  - 📱 Responsividade melhor para mobile
  - 🎨 Melhor espaçamento entre elementos

### 3. Clientes e anunciantes (`customers`)
- **Estrutura**: Componente `ReportsCustomers` - ainda precisa localizar
- **Propostas de melhoria**:
  - ✨ Hero section "Organize seus clientes"
  - 📋 Melhorar listagem com cards em grid
  - ➕ Adicionar CTA destacada para novo cliente

### 4. Contas (`accounts`)
- **Estrutura**: Tabela com filtros e formulário
- **Pontos fracos**: Interface pesada, sem visual hierarchy
- **Propostas de melhoria**:
  - ✨ Hero section "Gerencie suas contas"
  - 🔍 Melhorar filtros com melhor UX
  - 📱 Cards em grid em mobile ao invés de tabela

### 5. Campanhas (`campaigns`)
- **Estrutura**: Tabela com dados, filtros avançados
- **Pontos fracos**: Tabela muito densa, difícil de ler
- **Propostas de melhoria**:
  - ✨ Hero section "Acompanhe suas campanhas"
  - 📊 KPI cards no topo (total de campanhas, gastos, ROI)
  - 🔄 Melhor visual para status (ativa/pausada/encerrada)

### 6. Relatórios (`reports`)
- **Estrutura**: Criador e listador de relatórios
- **Pontos fracos**: Interface confusa, sem clara CTA
- **Propostas de melhoria**:
  - ✨ Hero section "Crie relatórios de mídia"
  - ➕ Botão destacado "Novo relatório"
  - 📋 Grid de relatórios salvos com cards

### 7. Importações (`imports`)
- **Estrutura**: Upload, visualização e edição de dados
- **Pontos fracos**: Formulário complexo, muitas opções
- **Propostas de melhoria**:
  - ✨ Hero section "Envie e valide dados"
  - 📤 Dropzone melhorada
  - 📋 Timeline de importações clara

### 8. Super Tag (`supertag`)
- **Estrutura**: Sites, eventos, estatísticas
- **Status**: Já tem mockup com bom design
- **Propostas de melhoria**:
  - ✓ Mantém hero section
  - 📊 Melhorar cards de estatísticas
  - 🎨 Unificar espaçamento com outras páginas

### 9. Fluxos (`flow`)
- **Estrutura**: Listador e editor visual de fluxos
- **Pontos fracos**: Falta organização visual
- **Propostas de melhoria**:
  - ✨ Hero section "Desenhe jornadas do cliente"
  - 🏗️ Grid melhor para fluxos
  - 📊 Cards com preview de fluxo

### 10. Eventos (`events`)
- **Estrutura**: Explorador de eventos com filtros
- **Pontos fracos**: Interface complexa, sem hierarquia
- **Propostas de melhoria**:
  - ✨ Hero section "Explore a atividade"
  - 🔍 Filtros em sidebar (tipo fluxos)
  - 📊 Timeline de eventos clara

### 11. Link Tester (`links`)
- **Estrutura**: Validador e rastreador de links
- **Pontos fracos**: Interface simples mas sem design
- **Propostas de melhoria**:
  - ✨ Hero section "Verifique destinos"
  - 🔗 Cards para cada link testado
  - ✅ Visual claro de status (válido/quebrado)

### 12. Acessos (`access`)
- **Estrutura**: Gerenciador de permissões
- **Pontos fracos**: Padrão, sem hierarquia visual
- **Propostas de melhoria**:
  - ✨ Hero section "Gerencie permissões"
  - 👥 Cards ou lista melhorada de usuários
  - 🔐 Badges de role/permissão claras

---

## Padrão de Design a Aplicar

### Hero Section Padrão
```jsx
<div className="reports-page-hero">
  <div className="reports-page-hero__inner">
    <div className="reports-page-hero__eyebrow">Categoria</div>
    <h1>Título da Página</h1>
    <p>Descrição clara do que faz nesta página</p>
  </div>
</div>
```

### Cores Padrão
- **Eyebrow**: #155fce (azul)
- **Background gradient**: #f0f5ff → #dce8ff
- **Text primary**: #17241f
- **Text secondary**: #627168
- **Border**: #e0e8f0

### Espaçamento Padrão
- **Gap between sections**: 24px
- **Padding cards**: 24px (desktop), 16px (mobile)
- **Gap between cards**: 20px

### Responsive Breakpoints
- **Desktop**: Sem alterações
- **Tablet (≤1000px)**: Adaptar grids 2→1 coluna
- **Mobile (≤700px)**: Ajustar padding e font sizes

---

## Plano de Implementação

### Fase 1: Base CSS
1. Criar classe `.reports-page-hero` reutilizável
2. Melhorar `.reports-panel` base
3. Adicionar `.reports-page-main` para container

### Fase 2: Páginas de Alta Prioridade
1. ✅ Dados de mídia (monitor) - DONE
2. ⏳ Visão geral (overview)
3. ⏳ Campanhas (campaigns)
4. ⏳ Eventos (events)

### Fase 3: Páginas Médias
5. ⏳ Contas (accounts)
6. ⏳ Importações (imports)
7. ⏳ Fluxos (flow)

### Fase 4: Páginas Menores
8. ⏳ Relatórios (reports)
9. ⏳ Link Tester (links)
10. ⏳ Acessos (access)
11. ⏳ Clientes (customers)
12. ⏳ Super Tag (supertag) - ajustes
