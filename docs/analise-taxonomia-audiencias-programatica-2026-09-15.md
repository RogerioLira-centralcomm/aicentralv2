# Análise da base de audiências programáticas e proposta de taxonomia

Data da leitura: 15/09/2026
Escopo: análise somente leitura; nenhuma alteração realizada no banco ou no produto.

## 1. Resumo executivo

O catálogo não deve ser apresentado como uma tabela de segmentos com preço. Ele deve funcionar como uma biblioteca de possibilidades para o cliente reconhecer seu mercado, explorar estratégias e então pedir uma cotação ou um plano de mídia.

A leitura do banco encontrou **935 itens**, não apenas os “mais de 380” inicialmente estimados:

- **400** itens da plataforma `Programática`;
- **535** itens de fontes ou inventários específicos: Serasa, G1/Globo.com, Prime Video, CNN Brasil, Netflix, SBT, InfoMoney, Spotify Ads e DV360.

O problema principal não é falta de catálogo; é falta de arquitetura de descoberta. Hoje estão misturados no mesmo nível:

- mercado do anunciante, como finanças ou varejo;
- perfil de pessoa, como faixa etária ou renda;
- intenção ou comportamento, como comprar imóvel ou buscar crédito;
- contexto editorial, como política, esportes ou economia;
- canal/inventário, como Netflix, G1 ou Spotify;
- técnica de ativação, como retargeting, lookalike, CRM match ou keywords.

Por isso, a categoria atual não responde com clareza à primeira pergunta do cliente: **“quais audiências fazem sentido para o meu negócio?”**

## 2. Retrato da base atual

### 2.1 Catálogo completo — 935 itens

| Categoria atual | Itens | Participação |
|---|---:|---:|
| Entretenimento & Mídia | 390 | 41,7% |
| Consumo & Varejo | 204 | 21,8% |
| B2B & Indústria | 165 | 17,6% |
| Finanças & Seguros | 96 | 10,3% |
| Mobilidade | 46 | 4,9% |
| Saúde & Bem-estar | 22 | 2,4% |
| Educação & Carreira | 12 | 1,3% |
| Tecnologia & Telecom | 0 | 0,0% |

A concentração de 41,7% em “Entretenimento & Mídia” é causada principalmente pela classificação de inventários editoriais e de streaming como se fossem mercados. Dentro dela estão, por exemplo, demografia, gêneros de conteúdo, formatos, contexto editorial, retargeting e audiências próprias de publishers.

### 2.2 Recorte da plataforma Programática — 400 itens

| Categoria atual | Itens | Participação |
|---|---:|---:|
| B2B & Indústria | 123 | 30,8% |
| Consumo & Varejo | 120 | 30,0% |
| Entretenimento & Mídia | 47 | 11,8% |
| Mobilidade | 40 | 10,0% |
| Finanças & Seguros | 36 | 9,0% |
| Saúde & Bem-estar | 22 | 5,5% |
| Educação & Carreira | 12 | 3,0% |
| Tecnologia & Telecom | 0 | 0,0% |

Mesmo no recorte estritamente programático, “B2B & Indústria” agrupa mercados muito diferentes: imobiliário, construção, agronegócio, logística, tecnologia, porte empresarial, senioridade e função profissional. “Consumo & Varejo” também absorve demografia, renda, pets, alimentação, beleza e comportamento de compra.

### 2.3 Fontes e inventários

| Fonte/plataforma | Itens |
|---|---:|
| Programática | 400 |
| Serasa | 98 |
| G1 / Globo.com | 87 |
| Prime Video | 80 |
| CNN Brasil | 65 |
| Netflix | 60 |
| SBT | 57 |
| InfoMoney | 51 |
| Spotify Ads | 36 |
| DV360 | 1 |

Essas fontes devem virar **filtros de disponibilidade/ativação**, não categorias principais do catálogo.

## 3. Problemas de qualidade e consistência

### 3.1 A relação categoria–subcategoria está quebrada

- **525 itens (56,1%)** não possuem subcategoria.
- **410 itens (43,9%)** possuem subcategoria.
- Os **410 vínculos preenchidos são incompatíveis**: a audiência foi migrada para uma categoria nova, mas a subcategoria continuou ligada à categoria legada.

Exemplos:

