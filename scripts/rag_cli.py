#!/usr/bin/env python3
"""
三学藏佛典知识库公开检索工具 (sanxuezang-rag) — 全功能版
默认连接 https://sanxuezang.com/api/rag/v1，纯 Python 3.9+ 标准库实现，无需安装第三方依赖，无需配置 API Key。
支持功能：
  1. datasets     : 查看当前开放的知识库列表及支持特性
  2. search       : 单次混合检索（BM25 + 向量 + OpenCC 简繁自动互通 + 经律论分级统计 doc_aggs + 关键词高亮 + 可选 BGE Rerank 重排序 + 元数据过滤）
  3. batch-search : 多维查询词批量扩展检索与 CBETA 经律论注疏智能分级发现（综合相关度评分 + 契经/律典/阿毘达磨/论典/注疏自动归类）
  4. documents    : 按经名/书名关键词搜索经卷目录（简繁自动互通）
  5. chunks       : 分页读取指定经卷（doc_id）的原文切片
  6. full-doc     : 按 positions[0][0] 原始顺序完整还原整卷经文（用于主题原文汇编或整卷精读）
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_API_BASE = os.environ.get("SANXUEZANG_RAG_API", "https://sanxuezang.com/api/rag/v1").rstrip("/")
USER_AGENT = "sanxuezang-rag-skill/1.1"


def http_request(
    method: str,
    endpoint: str,
    params: dict[str, Any] | None = None,
    body: dict[str, Any] | None = None,
    api_base: str = DEFAULT_API_BASE,
    timeout: float = 55.0,
) -> dict[str, Any]:
    url = f"{api_base}/{endpoint.lstrip('/')}"
    if params:
        clean_params = {k: v for k, v in params.items() if v is not None and v != ""}
        if clean_params:
            url = f"{url}?{urllib.parse.urlencode(clean_params)}"

    headers = {
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    data_bytes = None
    if body is not None:
        data_bytes = json.dumps(body, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json; charset=utf-8"

    last_err: Exception | None = None
    openers = [
        urllib.request.build_opener(),
        urllib.request.build_opener(urllib.request.ProxyHandler({})),
    ]
    for attempt in range(3):
        opener = openers[attempt % len(openers)]
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
        try:
            with opener.open(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                return json.loads(raw)
        except urllib.error.HTTPError as exc:
            err_body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (429, 502, 503, 504) and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            try:
                err_json = json.loads(err_body)
                msg = err_json.get("error") or err_json.get("message") or f"HTTP {exc.code}"
            except Exception:
                msg = f"HTTP {exc.code}: {err_body[:200]}"
            print(f"[错误] {msg}", file=sys.stderr)
            sys.exit(1)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_err = exc
            if attempt < 2:
                time.sleep(1.0 * (attempt + 1))
                continue
    reason = getattr(last_err, "reason", last_err)
    print(f"[网络错误] 无法连接检索接口 ({url}): {reason}", file=sys.stderr)
    sys.exit(1)


def strip_em(text: str) -> str:
    return re.sub(r"</?em>", "**", text)


def cmd_datasets(args: argparse.Namespace) -> None:
    res = http_request("GET", "datasets", api_base=args.api_base)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return
    datasets = res.get("datasets") or []
    default_kb = res.get("default_kb") or "cbeta"
    print(f"当前开放知识库共 {len(datasets)} 个（默认: {default_kb}）：\n")
    for ds in datasets:
        print(f"- [{ds.get('kb')}] {ds.get('title')}")
        print(f"  文档数: {ds.get('doc_count', 0):,} | 切片数: {ds.get('chunk_count', 0):,}")
        if ds.get("description"):
            print(f"  说明: {ds.get('description')}")
        features = ds.get("features") or []
        if features:
            print(f"  特性: {', '.join(features)}")
        examples = ds.get("examples") or []
        if examples:
            print(f"  示例查询: {' / '.join(examples)}")
        print()


def cmd_search(args: argparse.Namespace) -> None:
    payload: dict[str, Any] = {
        "kb": args.kb,
        "query": args.query,
        "page": args.page,
        "page_size": args.top_k,
        "dual_script": not args.no_dual_script,
        "highlight": not args.no_highlight,
        "similarity_threshold": args.similarity_threshold,
        "vector_similarity_weight": args.vector_weight,
    }
    if args.candidate_k:
        payload["candidate_k"] = args.candidate_k
    if args.title:
        payload["title"] = args.title
    if args.doc_ids:
        payload["doc_ids"] = [x.strip() for x in args.doc_ids.split(",") if x.strip()]
    if args.rerank:
        payload["rerank"] = args.rerank_model or True
    if args.metadata_condition:
        try:
            payload["metadata_condition"] = json.loads(args.metadata_condition)
        except Exception as exc:
            print(f"[参数错误] --metadata-condition 必须是合法 JSON 对象: {exc}", file=sys.stderr)
            sys.exit(1)
    if args.reference_metadata:
        payload["reference_metadata"] = True

    res = http_request("POST", "search", body=payload, api_base=args.api_base)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    chunks = res.get("chunks") or []
    doc_aggs = res.get("doc_aggs") or []
    expanded = res.get("expanded_queries") or [args.query]
    print(f"知识库: {res.get('kb')} | 查询: {args.query}")
    if len(expanded) > 1:
        print(f"简繁互通扩展: {' / '.join(expanded)}")
    if res.get("title_filter"):
        print(f"限定经名过滤: {res.get('title_filter')}")
    if res.get("rerank_model"):
        print(f"神经网络重排序 (Rerank): {res.get('rerank_model')}")
    print(f"共匹配约 {res.get('total', len(chunks))} 条，当前第 {res.get('page', 1)} 页（返回 {len(chunks)} 条）：\n")

    if doc_aggs and not args.no_aggs:
        print("【候选池高频命中经卷统计 (doc_aggs Top 12)】")
        for agg in doc_aggs[:12]:
            label = agg.get("source_kind_label") or agg.get("source_kind") or ""
            print(f"  - [{label}] {agg.get('doc_name')} (命中 {agg.get('count')} 段 | doc_id={agg.get('doc_id')})")
        print()

    if not chunks:
        print("未检索到匹配切片。建议尝试缩短关键词、降低 --similarity-threshold 或去掉 --title 限制。")
        return

    for idx, ch in enumerate(chunks, 1):
        doc_name = ch.get("doc_name") or "未知经卷"
        kind_label = ch.get("source_kind_label") or ch.get("source_kind") or ""
        doc_id = ch.get("doc_id") or ""
        chunk_id = ch.get("chunk_id") or ""
        sim = ch.get("similarity", 0.0)
        v_sim = ch.get("vector_similarity", 0.0)
        t_sim = ch.get("term_similarity", 0.0)
        print(f"--- [{idx}] [{kind_label}] {doc_name} (综合分={sim:.4f}, 词频={t_sim:.4f}, 向量={v_sim:.4f}) ---")
        print(f"doc_id: {doc_id} | chunk_id: {chunk_id}")
        kws = ch.get("important_keywords") or []
        if kws:
            print(f"核心关键词: {', '.join(kws[:10])}")
        qs = ch.get("questions") or []
        if qs:
            print(f"索引问题: {' / '.join(str(q).strip() for q in qs[:3] if str(q).strip())}")
        if ch.get("highlight") and not args.no_highlight:
            print(f"高亮匹配: {strip_em(ch['highlight'])}")
        print(ch.get("content", "").strip())
        print()


def cmd_batch_search(args: argparse.Namespace) -> None:
    queries = [q.strip() for q in args.queries if q.strip()]
    if not queries:
        print("[参数错误] 请至少提供一个查询词", file=sys.stderr)
        sys.exit(1)

    payload: dict[str, Any] = {
        "kb": args.kb,
        "queries": queries,
        "page_size": args.per_query_k,
        "dual_script": not args.no_dual_script,
        "highlight": args.highlight,
        "similarity_threshold": args.similarity_threshold,
        "vector_similarity_weight": args.vector_weight,
        "top_docs": args.top_docs,
        "top_chunks": args.top_chunks,
    }
    if args.title:
        payload["title"] = args.title

    res = http_request("POST", "batch_search", body=payload, api_base=args.api_base, timeout=60.0)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    print(f"知识库: {res.get('kb')} | 批量查询词 ({res.get('queries_submitted')} 个): {', '.join(queries)}")
    print(f"实际执行检索 ({len(res.get('queries_executed') or [])} 次简繁变体) | 命中独立经卷: {res.get('total_unique_documents', 0)} 部 | 独立切片: {res.get('total_unique_chunks', 0)} 段\n")

    grouped = res.get("grouped_by_kind") or {}
    category_order = [
        ("sutra", "一、专门契经 (Sutra)"),
        ("vinaya", "二、律典 (Vinaya)"),
        ("abhidharma", "三、阿毘达磨 (Abhidharma)"),
        ("treatise", "四、论典 (Treatise)"),
        ("commentary", "五、注疏 (Commentary)"),
        ("other_textual", "六、其他经典 (Other)"),
    ]

    print("==================================================================")
    print("  CBETA 经典智能查找 · 分级经卷发现报告 (按综合相关度排序)")
    print("==================================================================\n")

    for kind_key, title_str in category_order:
        docs = grouped.get(kind_key) or []
        if not docs:
            continue
        print(f"### {title_str}（共 {len(docs)} 部）")
        for i, d in enumerate(docs[:20], 1):
            t_flag = " [经名直接命中]" if d.get("title_matched") else ""
            print(
                f"  {i}. {d.get('doc_name')}{t_flag}\n"
                f"     综合分={d.get('composite_score'):.4f} | 最高相似={d.get('max_similarity'):.4f} | "
                f"命中切片={d.get('hits_count')} (全库候选命中={d.get('doc_agg_count')}) | doc_id={d.get('doc_id')}\n"
                f"     命中查询词: {', '.join(d.get('matched_queries') or [])}"
            )
            samples = d.get("sample_chunks") or []
            if samples and args.show_samples:
                snippet = samples[0].get("content", "").replace("\n", " ")[:180]
                print(f"     代表引文: {snippet}...")
        print()

    chunks = res.get("chunks") or []
    if chunks:
        print("==================================================================")
        print(f"  跨查询全局高分原文切片 Top {min(len(chunks), args.top_chunks)}")
        print("==================================================================\n")
        for idx, ch in enumerate(chunks[: args.top_chunks], 1):
            print(
                f"--- [{idx}] [{ch.get('source_kind_label')}] {ch.get('doc_name')} "
                f"(综合分={ch.get('similarity'):.4f} | 命中词: {ch.get('matched_query', '')}) ---"
            )
            print(f"doc_id: {ch.get('doc_id')} | chunk_id: {ch.get('chunk_id')}")
            print(ch.get("content", "").strip())
            print()


def cmd_documents(args: argparse.Namespace) -> None:
    params = {
        "kb": args.kb,
        "keyword": args.keyword,
        "page": args.page,
        "page_size": args.page_size,
    }
    res = http_request("GET", "documents", params=params, api_base=args.api_base)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    docs = res.get("documents") or []
    expanded = res.get("expanded_keywords") or []
    print(f"知识库: {res.get('kb')} | 经名关键词: {args.keyword or '(全部)'}")
    if len(expanded) > 1:
        print(f"简繁互通扩展: {' / '.join(expanded)}")
    print(f"共找到 {res.get('total', len(docs))} 部文档（当前显示 {len(docs)} 部）：\n")
    for idx, d in enumerate(docs, 1):
        label = d.get("source_kind_label") or d.get("source_kind") or ""
        print(f"{idx:2d}. [{label}] {d.get('doc_name')}")
        print(f"    doc_id: {d.get('doc_id')} | 切片数: {d.get('chunk_count', 0)} | Token数: {d.get('token_count', 0)}")


def cmd_chunks(args: argparse.Namespace) -> None:
    params = {
        "kb": args.kb,
        "doc_id": args.doc_id,
        "keyword": args.keyword,
        "page": args.page,
        "page_size": args.page_size,
    }
    res = http_request("GET", "chunks", params=params, api_base=args.api_base)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    chunks = res.get("chunks") or []
    print(f"文档: [{res.get('source_kind_label', '')}] {res.get('doc_name')} (doc_id: {res.get('doc_id')})")
    print(f"总切片数: {res.get('total', len(chunks))} | 当前第 {res.get('page', 1)} 页（每页 {res.get('page_size')} 条）：\n")
    for idx, ch in enumerate(chunks, 1):
        print(f"--- [第 {idx} 段 | chunk_id: {ch.get('chunk_id')}] ---")
        print(ch.get("content", "").strip())
        print()


def cmd_full_doc(args: argparse.Namespace) -> None:
    if not args.doc_id and not args.doc_name:
        print("[参数错误] 请提供 --doc-id 或 --doc-name", file=sys.stderr)
        sys.exit(1)
    params = {
        "kb": args.kb,
        "doc_id": args.doc_id,
        "doc_name": args.doc_name,
    }
    res = http_request("GET", "full_document", params=params, api_base=args.api_base, timeout=60.0)
    if args.json:
        if args.output:
            Path(args.output).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"已保存整卷 JSON 到: {args.output}（共 {res.get('total_chunks', 0)} 段）")
        else:
            print(json.dumps(res, ensure_ascii=False, indent=2))
        return

    header = (
        f"# {res.get('doc_name')}\n\n"
        f"- **知识库**: `{res.get('kb')}`\n"
        f"- **类别**: {res.get('source_kind_label')} (`{res.get('source_kind')}`)\n"
        f"- **文档 ID (`doc_id`)**: `{res.get('doc_id')}`\n"
        f"- **总切片数 (`total_chunks`)**: {res.get('total_chunks', 0)}（已按 `positions[0][0]` 原始顺序完整还原）\n\n"
        f"---\n\n"
    )
    full_content = header + (res.get("full_text") or "") + "\n"
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(full_content, encoding="utf-8")
        print(f"已完整还原 [{res.get('source_kind_label')}] {res.get('doc_name')}（共 {res.get('total_chunks', 0)} 段，{len(full_content):,} 字符）并保存至: {out_path}")
    else:
        print(full_content)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="三学藏佛典知识库公开检索 CLI (sanxuezang-rag) — 全功能版",
    )
    parser.add_argument(
        "--api-base",
        default=DEFAULT_API_BASE,
        help=f"API 基础地址 (默认: {DEFAULT_API_BASE})",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="以原始 JSON 格式输出，方便 Agent 程序化解析",
    )

    sub = parser.add_subparsers(dest="cmd", required=True)

    # 1. datasets
    sub.add_parser("datasets", help="列出当前开放的知识库及支持特性")

    # 2. search
    p_search = sub.add_parser("search", help="检索佛典原文切片（支持简繁自动互通、经名过滤、doc_aggs 统计、高亮与 Rerank）")
    p_search.add_argument("query", help="检索问题或关键词（简体或繁体均可，单次最长 10,000 字符）")
    p_search.add_argument("--kb", default="cbeta", help="知识库标识（默认: cbeta）")
    p_search.add_argument("--top-k", type=int, default=30, help="返回切片数量 (默认 30，最大 200)")
    p_search.add_argument("--candidate-k", type=int, default=None, help="底层候选池大小 top_k (默认 max(top_k*3, 100)，最大 500)")
    p_search.add_argument("--page", type=int, default=1, help="页码 (默认 1，最大 200)")
    p_search.add_argument("--title", default=None, help="按经名/书名关键词筛选（如 '金刚'、'摩诃止观'）")
    p_search.add_argument("--doc-ids", default=None, help="限定在指定的 doc_id 列表内检索（逗号分隔）")
    p_search.add_argument("--no-dual-script", action="store_true", help="关闭简繁自动互通，仅按原字面检索")
    p_search.add_argument("--no-highlight", action="store_true", help="关闭关键词高亮返回")
    p_search.add_argument("--no-aggs", action="store_true", help="文本模式下不打印 doc_aggs 经卷聚合统计")
    p_search.add_argument("--rerank", action="store_true", help="启用 BGE 神经网络重排序 (BAAI/bge-reranker-v2-m3)")
    p_search.add_argument("--rerank-model", default=None, help="指定重排序模型名称")
    p_search.add_argument("--similarity-threshold", type=float, default=0.15, help="最低相似度阈值 (默认 0.15)")
    p_search.add_argument("--vector-weight", type=float, default=0.3, help="向量权重 (默认 0.3，即 70%% BM25 词频 + 30%% 向量)")
    p_search.add_argument("--metadata-condition", default=None, help="元数据过滤条件 (JSON 对象字符串)")
    p_search.add_argument("--reference-metadata", action="store_true", help="返回引用元数据 (reference_metadata)")

    # 3. batch-search
    p_batch = sub.add_parser("batch-search", help="多维查询词批量扩展检索与 CBETA 经律论注疏智能分级发现")
    p_batch.add_argument("queries", nargs="+", help="多个查询词（最多 30 个，支持从核心名相、异译、譬喻、法数、经论名等多维度扩展）")
    p_batch.add_argument("--kb", default="cbeta", help="知识库标识（默认: cbeta）")
    p_batch.add_argument("--per-query-k", type=int, default=30, help="每个查询词召回的切片数 (默认 30，最大 100)")
    p_batch.add_argument("--top-docs", type=int, default=80, help="返回的聚合经卷上限 (默认 80，最大 300)")
    p_batch.add_argument("--top-chunks", type=int, default=40, help="返回的全局高分切片上限 (默认 40，最大 300)")
    p_batch.add_argument("--title", default=None, help="全局限定经名/书名关键词筛选")
    p_batch.add_argument("--no-dual-script", action="store_true", help="关闭简繁自动互通")
    p_batch.add_argument("--highlight", action="store_true", help="开启高亮标签")
    p_batch.add_argument("--show-samples", action="store_true", default=True, help="在经卷分级列表中展示代表引文摘要")
    p_batch.add_argument("--similarity-threshold", type=float, default=0.15, help="最低相似度阈值 (默认 0.15)")
    p_batch.add_argument("--vector-weight", type=float, default=0.3, help="向量权重 (默认 0.3)")

    # 4. documents
    p_docs = sub.add_parser("documents", help="按经名/书名关键词查找文档列表（获取 doc_id 及经律论分类）")
    p_docs.add_argument("keyword", nargs="?", default="", help="经名或书名关键词（简繁自动互通）")
    p_docs.add_argument("--kb", default="cbeta", help="知识库标识（默认: cbeta）")
    p_docs.add_argument("--page", type=int, default=1, help="页码 (默认 1)")
    p_docs.add_argument("--page-size", type=int, default=30, help="每页条数 (默认 30，最大 200)")

    # 5. chunks
    p_chunks = sub.add_parser("chunks", help="分页读取单卷经文的上下文切片")
    p_chunks.add_argument("doc_id", help="目标文档的 doc_id")
    p_chunks.add_argument("--kb", default="cbeta", help="知识库标识（默认: cbeta）")
    p_chunks.add_argument("--keyword", default="", help="在单卷内部进一步筛选的关键词")
    p_chunks.add_argument("--page", type=int, default=1, help="页码 (默认 1)")
    p_chunks.add_argument("--page-size", type=int, default=30, help="每页条数 (默认 30，最大 200)")

    # 6. full-doc
    p_full = sub.add_parser("full-doc", help="按 positions[0][0] 原始顺序拉取并还原整卷全文（用于主题原文汇编或整卷阅读）")
    p_full.add_argument("--doc-id", default=None, help="目标经卷的 doc_id")
    p_full.add_argument("--doc-name", default=None, help="目标经卷的名称关键词（未提供 doc-id 时自动查找第一匹配卷）")
    p_full.add_argument("--kb", default="cbeta", help="知识库标识（默认: cbeta）")
    p_full.add_argument("--output", "-o", default=None, help="将完整还原的整卷经文保存到指定文件路径")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    if args.cmd == "datasets":
        cmd_datasets(args)
    elif args.cmd == "search":
        cmd_search(args)
    elif args.cmd == "batch-search":
        cmd_batch_search(args)
    elif args.cmd == "documents":
        cmd_documents(args)
    elif args.cmd == "chunks":
        cmd_chunks(args)
    elif args.cmd == "full-doc":
        cmd_full_doc(args)


if __name__ == "__main__":
    main()
