"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, API_BASE, ReportSummary } from "@/lib/api";

const SCOPE_LABEL: Record<number, string> = {
  1: "范围一 · 直接排放",
  2: "范围二 · 外购能源",
  3: "范围三 · 其他间接",
};

export default function Dashboard() {
  const [data, setData] = useState<ReportSummary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api.summary().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <p className="error">无法连接后端：{error}</p>;
  if (!data) return <p className="muted">加载中…</p>;

  const scopeValue = (s: number) =>
    data.by_scope.find((x) => x.scope === s)?.emissions_tco2e ?? 0;

  return (
    <>
      <h1>排放总览</h1>
      {data.pending_batches > 0 && (
        <p className="error">
          ⏳ 有 {data.pending_batches} 个待确认导入批次尚未计入本页汇总与 CSV 导出,
          请前往 <Link href="/batches">批量导入</Link> 复核确认或驳回。
        </p>
      )}
      {data.unmatched_records > 0 && (
        <p className="error">
          ⚠️ 有 {data.unmatched_records} 条记录未匹配到适用排放因子,未计入汇总。请在「排放因子」中补充对应地区/年度的因子。
        </p>
      )}
      <div className="stat-grid">
        <div className="stat total">
          <div className="label">总排放量 (tCO₂e)</div>
          <div className="value">{data.total_tco2e.toLocaleString()}</div>
        </div>
        {[1, 2, 3].map((s) => (
          <div key={s} className={`stat scope-${s}`}>
            <div className="label">{SCOPE_LABEL[s]}</div>
            <div className="value">{scopeValue(s).toLocaleString()}</div>
          </div>
        ))}
      </div>

      <div className="card">
        <h2>按类别</h2>
        <table>
          <thead>
            <tr><th>范围</th><th>类别</th><th>排放量 (tCO₂e)</th></tr>
          </thead>
          <tbody>
            {data.by_category.map((c) => (
              <tr key={`${c.scope}-${c.category}`}>
                <td><span className={`badge s${c.scope}`}>范围{c.scope === 1 ? "一" : c.scope === 2 ? "二" : "三"}</span></td>
                <td>{c.category}</td>
                <td>{c.emissions_tco2e.toLocaleString()}</td>
              </tr>
            ))}
            {data.by_category.length === 0 && (
              <tr><td colSpan={3} className="muted">暂无数据，请先在「数据录入」中添加能耗记录</td></tr>
            )}
          </tbody>
        </table>
      </div>

      <div className="card">
        <h2>按厂区</h2>
        <table>
          <thead>
            <tr><th>厂区</th><th>范围</th><th>排放量 (tCO₂e)</th></tr>
          </thead>
          <tbody>
            {data.by_facility.map((f) => (
              <tr key={`${f.facility_id}-${f.scope}`}>
                <td>{f.facility_name}</td>
                <td><span className={`badge s${f.scope}`}>范围{f.scope === 1 ? "一" : f.scope === 2 ? "二" : "三"}</span></td>
                <td>{f.emissions_tco2e.toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <a className="export-btn" href={`${API_BASE}/api/reports/export.csv`}>
        导出排放明细 CSV
      </a>
    </>
  );
}
