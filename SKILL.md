---
name: sanxuezang-rag
description: 三学藏佛典知识库公开检索技能（CBETA Production 等已开放库）。供 AI Agent 检索佛经、律典、论疏原文切片，支持简繁自动互通、BM25+向量混合检索、BGE Rerank 重排序、多维查询词批量扩展与经律论注疏智能分级发现、按经名定向筛选及单卷全文按原序连续还原。当需要查询佛教经典原文、核对经论出处、搜集义理证据、做佛典主题汇编或调用三学藏 RAG 知识库时使用。
---

# 三学藏佛典知识库公开检索 (sanxuezang-rag)

通过三学藏官网公开只读检索网关（`https://sanxuezang.com/api/rag/v1`）检索已开放的佛教典籍知识库。

- **零配置即用**：无需注册账号、无需配置 API Key、无需安装第三方 Python 依赖（仅需 Python 3.9+ 标准库）。
- **全功能无缩水**：完整开放底层定制版 RAGFlow 检索引擎的核心能力：
  1. **简繁双语自动互通（OpenCC Dual-Script）**：底层文献多为 CBETA 繁体原典，网关内置简繁双向转换与多路召回合并，输入简体或繁体均可精准召回。
  2. **混合检索与参数调优（Hybrid BM25 + Vector）**：支持自定义相似度阈值（`--similarity-threshold`）、向量/词频权重配比（`--vector-weight`，默认 70% BM25 词频 + 30% 向量语义）及底层候选池大小（`--candidate-k`，最高 500）。
  3. **可选 BGE 神经网络重排序（Neural Rerank）**：支持一键开启 `--rerank`（调用 `BAAI/bge-reranker-v2-m3` 对候选切片做深度语义重排）。
  4. **候选池经卷聚合与经律论自动分类（`doc_aggs`）**：每次检索自动返回候选池高频命中经卷统计，并按 CBETA 经录规则自动标注类别：**契经 (`sutra`) / 律典 (`vinaya`) / 阿毘达磨 (`abhidharma`) / 论典 (`treatise`) / 注疏 (`commentary`) / 其他经典 (`other_textual`)**。
  5. **丰富切片元数据**：每条切片返回综合得分、词频得分、向量得分、高亮片段（`highlight`）、索引阶段生成的问答对（`questions`）、核心关键词（`important_keywords`）及原文坐标（`positions`）。
  6. **多维查询词批量扩展与经典智能发现（`batch-search`）**：支持一次提交多达 30 个多维度查询词，自动跨查询聚合命中经卷、计算综合相关度评分（`composite_score`），并按「契经 / 律典 / 阿毘达磨 / 论典 / 注疏」分级输出经典发现报告。
  7. **整卷原文按原序完整还原（`full-doc`）**：针对强相关经卷，支持一键拉取该卷全部切片并按 `positions[0][0]` 原始文本顺序完整拼接还原，直接支撑「主题摘录 + 强相关整卷附录」汇编工作流。

---

## 快速开始（CLI 命令）

随附脚本位于 [`scripts/rag_cli.py`](scripts/rag_cli.py)，所有命令均支持附加 `--json` 输出结构化 JSON 供 Agent 解析。

### 1. 查看当前开放的知识库

```bash
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py datasets
```

当前默认开放知识库为 `cbeta`（**CBETA 电子佛典知识库 Production**，收录大正藏 T、卍续藏 X、嘉兴藏 B、藏外佛教文献 ZW 等 11,822 部佛典，共 1,614,449 个原文切片）。

### 2. 单次检索佛典原文切片 (`search`)

```bash
# 基础检索（默认返回 Top 30，自动简繁互通 + 展示 doc_aggs 经卷统计 + 关键词高亮）
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py search "阿赖耶识 种子 现行"

# 限定在某部经论内检索（--title 支持经名简称，如“金刚”、“摩诃止观”、“成唯识论”）
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py search "应无所住而生其心" --title "金刚" --top-k 20

# 大批量召回（单次最多返回 200 段，底层候选池最高 500）
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py search "一念三千 三谛圆融" --top-k 100 --candidate-k 300

# 启用 BGE 神经网络重排序 (--rerank) 提升复杂语义问题排序精度
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py search "菩萨如何于生死中行方便而不染着" --rerank --top-k 20

# 输出原始 JSON 供程序处理
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py --json search "缘起性空" --top-k 20
```

