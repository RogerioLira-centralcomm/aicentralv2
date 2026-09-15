# Inventário estrutural do Conversas PHP

Gerado por `scripts/inventory_cadu_conversations.py`; leitura local, sem executar PHP ou consultar banco.

Lexical candidates; aliases and methods are not independent user features. Table names are not verified database schemas.

## Resumo

- files: 60
- lines: 31650
- symbols: 726
- tool_aliases: 54
- tool_implementations: 18

## Escopo confirmado

Documentos pertencem ao Cadu Media/SmartPlanner e mantêm conexão com Conversas. Canais e formatos entram na migração.
Cotações, analytics e dados de mídia ficam fora desta migração do chat; sua presença abaixo é somente referência, sem exclusão de dados.

## Ferramentas: aliases agrupados por implementação

| Implementação | Escopo | Aliases |
|---|---|---|
| api/chat/tools/AnalyticsData.php | Fora desta migração | `analytics_data` (L306), `consultar_analytics` (L307), `dados_analytics` (L308) |
| api/chat/tools/AudienceSearch.php | Referência para reconstrução; não entregue | `audience_search` (L289), `audience_detail` (L290) |
| api/chat/tools/BriefingCreator.php | Referência para reconstrução; não entregue | `briefing` (L291), `briefing_create` (L292) |
| api/chat/tools/ChannelSearch.php | Referência para reconstrução; não entregue | `channel_search` (L334), `channel_detail` (L335), `canal_buscar` (L336), `canal_detalhe` (L337) |
| api/chat/tools/CotacaoCreator.php | Fora desta migração | `cotacao` (L303), `cotacao_create` (L304), `solicitar_cotacao` (L305) |
| api/chat/tools/CreativeAnalyzer.php | Referência para reconstrução; não entregue | `creative_analyze` (L288) |
| api/chat/tools/DocSaver.php | Conexão com Docs do Media/SmartPlanner | `doc` (L293), `doc_save` (L294), `save_doc` (L295) |
| api/chat/tools/FormatSearch.php | Referência para reconstrução; não entregue | `format_search` (L339), `format_detail` (L340), `formato_buscar` (L341), `formato_detalhe` (L342) |
| api/chat/tools/GoogleAdsData.php | Fora desta migração | `google_ads_data` (L316), `gads_data` (L317), `dados_google_ads` (L318) |
| api/chat/tools/GoogleAnalyticsData.php | Fora desta migração | `google_analytics_data` (L313), `ga_data` (L314), `dados_google_analytics` (L315) |
| api/chat/tools/ImageGenerator.php | Referência para reconstrução; não entregue | `image_generate` (L344), `generate_image` (L345), `gerar_imagem` (L346), `criar_imagem` (L347) |
| api/chat/tools/LinkTester.php | Referência para reconstrução; não entregue | `link_test` (L287) |
| api/chat/tools/LinkedInAdLibrary.php | Fora desta migração | `linkedin_ad_library` (L329), `linkedin_ads` (L330), `pesquisar_linkedin_ads` (L331), `linkedin_ad_search` (L332) |
| api/chat/tools/LinkedInAdsData.php | Fora desta migração | `linkedin_ads_data` (L325), `dados_linkedin_ads` (L326), `linkedin_campaigns` (L327) |
| api/chat/tools/MetaAdsData.php | Fora desta migração | `meta_ads_data` (L320), `meta_data` (L321), `dados_meta_ads` (L322), `facebook_ads_data` (L323) |
| api/chat/tools/Screenshot.php | Referência para reconstrução; não entregue | `screenshot_url` (L296), `screenshot` (L297) |
| api/chat/tools/SearchConsoleData.php | Fora desta migração | `search_console_data` (L310), `gsc_data` (L311), `dados_search_console` (L312) |
| api/chat/tools/WebSearch.php | Referência para reconstrução; não entregue | `web_search` (L298), `search_web` (L299), `web_scrape` (L300), `web_map` (L301), `web_crawl` (L302) |

## Evidências por arquivo

Cada identificador traz sua linha. Campos são candidatos: podem incluir parâmetros internos; não constituem uma API pública autorizada.

### api/chat/deep-search-health.php

238 linhas; SHA-256 `19ddb7bf24931d70707f5b0b0c5a6fbc65a8af1717326aba7452cd0b5846e274`.

**symbols**: `dsh_count_items` (L18); `dsh_first_domains` (L33); `foreach` (L41, 96, 171, 212, 223); `dsh_run_light` (L55); `dsh_run_deep_search_post` (L87)

**php_fields**: `full` (L16); `battery` (L16); `web` (L25, 25, 26, 40); `fontes` (L96); `found` (L104, 107); `http_status` (L106); `total` (L108); `creditsUsed` (L109); `error` (L110); `query` (L111)

### api/chat/deep-search.php

691 linhas; SHA-256 `20821ac962e8529c51d701dc8270792800f1aaa08e611311444eec1824c57713`.

**symbols**: `ds_clean_markdown` (L62); `ds_truncate` (L87); `ds_extract_content` (L102); `ds_normalize_scrape_formats` (L119); `ds_normalize_categories` (L126); `foreach` (L132, 202, 229, 264, 286, 326, 392, 457); `ds_resolve_exclude_domains` (L142); `ds_build_search_body_base` (L153); `ds_merge_items_from_response` (L191); `ds_search_many` (L218); `ds_build_angles` (L302); `ds_search_light` (L337); `ds_search_deep` (L362); `ds_process_items` (L384); `ds_fallback_context` (L489); `ds_execute` (L499)

**php_fields**: `excludeDomains` (L144, 144, 145); `country` (L156, 341); `location` (L157, 342); `categories` (L165); `tbs` (L170, 171, 345, 346, 538); `news` (L173, 201, 201, 202, 348, 368); `web` (L198, 198, 199); `query` (L503, 523); `q` (L503, 523); `continuation` (L524); `multiAngle` (L525); `topic` (L526); `limit` (L543)

### api/chat/tool-context.php

513 linhas; SHA-256 `f6bb37d7035decd3bed343c6595976697cea5ef9125120636a1c90a295d3d72b`.

**symbols**: `set_error_handler` (L15, 34); `foreach` (L96, 201, 239, 280, 325, 383, 405, 447, 466); `buildToolSummary` (L126); `summarizeAudience` (L198); `summarizeChannel` (L236); `summarizeFormat` (L277); `summarizeLinkTest` (L301); `summarizeCreativeAnalyze` (L313); `summarizeWebSearch` (L321); `summarizeWebScrape` (L337); `summarizeWebMap` (L368); `summarizeWebCrawl` (L396); `summarizeAnalytics` (L423); `summarizeSearchConsole` (L434); `summarizeGoogleAds` (L442); `summarizeMetaAds` (L461); `summarizeLinkedInAds` (L480); `summarizeLinkedInAdLibrary` (L491); `summarizeCotacao` (L506)

