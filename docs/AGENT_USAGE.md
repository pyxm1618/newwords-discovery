# AI / Agent 调用说明

本仓库提供给 Codex、Antigravity 及其他自动化 Agent 使用的私有 SEO 数据 API。

## 固定生产地址

Keyword Volume API 的正式地址为：

```text
POST https://newwords-discovery.vercel.app/api/v1/keyword-volume
```

`newwords-discovery.vercel.app` 是当前 Vercel 项目的生产域名。普通的 deployment URL 会变化，Agent 不应使用带随机后缀的 deployment URL。

## Agent 不需要 Google 凭据

以下凭据只保存在 Vercel 服务端，调用方不应持有：

```text
GOOGLE_ADS_CLIENT_ID
GOOGLE_ADS_CLIENT_SECRET
GOOGLE_ADS_REFRESH_TOKEN
GOOGLE_ADS_CUSTOMER_ID
```

Agent 只需要访问本服务，并使用本服务自己的 Bearer API Key。

## API Key 的服务端与调用端角色

Vercel 中保存：

```text
SEO_DATA_API_KEY
```

这是服务端用于验证请求的密钥。

调用端需要持有同一个值，但建议在调用端保存为：

```text
NEWWORDS_DISCOVERY_API_KEY
```

两者的值相同，但名称不同是为了明确角色：

- `SEO_DATA_API_KEY`：仅 Vercel 服务端使用。
- `NEWWORDS_DISCOVERY_API_KEY`：仅调用 Agent 的运行环境使用。

不要把真实 API Key 写进 GitHub、README、提示词、Skill、Agent.md、脚本源码、命令示例或聊天记录。

## 正确的 Agent 行为

Agent 应遵循以下规则：

1. 使用固定生产 URL，不自行寻找其他 deployment URL。
2. 从运行环境读取 `NEWWORDS_DISCOVERY_API_KEY`。
3. 不要求用户每次重新提供 API Key。
4. 不打印、回显、记录或提交 API Key。
5. 如果 `NEWWORDS_DISCOVERY_API_KEY` 不存在，只报告“调用端密钥未配置”，不要要求用户把密钥直接贴进聊天。
6. 请求时通过 `Authorization: Bearer ...` 发送密钥。
7. Google OAuth、refresh token 和 customer ID 全部由 Vercel 服务端处理。

## 调用示例

调用端已经配置 `NEWWORDS_DISCOVERY_API_KEY` 后：

```bash
curl -X POST 'https://newwords-discovery.vercel.app/api/v1/keyword-volume' \
  -H "Authorization: Bearer $NEWWORDS_DISCOVERY_API_KEY" \
  -H 'Content-Type: application/json' \
  --data '{"keywords":["i ching online","i ching reading"]}'
```

Agent 不应把环境变量展开后的真实值显示给用户。

## 请求参数

最小请求：

```json
{
  "keywords": ["i ching online", "i ching reading"]
}
```

默认口径：

```text
geo: 2840 = United States
language: 1000 = English
network: GOOGLE_SEARCH
```

也可以显式覆盖：

```json
{
  "keywords": ["i ching online"],
  "geo_target_constant": "2840",
  "language_constant": "1000",
  "network": "GOOGLE_SEARCH"
}
```

## 返回数据

成功时返回结构化 JSON，例如：

```json
{
  "source": "google_ads",
  "query": {
    "geo_target_constant": "2840",
    "language_constant": "1000",
    "network": "GOOGLE_SEARCH"
  },
  "results": [
    {
      "keyword": "i ching online",
      "avg_monthly_searches": 22200,
      "competition": "LOW",
      "competition_index": 0,
      "monthly_search_volumes": []
    }
  ]
}
```

`competition` 和 `competition_index` 是 Google Ads 广告竞争指标，不是 SEO Keyword Difficulty。

## 一次配置，而不是每次提供

Bearer Key 必须同时存在于服务端和调用端，这是任何私有 API 认证的基本要求。Vercel 环境变量负责保存服务端副本；调用 Agent 的 Secret Store / 环境变量负责保存调用端副本。

正常状态应是：用户只配置一次，之后 Agent 自动读取并调用，而不是每次请求都向用户索要密钥。
