# 子代理（run_subagent）使用参考

本项目大量依赖子代理做**深度研究 + model council**（多模型评议），本文归档使用规范
和本项目特定的调用惯例。

## 三个工具

| 工具 | 用途 |
|---|---|
| `run_subagent` | 起一个子代理，异步跑，返回 `subagent_id` |
| `message_subagent` | 给已跑的子代理发追加指令（异步，下一轮生效） |
| `wait_for_subagents` | 主 agent 无独立工作时挂起等结果 |
| `cancel_subagent` | 取消 |

## 子代理类型

| type | 用途 |
|---|---|
| `deep_research` | **深度研究** —— 用户在 deep research mode 时**必须首选**且**必须委派** |
| `research` | 普通网页研究，需要联网查资料 |
| `general_purpose` | 写作、脑暴、规划、写代码、数据处理、文档、没指定文件格式的 |
| `asset` | 生成 pdf/docx/pptx/xlsx 文件 |
| `website_building` | 建网站、web app、web game |
| `codebase` | 处理**已存在**的代码仓库 |
| `memory` / `past_context` | 挖用户历史记忆 / 过往会话 |

**选择原则**：
- **文件格式（pdf/docx/pptx/xlsx）明确出现在需求里 → `asset`**
- **需要联网找当前信息 → `research`**，仅仅"听着像该研究一下"**不算**
- **写作/规划/编码没指定文件格式 → `general_purpose`**
- **建站/web app/web game → `website_building`**

## 深度研究模式（本项目频繁使用）

用户在 deep research mode 时，主 agent 收到会带 `deep-research` skill，其内容强制：

> **第一个工具调用必须是** `run_subagent(subagent_type="deep_research", objective=<用户完整请求>)`
> **紧接着** 调 `wait_for_subagents`，不能自己先搜。
> 子代理返回后，主 agent 要 **重新 `share_file` 每一个被保存的文件**（子代理自己
> share 的用户看不到，只有主 agent share 的才可见）。

**本项目使用模式**：
- 三份 Ogée 深研报告都是这么产的，push 到 `Sessions/22_.../report/perplexity_20260716_deep_research_*.md`
- 主 agent 收到子代理 summary 后，**必须** 自己再调一次 `share_file`

## Model Council（多模型评议）

- 用户要 "compare what different models think" / "model council" → 从三大厂各选一个前沿模型
  （OpenAI / Anthropic / Google），除非用户指定
- 参考 `../skills/model-catalog/multi-model-comparison.md` 里的 agreement/disagreement 合成格式
- 本项目历史上跑过 `council_report_claude_opus_4_8` / `council_report_gemini_3_1_pro` /
  `council_report_gpt_5_4` + `council_synthesis`

## 本项目子代理调用惯例

- **objective ≤ ~2000 字符**。大 spec 先写文件，objective 里引用路径
- **preload_skills** 传已加载的 skill 名，避免子代理重加载浪费 step
- **子代理没有 memory 工具** —— 用户要个性化输出时，主 agent 先 `memory_search`
  把相关 context 塞进 objective
- **文件共享** —— 主 agent 和子代理共用 sandbox；父子间靠 workspace 文件传大数据集
  ```
  子代理  →  写 /home/user/workspace/xxx.md
  父代理  →  读 /home/user/workspace/xxx.md
  ```
- **禁止的坑**：子代理跑完不 share_file，用户看不到产物；给多个并行子代理指同一
  个输出文件路径导致互相覆盖

## 中断/失败恢复

- 子代理报 "credits exhausted" → 用 `message_subagent` 让它继续，**不要** 起新 subagent
- browser_task 报 credits 用完 → 起**新的** browser_task 继续

## wide_browse（20+ 站点批量浏览）

- 不是子代理，是独立工具；20+ 实体时**必须先** `confirm_action`
  ```
  action="browse"
  question="Computer will browse across many websites... may consume a significant
  amount of credits."
  ```
- 输入是文件（一行一实体），输出是 JSON schema 结构化结果
- 本项目 示例项目/示例模型 场景很少需要（都是特定数据源），但若要一次性核对 20+ 篇文献 DOI 就用得上