**php_fields**: `conversation_id` (L53); `limit` (L54); `url` (L183, 302, 314, 338, 370, 398); `device` (L183); `titulo` (L187, 191); `search` (L228, 233, 252, 274, 293, 298, 374, 375); `query` (L322, 492); `count` (L384); `links` (L385); `platform` (L424); `type` (L424, 435, 443, 462, 481); `audiencia` (L508); `objetivo` (L509); `budget` (L510)

**event_cases**: `audience_detail` (L128); `audience_search` (L129); `channel_detail` (L132); `channel_search` (L133); `format_detail` (L136); `format_search` (L137); `link_test` (L140); `creative_analyze` (L143); `web_search` (L146); `search_web` (L147); `web_scrape` (L150); `web_map` (L153); `web_crawl` (L156); `google_analytics_data` (L159); `analytics_data` (L160); `search_console_data` (L163); `google_ads_data` (L166); `meta_ads_data` (L169); `linkedin_ads_data` (L172); `linkedin_ad_library` (L175); `cotacao` (L178); `screenshot_url` (L181); `screenshot` (L182); `briefing` (L185); `briefing_create` (L186); `doc` (L189); `doc_save` (L190)

### api/chat/tools/AnalyticsData.php

235 linhas; SHA-256 `750744bec611c8c1f8c62aad6e9ba5d6926075009248c95879dbf3fa22baa329`.

**symbols**: `getToolType` (L20); `process` (L25); `formatCardData` (L169)

**php_fields**: `platform` (L27); `plataforma` (L27); `type` (L28); `tipo` (L28)

**event_cases**: `overview` (L124); `top_pages` (L127); `top_sources` (L130); `top_queries` (L133); `realtime` (L136); `devices` (L139); `campaigns` (L142); `all` (L145)

### api/chat/tools/AudienceSearch.php

574 linhas; SHA-256 `7c6b72509f1b759c89aafddad4995d1d36da0748383a98c054510283155582d1`.

**symbols**: `setMode` (L37); `getToolType` (L42); `process` (L46); `plataformaFilter` (L58); `formatCardData` (L68); `findAudienceIds` (L80); `searchExactMatch` (L110); `foreach` (L135, 158, 190, 208, 227, 257, 260, 286, 302, 403, 510); `searchFTS` (L143); `searchFTSAnyWord` (L166); `searchLikePerWord` (L203); `sanitizeSearchWords` (L269); `getSuggestions` (L280); `processDetail` (L336); `usort` (L394); `processSearch` (L470); `processImageUrl` (L533); `parseTags` (L546); `buildSlug` (L564)

**php_fields**: `plataforma_id` (L47, 47); `id` (L337); `search` (L338, 471); `limit` (L339, 472); `q` (L471)

**tables**: `cadu_audiencias` (L113, 149, 181, 247, 296, 313, 381, 501); `cadu_categorias` (L248, 295, 312, 382, 502); `cadu_subcategorias` (L383); `cadu_audiencias_plataformas` (L384, 503)

### api/chat/tools/BaseTool.php

448 linhas; SHA-256 `2d1f8e266e70ff803b7191fb35b9cf52c0a029fe4389ce1f9336c1fb9a6ff67f`.

**symbols**: `__construct` (L27); `setConversationContext` (L39); `run` (L69); `generateTitle` (L273); `generateDescription` (L306); `generateFallbackUuid` (L313); `findByUuid` (L327); `findByShareToken` (L358); `listByUser` (L391); `foreach` (L410); `togglePublic` (L423)

**php_fields**: `url` (L278); `context` (L283, 283); `search` (L286, 289); `q` (L286); `objetivo` (L293); `titulo` (L296)

**event_cases**: `link_test` (L277); `creative_analyze` (L282); `audience_search` (L285); `audience_detail` (L288); `briefing` (L292); `doc` (L295)

### api/chat/tools/BriefingCreator.php

144 linhas; SHA-256 `3750d2d88cf5050a30dd4c1abec30924d6811007b86d938d9ff06a74e0dfcd90`.

**symbols**: `getToolType` (L17); `process` (L21); `formatCardData` (L126); `generateDescription` (L130); `generateUuidV4` (L138)

**php_fields**: `titulo` (L22, 131); `title` (L22); `conteudo` (L23); `content` (L23); `briefing` (L23); `objetivo` (L24); `objective` (L24); `budget` (L25); `orcamento` (L25); `canais` (L26); `channels` (L26); `tags` (L27); `responsavel` (L28); `cliente` (L29)

**tables**: `tbl_briefings` (L57)

### api/chat/tools/ChannelSearch.php

388 linhas; SHA-256 `39cdb52e3381d3c6f6bc20d7946f78ba0f15d7fbe84c13cc8e4b82b695f9df31`.

**symbols**: `setMode` (L24); `getToolType` (L29); `process` (L33); `formatCardData` (L40); `processDetail` (L48); `processSearch` (L95); `foreach` (L114, 171, 193, 277); `findById` (L129); `findBySlugOrName` (L137); `searchByQuery` (L165); `searchByCategoria` (L201); `searchByTipo` (L214); `getPopularChannels` (L227); `getChannelNews` (L243); `getRelatedPlatforms` (L262); `buildChannelDetail` (L303); `buildChannelSummary` (L344); `parseJsonb` (L372); `sanitizeWords` (L381)

**php_fields**: `id` (L49); `search` (L50, 96); `slug` (L50); `q` (L96); `categoria` (L97); `category` (L97); `tipo` (L98); `type` (L98); `limit` (L99)

**tables**: `cadu_canais` (L131, 139, 152, 186, 203, 216, 229); `cadu_canais_noticias` (L247); `cadu_canais_plataformas_map` (L268); `cadu_audiencias_plataformas` (L269); `cadu_plataformas_formatos` (L270)

### api/chat/tools/CotacaoCreator.php

185 linhas; SHA-256 `9a0c0c8f6f06ef6f100367b684dbf0294ea0e650ae2ee3989a999e9d0527d131`.

**symbols**: `getToolType` (L23); `process` (L27); `formatCardData` (L172); `generateTitle` (L176); `generateDescription` (L181)

**php_fields**: `audiencia_id` (L29); `id` (L29); `audiencia` (L30, 177); `search` (L30); `nome` (L30); `nome_campanha` (L31); `campanha` (L31); `objetivo` (L32); `praca` (L33); `budget` (L34); `periodo_meses` (L35); `periodo` (L35); `observacoes` (L36)

