# AI / Agent 调用说明

本仓库提供给 Codex、Antigravity 及其他自动化 Agent 使用的私有 SEO 数据 API。

## 固定入口

```text
POST https://newwords-discovery.vercel.app/api/v1/keyword-volume
POST https://newwords-discovery.vercel.app/api/v1/trends
```

Agent 使用固定生产域名，不使用随机 Preview URL 作为长期配置。

## 当前生产状态

截至 **2026-09-19**，两个接口都已完成真实 authenticated smoke：

- `/api/v1/trends`：生产 HTTP `200`，真实返回 `google_trends_bigquery` 数据及 BigQuery usage。
- `/api/v1/keyword-volume`：生产 HTTP `200`，真实返回 `google_ads` 历史搜索量。
- 本次验证对应生产代码 revision：`c2911ffbb52a6d28b2c31db7e57ec8ac1fad537c`。

这表示当前生产链路已验证，不表示未来部署自动继承“已验证”状态。部署新 revision、轮换密钥或修改上游权限后，应重新做 authenticated smoke。

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

1. 用 `/api/v1/trends` 的 `rising` 获取每日候选词和完整 rolling weekly history。
2. 下游 AI 先利用 history 判断过去长期低基数、首次出现、连续爬升、单周尖峰、回落后二次爬升、历史重复/季节性等生命周期事实；这些判断不在 API 内硬编码。
3. 再按业务规则排除品牌词、事件噪声和明显无关词。
4. 把保留候选批量发送给 `/api/v1/keyword-volume` 获取 Google Ads 搜索量。
5. KD、allintitle 等指标继续调用各自数据源；不要拿 Ads competition 或 BigQuery rank 代替。
6. 保存 Trends 的 `refresh_date`、history metadata 与 `usage`，保证结果可追溯。

## 错误与验证规则

- `401`：调用端 API Key 缺失或错误。只报告调用端密钥未配置/无效，不要求用户在聊天中粘贴真实密钥。
- `500 server_configuration_error`：服务端对应数据源的环境变量不完整。不要误判成关键词无数据。
- `502/504`：上游 Google 服务失败或超时。不要把失败响应写入正式关键词结果。
- 文档存在路由并不等于当前生产部署和上游凭据已经验证。需要声明“已真实可用”时，应同时确认当前 Vercel deployment 为 READY，并完成真实 authenticated smoke。

## 一次配置

正常模式是：服务端保存上游凭据，调用端保存一次 `NEWWORDS_DISCOVERY_API_KEY`，之后 Agent 自动调用。

不要每次任务都重新向用户索取 Google Ads OAuth、BigQuery service account 或 API Key。

## 服务端凭据运维

BigQuery 的 Service Account JSON 只保存在 Vercel 的 `GOOGLE_CLOUD_SERVICE_ACCOUNT_JSON` 中。生产验证通过后，本地下载的 JSON 文件应删除；但 Google Cloud 中与该 JSON 对应的 key 不能删除，否则 Vercel 会失去认证能力。

Service Account 需要具备创建 BigQuery query job 的权限；当前生产配置使用 `BigQuery Job User`。

如果为了首次创建 key 临时覆盖了“禁止创建服务账号密钥”的组织政策，完成 key 创建后应恢复继承/限制状态。恢复“禁止创建新 key”不会让已经创建且正在使用的 key 失效。

GitHub Actions 中可保存同值的 `SEO_DATA_API_KEY` repository secret，用于不暴露真实值的生产回归 smoke。Agent 日常调用仍建议使用环境变量 `NEWWORDS_DISCOVERY_API_KEY`。