- categoria atual `B2B & Indústria` com subcategoria legada `Buscando Imóveis para Comprar`;
- categoria atual `Consumo & Varejo` com subcategoria legada `Renda Familiar`;
- categoria atual `Mobilidade` com subcategoria legada `Planejando Férias`;
- categoria atual `Entretenimento & Mídia` com subcategoria legada `Consumidores de Notícias`.

Na prática, não existe hoje uma árvore de categorias/subcategorias confiável para uso no produto.

### 3.2 Categorias novas sem acabamento

Existem 8 categorias ativas e 14 categorias legadas inativas. Nas categorias ativas:

- todas têm `ordem_exibicao = 0`;
- descrições, ícones e metadados estão vazios;
- `total_audiencias` armazenado está zerado, embora a consulta calcule a contagem dinamicamente;
- `Tecnologia & Telecom` está ativa, mas não tem audiência vinculada.

### 3.3 Duplicidades e nomenclatura

- Foram encontrados nomes exatamente repetidos após normalização de caixa e espaços, incluindo “Tecnologia”, “Mulheres (geral)”, “Homens (geral)”, “Keywords contextuais”, “Branded content”, “Mobile” e “Video pre-roll”.
- Há **5 IDs externos de audiência repetidos**.
- Os slugs são únicos, mas isso mascara duplicidades semânticas entre fontes.
- Há variações como `Mulheres geral`, `Mulheres (Geral)` e `Mulheres Serasa`, que deveriam compartilhar um conceito canônico e preservar a fonte como atributo.
- Existe ao menos um item claramente defeituoso: `Audiencia UNKNOWN_unknown-sem-nome`.

Duplicidade entre fontes nem sempre significa erro: “Mulheres 25–44 no G1” e “Mulheres 25–44 na CNN” são ativações diferentes. O erro é tratá-las como conceitos totalmente diferentes. A solução é separar **conceito de audiência** de **oferta disponível por plataforma**.

### 3.4 Campos editoriais e de evidência

Cobertura relevante:

| Campo | Cobertura |
|---|---:|
| Nome, slug, título, descrição curta | 100% |
| Tags | 99,7% |
| Propensão de compra | 97,5% |
| Descrição longa/comercial/caso de uso/diferenciais | 72,2% |
| Momentos, interesses correlatos e categorias de desempenho | 71,9% |
| Insights de planejamento | 0% |

A base aparenta ter muito conteúdo estimado ou gerado, porém não explicita no catálogo a procedência de cada afirmação. Para ganhar confiança comercial, “fonte”, “natureza do sinal”, “atualização” e “nível de confiança” precisam ter mais peso que métricas estimadas de performance.

### 3.5 Segunda passada: o catálogo contém entidades diferentes

Uma classificação estrutural item a item, feita sobre os 935 registros e preservada em CSV para revisão, encontrou esta composição preliminar:

| Papel real no catálogo | Registros físicos |
|---|---:|
| Conceito de audiência | 436 |
| Contexto/afinidade de conteúdo | 327 |
| Perfil transversal | 82 |
| Formato ou pacote de inventário | 52 |
| Tática de ativação | 37 |
| Inválido/quarentena | 1 |

Essa é uma descoberta central: **os 935 registros não são 935 conceitos comparáveis de audiência**. Uma parte relevante são ofertas, filtros, formatos ou modos de ativação. Antes de deduplicar, é necessário separar esses papéis.

No recorte de 400 registros da plataforma Programática, a leitura preliminar encontrou 349 conceitos de audiência, 36 perfis transversais, 11 contextos/afinidades e 4 táticas de ativação.

A proposta automatizada marcou 455 mapeamentos com confiança alta e 480 com confiança média. Confiança média não significa erro; significa que a regra encontrou sobreposição de mercados, subcategoria legada, conceito sem submercado específico ou possível consolidação. Esses registros formam a fila editorial humana antes da migração.

### 3.6 Distribuição preliminar na nova taxonomia

Considerando registros físicos — ainda sem consolidar conceitos repetidos por fornecedor — o primeiro mapeamento ficou assim:

