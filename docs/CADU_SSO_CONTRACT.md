# Cadu SSO — contrato PHP e Python

O PHP e o Flask usam a mesma pessoa em `tbl_contato_cliente`, mas mantêm cookies de sessão próprios. A troca de login acontece por um ticket aleatório, de uso único, válido por no máximo 90 segundos.

## Google como entrada central

Durante a transição, o Cadu PHP continua sendo a fonte de verdade do cadastro Google aberto. O Auth encaminha novos usuários para `https://cadu.centralcomm.media/google-login.php?v3=1`; o PHP lê os dados Google, cria cliente, contato e plano Free com o fluxo que já funciona. A configuração `google_login_cadu` fica preparada para a futura troca do callback para `https://auth.centralcomm.media/auth/google/callback`. Calendar/Meet continua em outro cliente e só pede autorização quando a pessoa conecta a agenda.

O destino original define a política. CentralX usa o cliente interno do Flask, exige `@centralcomm.media` e mantém a aprovação existente na base. Cadu, Studio, Planner, Skills e Connect usam o cadastro aberto do PHP. Até o endpoint PHP de emissão do ticket estar ativo, o primeiro acesso termina no Cadu v3; depois, o ticket devolve a pessoa ao produto escolhido sem refazer o login.

## PHP para Python

1. PHP confirma sua sessão e o `id_contato_cliente`.
2. Gera 32 bytes com `random_bytes(32)` e codifica em base64url sem padding.
3. Grava somente `hash('sha256', $ticket)` em `cadu_sso_tickets`, com `source_app='php'`, usuário, destino permitido e expiração de até 90 segundos.
4. Redireciona para `https://auth.centralcomm.media/auth/sso/consume?ticket=VALOR_BRUTO`.
5. O Flask bloqueia a linha, valida usuário/expiração, marca `consumed_at`, cria seu cookie e segue para o destino.

## Python para PHP

1. O usuário abre `/auth/sso/to-cadu` já autenticado no Flask.
2. O Flask cria o ticket da mesma forma e redireciona para `CADU_SSO_CONSUME_URL` (`https://cadu.centralcomm.media/sso-consume.php`).
3. O PHP valida e consome a linha dentro de uma transação, cria `PHPSESSID` e redireciona para `target_url`.

## Regras obrigatórias

- Nunca colocar senha, email ou ID de usuário no ticket.
- Nunca armazenar o token bruto no banco ou em logs.
- Consumir com transação e bloqueio de linha; `consumed_at` torna o token irrecuperável.
- Aceitar destinos somente nos hosts oficiais configurados.
- Enviar `Cache-Control: no-store` e `Referrer-Policy: no-referrer` nas respostas de troca.
- Limpar periodicamente tickets expirados e consumidos antigos.
- O cookie Flask deve usar nome próprio, `Secure`, `HttpOnly`, `SameSite=Lax` e domínio `.centralcomm.media` em produção.
- A primeira troca de `session` para `centralx_session` exige um novo login uma única vez; faça essa mudança junto da publicação do Auth.
- O cookie PHP continua separado. Nenhuma linguagem precisa conhecer a chave ou o formato da sessão da outra.

## Entrada centralizada

- `https://cadu.centralcomm.media/login` e `login.php` não validam mais senha: redirecionam para `https://auth.centralcomm.media/login` com o destino Cadu em `next`.
- O formulário no Auth valida a mesma tabela e os mesmos hashes (bcrypt e MD5 legado) que o PHP usava. A senha não é enviada ao PHP depois disso.
- Ao abrir Cadu a partir do Auth, `/auth/sso/to-cadu` emite o ticket e `sso-consume.php` cria o `PHPSESSID` local. A navbar PHP deve apontar **Workspace/Conta** para `https://workspace.centralcomm.media/workspace/app` e **Sair** para `https://auth.centralcomm.media/logout`.