**tables**: `cadu_audiencias` (L41, 77); `cadu_categorias` (L78); `cadu_subcategorias` (L79)

### api/chat/tools/CreativeAnalyzer.php

406 linhas; SHA-256 `17e20c105109d0afe584fa476a7e217d8101c78890179e110eae01009b09332c`.

**symbols**: `getToolType` (L18); `process` (L22); `formatCardData` (L99); `generateDescription` (L103); `verifyImage` (L114); `performAnalysis` (L161); `foreach` (L170); `downloadImage` (L330); `getFileSpecs` (L368)

**php_fields**: `url` (L23, 104); `context` (L24); `contexto` (L24)

### api/chat/tools/DocSaver.php

243 linhas; SHA-256 `c08a85e3544faf47f943a343a7b5b49666e0c8558f42e23a75674dd98f917050`.

**symbols**: `getToolType` (L21); `process` (L25); `formatCardData` (L51); `generateDescription` (L55); `saveAsArtifact` (L64); `saveAsDoc` (L183); `extractTitle` (L203); `foreach` (L211); `getArtifactColumns` (L226)

**php_fields**: `conteudo` (L26, 57); `content` (L26); `markdown` (L26); `titulo` (L27, 56); `title` (L27); `tipo` (L28); `type` (L28); `formato` (L29); `format` (L29)

**tables**: `cadu_artifacts` (L129)

### api/chat/tools/FormatSearch.php

400 linhas; SHA-256 `f4ceb6d9f5a159dee39e7428261bc1390359c32ff06ec65b5589069285e7491d`.

**symbols**: `setMode` (L24); `getToolType` (L29); `process` (L33); `formatCardData` (L40); `processDetail` (L48); `processSearch` (L99); `foreach` (L118, 201, 226, 251); `findById` (L136); `findByNameOrSlug` (L149); `searchByQuery` (L189); `searchByPlataforma` (L234); `searchByTipo` (L259); `getPopularFormats` (L275); `getRelatedFormats` (L290); `getPlataformasList` (L307); `buildFormatDetail` (L327); `buildFormatSummary` (L369); `sanitizeWords` (L393)

**php_fields**: `id` (L49); `search` (L50, 100); `nome` (L50); `plataforma` (L51, 101); `plataforma_slug` (L51, 101); `q` (L100); `tipo` (L102); `type` (L102); `limit` (L103)

**tables**: `cadu_formatos` (L140, 160, 176, 220, 245, 263, 279, 294, 312); `cadu_plataformas_formatos` (L141, 161, 177, 221, 246, 264, 280, 295, 311)

### api/chat/tools/GoogleAdsData.php

146 linhas; SHA-256 `1345d40502c69a0188f039ff53bd4650e3687646b8975d161bb8953499e5f090`.

**symbols**: `getToolType` (L17); `process` (L22); `formatCardData` (L83); `foreach` (L106); `generateTitle` (L133)

**php_fields**: `type` (L24, 135); `tipo` (L24); `overview` (L65); `campaigns` (L66)

**event_cases**: `overview` (L55); `campaigns` (L58); `all` (L61)

### api/chat/tools/GoogleAnalyticsData.php

230 linhas; SHA-256 `e5f5bf20cbad76489187e54d60a84cbb1be024c56cc09ed122f8767d41c7a2ed`.

**symbols**: `getToolType` (L17); `process` (L22); `formatCardData` (L95); `foreach` (L126, 140); `generateTitle` (L215)

**php_fields**: `type` (L24, 217); `tipo` (L24); `overview` (L74); `top_pages` (L75); `top_sources` (L76); `realtime` (L77)

**event_cases**: `overview` (L55); `top_pages` (L58); `pages` (L59); `top_sources` (L62); `sources` (L63); `traffic` (L64); `realtime` (L67); `all` (L70)

### api/chat/tools/ImageGenerator.php

1293 linhas; SHA-256 `9af30abbbca3fda3eece52ed97ce95cd13d7168af5c1992b1fe2e36185e83be2`.

**symbols**: `getToolType` (L96); `process` (L100); `foreach` (L114, 126, 304, 471, 612, 810, 852); `extractUsageMetadata` (L289); `calculateRealCost` (L336); `registerTokenUsage` (L371); `improvePrompt` (L454); `getStyleContext` (L506); `getAspectContext` (L524); `generateImage` (L539); `normalizeHeavyReferenceImage` (L654); `resolveReferenceImagePayload` (L704); `requestGeminiImageParts` (L752); `composeImages` (L849); `editImage` (L893); `handleApiError` (L926); `saveImageLocally` (L953); `aspectRatioToDimensions` (L1058); `convertImageToPng` (L1073); `formatTime` (L1125); `formatBytes` (L1141); `getGoogleApiKey` (L1150); `formatCardData` (L1174); `generateTitle` (L1195); `loadProjetoBrandingRow` (L1204); `enrichPromptWithBranding` (L1219); `shouldUseProjetoLogo` (L1246); `resolveBrandingLogoUrl` (L1271); `generateDescription` (L1288)

**php_fields**: `projeto_id` (L103); `prompt` (L105, 1196); `style` (L120); `aspect_ratio` (L121); `quality` (L122); `negative_prompt` (L123); `reference_images` (L125, 125, 126); `reference_image` (L136); `candidates` (L611, 612, 809, 810); `use_branding_logo` (L1248)

**tables**: `cadu_docs_client_images` (L1033)

### api/chat/tools/LinkTester.php

705 linhas; SHA-256 `58051f51937ed10064c2b9a0a4d678bb3de82bd818a4014a8d10c90ed90cd6dd`.

**symbols**: `getToolType` (L17); `process` (L21); `tryInternalApi` (L109); `formatCardData` (L170); `generateDescription` (L175); `ensureLinkAnalyzerLoaded` (L186); `extractClassWithTokenizer` (L246); `elseif` (L280, 324); `extractFunctionWithTokenizer` (L295); `extractSourceRange` (L339); `saveToLinkTestsTable` (L350); `extractMainData` (L405); `foreach` (L426, 497, 504, 514, 698); `sanitizeForJson` (L684)

**php_fields**: `url` (L23, 176); `success` (L151, 156); `data` (L156, 157, 158); `error` (L161); `ssl` (L406, 604, 605); `robots` (L407, 407, 408, 411, 412, 413, 414); `http_status` (L419); `httpCode` (L419); `tags` (L425, 425, 426); `screenshot` (L445, 446, 474); `performance` (L449, 450, 451, 452); `conversion` (L455); `compliance` (L466); `meta` (L471); `redirects` (L477, 478); `url_final` (L478); `page_content` (L481); `recommendations` (L491); `dominio` (L560); `score_total` (L561)

