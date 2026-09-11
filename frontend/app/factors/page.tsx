"use client";

import { useEffect, useState } from "react";
import { api, EmissionFactor } from "@/lib/api";

export default function FactorsPage() {
  const [factors, setFactors] = useState<EmissionFactor[]>([]);
  const [error, setError] = useState("");

  useEffect(() => {
    api.listFactors().then(setFactors).catch((e) => setError(e.message));
  }, []);

  return (
    <>
      <h1>排放因子库</h1>
      {error && <p className="error">{error}</p>}
      <div className="card">
        <p className="muted">
          因子值为缺省参考值，请根据所在地区/年度官方发布值通过 API（PUT /api/factors/{"{id}"}）更新。
        </p>
        <table>
          <thead>
            <tr>
              <th>范围</th><th>能源类型</th><th>类别</th><th>单位</th>
              <th>因子 (kgCO₂e/单位)</th><th>来源</th>
            </tr>
          </thead>
          <tbody>
            {factors.map((f) => (
              <tr key={f.id}>
                <td><span className={`badge s${f.scope}`}>范围{f.scope}</span></td>
                <td>{f.name_zh}</td>
                <td>{f.category}</td>
                <td>{f.unit}</td>
                <td>{f.factor_value}</td>
                <td className="muted">{f.source ?? "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