### 3. 多维查询词批量扩展与经律论智能发现 (`batch-search`)

研究某个佛学主题（如「十二因缘」「八识规矩」「净土三资粮」「入寺礼仪」）时，单一查询词容易漏掉异译或不同宗派表述。使用 `batch-search` 可一次传入最多 30 个查询词，自动完成跨查询去重、经卷命中频次聚合、经名匹配加权，并按**专门契经 / 律典 / 阿毘达磨 / 论典 / 注疏**分级输出：

```bash
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py batch-search \
  "十二因缘" "十二缘起" "十二有支" "无明缘行" "此有故彼有" "流转还灭" \
  --per-query-k 30 --top-docs 60 --top-chunks 30
```

### 4. 按经名查找目录与 `doc_id` (`documents`)

```bash
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py documents "楞严经"
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py documents "摩诃止观" --page-size 50
```

### 5. 分页读取单卷切片 (`chunks`) 或完整还原整卷经文 (`full-doc`)

```bash
# 分页读取指定 doc_id 的切片
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py chunks <doc_id> --page 1 --page-size 50

# 按 positions[0][0] 原始顺序一键还原整卷全文并保存到本地文件
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py full-doc --doc-id <doc_id> -o ./整卷原文.md

# 也可直接按经卷名还原整卷全文
python3 /path/to/sanxuezang-rag/scripts/rag_cli.py full-doc --doc-name "般若波罗蜜多心经"
```

---

## Agent 高级检索与主题汇编工作流指南

### 一、10 维度查询词扩展策略（配合 `batch-search`）

当用户要求全面调研某个佛教主题、搜集经证或寻找相关经典时，建议先由 Agent 生成 **8～15 个多维度查询词**，再用 `batch-search` 一次性检索聚合：

1. **核心名相**：用户原词及其标准佛学名相（如 `佛塔`、`窣堵波`、`浮图`、`塔婆`）
2. **古汉音译与异译**：旧译、新译、音译词（如 `阿赖耶` / `阿梨耶` / `藏识`）
3. **经典固定句式**：经中常见发端或结语（如 `作礼围绕`、`右绕三匝`、`应如是住`）
4. **核心动作与行法**：具体修行或仪轨动作（如 `供养恭敬`、`瞻礼赞叹`、`至心归命`）
5. **经典譬喻**：经典常用比喻（如 `如梦泡影`、`盲龟值木`、`芭蕉水沫`）
6. **对举概念与反面遮诠**：正反对比或遮诠词（如 `常乐我净`、`无我无常`）
7. **法数归摄**：带数字的法相词组（如 `四种四谛`、`三性三无性`、`十种功德`）
8. **果位与利益**：功德、果报、因果表述（如 `得福甚多`、`获福无量`、`灭无量罪`）
9. **专门契经名**：已知探讨该主题的代表经名（如 `右绕佛塔功德经`、`造塔延命功德经`）
10. **重要律典与论疏名**：相关律部或论疏名称（如 `四分律`、`摩诃僧祇律`、`大智度论`、`瑜伽师地论`）

### 二、综合相关度评分公式（网关内置）

`batch-search` 对每部命中文档自动计算综合相关度评分：
$$\text{composite\_score} = \text{max\_sim} \times \left(1 + 0.3 \times \frac{\min(\text{hits}, 5)}{5}\right) + \begin{cases} 0.15 & \text{若文档标题包含任一查询词} \\ 0 & \text{其他} \end{cases}$$

### 三、「主题摘录 + 强相关整卷附录」汇编规范

当用户要求整理某主题的佛典原文资料集时，推荐采用以下两段式工作流：
1. **第一部分：分类主题摘录**：使用 `batch-search` 获取跨经论的高分原文切片，按子主题归类，每条引文严格标注 `doc_name`（经名+卷数）并保持原文逐字忠实，不将 AI 改写混作佛经原文。
2. **第二部分：强相关整卷全文附录**：从 `batch-search` 的 `ranked_documents` 中挑出标题直接命中或高密度命中的专门短经/核心单卷，调用 `full-doc --doc-id <id>` 拉取按 `positions[0][0]` 排序还原的整卷原文，附于汇编文档末尾，确保上下文完整不割裂。

---

## 直接 HTTP 接口接入

若在非 Python 环境或自定义 Agent 框架中直接调用 HTTP 接口，请阅读 [HTTP 接口参考文档](references/api.md)。
