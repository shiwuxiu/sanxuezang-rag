# 三学藏佛典知识库公开检索 HTTP 接口文档 (v1.1)

基础地址：`https://sanxuezang.com/api/rag/v1`

- **认证方式**：公开只读接口，无需 API Key 或 Cookie。
- **编码与格式**：全部请求与响应均为 `UTF-8` 编码的 JSON（`application/json; charset=utf-8`）。
- **请求体上限**：单次 POST 请求体最大 `256 KiB`。
- **合理使用配额**：单 IP 默认每分钟最多 180 次请求、每小时最多 3,000 次请求；全局并发上限 12。触发限流时返回 `HTTP 429` 及 `Retry-After` 秒数。

---

## 1. 查看开放的知识库列表

`GET /api/rag/v1/datasets`

### 响应示例

```json
{
  "ok": true,
  "default_kb": "cbeta",
  "datasets": [
    {
      "kb": "cbeta",
      "title": "CBETA 电子佛典知识库 (Production)",
      "description": "收录大正藏 (T)、卍续藏 (X)、嘉兴藏 (B)、藏外佛教文献 (ZW) 等 11,822 部佛典原文切片（161.4万+ chunks），支持简繁自动互通检索、BM25+向量混合检索、BGE 神经网络重排序 (Rerank)、多维查询词批量扩展与经律论注疏智能分级聚合、关键词高亮、索引问题元数据、按经名定向筛选及单卷全文按原序连续读取。",
      "doc_count": 11822,
      "chunk_count": 1614449,
      "examples": [
        "《金刚经》应无所住而生其心",
        "阿赖耶识 种子 现行",
        "摩诃止观 一念三千"
      ],
      "features": [
        "hybrid_search_bm25_vector",
        "opencc_dual_script",
        "doc_aggs_canonical_classification",
        "highlight",
        "chunk_questions_keywords_positions",
        "optional_bge_rerank",
        "batch_multi_query_expansion",
        "full_scroll_reconstruction"
      ]
    }
  ]
}
```

---

## 2. 单次混合检索 (`POST /api/rag/v1/search`)

对指定知识库执行 BM25 全文 + 向量混合检索，默认开启简繁双语自动扩展与合并去重，并返回候选池高频经卷聚合统计（`doc_aggs`）及经律论自动分类。

