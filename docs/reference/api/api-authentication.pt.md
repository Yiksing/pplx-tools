---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-authentication.md"
translation_source_sha256: "dc9067f0d08c997245ee548a335fc762ad0cbe986661ba0ad7f976150131dd72"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="authentication-model" data-pplx-source-anchor="true"></a>
# Modelo de autenticação

> Esta página apresenta a área de referência da API — o registro testado em campo do projeto pplx_export da API web privada do Perplexity.
> Público-alvo: mantenedores e usuários deste projeto. Todos os endpoints foram verificados via captura de rede WebBridge + requisições diretas autenticadas por cookie (2026-07).
> **Qualquer alteração ou adição ao conhecimento da API deve ser sincronizada nestas páginas** (requisito explícito do usuário).
> Última atualização: 2026-07-23
>
> A área de referência é dividida em: **1. Modelo de autenticação** (esta página) · [2. GraphQL (consultas persistentes / APQ)](api-graphql.md) · [3. Endpoints REST (agrupados por finalidade)](api-rest-endpoints.md) · [4–5. Estrutura de resposta e semântica de erros](api-responses-errors.md) · [6–8. Itens TBD, descoberta de endpoints e roteiro](api-discovery-roadmap.md) — para o design do sistema circundante, veja o [mapa de leitura da arquitetura](../../architecture/index.md).

---

<a id="authentication-model_1" data-pplx-source-anchor="true"></a>
## Modelo de autenticação

<a id="cookie-session" data-pplx-source-anchor="true"></a>
### Sessão de cookie
- Todas as requisições à API precisam apenas do cookie de sessão do navegador (nenhum token CSRF é necessário; tanto GET quanto POST foram verificados funcionando via requisições diretas).
- Cookie chave: `__Secure-next-auth.session-token` (token de sessão da **conta atualmente ativa**).
- Cloudflare está na frente: `cf_clearance`/`__cf_bm` estão vinculados à impressão digital TLS do navegador — **requisições curl simples recebem 403**;
  a ferramenta passa com Python urllib + cookies importados do navegador (UA mascarado como Chrome desktop).

<a id="multi-account-discovered-2026-07-20" data-pplx-source-anchor="true"></a>
### Multi-contas (descoberto em 2026-07-20)
- Quando várias contas estão logadas no mesmo navegador, cada conta possui seu próprio cookie `__Secure-pplx.session.<user_id>`
  (domínio www.perplexity.ai; o valor avança com as respostas).
- O valor de `__Secure-next-auth.session-token` = o valor do cookie por conta da conta ativa.
- **Alternar contas na web** = navegar para `https://www.perplexity.ai/?pplx_account=<user_id>`; o servidor reescreve o token ativo.
- **Alternância automática pelo lado da ferramenta** (implementada no pplx_export): enumerar os cookies `__Secure-pplx.session.*` do navegador,
  substituir `__Secure-next-auth.session-token` por cada um por vez e sondar `/api/auth/session` até que o email alvo corresponda.
- `GET /api/auth/linked-accounts` retorna `accounts: [{user_id, email, display_name, subscription_tier, is_primary}]`,
  mas **retorna a lista completa de contas apenas enquanto a conta primária está ativa** (apenas a conta atual quando uma não primária está ativa) — portanto, a ferramenta não depende disso.
- Exemplos de contas registradas (a tabela real de contas reside no `config.toml` de nível de usuário; espaços reservados mostrados aqui):
  A `alice` / alice@example.com / uid `00000000-0000-4000-8000-0000000000aa` (Max);
  B `bob` / bob@example.com / uid `00000000-0000-4000-8000-0000000000bb` (Pro, primária).
