# Perplexity 命令行工具集

<p class="homepage-scope-note" role="note">
  <strong>适用于现有订阅，而非按量计费 API</strong>
</p>

Perplexity 对话记录归档与交互查询工具（`pplx-export` / `pplx-ask` 双命令）。

通过浏览器 cookie 直连 Perplexity REST/GraphQL API，把对话（含步骤、引文、深研报告、
computer 资产、子代理工作流）完整归档为本地 Markdown + JSON。成功导出会同时保留
原始响应与渲染产物，因此无需重抓即可离线重渲。

## 简介

除了归档历史对话之外，本项目的目的更多是让离数据更近、有更强算力的本地 agent
具备一定的 Perplexity Computer 能力。通过在工作循环中直接访问 Perplexity
深度研究模式生成的报告，本地 agent 可以利用高质量信息更精确地调整代码中的关键
参数，同时更充分地利用现有的 Perplexity Max 订阅。

> 截止至7月20日，Perplexity 并未提供类Unix环境中的官方 CLI
> 我们注意到官方于7月23日提供了Computer模式中所使用的pplx工具的公开发布版本；但该工具仍是按量计费的

但它并非 Computer 模式的完整替代。有两项能力无法复制：

- 深度研究 skill 可自由指定模型；
- 模型委员会 skill 可指定多个不同模型分别深度研究、输出报告并直接横向比较。

仓库中的 [`_platform_context/`](https://github.com/Yiksing/pplx-tools/tree/main/_platform_context)
目录存档了一些系统提示词和运行规则，可帮助在本地近似 Computer 的部分工作流，
包括深度研究模式选择和子代理模型选择。

## 功能概览

### `pplx-export` —— 归档你的 library

- library 索引与空间索引
- 单线程/批量导出（增量早停 + 断点续跑）
- 资产补救与用量补录
- 对话关系图
- 离线重渲（`re-render`，零网络）
- 周期增量 cron 片段

### `pplx-ask` —— 在命令行发问

- SSE 流式发问（search / deep-research / council / study 四模式）
- 完成后自动移入 BOT 空间、已读回执
- 创建的线程自动归档——供其他 agent 调用检索实时信息

五种模式的产物边界（引文/报告/资产/子代理）见[模式](guide/modes.md)；渲染保真
原则见[导出管线](architecture/export-pipeline.md)。

!!! note "文档来源"

    MkDocs 站点中的多数页面依据当前代码与测试生成或重建；部分页面也保留了此前与
    agent 讨论形成的设计背景、观察记录和决策。若文档表述与实现不一致，以当前代码
    和测试为准。

## 接下来去哪

- **使用工具**——按任务阅读[使用指南](guide/index.md)。
- **理解实现**——从[系统架构阅读地图](architecture/index.md)进入。
- **处理已观察到的 Web 接口**——查阅 [Web API 参考](reference/api/index.md)。
- **安全修改项目**——遵循[维护者指南](development/index.md)。