**tables**: `cadu_link_tests` (L364)

### api/chat/tools/LinkedInAdLibrary.php

198 linhas; SHA-256 `ce72e344cda10faf45da92e891f5913c92cc5d91becfb3fabb777296b5ac65c4`.

**symbols**: `getToolType` (L27); `process` (L32); `foreach` (L114, 167); `processAd` (L133); `formatCardData` (L162); `generateTitle` (L192)

**php_fields**: `query` (L34, 194); `q` (L34, 194); `search` (L34, 194); `country` (L40); `pais` (L40); `limit` (L41); `elements` (L102); `ads` (L102); `results` (L102); `data` (L102); `paging` (L111); `total` (L111)

### api/chat/tools/LinkedInAdsData.php

163 linhas; SHA-256 `dbc590e539e960b19b1081ea5efc236d268d9f00786964126a75b3937b6b3484`.

**symbols**: `getToolType` (L19); `process` (L24); `formatCardData` (L100); `foreach` (L122); `generateTitle` (L150)

**php_fields**: `type` (L26, 152); `tipo` (L26); `overview` (L76); `campaigns` (L77)

**event_cases**: `overview` (L65); `campaigns` (L68); `all` (L72)

### api/chat/tools/MetaAdsData.php

149 linhas; SHA-256 `e20233fb54cb673df0df62e45581b60920c27f8fc8f1ba89373656295dbe743e`.

**symbols**: `getToolType` (L17); `process` (L22); `formatCardData` (L83); `foreach` (L107); `generateTitle` (L136)

**php_fields**: `type` (L24, 138); `tipo` (L24); `overview` (L65); `campaigns` (L66)

**event_cases**: `overview` (L55); `campaigns` (L58); `all` (L61)

### api/chat/tools/Screenshot.php

185 linhas; SHA-256 `a7f25d762310047772832d30f97f20764bccea26b7d3d405e690235265b3802d`.

**symbols**: `getToolType` (L21); `process` (L25); `formatCardData` (L85); `generateTitle` (L89); `generateDescription` (L95); `ensureScreenshotOneConstants` (L104); `generateScreenshotUrl` (L116); `signScreenshotOneUrl` (L171)

**php_fields**: `url` (L26, 90); `device` (L42, 91); `format` (L43); `full_page` (L44); `user_agent` (L150, 152); `viewport_width` (L161); `viewport_height` (L162); `signature` (L181)

### api/chat/tools/SearchConsoleData.php

244 linhas; SHA-256 `0b541531b83cedd398f321a3ac82e21052b95bb2476f329389aacbd557c093f7`.

**symbols**: `getToolType` (L20); `process` (L25); `formatCardData` (L105); `foreach` (L134, 149, 162); `generateTitle` (L229)

**php_fields**: `type` (L27, 231); `tipo` (L27); `performance` (L77); `top_queries` (L78); `top_pages` (L79); `devices` (L80)

**event_cases**: `performance` (L58); `overview` (L59); `top_queries` (L62); `queries` (L63); `top_pages` (L66); `pages` (L67); `devices` (L70); `all` (L73)

### api/chat/tools/WebSearch.php

1242 linhas; SHA-256 `326f5b3fa1e9a64923f883d82ae1155edea1b630cd4145199baafb2c53b76ef6`.

**symbols**: `__construct` (L39); `getToolType` (L44); `process` (L48); `formatCardData` (L68); `generateTitle` (L84); `generateDescription` (L105); `executeSearch` (L130); `parseFirecrawlResults` (L225); `foreach` (L240, 249, 287, 431, 477, 518, 530, 584, 585, 613, 614, 632, 633, 663, 664, 683, 684, 700, 701, 720, 742, 782, 955, 990, 1114, 1137); `searchWithTavily` (L281); `executeScrape` (L320); `extractImages` (L423); `extractLinks` (L496); `detectTechnologies` (L561); `getHttpInfo` (L759); `resolveUrl` (L822); `executeMap` (L848); `executeCrawl` (L901); `formatSearchCard` (L987); `formatScrapeCard` (L1014); `formatMapCard` (L1045); `formatCrawlCard` (L1058); `pollCrawlStatus` (L1071); `categorizeLinks` (L1104); `cleanMarkdownForText` (L1153); `truncateText` (L1226)

**php_fields**: `action` (L49, 85, 106); `url` (L89, 92, 95, 321, 849, 902); `query` (L100, 120, 131); `q` (L100, 131); `search` (L100, 131, 861, 862, 889); `limit` (L137, 864, 865, 912); `lang` (L138); `country` (L139); `tbs` (L147); `sources` (L159); `web` (L236, 237); `news` (L239, 240); `extract_mode` (L331); `wait_for` (L349, 350); `only_main_content` (L352, 353); `markdown` (L363); `html` (L364); `metadata` (L365); `include_subdomains` (L867, 868); `include_paths` (L923, 923, 924); `exclude_paths` (L926, 926, 927); `max_depth` (L929, 930); `error` (L1077, 1088); `status` (L1081)

**event_cases**: `scrape` (L56, 72, 88, 109); `map` (L58, 74, 91, 112); `crawl` (L60, 76, 94, 115); `search` (L62, 78, 98, 118)

### api/chat/tools-dify.php

374 linhas; SHA-256 `0fa0b973abf802d7470d122a72c9fafcaff8736d48cc795d5ff49a637dcb6e25`.

**symbols**: `set_error_handler` (L98); `register_shutdown_function` (L106); `getApiKeyFromRequest` (L125); `loadAndCreateTool` (L241)

**php_fields**: `action` (L35, 35, 46, 46, 358); `api_key` (L139, 140); `tool` (L302); `params` (L303)

### api/chat/tools.php

696 linhas; SHA-256 `d004f7ba5b574c96f0391c96c92708acec8a0e93512c196fde0b981365910500`.

**symbols**: `foreach` (L50, 87); `set_error_handler` (L196, 238); `register_shutdown_function` (L207); `set_exception_handler` (L245); `loadAndCreateTool` (L354)

**php_fields**: `action` (L46, 46, 71, 71, 110, 110, 272, 272, 542); `tool` (L432); `params` (L433); `conversation_id` (L434); `message_id` (L435); `projeto_id` (L436, 438, 439, 443, 451, 455, 458); `url` (L474); `tool_type` (L578); `limit` (L579); `offset` (L580); `uuid` (L608, 651)

