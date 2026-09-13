"use client";

import { ChangeEvent, useEffect, useState } from "react";
import {
  api,
  Batch,
  BatchRow,
  BatchStatus,
  BatchSummary,
} from "@/lib/api";

const STATUS_LABEL: Record<BatchStatus, string> = {
  pending: "待确认",
  confirmed: "已确认",
  rejected: "已驳回",
};

const STATUS_STYLE: Record<BatchStatus, React.CSSProperties> = {
  pending: { background: "#fef3c7", color: "#b45309" },
  confirmed: { background: "#dcfce7", color: "#15803d" },
  rejected: { background: "#e2e8f0", color: "#475569" },
};

const FIELD_LABEL: Record<string, string> = {
  __row__: "整行",
  facility_code: "厂区编号",
  energy_type: "能源类型",
  period: "期间",
  consumption: "消耗量",
};

export default function BatchesPage() {
  const [batches, setBatches] = useState<BatchSummary[]>([]);
  const [statusFilter, setStatusFilter] = useState<"" | BatchStatus>("");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const [detail, setDetail] = useState<Batch | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [acting, setActing] = useState(false);

  const load = () => {
    api
      .listBatches(statusFilter || undefined)
      .then(setBatches)
      .catch((e) => setError(e.message));
  };

  useEffect(load, [statusFilter]);

  const openBatch = (id: number) => {
    setError("");
    api
      .getBatch(id)
      .then((b) => {
        setDetail(b);
        setReviewNote(b.review_note ?? "");
      })
      .catch((e) => setError(e.message));
  };

  const onPickFile = (e: ChangeEvent<HTMLInputElement>) => {
    setFile(e.target.files?.[0] ?? null);
    setError("");
  };

  const upload = async () => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const batch = await api.importBatch(file);
      setFile(null);
      load();
      openBatch(batch.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "上传失败");
    } finally {
      setUploading(false);
    }
  };

  const runAction = async (
    fn: (id: number, note?: string) => Promise<Batch>,
    confirmText?: string,
  ) => {
    if (!detail) return;
    if (confirmText && !window.confirm(confirmText)) return;
    setActing(true);
    setError("");
    try {
      const updated = await fn(detail.id, reviewNote || undefined);
      setDetail(updated);
      setReviewNote(updated.review_note ?? "");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "操作失败");
    } finally {
      setActing(false);
    }
  };

  const validRows = (detail?.rows ?? []).filter((r) => r.is_valid);
  const errorRows = (detail?.rows ?? []).filter((r) => !r.is_valid);

  return (
    <>
      <h1>月度能耗表批量导入</h1>

      <div className="card">
        <h2>上传能耗表（CSV）</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          必需列：厂区编号、能源类型、期间（YYYY-MM)、消耗量；可选列：厂区名称、备注。
          上传后逐行校验，<b>合法行进入同一个待确认批次</b>，错误行随批保留行号与字段错误；
          复核确认后整批锁定并计入仪表盘，未确认数据不会出现在任何汇总与导出中。
        </p>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap" }}>
          <input
            type="file"
            accept=".csv"
            onChange={onPickFile}
            style={{ maxWidth: 320 }}
          />
          <button onClick={upload} disabled={!file || uploading}>
            {uploading ? "解析中…" : "上传并校验"}
          </button>
          <a className="export-btn" href={api.templateUrl()} style={{ background: "#0f766e" }}>
            下载 CSV 模板
          </a>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={{ margin: 0 }}>导入批次</h2>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as "" | BatchStatus)}
            style={{ width: 140 }}
          >
            <option value="">全部状态</option>
            <option value="pending">待确认</option>
            <option value="confirmed">已确认</option>
            <option value="rejected">已驳回</option>
          </select>
        </div>
        <table style={{ marginTop: 12 }}>
          <thead>
            <tr>
              <th>#</th><th>文件</th><th>状态</th>
              <th>合法/错误/总行数</th><th>确认后汇总影响 (tCO₂e)</th>
              <th>未匹配因子</th><th>上传时间</th><th></th>
            </tr>
          </thead>
          <tbody>
            {batches.map((b) => (
              <tr key={b.id}>
                <td>{b.id}</td>
                <td>{b.filename}</td>
                <td><span className="badge" style={STATUS_STYLE[b.status]}>{STATUS_LABEL[b.status]}</span></td>
                <td>
                  {b.valid_rows} / <span style={{ color: b.error_rows ? "#b91c1c" : undefined }}>{b.error_rows}</span> / {b.total_rows}
                </td>
                <td>{b.status === "pending" ? b.impact_tco2e.toLocaleString() : "—"}</td>
                <td>
                  {b.unmatched_valid_rows > 0 ? (
                    <span style={{ color: "#b45309" }}>{b.unmatched_valid_rows} 行可追踪不计排</span>
                  ) : "—"}
                </td>
                <td className="muted">{new Date(b.created_at).toLocaleString("zh-CN")}</td>
                <td>
                  <button
                    style={{ background: "#0f766e", padding: "4px 10px", fontSize: 13 }}
                    onClick={() => openBatch(b.id)}
                  >
                    {b.status === "pending" ? "复核" : "查看"}
                  </button>
                </td>
              </tr>
            ))}
            {batches.length === 0 && (
              <tr><td colSpan={8} className="muted">暂无批次</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {detail && (
        <div className="modal-mask" onClick={(e) => e.target === e.currentTarget && setDetail(null)}>
          <div className="modal">
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={{ margin: 0 }}>
                批次 #{detail.id} · {detail.filename}{" "}
                <span className="badge" style={STATUS_STYLE[detail.status]}>{STATUS_LABEL[detail.status]}</span>
              </h2>
              <button className="ghost" onClick={() => setDetail(null)}>关闭</button>
            </div>

            <p className="muted">
              共 {detail.total_rows} 行：合法 {detail.valid_rows} 行、错误 {detail.error_rows} 行；
              确认后汇总影响 <b>{detail.impact_tco2e.toLocaleString()} tCO₂e</b>
              {detail.unmatched_valid_rows > 0 && (
                <>；其中 <b style={{ color: "#b45309" }}>{detail.unmatched_valid_rows} 行未匹配因子，可追踪但不计排放量</b></>
              )}
              。未确认前，本批数据不计入仪表盘与 CSV 导出。
            </p>

            <h2>有效记录（{validRows.length}）</h2>
            <table>
              <thead>
                <tr>
                  <th>行号</th><th>厂区</th><th>期间</th><th>能源</th>
                  <th>消耗量</th><th>匹配因子</th><th>排放量 (tCO₂e)</th>
                </tr>
              </thead>
              <tbody>
                {validRows.map((r: BatchRow) => (
                  <tr key={r.id}>
                    <td>{r.row_number}</td>
                    <td>{r.facility_name || r.facility_code}{r.facility_region ? `（${r.facility_region}）` : ""}</td>
                    <td>{r.period}</td>
                    <td>{r.factor_name ?? r.energy_type}</td>
                    <td>{r.consumption?.toLocaleString()} {r.unit ?? ""}</td>
                    <td className="muted">
                      {r.matched
                        ? `${r.factor_value} kgCO₂e/${r.unit}（${r.factor_region} ${r.factor_year}）`
                        : <span style={{ color: "#b45309" }}>因子库无适用因子,不计排放</span>}
                    </td>
                    <td>{r.emissions_tco2e != null ? r.emissions_tco2e.toLocaleString() : "-"}</td>
                  </tr>
                ))}
                {validRows.length === 0 && (
                  <tr><td colSpan={7} className="muted">没有合法行,请按错误提示修正后整份重新上传</td></tr>
                )}
              </tbody>
            </table>

            {errorRows.length > 0 && (
              <>
                <h2 style={{ marginTop: 18 }}>错误行（{errorRows.length},不导入、不计排）</h2>
                <table>
                  <thead>
                    <tr>
                      <th>行号</th><th>厂区编号</th><th>能源类型</th><th>期间</th>
                      <th>消耗量</th><th>字段错误</th>
                    </tr>
                  </thead>
                  <tbody>
                    {errorRows.map((r) => (
                      <tr key={r.id}>
                        <td>{r.row_number}</td>
                        <td>{r.raw_data["厂区编号"] || "-"}</td>
                        <td>{r.raw_data["能源类型"] || "-"}</td>
                        <td>{r.raw_data["期间"] || "-"}</td>
                        <td>{r.raw_data["消耗量"] || "-"}</td>
                        <td style={{ color: "#b91c1c" }}>
                          {r.errors.map((e, i) => (
                            <div key={i}>
                              {e.field === "__row__" ? "" : `【${FIELD_LABEL[e.field] ?? e.field}】`}
                              {e.message}
                            </div>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <div style={{ marginTop: 18 }}>
              <label>复核意见（可选）</label>
              <input
                value={reviewNote}
                onChange={(e) => setReviewNote(e.target.value)}
                placeholder="确认/驳回/退回时的说明"
                disabled={detail.status === "rejected"}
              />
            </div>

            <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
              {detail.status === "pending" && (
                <>
                  <button
                    disabled={acting || detail.valid_rows === 0}
                    onClick={() => runAction(
                      api.confirmBatch,
                      `确认批次 #${detail.id}?${detail.error_rows > 0 ? `有 ${detail.error_rows} 个错误行会被忽略,` : ""}合法行将整批锁定并计入仪表盘,不可再单条修改。`,
                    )}
                  >
                    确认整批（{detail.valid_rows} 行）
                  </button>
                  <button
                    className="danger"
                    disabled={acting}
                    onClick={() => runAction(
                      api.rejectBatch,
                      `驳回批次 #${detail.id}?整份表将作废且不产生任何记录。`,
                    )}
                  >
                    驳回
                  </button>
                </>
              )}
              {detail.status === "confirmed" && (
                <button
                  className="danger"
                  disabled={acting}
                  onClick={() => runAction(
                    api.returnBatch,
                    `退回批次 #${detail.id} 修订?该批已确认的 ${detail.valid_rows} 条记录将被删除并从所有汇总移除,修订后请整份重新上传。`,
                  )}
                >
                  退回修订（删除已确认记录）
                </button>
              )}
              {detail.status === "rejected" && (
                <span className="muted">该批次已驳回作废；修正原表后可重新上传，相同内容不会被判定为重复。</span>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
}
