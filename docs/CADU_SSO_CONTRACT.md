# Cadu SSO — contrato Auth e família Cadu

O Auth em `auth.centralcomm.media` é a entrada única da família Cadu. Workspace, Connect, Studio, Skills e Planner usam a mesma sessão assinada, com cookie `Secure`, `HttpOnly`, `SameSite=Lax` e domínio `.centralcomm.media` em produção.

## Google como entrada central

O login usa OIDC com `openid email profile`, além de `state`, `nonce` e PKCE. O client de login é separado do client de integrações Google Workspace. O login valida uma conta ativa já cadastrada e nunca usa permissões de Drive, Calendar, Meet, Analytics, Search Console ou Ads.

O destino original define a política. CentralX usa o client interno e exige `@centralcomm.media`; a família Cadu usa o client de clientes e preserva a autorização da organização. Retornos aceitam somente hosts oficiais configurados.

## Google Workspace por cliente e pessoa autorizadora

A autorização de dados usa:

- início: `https://auth.centralcomm.media/auth/google/workspace`;
- callback: `https://auth.centralcomm.media/auth/google/workspace/callback`;
- client OAuth separado para Drive, Calendar, Meet, Analytics, Search Console e Ads;
- refresh token criptografado por autorização, identificado pelo `client_id` Cadu e pelo usuário que concedeu acesso;
- estado OAuth e PKCE separados do login;
- escopos concedidos registrados para auditoria e reautorização.

O `client_id` Cadu é a fronteira do Workspace tanto para agências quanto para clientes finais. Cada pessoa conectada ao cliente autoriza a própria conta Google; uma autorização não substitui nem permite desconectar a de outra pessoa. Recursos descobertos no Drive ficam disponíveis no contexto daquele `client_id` e podem ser associados aos projetos do Workspace sem copiar o arquivo original. A integração Google não usa `organization_id`.

## Regras obrigatórias

- Nunca colocar senha, token ou segredo em URL ou log.
- Consumir cada callback OAuth uma única vez.
- Aceitar destinos somente nos hosts oficiais configurados.
- Usar `Cache-Control: no-store` e `Referrer-Policy: no-referrer` nas trocas de autorização.
- Revogar o token no Google ao desconectar quando o endpoint estiver disponível.
- Tratar `invalid_grant`, escopo insuficiente e conta suspensa como estados de reautorização.
- Não misturar refresh tokens de pessoas diferentes nem tokens de login.
