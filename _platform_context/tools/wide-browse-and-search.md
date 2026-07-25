# 网页信息获取工具选择树

按"从轻到重"排序，选**能满足需求的最轻工具**。

## 决策树

```
需要静态网页文本 / 单个 URL 内容
        ├─ 单个 URL 已知 → fetch_url（可加 prompt 用 LLM 提取）
        └─ 单个 URL 已知且需要原始文件 → bash + curl / wget
                （比如 gitlab.com 的 raw source）

需要"当前信息"（新闻、价格、时效性）或"入门某话题"
        └─ search_web（并行 ≤3 query，短关键词，不要长句）

需要专业领域搜索
        ├─ 学术论文 → search_vertical(vertical="academic")
        ├─ 图片 → search_vertical(vertical="image")
        ├─ 视频 → search_vertical(vertical="video")
        ├─ 购物 → search_vertical(vertical="shopping")
        └─ 找人 → 先 load_skill(name="search")，跟 recipes/people-research.md

要在网页上"做动作"（登录、填表、点击、下单）
        └─ browser_task

10+ 个网站批量提取结构化数据
        └─ wide_browse（20+ 站点必须先 confirm_action）

需要网页视觉截图
        └─ pplx-tool screenshot_page
```

## search_web 使用要点

- 短关键词（像 Google 那样打），不要写完整句
- 不要用 `"..."` 引号（会太严格）
- 一次 ≤3 query，并行分维度探索
- 多实体比较：拆分成单实体 query，别塞一起
- 时效性问题在 query 里加年份，比如 "示例项目 L2 processor changes 2026"

## fetch_url 使用要点

- `prompt` 参数：让 LLM 从长页面里提取指定信息，节省 token
- **不加 prompt** 且 `max_length` 调大 → 返回原文，适合抓 diff / 代码 / DOI 页
- 缓存过期或返回错的 → `force_fetch=True`（贵，谨慎用）
- **不能用于**：本地文件、内部路径、私有 S3 —— 用 `read`

## browser_task 使用要点

- **认证约束**：云端沙盒无 saved cookie，涉及用户账号必须要么用户提供凭证、要么走
  `use_local_browser={"local": true, ...}`（本地 Comet 浏览器，有其现存 session）
- **求职类**（找工作/招聘）必须 browser_task 直接上招聘板，**不要** 用 search_web
  找职位链接（结果都是过期/假链接）
- **子代理不能用 browser_task**，只有主 agent 能

## wide_browse 使用要点

**必须的三步**：
1. 写实体文件（一行一个 URL 或站点名，去重）
2. **数一下有多少行 —— 20+ 必须先 `confirm_action`**：
   ```
   action="browse"
   question="Computer will browse across many websites to get you the best
   information. This may consume a significant amount of credits."
   ```
3. 通过确认（或 <20）后调 wide_browse

- 输出 schema 写成独立 JSON 文件后传路径（不是 inline）
- 结果自动汇总到 workspace JSON
- 不能截图 —— 要截图用 `screenshot_page`

## 用词禁令

**不要用** "scrape / scraping / crawl / crawling" —— 用 "collect / extract /
gather / fetch / browse" 替代（用户明确指令）。

## 本项目实际用法

- **深研报告** 里所有 URL 都是子代理通过 search_web + fetch_url 交叉核实过的
- **上游 sib4v2_corral diff** 是 `git clone https://gitlab.com/kdhaynes/sib4v2_corral`
  之后本地 `git diff`，**不**通过 web 工具
- **文献 DOI** 一律 `fetch_url("https://doi.org/...")` 验证可访问后才引用
- **本地代理跑完的产物** 通过 workspace 文件流转，不涉及 web 工具