| Mercado principal proposto | Registros |
|---|---:|
| Entretenimento, Conteúdo & Esportes | 131 |
| Varejo & Consumo | 91 |
| B2B, Enterprise & Indústria | 93 |
| Finanças & Seguros | 81 |
| Automotivo, Mobilidade & Logística | 44 |
| Saúde, Bem-estar & Beleza | 37 |
| Imobiliário & Construção | 32 |
| Agronegócio | 30 |
| Educação & Carreira | 21 |
| Serviços ao Consumidor | 22 |
| Transversal/sem mercado obrigatório | 353 |

Os números não representam ainda o tamanho final de cada coleção. Um mesmo conceito pode aparecer em vários fornecedores, e ofertas contextuais de publishers aumentam principalmente Entretenimento e Finanças. A próxima etapa editorial deve consolidar os conceitos antes de usar essas contagens na interface.

## 4. Nova arquitetura recomendada

A recomendação é substituir a árvore única por uma arquitetura facetada com quatro camadas.

### A organização fará parte de cada audiência?

**Sim, mas com uma distinção importante.** A organização será metadado de cada conceito de audiência, e não um rótulo único aplicado indistintamente a toda linha da base.

- Conceitos verticais recebem `mercado_principal`, zero ou mais `mercados_relacionados` e um `submercado`.
- Conceitos genéricos, como idade, gênero, renda e momento de vida, recebem `escopo = transversal`; não precisam de mercado principal.
- Contextos editoriais podem se relacionar a mercados, mas continuam identificados como contexto, não como audiência comportamental.
- Táticas como lookalike, CRM match e retargeting pertencem à estratégia de ativação.
- Formatos como pre-roll, native e branded content pertencem à oferta de mídia.
- As linhas de fornecedores passam a ser ofertas de ativação ligadas a um conceito canônico.

Exemplo: `Compradores de imóveis` terá mercado principal `Imobiliário & Construção`, poderá ter relação com `Finanças & Seguros`, sinal `Intenção de compra` e estágio `Consideração/Conversão`. Já `Mulheres 25–44` será transversal e poderá ser combinada com qualquer mercado. `Retargeting de visitantes` será uma tática, não uma audiência vertical.

### Camada 1 — Mercado principal do cliente

É a porta de entrada e o agrupamento que deve ficar em evidência para conceitos verticais. Perfis, contextos e táticas transversais aparecem como coleções complementares.

1. **Imobiliário & Construção**
   - Compra de imóveis
   - Aluguel de imóveis
   - Investimento imobiliário
   - Lançamentos e alto padrão
   - Construção, reforma e materiais
   - Arquitetura, decoração e urbanismo
   - Profissionais e empresas do setor

2. **Finanças & Seguros**
   - Bancos e contas digitais
   - Crédito e empréstimos
   - Cartões e meios de pagamento
   - Investimentos e patrimônio
   - Seguros
   - Previdência
   - Fintechs
   - Educação financeira

3. **Varejo & Consumo**
   - Compradores e e-commerce
   - Moda e acessórios
   - Beleza e cuidados pessoais
   - Eletrônicos e eletrodomésticos
   - Casa e decoração
   - Alimentos e bebidas
   - Supermercados e delivery
   - Pets
   - Ofertas e sazonalidades de varejo

4. **Serviços ao Consumidor**
   - Saúde e serviços médicos
   - Educação e cursos
   - Jurídico e contabilidade
   - Turismo e hospitalidade
   - Telecom e conectividade
   - Serviços residenciais
   - Serviços profissionais e locais
   - Assinaturas e serviços digitais

5. **B2B, Enterprise & Indústria**
   - C-level, diretoria e decisores
   - Finanças, RH, marketing, vendas, TI e operações
   - Pequenas e médias empresas
   - Grandes empresas e enterprise
   - Indústria e manufatura
   - Tecnologia e software B2B
   - Construção e infraestrutura B2B
   - Serviços corporativos
   - Atacado e distribuição

6. **Automotivo, Mobilidade & Logística**
   - Compra e troca de veículos
   - Categorias de veículos
   - Serviços automotivos
   - Mobilidade urbana e aplicativos
   - Viagens e transporte de passageiros
   - Transporte de cargas
   - Logística, armazenagem e operadores 3PL/4PL
   - Empresas e decisores do setor

