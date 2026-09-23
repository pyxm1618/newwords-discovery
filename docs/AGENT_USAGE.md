# AI / Agent 调用说明

本仓库提供给 Codex、Antigravity 及其他自动化 Agent 使用的私有 SEO 数据 API。

## 固定入口

```text
POST https://newwords-discovery.vercel.app/api/v1/keyword-volume
POST https://newwords-discovery.vercel.app/api/v1/trends
POST https://newwords-discovery.vercel.app/api/v1/trending-now
```

Agent 使用固定生产域名，不使用随机 Preview URL 作为长期配置。

## 当前生产状态

截至 **2026-09-19**，两个接口都完成了真实 authenticated production smoke，但验收 revision 必须按能力分别记录：

- `/api/v1/keyword-volume`：生产 HTTP `200`，真实返回 `source=google_ads`。Keyword Volume 的历史验收 revision 是 `c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c`。
- `/api/v1/trends`：rolling-history 运行实现 revision `8b2096a49f3026fe61fdc2872cada82f9a2d0356` 到达 Vercel Production `READY` 后，US Rising、US Top、GB Rising、GB Top 四条真实链路全部 HTTP `200`。
- Trends 首次 uncached 验收使用 `refresh_date=2026-09-18`：US 每个返回 term 有 261 个 weekly history points，GB 有 262 个；四路均返回 `history.score_aggregation=mean_across_available_regions`。
- 同一 US Rising `limit=5` 请求，rolling-history 版本实际 `total_bytes_processed=79,252,802`、`total_bytes_billed=79,691,776`、`cache_hit=false`。
- 旧的 `44,779,770 / 45,088,768` 只代表修复前 candidate-only 查询的成本基线，不能再作为当前 rolling-history 接口的验收结果。
- 后续文档-only 部署后的四路回归 smoke 再次全部 HTTP `200`；由于命中 BigQuery cache，该轮 `processed=0`、`billed=0`。

不要把后续文档提交的 `main` SHA 写成 Trends 运行实现 SHA。对于这次修复，运行实现证据固定指向 `8b2096a49f3026fe61fdc2872cada82f9a2d0356`；文档提交可以继续推动 `main`，但并不改变运行代码。

这表示上述已验收运行链路在该日期真实可用，不表示未来 runtime 修改、密钥轮换或上游权限变化自动继承“已验证”状态；发生这些变化后应重新做 authenticated smoke。

## Agent 只持有一个调用密钥

服务端：

```text
SEO_DATA_API_KEY
```

调用端建议：

```text
NEWWORDS_DISCOVERY_API_KEY
```

Agent 不持有：

- Google Ads OAuth client secret / refresh token
- BigQuery service-account JSON
- 其他服务端上游凭据

不要把真实密钥写进 GitHub、README、提示词、Skill、Agent.md、脚本源码、命令示例或聊天记录。

## 选择正确的数据源

### Keyword Volume

用途：验证已有候选词的 Google Ads 历史搜索量等指标。

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/keyword-volume' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"keywords":["i ching online","i ching reading"]}'
```

默认：

```text
geo: 2840 = United States
language: 1000 = English
network: GOOGLE_SEARCH
```

注意：

- Google Ads `competition` / `competition_index` 是广告竞争，不是 SEO KD。
- 不要把 Keyword Volume API 当成新词发现源本身。

### Google Trending Now RPC

用途：获取 Google Trends “Trending now” 当前实时趋势池。该链路直接读取 Google Trends 网页正在使用的 `batchexecute` RPC，不经过 BigQuery、Google Ads 或 Google Trends API Alpha。

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/trending-now' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"country_code":"US","hours":4,"limit":50,"hl":"en"}'
```

支持窗口：

```text
4 hours
24 hours
48 hours
168 hours (7 days)
```

默认：

```text
country_code: US
hours: 4
limit: 50
hl: en
```

注意：

- 数据源标记固定为 `source=google_trending_now_rpc`。
- 这是 Google 网页内部使用的未公开 RPC，不是正式开发者 API；Google 可能变更 RPC id、响应结构或限流策略。
- 该接口当前无需 Google API key，也不消耗 BigQuery 查询额度或 Google Ads operation。
- **没有 RSS 自动降级。** RPC 失败、429、协议变化或无数据时，调用方必须看到真实失败/空结果，不能把别的数据源伪装成 RPC。
- 一个国家 + 一个窗口默认只调用一次。查不到时不要自动向前扫 BigQuery 多天来“确认没有”，避免无意义扫描费用。
- `search_volume` 是 Trending Now RPC 返回的实时趋势规模信号，不等于 Google Ads 月搜索量。
- `increase_percentage` 是当前窗口中的上升百分比，不是 SEO KD。
- `trend_breakdown` 是 Google 聚合到同一趋势下的相关/变体查询，可用于识别真正的衍生需求。
- `started_at` / `ended_at` / `active` 用于判断趋势是否仍处在异常上升期。
- 返回的 `news_refs` 只是 Google 内部新闻引用标识；当前接口不自动解析新闻正文。

