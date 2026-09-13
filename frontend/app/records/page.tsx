"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, EnergyRecord, EnergyType, Facility } from "@/lib/api";

export default function RecordsPage() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [energyTypes, setEnergyTypes] = useState<EnergyType[]>([]);
  const [records, setRecords] = useState<EnergyRecord[]>([]);
  const [error, setError] = useState("");

  const [facilityId, setFacilityId] = useState("");
  const [energyType, setEnergyType] = useState("");
  const [period, setPeriod] = useState("");
  const [consumption, setConsumption] = useState("");
  const [remark, setRemark] = useState("");
  // 编辑已有记录:非 null 时表单进入编辑模式,仅月份/消耗量/备注可改
  const [editingId, setEditingId] = useState<number | null>(null);

  const load = () => {
    Promise.all([api.listFacilities(), api.listEnergyTypes(), api.listRecords()])
      .then(([f, t, r]) => {
        setFacilities(f);
        setEnergyTypes(t);
        setRecords(r);
      })
      .catch((e) => setError(e.message));
  };

  useEffect(load, []);

  const selectedType = energyTypes.find((t) => t.energy_type === energyType);
  const selectedFacility = facilities.find((f) => f.id === Number(facilityId));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      if (editingId) {
        await api.updateRecord(editingId, {
          period,
          consumption: Number(consumption),
          remark: remark || null,
        });
        setEditingId(null);
      } else {
        await api.createRecord({
          facility_id: Number(facilityId),
          energy_type: energyType,
          period,
          consumption: Number(consumption),
          remark: remark || undefined,
        });
      }
      setConsumption("");
      setRemark("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    }
  };

  const startEdit = (r: EnergyRecord) => {
    setEditingId(r.id);
    setFacilityId(String(r.facility_id));
    setEnergyType(r.energy_type);
    setPeriod(r.period);
    setConsumption(String(r.consumption));
    setRemark(r.remark ?? "");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelEdit = () => {
    setEditingId(null);
    setConsumption("");
    setRemark("");
  };

  const remove = async (id: number) => {
    await api.deleteRecord(id);
    load();
  };

  return (
    <>
      <h1>能耗数据录入</h1>

      <div className="card">
        {editingId && <h2>编辑记录 #{editingId}</h2>}
        <form className="entry" onSubmit={submit}>
          <div>
            <label>厂区</label>
            <select required disabled={!!editingId} value={facilityId} onChange={(e) => setFacilityId(e.target.value)}>
              <option value="">请选择</option>
              {facilities.map((f) => (
                <option key={f.id} value={f.id}>{f.name}（{f.region}）</option>
              ))}
            </select>
          </div>
          <div>
            <label>能源类型</label>
            <select required disabled={!!editingId} value={energyType} onChange={(e) => setEnergyType(e.target.value)}>
              <option value="">请选择</option>
              {energyTypes.map((t) => (
                <option key={t.energy_type} value={t.energy_type}>
                  [范围{t.scope}] {t.name_zh}（{t.unit}）
                </option>
              ))}
            </select>
          </div>
          <div>
            <label>期间（月份）</label>
            <input required type="month" value={period} onChange={(e) => setPeriod(e.target.value)} />
          </div>
          <div>
            <label>消耗量{selectedType ? `（${selectedType.unit}）` : ""}</label>
            <input
              required type="number" min="0" step="any" value={consumption}
              onChange={(e) => setConsumption(e.target.value)}
            />
          </div>
          <div>
            <label>备注</label>
            <input value={remark} onChange={(e) => setRemark(e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit">{editingId ? "保存修改" : "保存记录"}</button>
            {editingId && (
              <button type="button" className="danger" onClick={cancelEdit}>取消</button>
            )}
          </div>
        </form>
        {editingId ? (
          <p className="muted" style={{ marginBottom: 0 }}>
            仅可修改月份、消耗量和备注;厂区与能源类型不可改。保存后排放量按当前因子自动重算,其他记录不受影响。
          </p>
        ) : (
          selectedType && selectedFacility && (
            <p className="muted" style={{ marginBottom: 0 }}>
              将按「{selectedFacility.region} → 全国」优先、年度 ≤ 数据期间最新的规则自动匹配排放因子。
            </p>
          )
        )}
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <h2>已录入记录</h2>
        <table>
          <thead>
            <tr>
              <th>期间</th><th>厂区</th><th>范围</th><th>能源</th>
              <th>消耗量</th><th>匹配因子</th><th>排放量 (tCO₂e)</th><th></th>
            </tr>
          </thead>
          <tbody>
            {records.map((r) => (
              <tr key={r.id}>
                <td>{r.period}</td>
                <td>{r.facility_name}</td>
                <td>
                  {r.scope
                    ? <span className={`badge s${r.scope}`}>范围{r.scope}</span>
                    : <span className="badge" style={{ background: "#fee2e2", color: "#b91c1c" }}>未匹配</span>}
                </td>
                <td>{r.factor_name ?? r.energy_type}</td>
                <td>{r.consumption.toLocaleString()} {r.unit ?? ""}</td>
                <td className="muted">
                  {r.matched
                    ? `${r.factor_value} kgCO₂e/${r.unit}（${r.factor_region} ${r.factor_year}）`
                    : "因子库无适用因子"}
                </td>
                <td>{r.emissions_tco2e != null ? r.emissions_tco2e.toLocaleString() : "-"}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="danger" style={{ background: "#0f766e", marginRight: 6 }} onClick={() => startEdit(r)}>编辑</button>
                  <button className="danger" onClick={() => remove(r.id)}>删除</button>
                </td>
              </tr>
            ))}
            {records.length === 0 && (
              <tr><td colSpan={8} className="muted">暂无记录</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