7. **Agronegócio**
   - Produtores rurais
   - Pecuária
   - Insumos e fertilizantes
   - Máquinas e equipamentos
   - Veterinária e saúde animal
   - Agroindústria
   - Empresas, serviços e decisores do agro

8. **Saúde, Bem-estar & Beleza**
   - Saúde e prevenção
   - Planos de saúde
   - Profissionais e empresas de saúde
   - Fitness e esportes praticados
   - Nutrição e alimentação saudável
   - Beleza e cosméticos
   - Maternidade e cuidados infantis
   - Produtos e equipamentos médicos

9. **Educação & Carreira**
   - Ensino básico e famílias
   - Graduação e pós-graduação
   - Cursos livres e profissionalizantes
   - Idiomas
   - Pré-vestibular e concursos
   - Desenvolvimento profissional
   - Instituições, profissionais e decisores de educação

10. **Entretenimento, Conteúdo & Esportes**
    - Esportes e futebol
    - Games
    - Cinema e séries
    - Música e shows
    - Notícias e atualidades
    - Cultura e entretenimento
    - Conteúdo infantil e familiar

Os cinco primeiros grupos refletem diretamente os mercados citados como prioritários. Os demais evitam que verticais materialmente diferentes sejam novamente escondidas dentro de “Serviços”, “Consumo” ou “B2B”.

### Coleções transversais, fora da árvore de mercados

- Demografia e fase de vida;
- Renda e perfil socioeconômico;
- Geografia e comportamento local;
- Contextos, conteúdos e palavras-chave;
- Dados próprios, CRM e retargeting;
- Audiências semelhantes/modeladas;
- Formatos, dispositivos e inventário;
- Datas sazonais e eventos.

### Camada 2 — Objetivo ou momento da campanha

Esta camada responde “o que o cliente quer alcançar?” e deve ser transversal aos mercados:

- Conhecimento e alcance;
- Consideração e afinidade;
- Intenção ativa;
- Aquisição/conversão;
- Visita a loja ou ponto de interesse;
- Reengajamento/retargeting;
- Fidelização e base própria;
- Sazonalidade e momento de vida.

### Camada 3 — Natureza do sinal

- Interesse/afinidade;
- Intenção de compra;
- Comportamento de consumo;
- Dados demográficos;
- Renda e perfil socioeconômico;
- Cargo, função e senioridade;
- Empresa, setor, porte e maturidade;
- Localização e visitação física;
- Contexto editorial/keywords;
- Consumo de conteúdo;
- Dados próprios/CRM;
- Lookalike/modelado;
- Retargeting.

### Camada 4 — Disponibilidade de ativação

- Plataforma ou publisher;
- Canal/formato: display, vídeo, CTV, áudio, native etc.;
- Cobertura geográfica;
- Escala/faixa de alcance, quando houver dado verificável;
- Atualização e procedência;
- Restrições de uso;
- Disponibilidade mediante cotação.

## 5. Modelo de dados normalizado

Uma audiência comercial não deveria ser uma linha isolada que repete o mesmo conceito em cada publisher. O modelo recomendado separa:

1. **Conceito de audiência** — nome canônico e descrição do público;
2. **Mercados relacionados** — relação muitos-para-muitos, com mercado primário para conceitos verticais e valor nulo para transversais;
3. **Objetivos/momentos** — relação muitos-para-muitos;
4. **Sinais** — interesse, intenção, demografia, B2B, contexto, CRM etc.;
5. **Ofertas de ativação** — fonte, plataforma, ID externo, canal, geografia e disponibilidade;
6. **Evidências** — origem, data, metodologia, confiança e campos estimados;
7. **Conteúdo comercial** — benefício, caso de uso e recomendação de planejamento.

Exemplo conceitual:

`Compradores de imóveis` é o conceito canônico. Ele pode se relacionar a `Imobiliário & Construção`, ter objetivo `Aquisição`, sinal `Intenção de compra` e possuir ofertas separadas em Programática, Serasa ou publishers. Assim, o cliente encontra uma ideia uma única vez e depois descobre onde ela pode ser ativada.

### Campos canônicos mínimos

