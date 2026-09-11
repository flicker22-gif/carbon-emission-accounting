"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, EmissionFactor, EnergyRecord, Facility } from "@/lib/api";

export default function RecordsPage() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [factors, setFactors] = useState<EmissionFactor[]>([]);
  const [records, setRecords] = useState<EnergyRecord[]>([]);
  const [error, setError] = useState("");

  const [facilityId, setFacilityId] = useState("");
  const [factorId, setFactorId] = useState("");
  const [period, setPeriod] = useState("");
  const [consumption, setConsumption] = useState("");
  const [remark, setRemark] = useState("");

  const load = () => {
    Promise.all([api.listFacilities(), api.listFactors(), api.listRecords()])
      .then(([f, fac, r]) => {
        setFacilities(f);
        setFactors(fac);
        setRecords(r);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const selectedFactor = factors.find((f) => f.id === Number(factorId));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.createRecord({
        facility_id: Number(facilityId),
        factor_id: Number(factorId),
        period,
        consumption: Number(consumption),
        remark: remark || undefined,
      });
      setConsumption("");
      setRemark("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    }
  };

  const remove = async (id: number) => {
    await api.deleteRecord(id);
    load();
  };

  return (
    <>
      <h1>能耗数据录入</h1>

      <div className="card">
        <form className="entry" onSubmit={submit}>
          <div>
            <label>厂区</label>
            <select required value={facilityId} onChange={(e) => setFacilityId(e.target.value)}>
              <option value="">请选择</option>
              {facilities.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>
          <div>
            <label>能源类型</label>
            <select required value={factorId} onChange={(e) => setFactorId(e.target.value)}>
              <option value="">请选择</option>
              {factors.map((f) => (
                <option key={f.id} value={f.id}>
                  [范围{f.scope}] {f.name_zh}（{f.unit}）
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>期间（月份）</label>
            <input required type="month" value={period} onChange={(e) => setPeriod(e.target.value)} />
          </div>
          <div>
            <label>消耗量{selectedFactor ? `（${selectedFactor.unit}）` : ""}</label>
            <input
              required type="number" min="0" step="any" value={consumption}
              onChange={(e) => setConsumption(e.target.value)}
            />
          </div>
          <div>
            <label>备注</label>
            <input value={remark} onChange={(e) => setRemark(e.target.value)} />
          </div>
          <div>
            <button type="submit">保存记录</button>
          </div>
        </form>
        {selectedFactor && (
          <p className="muted" style={{ marginBottom: 0 }}>
            当前因子：{selectedFactor.factor_value} kgCO₂e/{selectedFactor.unit}
            {selectedFactor.source ? `（来源：${selectedFactor.source}）` : ""}
          </p>
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h2>已录入记录</h2>
        <table>
          <thead>
            <tr>
              <th>期间</th><th>厂区</th><th>范围</th><th>能源</th>
              <th>消耗量</th><th>排放量 (tCO₂e)</th><th></th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id}>
                <td>{r.period}</td>
                <td>{r.facility_name}</td>
                <td><span className={`badge s${r.scope}`}>范围{r.scope}</span></td>
                <td>{r.factor_name}</td>
                <td>{r.consumption.toLocaleString()} {r.unit}</td>
                <td>{r.emissions_tco2e.toLocaleString()}</td>
                <td>
                  <button className="danger" onClick={() => remove(r.id)}>删除</button>
                </td>
              </tr>
            ))}
            {records.length === 0 && (
              <tr><td colSpan={7} className="muted">暂无记录</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
