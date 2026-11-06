"use client";

import { useMemo, useRef, useState } from "react";

import { ApiRequestError, clientRequest } from "@/lib/api";
import type {
  KnowledgeDocument,
  KnowledgeSearchItem,
  KnowledgeSearchResponse
} from "@/lib/types";
import { cn, formatDateTime } from "@/lib/utils";
import { Icon } from "./icons";

const STATUS_LABELS: Record<string, string> = {
  READY: "可检索",
  DISABLED: "已停用",
  DRAFT: "草稿",
  PROCESSING: "解析中",
  FAILED: "解析失败"
};

const STATUS_STYLES: Record<string, string> = {
  READY: "bg-success-soft text-success",
  DISABLED: "bg-subtle text-ink-tertiary",
  DRAFT: "bg-warning-soft text-warning",
  PROCESSING: "bg-info-soft text-info",
  FAILED: "bg-danger-soft text-danger"
};

export function KnowledgeConsole({
  initialDocuments,
  csrfToken,
  canManage
}: {
  initialDocuments: KnowledgeDocument[];
  csrfToken: string;
  canManage: boolean;
}) {
  const [documents, setDocuments] = useState(initialDocuments);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("VPN 证书无效");
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<KnowledgeSearchItem[] | null>(null);
  const formRef = useRef<HTMLFormElement>(null);

  const totals = useMemo(
    () => ({
      ready: documents.filter((document) => document.status === "READY").length,
      chunks: documents.reduce((sum, document) => sum + document.chunk_count, 0)
    }),
    [documents]
  );

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canManage) return;
    const formData = new FormData(event.currentTarget);
    const file = formData.get("file");
    if (!(file instanceof File) || file.size === 0) {
      setError("请选择 Markdown、TXT 或 PDF 文档");
      return;
    }
    setPending("upload");
    setError(null);
    setNotice(null);
    try {
      const created = await clientRequest<KnowledgeDocument>("/api/knowledge/documents", {
        method: "POST",
        body: formData,
        csrfToken
      });
      setDocuments((current) => [created, ...current]);
      setNotice(`《${created.title}》已导入，生成 ${created.chunk_count} 个可检索片段。`);
      formRef.current?.reset();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "导入失败，请稍后重试");
    } finally {
      setPending(null);
    }
  }

  async function updateStatus(document: KnowledgeDocument) {
    if (!canManage) return;
    const nextStatus = document.status === "READY" ? "DISABLED" : "READY";
    setPending(document.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<KnowledgeDocument>(
        `/api/knowledge/documents/${encodeURIComponent(document.id)}`,
        {
          method: "PATCH",
          body: JSON.stringify({ status: nextStatus }),
          csrfToken
        }
      );
      setDocuments((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setNotice(nextStatus === "READY" ? "文档已恢复检索" : "文档已停用，历史引用仍保留");
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "更新失败，请稍后重试");
    } finally {
      setPending(null);
    }
  }

  async function reindex(document: KnowledgeDocument) {
    if (!canManage) return;
    setPending(document.id);
    setError(null);
    setNotice(null);
    try {
      const updated = await clientRequest<KnowledgeDocument>(
        `/api/knowledge/documents/${encodeURIComponent(document.id)}/reindex`,
        { method: "POST", csrfToken }
      );
      setDocuments((current) =>
        current.map((item) => (item.id === updated.id ? updated : item))
      );
      setNotice(`索引已重建，共 ${updated.chunk_count} 个片段`);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "重建索引失败");
    } finally {
      setPending(null);
    }
  }

  async function search(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!query.trim()) return;
    setSearching(true);
    setError(null);
    try {
      const response = await clientRequest<KnowledgeSearchResponse>(
        `/api/knowledge/search?q=${encodeURIComponent(query.trim())}`
      );
      setResults(response.items);
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : "检索失败，请稍后重试");
      setResults(null);
    } finally {
      setSearching(false);
    }
  }

  return (
    <div className="mx-auto max-w-[1200px]">
      <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="sd-eyebrow">知识</p>
          <h1 className="sd-page-title mt-1">知识库</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-ink-secondary">
            文档导入后保留章节、页码和字符偏移。Case 回答只引用检索到的片段，来源可回到原文核对。
          </p>
        </div>
        <div className="flex gap-2">
          <span className="sd-chip">{documents.length} 份文档</span>
          <span className="sd-chip">{totals.ready} 份可检索</span>
          <span className="sd-chip">{totals.chunks} 个片段</span>
        </div>
      </header>

      {(error || notice) && (
        <div
          className={cn(
            "mb-4 rounded-control border px-3 py-2 text-xs",
            error
              ? "border-danger bg-danger-soft text-danger"
              : "border-brand-border bg-brand-soft text-brand"
          )}
          role={error ? "alert" : "status"}
        >
          {error ?? notice}
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(330px,0.65fr)]">
        <section className="sd-card overflow-hidden">
          <div className="flex items-center justify-between border-b border-line px-5 py-4">
            <div>
              <h2 className="text-sm font-semibold text-ink">文档与索引</h2>
              <p className="mt-1 text-[10px] text-ink-tertiary">
                停用只影响后续检索，历史引用快照不会删除。
              </p>
            </div>
            <span className="sd-chip">M1</span>
          </div>

          {documents.length === 0 ? (
            <div className="px-6 py-14 text-center">
              <span className="mx-auto grid h-11 w-11 place-items-center rounded-overlay border border-line bg-subtle text-ink-tertiary">
                <Icon name="book" size={20} />
              </span>
              <p className="mt-4 text-sm font-semibold text-ink">知识库为空</p>
              <p className="mt-1 text-[11px] text-ink-secondary">
                {canManage ? "右侧上传文档后即可用于 Case 检索。" : "请联系管理员导入文档。"}
              </p>
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {documents.map((document) => (
                <li key={document.id} className="px-5 py-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-xs font-semibold text-ink">{document.title}</h3>
                        <span className="text-[9px] text-ink-tertiary">{document.version}</span>
                        <span
                          className={cn(
                            "rounded-full px-2 py-0.5 text-[9px] font-medium",
                            STATUS_STYLES[document.status] ?? "bg-subtle text-ink-secondary"
                          )}
                        >
                          {STATUS_LABELS[document.status] ?? document.status}
                        </span>
                      </div>
                      <p className="mt-1.5 text-[10px] text-ink-tertiary">
                        {document.source_type} · {document.chunk_count} 个片段 · 更新于{" "}
                        {formatDateTime(document.updated_at)}
                      </p>
                      <p className="mt-1 text-[9px] text-ink-tertiary">
                        可见范围：
                        {document.acl.departments?.length
                          ? document.acl.departments.join("、")
                          : "全员"}
                      </p>
                    </div>
                    {canManage && (
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => void reindex(document)}
                          disabled={pending === document.id}
                          className="sd-button-secondary h-7 px-2 text-[9px]"
                        >
                          重建索引
                        </button>
                        <button
                          type="button"
                          onClick={() => void updateStatus(document)}
                          disabled={pending === document.id}
                          className="sd-button-ghost h-7 px-2 text-[9px]"
                        >
                          {document.status === "READY" ? "停用" : "启用"}
                        </button>
                      </div>
                    )}
                  </div>
                  {document.parse_error && (
                    <p className="mt-2 rounded-control bg-danger-soft px-2.5 py-1.5 text-[9px] text-danger">
                      {document.parse_error}
                    </p>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-4">
          {canManage && (
            <section className="sd-card p-5">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-ink">导入文档</h2>
                  <p className="mt-1 text-[10px] text-ink-tertiary">支持 MD、TXT、PDF，最大 5 MB</p>
                </div>
                <Icon name="plus" size={16} className="text-ink-tertiary" />
              </div>
              <form ref={formRef} onSubmit={upload} className="mt-4 space-y-3">
                <div>
                  <label className="sd-label" htmlFor="knowledge-file">
                    文档文件
                  </label>
                  <input
                    id="knowledge-file"
                    name="file"
                    type="file"
                    accept=".md,.markdown,.txt,.pdf"
                    className="block w-full rounded-control border border-line-strong bg-surface px-3 py-2 text-[10px] text-ink-secondary file:mr-3 file:rounded-control file:border-0 file:bg-brand-soft file:px-2.5 file:py-1 file:text-[10px] file:text-brand"
                  />
                </div>
                <div className="grid gap-3 sm:grid-cols-2">
                  <div>
                    <label className="sd-label" htmlFor="knowledge-title">
                      标题（可选）
                    </label>
                    <input id="knowledge-title" name="title" className="sd-input" placeholder="默认使用文件名" />
                  </div>
                  <div>
                    <label className="sd-label" htmlFor="knowledge-version">
                      版本
                    </label>
                    <input id="knowledge-version" name="version" className="sd-input" defaultValue="v1" />
                  </div>
                </div>
                <div>
                  <label className="sd-label" htmlFor="knowledge-departments">
                    可见部门（可选，逗号分隔）
                  </label>
                  <input
                    id="knowledge-departments"
                    name="departments"
                    className="sd-input"
                    placeholder="留空表示全员可见"
                  />
                </div>
                <button type="submit" disabled={pending === "upload"} className="sd-button-primary w-full">
                  {pending === "upload" ? "正在解析与切分…" : "导入并建立索引"}
                </button>
              </form>
            </section>
          )}

          <section className="sd-card p-5">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-sm font-semibold text-ink">检索测试</h2>
                <p className="mt-1 text-[10px] text-ink-tertiary">词法匹配 + 本地哈希向量</p>
              </div>
              <Icon name="search" size={16} className="text-ink-tertiary" />
            </div>
            <form onSubmit={search} className="mt-4 flex gap-2">
              <input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                className="sd-input"
                placeholder="输入问题进行检索"
              />
              <button type="submit" disabled={searching} className="sd-button-secondary shrink-0 px-3">
                {searching ? "…" : "检索"}
              </button>
            </form>

            {results && (
              <div className="mt-4 space-y-2">
                {results.length === 0 ? (
                  <p className="rounded-control border border-line bg-subtle px-3 py-4 text-center text-[10px] text-ink-tertiary">
                    未找到达到阈值的片段，Case 会拒答或追问。
                  </p>
                ) : (
                  results.map((result) => (
                    <div key={result.chunk_id} className="rounded-control border border-line bg-subtle px-3 py-2.5">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-[10px] font-medium text-ink">{result.title}</p>
                        <span className="font-mono text-[9px] text-brand">
                          {result.score.toFixed(2)}
                        </span>
                      </div>
                      <p className="mt-1 text-[9px] text-ink-tertiary">
                        {result.version} · 第 {result.page} 页 · {result.section || "正文"}
                      </p>
                      <p className="mt-1.5 line-clamp-3 text-[10px] leading-5 text-ink-secondary">
                        {result.quote}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