| Grupo | Campos |
|---|---|
| Identidade | `canonical_name`, `slug`, `short_description` |
| Navegação | `market_scope`, `primary_market`, `related_markets`, `submarkets` |
| Tipo de entidade | `catalog_role`: conceito, contexto, perfil, tática, formato ou oferta |
| Estratégia | `funnel_stage`, `campaign_objectives`, `recommended_use_cases` |
| Sinal | `signal_type`, `intent_level`, `b2b_b2c`, `data_origin` |
| Ativação | `provider`, `external_id`, `channels`, `geography`, `availability_status` |
| Qualidade | `source_date`, `confidence_level`, `is_estimated`, `restrictions` |
| Produto | `featured`, `display_order`, `quote_required`, `curation_status` |

## 6. Regras de normalização

1. Manter o nome do conceito curto, legível e no plural: `Compradores de imóveis`, não uma frase longa de fornecedor.
2. Remover do nome canônico a fonte, metodologia e geografia; guardar esses dados em campos próprios.
3. Padronizar gênero e idade: `Mulheres`, `Homens`, `18–24`, `25–34`, `35–44`, `45–54`, `55+`.
4. Padronizar renda em uma única régua e marcar a fonte/metodologia; não misturar classes sociais e faixas de renda como equivalentes.
5. Diferenciar explicitamente `Interesse`, `Afinidade`, `Intenção`, `Compra`, `Visita`, `Cargo/Função`, `Contextual`, `CRM`, `Lookalike` e `Retargeting`.
6. Marcar cada item como `B2C`, `B2B` ou `Híbrido`.
7. Permitir vários mercados relacionados; exigir mercado primário apenas para conceitos verticais e usar `escopo = transversal` nos demais.
8. Tratar publisher/plataforma como oferta de ativação, nunca como mercado.
9. Consolidar conceitos duplicados sem apagar ofertas específicas por fonte.
10. Colocar itens defeituosos, obsoletos ou sem origem em quarentena editorial.
11. Não exibir estimativas de CTR, conversão, CPA ou tamanho de mercado como promessa comercial sem metodologia e atualização verificáveis.
12. Preservar o registro original e a decisão de mapeamento em trilha de auditoria.

## 7. Orientação do produto

### O que deve ficar em evidência

Na entrada do catálogo:

1. pergunta ou seleção de **mercado do cliente**;
2. cards dos mercados prioritários;
3. sugestões de públicos organizadas por objetivo;
4. filtros por intenção, perfil, momento, geografia e canal;
5. detalhe com “por que usar”, “quando usar”, “como pode ser ativada” e fontes disponíveis;
6. seleção de audiências em uma lista de interesse;
7. CTA principal: **Pedir plano de mídia**;
8. CTA secundário: **Solicitar cotação destas audiências**.

O cliente deve conseguir explorar sem interpretar IDs técnicos, CPMs ou diferenças entre fornecedores.

### O que não deve comandar a experiência agora

- preço/CPM;
- carrinho com linguagem de e-commerce;
- ordenação por plataforma;
- métricas estimadas tratadas como garantia;
- árvore rígida de uma categoria e uma subcategoria;
- centenas de cards quase idênticos no primeiro nível.

Preço pode continuar no backoffice e no fluxo de elaboração comercial, mas não agrega valor à fase de descoberta descrita. O produto vende **capacidade de encontrar e combinar públicos relevantes**, não uma unidade avulsa de audiência.

## 8. Sequência recomendada de saneamento

1. Congelar a taxonomia atual para evitar novos vínculos inconsistentes.
2. Criar a lista canônica dos 10 mercados e suas subcategorias.
3. Separar conceito de audiência e oferta por plataforma.
4. Classificar automaticamente os 935 itens por regras e semântica, permitindo múltiplos mercados.
5. Revisar manualmente os itens ambíguos, regulados e B2B/B2C híbridos.
6. Consolidar duplicidades conceituais e preservar as ativações por fonte.
7. Colocar registros inválidos ou sem nome em quarentena.
8. Só então redesenhar a navegação e os CTAs do catálogo.

## 9. Critério de sucesso

A nova organização funciona quando um cliente consegue, sem conhecer programática:

- entrar pelo próprio mercado;
- entender os tipos de público disponíveis;
- comparar estratégias, não apenas fornecedores;
- selecionar possibilidades relevantes;
- pedir um plano de mídia ou cotação com contexto suficiente para o time comercial.

Essa deve ser a direção central do produto nesta fase.