**event_cases**: `execute` (L416); `list` (L561); `get` (L601); `toggle_public` (L642)

**tables**: `cadu_ci_projetos` (L446)

### api/chat-skills.php

160 linhas; SHA-256 `03a6007f4cceb83a4f4330352be042a2359d38ae938a156c93735e8282b0dd64`.

**symbols**: `cadu_chat_skills_valid_slug` (L45); `foreach` (L50)

**event_cases**: `set_active` (L90); `save_prompt` (L106); `reset_one` (L134); `reset_all` (L146)

**tables**: `cadu_chat_user_skill_active` (L98); `cadu_chat_skill_user_prompts` (L125, 141, 147)

### api/dify-feedback.php

105 linhas; SHA-256 `68aa66819f951f808b8e2bac6a859cac0ba28f8de47bbe98ceb1bce3ce8e6737`.

**php_fields**: `message_id` (L41); `rating` (L42); `user` (L43); `result` (L104)

### api/dify-messages.php

405 linhas; SHA-256 `085cf4ddd7d14933058ba9d5a46ab6e095c935c818f508ad2cf3b4c61d35e347`.

**symbols**: `dify_messages_resolve_client_id` (L39); `foreach` (L115)

**php_fields**: `action` (L81, 213, 213); `conversation_id` (L86, 87, 149, 194, 214, 263); `user_message` (L161, 162, 163, 193, 264); `projeto_id` (L170, 176); `message_id` (L215); `tool_call` (L216); `assistant_message` (L265); `tokens_used` (L266); `source` (L267); `tool_calls` (L268); `dify_conversation_id` (L269, 269)

**tables**: `tbl_contato_cliente` (L44); `cadu_conversations` (L92, 182, 227, 281, 299, 345, 355); `cadu_conversation_messages` (L107, 226, 247, 319, 335, 347); `cadu_ci_projetos` (L172)

### api/dify-proxy.php

325 linhas; SHA-256 `d8846f9dbe5c127cd7129a4f7faad82ac81375dd6def2a1ff362eeceda784b94`.

**symbols**: `curl_setopt` (L167); `foreach` (L205, 217)

**php_fields**: `action` (L44); `user` (L48, 55); `limit` (L49, 56); `conversation_id` (L54); `response_mode` (L121)

### api/dify-tool-audiencias.php

289 linhas; SHA-256 `b34cb16ab6114798ac48d7877927f2d89144830e8f6a80b50c4146ec3f6e5228`.

**symbols**: `set_error_handler` (L19); `foreach` (L169); `gerarResumoAudiencias` (L251)

**php_fields**: `search` (L54, 60); `limit` (L61, 61)

**tables**: `cadu_audiencias` (L86, 141); `cadu_categorias` (L87, 142); `cadu_audiencias_plataformas` (L88, 143)

### api/dify-upload.php

176 linhas; SHA-256 `93bcea62d40a6eec42204a5d87fea9894fa1485453cbb8f72ae55847aa27012d`.

**php_fields**: `file` (L38, 38, 40, 40, 45); `user` (L46)

### api/extract-file-content.php

307 linhas; SHA-256 `7fbfc992c64c198631d95ae3c4cf9389a2a62a416688974b7d77c696e3363e10`.

**symbols**: `foreach` (L52); `extractPdfContent` (L101); `extractPdfViaVision` (L144); `extractPdfFirstPageAsImage` (L188); `extractImageContent` (L244); `callGeminiVision` (L266)

**php_fields**: `files` (L41)

### api/projetos/branding.php

115 linhas; SHA-256 `207b9ab0a46a37f213d60382dcb183d193ce700114a8650fbbce9062fa88b917`.

**php_fields**: `projeto_id` (L12, 37); `branding_id` (L44, 44); `nome` (L57)

**tables**: `cadu_docs_branding` (L48, 61, 84); `cadu_ci_projetos` (L94)

### api/projetos/retrieve.php

90 linhas; SHA-256 `291e4d89af933f3025159928041e0d550a985f50a52f6652eec4d93dd6390f15`.

**symbols**: `foreach` (L55)

**php_fields**: `projeto_id` (L20); `query` (L21); `top_k` (L22)

**tables**: `cadu_ci_chunks` (L34)

### assets/css/chat-cadu.css

1362 linhas; SHA-256 `6d0cf7c8b39634687cca966e5fc9b2e39a680a4f36ba2ab641656b3ce89dd0a1`.

### assets/css/chat-dify-layout.css

1147 linhas; SHA-256 `e883877e9b7bd30766217a7a6f36cc696827369eb99bb85908449632039cda19`.

### assets/css/chat-dify-page.css

909 linhas; SHA-256 `bd6076d0ca0425c79215d359196f8ad2e71931e66223c8e02c071cbbb468f559`.

### assets/css/chat-dify-skills.css

778 linhas; SHA-256 `2e0e2543d989aedf13e18543abcf50deb452cad5f05f9d26cb83b99f529e1a23`.

### assets/css/chat-model-select.css

174 linhas; SHA-256 `0662b020f4c4e4d0e63cf264d8c07825ccc04bbca797ee61f55cfb9d1661f4e0`.

### assets/css/dify-chat.css

3076 linhas; SHA-256 `17d587f402c0cabc3092a17ad7472165a30bb8fd92c7c79e3c2063c7f12d1a98`.

### assets/js/dify/CaduChatSkills.js

569 linhas; SHA-256 `74c19bbe8eec762730a1bbf3990d98870976f5e217227089140291213e29295e`.

**symbols**: `readSkillCookie` (L13); `writeSkillCookie` (L20); `slugInCatalog` (L27); `collectBundleSkillIds` (L31); `resolveActiveSlug` (L45); `esc` (L61); `escAttr` (L67); `normalizeSkill` (L71); `applyBundle` (L88); `apiGet` (L119, 186); `apiPost` (L126, 444, 498, 513, 555)

**api_paths**: `/api/chat-skills.php` (L8)

### assets/js/dify/DifyChat.js

2813 linhas; SHA-256 `0c2e69c97089b615ba7bf540e5b2e0cc7cfa1cedd02841e60e48ee9b8f9d702e`.

