# Web API 参考

`pplx-export` 与 `pplx-ask` 所使用的 Perplexity REST 和 GraphQL 行为观察记录。

!!! warning "观察到的接口，而非稳定性承诺"

    本区依据项目从 Web 应用、归档响应、前端 bundle 和当前实现中观察到的行为整理，
    不是 Perplexity 官方 API 契约。修改联网代码前，应重新验证带日期的观察结论。

## 推荐阅读顺序

1. [认证模型](api-authentication.md)——会话 cookie、令牌、关联账户与身份。
2. [GraphQL](api-graphql.md)——持久化查询、APQ 标识符与在用操作。
3. [REST 端点](api-rest-endpoints.md)——按用途分组的已观察端点。
4. [响应与错误语义](api-responses-errors.md)——响应形态、解析纪律、终态和风控行为。
5. [发现方法与路线图](api-discovery-roadmap.md)——端点发现方法和仍待确认的问题。

## 相关实现文档

- [pplx-ask 与多账户](../../architecture/ask-and-accounts.md)
- [限频与错误处理](../../architecture/rate-limiting-errors.md)
- [故障排查](../../guide/troubleshooting.md)
