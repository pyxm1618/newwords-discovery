# AI / Agent 调用说明

本仓库提供给 Codex、Antigravity 及其他自动化 Agent 使用的私有 SEO 数据 API。

## 固定生产地址

```text
POST https://newwords-discovery.vercel.app/api/v1/keyword-volume
POST https://newwords-discovery.vercel.app/api/v1/trends
```

Agent 必须使用固定生产域名，不使用随机 deployment URL。

## Agent 只持有本服务的 Bearer Key

Vercel 服务端保存：

```text
SEO_DATA_API_KEY
```

调用端保存同一个值，建议变量名：

```text
NEWWORDS_DISCOVERY_API_KEY
```

不要把真实密钥写进 GitHub、README、提示词、Skill、Agent.md、脚本源码、命令示例或聊天记录。

Agent 不需要直接持有 Google Ads OAuth 凭据，也不需要持有 BigQuery service-account JSON；这些都只保存在 Vercel 服务端。

## 正确的 Agent 行为

1. 使用固定生产 URL。
2. 从运行环境读取 `NEWWORDS_DISCOVERY_API_KEY`。
3. 不要求用户每次重新提供 API Key。
4. 不打印、回显、记录或提交 API Key。
5. 如果调用端密钥不存在，只报告“调用端密钥未配置”。
6. 通过 `Authorization: Bearer ...` 发送。
7. 根据数据需求选择正确端点，不把 Google Ads 搜索量和 Google Trends 热度混为一谈。

## Keyword Volume

用于验证候选词的 Google Ads 月搜索量、广告竞争等历史指标：

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

`competition` 与 `competition_index` 不是 SEO KD。

## Google Trends BigQuery

用于从 Google 官方 BigQuery 公共数据集中获取每日 Top / Rising 候选词。

最常用的新词发现请求：

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/trends' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"kind":"rising","country_code":"US"}'
```

指定国家和日期：

```json
{
  "kind": "rising",
  "country_code": "GB",
  "refresh_date": "2026-09-18",
  "limit": 25
}
```

规则：

- `kind=rising`：优先用于发现突然上升的候选词。
- `kind=top`：查看当天 Top 搜索词。
- `country_code`：ISO 两位国家码。
- `refresh_date`：不传时默认 UTC 昨天。
- `limit`：1–25。
- 返回的是公共数据集的每日候选词，不是任意关键词的 Trends 曲线。

返回中必须保留并可记录：

```json
{
  "usage": {
    "total_bytes_processed": 123456,
    "total_bytes_billed": 10000000,
    "cache_hit": false
  }
}
```

这三个字段用于实际核算 BigQuery 扫描量和缓存命中，不应被 Agent 丢弃。

## 找新词时的建议调用顺序

当任务目标是发现新词时：

1. 先用 `/api/v1/trends` 的 `rising` 获取当天候选词。
2. 按既有业务规则排除品牌词、明显事件噪声和无关词。
3. 再把保留候选词批量发送到 `/api/v1/keyword-volume` 获取 Google Ads 搜索量。
4. 后续 KD、allintitle 等筛选走对应数据源，不要把 BigQuery rank 当成 KD，也不要把 Google Ads competition 当成 KD。
5. 保存 Trends 返回的 `refresh_date` 与 `usage`，确保每轮结果可追溯。

## 一次配置，而不是每次提供

Bearer Key 必须同时存在于服务端和调用端。Google Ads OAuth 与 BigQuery service-account JSON 只存在服务端。

正常状态是：用户配置一次，之后 Agent 自动读取并调用，而不是每次请求都向用户索要密钥或 Google 凭据。