### 请求参数 (JSON Body)

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kb` | string | 否 | `"cbeta"` | 知识库标识（须在 `/datasets` 开放列表中） |
| `query` | string | 是 | - | 检索词或问题（最长 10,000 字符，简繁均可） |
| `page` | int | 否 | `1` | 页码（`1` ～ `200`） |
| `page_size` | int | 否 | `30` | 返回切片条数（兼容别名 `top_k`，`1` ～ `200`） |
| `candidate_k` | int | 否 | `max(page_size*3, 100)` | 底层检索候选池大小（`1` ～ `500`） |
| `title` | string | 否 | `""` | 按经名/书名关键词过滤（如 `"金刚"`、`"摩诃止观"`，简繁自动互通） |
| `doc_ids` | array[string] | 否 | `[]` | 限定在指定的 `doc_id` 列表内检索（最多 200 个） |
| `dual_script` | bool | 否 | `true` | 是否自动进行简繁双语扩展检索与结果合并 |
| `highlight` | bool | 否 | `true` | 是否返回关键词高亮片段（`<em>...</em>`） |
| `rerank` | bool/string | 否 | `false` | 传 `true` 启用 `BAAI/bge-reranker-v2-m3@SILICONFLOW` 神经网络重排序 |
| `similarity_threshold` | float | 否 | `0.15` | 最低相似度阈值（`0.0` ～ `1.0`） |
| `vector_similarity_weight` | float | 否 | `0.3` | 向量相似度权重（`0.3` 表示 70% BM25 词频 + 30% 向量语义） |
| `metadata_condition` | object | 否 | `null` | 原生元数据过滤条件字典 |
| `reference_metadata` | bool | 否 | `false` | 是否返回引用元数据 |

### 响应示例

```json
{
  "ok": true,
  "kb": "cbeta",
  "query": "应无所住而生其心",
  "expanded_queries": ["应无所住而生其心", "應無所住而生其心"],
  "title_filter": "金刚",
  "rerank_model": null,
  "total": 64,
  "page": 1,
  "page_size": 2,
  "doc_aggs": [
    {
      "doc_id": "783e4922578e11f1b25acfa92f824e8a",
      "doc_name": "[金剛經註解][X0468].docx",
      "count": 5,
      "source_kind": "commentary",
      "source_kind_label": "注疏"
    }
  ],
  "chunks": [
    {
      "chunk_id": "ddd4344391efda79",
      "doc_id": "783e4922578e11f1b25acfa92f824e8a",
      "doc_name": "[金剛經註解][X0468].docx",
      "source_kind": "commentary",
      "source_kind_label": "注疏",
      "kb": "cbeta",
      "content": "一、合理相分第三十\n是故，须菩提！诸菩萨摩诃萨应如是生清净心，不应住色生心，不应住声、香、味、触、法生心，应无所住而生其心。",
      "highlight": "一合理相分第三十是故须菩提诸菩萨摩诃萨应如是生清净心不应住色生心不应住声香味触法<em>生</em> <em>心</em> <em>应</em> <em>无所</em> <em>住</em> <em>而</em> <em>生</em> <em>其</em> <em>心</em>",
      "similarity": 0.4918,
      "term_similarity": 0.3204,
      "vector_similarity": 0.8919,
      "positions": [[29, 29, 412, 468, 520]],
      "important_keywords": ["清净心", "不住色生心", "不住声香味触法生心", "无所住", "生其心"],
      "questions": [],
      "tag_kwd": [],
      "doc_type_kwd": ""
    }
  ]
}
```

---

## 3. 多维查询词批量扩展与经律论智能发现 (`POST /api/rag/v1/batch_search`)

一次提交最多 30 个多维度查询词，自动完成简繁扩展、并发召回、按经卷聚合命中频次、计算综合相关度评分（`composite_score`），并按 **契经 (`sutra`) / 律典 (`vinaya`) / 阿毘达磨 (`abhidharma`) / 论典 (`treatise`) / 注疏 (`commentary`) / 其他经典 (`other_textual`)** 自动归类。

### 请求参数 (JSON Body)

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `kb` | string | 否 | `"cbeta"` | 知识库标识 |
| `queries` | array[string] | 是 | - | 查询词列表（`1` ～ `30` 个） |
| `page_size` | int | 否 | `30` | 每个查询词召回的切片数（`1` ～ `100`） |
| `top_docs` | int | 否 | `80` | 返回的聚合经卷上限（`1` ～ `300`） |
| `top_chunks` | int | 否 | `60` | 返回的跨查询全局高分切片上限（`1` ～ `300`） |
| `title` | string | 否 | `""` | 全局限定经名/书名关键词筛选 |
| `dual_script` | bool | 否 | `true` | 是否自动简繁互通 |
| `highlight` | bool | 否 | `false` | 是否返回高亮片段 |
| `similarity_threshold` | float | 否 | `0.15` | 最低相似度阈值 |
| `vector_similarity_weight` | float | 否 | `0.3` | 向量权重 |

### 响应结构

- `ranked_documents`：按 `composite_score` 降序排列的经卷列表（含 `doc_id`、`doc_name`、`source_kind`、`source_kind_label`、`composite_score`、`max_similarity`、`avg_similarity`、`hits_count`、`doc_agg_count`、`title_matched`、`matched_queries`、`sample_chunks`）。
- `grouped_by_kind`：按 `sutra`、`vinaya`、`abhidharma`、`treatise`、`commentary`、`other_textual` 六大类分组的经卷列表。
- `chunks`：跨所有查询词去重后的全局高分切片列表。

---

## 4. 按经名/书名搜索文档目录 (`GET /api/rag/v1/documents`)

`GET /api/rag/v1/documents?kb=cbeta&keyword=摩诃止观&page=1&page_size=30`

### 查询参数

- `kb`：知识库标识（默认 `cbeta`）
- `keyword`：经名或书名关键词（支持简体或繁体，自动双向匹配）
- `page`：页码（默认 `1`，最大 `200`）
- `page_size`：每页条数（默认 `30`，最大 `200`）

---

## 5. 分页读取单卷原文切片 (`GET /api/rag/v1/chunks`)

`GET /api/rag/v1/chunks?kb=cbeta&doc_id=<doc_id>&page=1&page_size=30`

### 查询参数

- `kb`：知识库标识（默认 `cbeta`）
- `doc_id`：文档 ID（必填，可从 `/search`、`batch_search` 或 `/documents` 获取）
- `keyword`：在单卷内部筛选的关键词（可选）
- `page`：页码（默认 `1`，最大 `200`）
- `page_size`：每页条数（默认 `30`，最大 `200`）

---

## 6. 按原序完整还原整卷经文 (`GET /api/rag/v1/full_document`)

`GET /api/rag/v1/full_document?kb=cbeta&doc_id=<doc_id>`
或
`GET /api/rag/v1/full_document?kb=cbeta&doc_name=般若波罗蜜多心经`

拉取该经卷的全部切片，并按切片元数据中的 `positions[0][0]` 原始位置索引升序排列，还原为完整连续的整卷经文（`full_text`）及有序切片数组（`chunks`）。
