# Cadu SSO — contrato Auth e família Cadu

O Auth em `auth.centralcomm.media` é a entrada única da família Cadu. Workspace, Connect, Studio, Skills e Planner usam a mesma sessão assinada, com cookie `Secure`, `HttpOnly`, `SameSite=Lax` e domínio `.centralcomm.media` em produção.

## Google como entrada central

O login usa OIDC com `openid email profile`, além de `state`, `nonce` e PKCE. O client de login é separado do client de integrações Google Workspace. O login valida uma conta ativa já cadastrada e nunca usa permissões de Drive, Calendar, Meet, Analytics, Search Console ou Ads.

O destino original define a política. CentralX usa o client interno e exige `@centralcomm.media`; a família Cadu usa o client de clientes e preserva a autorização da organização. Retornos aceitam somente hosts oficiais configurados.

## Google Workspace da organização

A autorização de dados usa:

- início: `https://auth.centralcomm.media/auth/google/workspace`;
- callback: `https://auth.centralcomm.media/auth/google/workspace/callback`;
- client OAuth separado para Drive, Calendar, Meet, Analytics, Search Console e Ads;
- refresh token criptografado por organização;
- estado OAuth e PKCE separados do login;
- escopos concedidos registrados para auditoria e reautorização.

Uma conexão da organização pode descobrir arquivos, pastas, calendários, espaços Meet, propriedades Analytics, sites Search Console e contas Ads. Recursos Google podem ser associados a projetos do Workspace e entram no registro universal de recursos.

## Regras obrigatórias

- Nunca colocar senha, token ou segredo em URL ou log.
- Consumir cada callback OAuth uma única vez.
- Aceitar destinos somente nos hosts oficiais configurados.
- Usar `Cache-Control: no-store` e `Referrer-Policy: no-referrer` nas trocas de autorização.
- Revogar o token no Google ao desconectar quando o endpoint estiver disponível.
- Tratar `invalid_grant`, escopo insuficiente e conta suspensa como estados de reautorização.
- Não misturar o refresh token da conexão organizacional com tokens de login.