**symbols**: `caduSafeErrorMessage` (L9); `constructor` (L28); `buildGuardrailsContext` (L151); `_dispatchLocalImageWorking` (L177); `_startImageAssistantPlaceholder` (L182); `_startLinkTestPlaceholder` (L188); `_extractLastAssistantText` (L200); `_extractTopicFromFirstUserMessage` (L227); `_extractConversationTopic` (L246); `_normalizeTopicFromUserMessage` (L260); `_cleanTopicForSearch` (L282); `_normalizeTopicFromAssistantText` (L297); `_isLikelySectionHeading` (L328); `_buildWebInjectQuery` (L339); `_recordGeneratedImageFromResults` (L380); `setApiKey` (L406); `setConversationId` (L411); `setProjetoId` (L423); `absoluteAssetUrl` (L435); `ensureProjetoBranding` (L443); `formatBrandingForContext` (L470); `shouldUseBrandingLogo` (L481); `enrichImageGenerateParams` (L500); `consumePendingHistoryContext` (L519); `syncSkillInputs` (L530); `syncConversationStateInputs` (L555); `_isBareOpener` (L586); `prepareFilesContext` (L598); `prepareProjectContext` (L669); `updateBrowserUrlForConversation` (L706); `getConversationId` (L718); `sendMessage` (L729); `isImageAnalysisRequest` (L833); `checkImageEditRequest` (L867); `checkImageGenerationWithReferenceRequest` (L946); `handleImageEditRequest` (L987); `handleImageEditFromLastGenerated` (L1079); `fileToBase64` (L1152); `compressImageFileForApi` (L1164); `_resolveReferenceImageForApi` (L1211); `_variationStaggerMs` (L1231); `compressDataUrlForApi` (L1240); `handleLocalResponse` (L1280); `handleImageWizard` (L1294); `renderImageWizard` (L1342); `setupImageWizardHandlers` (L1441); `generateVariationPrompts` (L1562); `fetchImageAsDataUrl` (L1584); `buildVariationPreservationInstructions` (L1607); `_decodeCardPrompt` (L1620); `_resolveVariationBasePrompt` (L1632); `_getActiveImageUrlFromCard` (L1642); `useImageAsReference` (L1649); `editImageFromCard` (L1674); `_stripHeavyToolParams` (L1683); `createVariationOnCard` (L1829); `runVariationOnCard` (L1854); `appendToolCallToMessage` (L1895); `_tagLastImageCardFromSave` (L1924); `generateMoreImages` (L1963); `escapeHtml` (L1978); `handleToolResponse` (L1987); `handleInjectResponse` (L2056); `_getVisibleAnswer` (L2184); `_isLeakedInternalPrompt` (L2196); `_sanitizeVisibleAnswer` (L2213); `_recoverVisibleAnswer` (L2222); `_clearThinkingBlock` (L2251); `_streamIntoMessage` (L2261); `_retryEmptyStreamResponse` (L2282); `handleDifyResponse` (L2313); `_buildImagePromptForRetry` (L2425); `_detectImageStyleAndRatio` (L2451); `_detectImageHallucination` (L2464); `_maybeFixImageHallucination` (L2491); `saveMessage` (L2543); `stop` (L2631); `getIsProcessing` (L2641); `loadHistory` (L2648); `newConversation` (L2683); `addToQueue` (L2714); `removeFromQueue` (L2740); `processNextInQueue` (L2754); `clearQueue` (L2776); `getQueueLength` (L2785); `getQueue` (L2792); `notifyQueueUpdate` (L2799)

**api_paths**: `/api/dify-messages.php` (L109); `/api/tokens.php` (L110); `/api/projetos/branding.php` (L451); `/api/extract-file-content.php` (L633); `/api/projetos/retrieve.php` (L683); `/api/chat-messages.php` (L2685)

**dom_ids**: `image-wizard-prompt` (L1396); `image-wizard-styles` (L1405); `image-wizard-ratios` (L1411); `image-wizard-variations` (L1420); `image-wizard-cancel` (L1428); `image-wizard-generate` (L1429)

### assets/js/dify/DifyChatUI.js

842 linhas; SHA-256 `2812ea3305118914a39e535abf9c2d621c2d65cf9f549cb4ef2a8bee75abe7fd`.

**symbols**: `difyContentIsToolHtml` (L7); `constructor` (L20); `_hideEmptyState` (L36); `addUserMessage` (L43); `_getFileIcon` (L90); `_formatFileSize` (L101); `addAssistantMessage` (L108); `addLocalMessage` (L148); `addToolMessage` (L173); `showToolLoadingCard` (L218); `updateToolMessage` (L230); `beginAssistantThinking` (L281); `showThinking` (L301); `hideThinking` (L339); `showInlineStatus` (L368); `hideInlineStatus` (L387); `showMessageLoading` (L400); `clearMessageLoading` (L410); `streamDotsHtml` (L419); `appendToMessage` (L423); `finalizeMessage` (L452); `finalizeToolMessage` (L490); `stripLegacySourceBadges` (L518); `addWebSourcesFooter` (L530); `addProjectSourcesBadge` (L537); `_addFeedbackButtons` (L608); `_handleFeedback` (L631); `showError` (L678); `scrollToBottom` (L720); `disableInput` (L727); `enableInput` (L737); `clearInput` (L748); `setInputValue` (L758); `focusInput` (L768); `setMessageContent` (L785); `openLightbox` (L828); `_escapeHtml` (L834)

**api_paths**: `/api/dify-feedback.php` (L642)

**dom_ids**: `msg-user-` (L46); `msg-assistant-` (L111); `msg-local-` (L151); `tool-` (L178); `msg-error-` (L679)

### assets/js/dify/DifyGuardrails.js

1630 linhas; SHA-256 `1aa28085b315be73671e3622d6f8c547909b281b3c46c8470219f9e5bdc821bd`.

**symbols**: `constructor` (L10); `normalizeUrlCandidate` (L17); `extractUrlFromMessage` (L52); `isContinuationOrConfirmation` (L67); `normalizeUserMessage` (L100); `isTextContentRequest` (L117); `process` (L142); `detectEditOnLastImage` (L263); `checkInject` (L308); `fetchAudiencias` (L376); `checkLocal` (L459); `detectTool` (L503); `checkDeepSearch` (L808); `isMetaEnrichMessage` (L858); `buildEnrichSearchQuery` (L872); `isMetaEnrichQuery` (L885); `resolveQueryFromConversationTopic` (L910); `detectDeepSearchIntent` (L933); `checkSiteAnalysis` (L1016); `fetchSiteScrapeContext` (L1042); `fetchDeepSearch` (L1128); `detectImageStyleAndRatio` (L1196); `extractVisualPromptFromPlanning` (L1234); `countImageGenerateRequests` (L1253); `buildImageGenerateResult` (L1267); `detectExplicitImageIntent` (L1326); `detectStandaloneImagePrompt` (L1388); `enrichImagePromptWithContext` (L1407); `analyzeImagePrompt` (L1430); `getSuggestionForPrompt` (L1509); `runTests` (L1525)

