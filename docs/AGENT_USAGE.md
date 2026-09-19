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

用途：从 Google Trends 公共 BigQuery 数据中获取每日 Top / Rising 候选词。

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

- `kind=rising`：用于发现当天快速上升候选词。
- `kind=top`：用于查看当天 Top 候选词。
- `refresh_date` 默认 UTC 昨天。
- `limit` 为 1–25。
- 该 API 不是任意关键词的 Google Trends 曲线查询。
- BigQuery rank 不是搜索量，也不是 SEO KD。

成功响应中的以下字段必须保留：

```json
{
  "usage": {
    "total_bytes_processed": 123456,
    "total_bytes_billed": 10000000,
    "cache_hit": false
  }
}
```

它们用于真实核算 BigQuery 扫描量、计费字节和缓存命中。

## 找新词时的调用顺序

1. 用 `/api/v1/trends` 的 `rising` 获取每日候选词。
2. 按业务规则排除品牌词、事件噪声和明显无关词。
3. 把保留候选批量发送给 `/api/v1/keyword-volume` 获取 Google Ads 搜索量。
4. KD、allintitle 等指标继续调用各自数据源；不要拿 Ads competition 或 BigQuery rank 代替。
5. 保存 Trends 的 `refresh_date` 与 `usage`，保证结果可追溯。

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