### Google Trends BigQuery

用途：从 Google Trends 公共 BigQuery 数据中获取每日 Top / Rising 候选词，并直接拿到该候选词在同一 `refresh_date` partition 中自带的 rolling weekly history。

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/trends' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"rising","country_code":"US"}'
```

可指定：

```json
{
  "kind": "rising",
  "country_code": "GB",
  "refresh_date": "2026-09-18",
  "limit": 25
}
```

注意：

- `kind=rising`：当天快速上升候选词，同时保留 Google 的 `percent_gain`。
- `kind=top`：当天 Top 候选词；稳定契约下 `percent_gain=null`。
- `refresh_date` 默认 UTC 昨天。
- `limit` 为 1–25，只限制 term 数量，不截断 history。
- 每个 result 的 `history` 是按 `week` 升序的完整 rolling weekly backfill；下游需要 12 个月时自行截最近约 52 周。
- 不要把 null score 补成 0；真实 `score=0`、回落段和后续二次爬升都必须保留。
- `rank` 是候选元数据，不是历史排名曲线。
- `score` 是 Google Trends 相对兴趣指数，不是搜索量。
- 当源数据没有明确 national/country row 时，API 会对可用 DMA/region score 取均值，并通过 `history.score_aggregation` 明确说明。
- 该 API 不是任意关键词的 Google Trends 曲线查询。
- BigQuery rank 不是搜索量，也不是 SEO KD。

成功响应中的以下字段必须保留：

```json
{
  "history": {
    "window": "rolling_5_years",
    "granularity": "week",
    "score_aggregation": "mean_across_available_regions"
  },
  "usage": {
    "total_bytes_processed": 123456,
    "total_bytes_billed": 10000000,
    "cache_hit": false
  }
}
```

`usage` 用于真实核算 BigQuery 扫描量、计费字节和缓存命中。

## 找新词时的调用顺序

1. 对“现在 / 最新 / 最近4小时”类请求，先用 `/api/v1/trending-now` 做实时发现；一个国家只请求一次目标窗口，失败或空结果就如实报告。
2. 用 `/api/v1/trends` 的 `rising` 做每日回溯和 rolling weekly history 生命周期验证；多日查询按用户要求收集实际存在的分区，不为证明“没有”而无限向前扫描。
3. 下游 AI 综合实时 started/active/growth 与 BigQuery history 判断首次出现、连续爬升、尖峰、回落、复发和季节性。
4. 再按业务规则排除品牌词、事件噪声和明显无关词。
5. 把保留候选批量发送给 `/api/v1/keyword-volume` 获取 Google Ads 历史月搜索量。
6. KD、allintitle 等指标继续调用各自数据源；不要拿 Trending Now volume、Ads competition 或 BigQuery rank 代替。
7. 保存实时 `observed_at` / `hours`，以及每日 Trends 的 `refresh_date`、history metadata 与 `usage`，保证结果可追溯。

## 错误与验证规则

- `401`：调用端 API Key 缺失或错误。只报告调用端密钥未配置/无效，不要求用户在聊天中粘贴真实密钥。
- `500 server_configuration_error`：服务端对应数据源的环境变量不完整。不要误判成关键词无数据。
- `502 upstream_rate_limited`：Google Trending Now RPC 对当前请求限流。直接报告该国家实时源暂不可用；不要自动用 RSS 或 BigQuery 冒充实时结果。\n- `502/504`：上游 Google 服务失败或超时。不要把失败响应写入正式关键词结果。
- 文档存在路由并不等于当前生产部署和上游凭据已经验证。需要声明“已真实可用”时，应同时确认当前 Vercel deployment 为 READY，并完成真实 authenticated smoke。

## 一次配置

正常模式是：服务端保存上游凭据，调用端保存一次 `NEWWORDS_DISCOVERY_API_KEY`，之后 Agent 自动调用。

不要每次任务都重新向用户索取 Google Ads OAuth、BigQuery service account 或 API Key。

## 服务端凭据运维

BigQuery 的 Service Account JSON 只保存在 Vercel 的 `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` 中。生产验证通过后，本地下载的 JSON 文件应删除；但 Google Cloud 中与该 JSON 对应的 key 不能删除，否则 Vercel 会失去认证能力。

Service Account 需要具备创建 BigQuery query job 的权限；当前生产配置使用 `BigQuery Job User`。

如果为了首次创建 key 临时覆盖了“禁止创建服务账号密钥”的组织政策，完成 key 创建后应恢复继承/限制状态。恢复“禁止创建新 key”不会让已经创建且正在使用的 key 失效。

GitHub Actions 中可保存同值的 `SEO_DATA_API_KEY` repository secret，用于不暴露真实值的生产回归 smoke。Agent 日常调用仍建议使用环境变量 `NEWWORDS_DISCOVERY_API_KEY`。