**api_paths**: `/api/dify-tool-audiencias.php` (L378); `/api/chat/tools.php` (L1048); `/api/chat/deep-search.php` (L1145)

### assets/js/dify/DifyMarkdown.js

827 linhas; SHA-256 `ac0a49cd52c3d314b9fcf135f69a4ad87be4b6d3ca8fdd10de42e522651731b7`.

**symbols**: `safeUserText` (L14); `constructor` (L20); `tokensToText` (L28); `tokensToHtml` (L49); `init` (L66); `code` (L76); `link` (L89); `highlightCode` (L105); `escapeHtml` (L121, 169); `normalizeListMarkers` (L133); `normalizeHeaders` (L157); `extractSmartDoc` (L177); `renderSmartDocIntro` (L212); `hasSmartDocContent` (L216); `renderSmartDocButton` (L223); `stripThinkingBlocks` (L263); `extractThinking` (L292); `wrapTables` (L349); `stripBrokenMarkdownLinks` (L359); `sanitizeBrokenAnchors` (L370); `render` (L381); `getLastThinking` (L454); `fallbackRender` (L458); `renderStreaming` (L508); `extractSmartDocStreaming` (L546); `renderSmartDocGenerating` (L578); `renderStreamingSimple` (L594); `formatInline` (L694); `renderSimpleTable` (L707); `finalize` (L739); `finalizeWithContent` (L760)

### assets/js/dify/DifyStream.js

630 linhas; SHA-256 `ea2ef061a21434c77371db9d83291f6206880ad0725dfc47fd6a9ffdbf69ddba`.

**symbols**: `difySafeStreamText` (L9); `difyValidFileUrl` (L16); `difyMergeAnswerChunk` (L35); `difyIsNetworkFetchError` (L62); `dedupeConsecutiveRepeats` (L76); `constructor` (L102); `setConfig` (L115); `mergeInputs` (L124); `getDifyConversationId` (L129); `setDifyConversationId` (L133); `send` (L143); `abort` (L618); `getIsStreaming` (L625)

**event_cases**: `message` (L305); `agent_message` (L306); `message_thinking` (L325); `thinking` (L326); `agent_thought` (L335); `tool_call` (L402); `message_end` (L412); `node_started` (L490); `node_finished` (L491); `workflow_started` (L496); `workflow_finished` (L497); `text_chunk` (L524); `message_file` (L540); `error` (L552); `ping` (L560)

**api_paths**: `/api/dify-proxy.php` (L103)

### assets/js/dify/DifyTools.js

2124 linhas; SHA-256 `6b40067aeffc4ceb3323347ae4fa8225673bc0aea8da8bf87cd19e73877af3fd`.

**symbols**: `toolsSafeUserText` (L10); `cleanImageDisplayPrompt` (L17); `isToolRenderedHtml` (L38); `constructor` (L51); `setUI` (L62); `setContext` (L66); `_buildToolRequest` (L75); `execute` (L100); `fetchImageGenerateWithRetry` (L143); `executeMultipleImages` (L203); `executeSingle` (L272); `translateError` (L442); `checkUrlAccessibility` (L490); `renderUrlError` (L524); `renderError` (L577); `getToolDisplayName` (L590); `renderResult` (L614); `getImageStyleMeta` (L639); `renderImageCarousel` (L672); `renderImageError` (L840); `renderGeneratedImage` (L856); `generateImageVariations` (L863); `escapeHtml` (L930); `escapeForJs` (L939); `decodeFromJs` (L964); `decodeBase64Utf8` (L983); `repairToolPayload` (L1002); `repairPromptText` (L1017); `safeDomainFromUrl` (L1046); `renderImageGenerateLoading` (L1059); `getImageSkeletonRatioClass` (L1084); `_styleLinkTestToolBlock` (L1098); `_findToolMessageRoot` (L1112); `_setRotatingStatusPhrase` (L1117); `_beginRotatingPhrases` (L1131); `_stopRotatingPhrases` (L1150); `_findLinkTestLoadingRoot` (L1157); `_linkTestLoadingPhrases` (L1161); `_setLinkTestStatusPhrase` (L1174); `beginLinkTestLoading` (L1178); `stopLinkTestLoading` (L1187); `_screenshotLoadingPhrases` (L1191); `beginScreenshotLoading` (L1201); `stopScreenshotLoading` (L1210); `renderLinkTestLoading` (L1214); `renderScreenshotLoading` (L1230); `renderScreenshot` (L1246); `renderLinkTest` (L1320); `_truncateLinkTestText` (L1416); `renderWebScrape` (L1424); `detectSocialPlatform` (L1545); `formatMarkdownSimple` (L1561); `renderWebSearch` (L1575); `renderAudience` (L1602); `renderGeneric` (L1659); `init` (L1692); `afterRender` (L1761); `markMediaToolBlock` (L1767); `openLightbox` (L1775); `setCardLoading` (L1795); `clearCardLoading` (L1802); `appendImageToCard` (L1807); `_ensureThumbsWrap` (L1826); `_findFixedContainingBlock` (L1856); `_resetDropdownPanel` (L1871); `_positionDropdownPanel` (L1881); `_closeCardDropdowns` (L1920); `_onContainerClick` (L1927); `_lightboxStep` (L2034); `_downloadUrl` (L2041); `_readGallery` (L2052); `_writeGallery` (L2067); `_syncThumbCount` (L2075); `_setActiveIndex` (L2081); `_renderThumbs` (L2105)

**event_cases**: `screenshot_url` (L619); `link_test` (L621); `web_scrape` (L623); `web_search` (L625); `audience_detail` (L627); `image_generate` (L629)

**api_paths**: `/api/chat/tools.php` (L52, 493)

### assets/js/dify/DifyUI.js

305 linhas; SHA-256 `6521b56df23b204147778868fb51732be7bc6d4b6f4b0e83a7d6b75a20652ec9`.

**symbols**: `constructor` (L7); `clearInput` (L17); `setInputValue` (L27); `focusInput` (L39); `disableInput` (L48); `enableInput` (L54); `hideEmptyState` (L63); `addUserMessage` (L68); `addAssistantMessage` (L97); `addLocalMessage` (L127); `addToolMessage` (L153); `updateToolMessage` (L176); `appendToMessage` (L189); `setMessageContent` (L204); `finalizeMessage` (L217); `showError` (L240); `showThinking` (L264); `hideThinking` (L277); `scrollToBottom` (L287); `escapeHtml` (L293); `getCurrentMessageId` (L300)

**dom_ids**: `msg-user-` (L71); `msg-assistant-` (L98); `msg-local-` (L128); `msg-tool-` (L154); `msg-error-` (L241)

### assets/js/web-search-toggle.js

62 linhas; SHA-256 `33d8f77762ae6c3d06a713c26cd5dabc9db1fa3b5c7484a99d730344b7d358ae`.

**symbols**: `readCookie` (L15); `writeCookie` (L24); `isOn` (L30); `apply` (L35); `init` (L41)

### chat-cadu-dify.php

132 linhas; SHA-256 `f843a83edecf9c73f9c4a8c9c2e823537144576e1fc141549fe3e6814b6313a8`.

**symbols**: `normalizarNome` (L30)

**php_fields**: `c` (L15); `id` (L15); `mode` (L47); `projeto` (L68)

**tables**: `cadu_ci_projetos` (L83)

### includes/dify/chat-data.php

125 linhas; SHA-256 `6c78b714403fcd38e5e72e1db28b3009740d2653a7c8e8cc6fccd784d97d7a37`.

**symbols**: `cadu_repair_mojibake_string` (L28); `cadu_repair_tool_calls_value` (L39); `foreach` (L44, 70, 111)

**tables**: `cadu_conversations` (L58, 94); `cadu_conversation_messages` (L103)

### includes/dify/chat-header.php

22 linhas; SHA-256 `ee5907049ce2ab7c515b78536ffb0cb418bf2b66d7a00d0b8bf46d9311fbc510`.

**dom_ids**: `chat-notifications` (L14)

### includes/dify/chat-inline-scripts.php

289 linhas; SHA-256 `7630d118b44cb42ef40823d6439618eb534a6074605446951546066afd7391c6`.

**symbols**: `toggleSidebar` (L68); `insertCommand` (L76); `toolbarInsertCommand` (L91); `showInput` (L175); `hideInput` (L180); `onScroll` (L185); `bind` (L200); `unbind` (L204)

**api_paths**: `/api/docs-save.php` (L36)

### includes/dify/chat-input.php

170 linhas; SHA-256 `1501bafb7ad257be94f97988c8e501fe4e97dc07241a9050337f3bc741607724`.

**dom_ids**: `attachments-preview` (L13); `message-input` (L17); `attach-btn` (L26); `file-input` (L29); `cd-skill-dropdown` (L33); `cd-skill-btn` (L34); `cd-skill-pill-label` (L35); `cd-skill-panel` (L38); `cd-skill-sheet-close` (L42); `cd-skill-reset-all` (L46); `cd-sheet-backdrop` (L50); `cd-projeto-dropdown` (L53); `cd-projeto-btn` (L54); `cd-projeto-label` (L56); `cd-projeto-panel` (L59); `cd-projeto-list` (L64); `web-search-toggle` (L69); `stop-btn` (L132); `send-btn` (L135); `cd-skill-edit-dialog` (L144); `cd-skill-edit-title` (L149); `cd-skill-edit-close` (L151); `cd-skill-edit-text` (L157); `cd-skill-char-count` (L158); `cd-skill-default-hint` (L160); `cd-skill-edit-reset-one` (L164); `cd-skill-edit-cancel` (L166); `cd-skill-edit-save` (L167)

### includes/dify/chat-messages.php

261 linhas; SHA-256 `014e16e8cd92f9ff3b0df1883a46b9f3d7145bffc26fd4599d08cc816fec6248`.

**symbols**: `getSeasonalCTAs` (L10)

**dom_ids**: `messages-container` (L210); `empty-state` (L245)

### includes/dify/chat-modals.php

79 linhas; SHA-256 `de7052d0defd4dc7746f62f26cea48d71bcb86b56a7e3762d11103fe896f8a1c`.

**dom_ids**: `turbo-modal` (L2); `cadu-lightbox` (L36); `cadu-lightbox-download` (L40); `cadu-lightbox-prev` (L47); `cadu-lightbox-img` (L51); `cadu-lightbox-next` (L53); `new-chat-modal` (L60)

### includes/dify/chat-model-select.php

31 linhas; SHA-256 `2d6d385e7558541888741e54f53b9c6f32ca871d502710ae8197851aea03ebb2`.

### includes/dify/chat-scripts.php

979 linhas; SHA-256 `b4efd2eb32cb30fe99bba23d3244ac586e5e210ef97efaef1f89d9c26361307b`.

**symbols**: `caduBuildPendingHistoryContext` (L19); `foreach` (L34); `debugLog` (L126); `toolbarInsertCommand` (L131); `openTurboModal` (L146); `activateTurboMode` (L150); `openNewChatModal` (L156); `startNewChat` (L160); `updateSendButton` (L166); `stopStreaming` (L176); `init` (L190, 492); `handleFiles` (L243); `addFile` (L253); `addFromUrl` (L297); `_uploadFile` (L347); `removeFile` (L372); `getUploadedFiles` (L384); `getFileObjects` (L397); `clear` (L409); `hasFiles` (L415); `_renderPreview` (L419); `_renderFileItem` (L437); `_getFileIcon` (L468); `_formatSize` (L478); `incrementMessages` (L501); `canSend` (L507); `getBlockReason` (L514); `checkTokenLimit` (L521); `resetForNewConversation` (L534); `_renderNotifications` (L539); `_getTokenNotif` (L553); `_getInteractionNotif` (L573); `_syncInputState` (L588); `renderHistoryToolCalls` (L680); `sendMessage` (L752); `renderQueueUI` (L900); `escapeHtml` (L953)

**api_paths**: `/api/dify-upload.php` (L354); `/api/usage/check-limit.php` (L523)

**dom_ids**: `file-` (L259); `message-queue` (L891)

### includes/dify/chat-sidebar.php

60 linhas; SHA-256 `ab6134aeda0c4b2c57f28f5878381390b33b25f3e3d12d29af62fe347347434a`.

**dom_ids**: `conversations-sidebar` (L7)

### includes/dify/chat-skills-config.php

39 linhas; SHA-256 `d338e5f64a161f9e7995053f78c3001c7d44616ea02fafc115f32f46a87e26b8`.

### includes/dify/chat-skills-db.php

153 linhas; SHA-256 `26c0548e4950653de3273f1583385a0b0b9a8fd18911b02fde87297b1f3a0dfc`.

**symbols**: `cadu_chat_skills_fallback_catalog` (L5); `foreach` (L25, 63, 125); `cadu_chat_skills_fetch_catalog` (L46); `cadu_chat_skills_bundle_for_user` (L86)

**tables**: `cadu_chat_skills` (L54); `cadu_chat_skill_user_prompts` (L94); `cadu_chat_user_skill_active` (L104)
