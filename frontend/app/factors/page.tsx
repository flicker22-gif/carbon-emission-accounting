"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, EmissionFactor, FactorImpactPreview, REGIONS } from "@/lib/api";

const emptyForm = {
  energy_type: "",
  name_zh: "",
  scope: 1,
  category: "",
  unit: "",
  factor_value: "",
  region: "全国",
  year: new Date().getFullYear(),
  source: "",
  note: "",
};

type FactorPayload = Omit<EmissionFactor, "id">;

const fmt = (v: number) =>
  v.toLocaleString("zh-CN", { maximumFractionDigits: 4 });

/** 排放量差值:增加红色、减少绿色、为零灰色 */
function Delta({ value }: { value: number }) {
  const cls = value > 0 ? "delta-up" : value < 0 ? "delta-down" : "muted";
  return (
    <span className={cls}>
      {value > 0 ? "+" : ""}
      {fmt(value)}
    </span>
  );
}

export default function FactorsPage() {
  const [factors, setFactors] = useState<EmissionFactor[]>([]);
  const [filterType, setFilterType] = useState("");
  const [filterRegion, setFilterRegion] = useState("");
  const [form, setForm] = useState(emptyForm);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [error, setError] = useState("");
  // 保存前试算:有影响记录时弹出确认,impact 非空即显示确认框
  const [impact, setImpact] = useState<FactorImpactPreview | null>(null);
  const [pendingPayload, setPendingPayload] = useState<FactorPayload | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [saving, setSaving] = useState(false);

  const load = () => {
    api
      .listFactors({
        energy_type: filterType || undefined,
        region: filterRegion || undefined,
      })
      .then(setFactors)
      .catch((e) => setError(e.message));
  };

  useEffect(load, [filterType, filterRegion]);

  const energyTypes = [...new Set(factors.map((f) => f.energy_type))];

  const set = (key: string, value: string | number) =>
    setForm((f) => ({ ...f, [key]: value }));

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    const payload: FactorPayload = {
      ...form,
      scope: Number(form.scope),
      year: Number(form.year),
      factor_value: Number(form.factor_value),
      source: form.source || null,
      note: form.note || null,
    };
    // 保存前先试算:无记录受影响则直接保存,否则弹确认框
    setPreviewing(true);
    try {
      const preview = await api.previewFactorImpact(editingId, payload);
      if (preview.affected_records === 0) {
        await save(payload);
      } else {
        setPendingPayload(payload);
        setImpact(preview);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "试算失败");
    } finally {
      setPreviewing(false);
    }
  };

  const save = async (payload: FactorPayload) => {
    setSaving(true);
    setError("");
    try {
      if (editingId) {
        await api.updateFactor(editingId, payload);
      } else {
        await api.createFactor(payload);
      }
      setForm(emptyForm);
      setEditingId(null);
      setImpact(null);
      setPendingPayload(null);
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const confirmSave = () => {
    if (pendingPayload) save(pendingPayload);
  };

  const startEdit = (f: EmissionFactor) => {
    setEditingId(f.id);
    setForm({
      energy_type: f.energy_type,
      name_zh: f.name_zh,
      scope: f.scope,
      category: f.category,
      unit: f.unit,
      factor_value: String(f.factor_value),
      region: f.region,
      year: f.year,
      source: f.source ?? "",
      note: f.note ?? "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const remove = async (id: number) => {
    if (!confirm("确定删除该因子?相关历史记录将重新匹配其他版本因子。")) return;
    await api.deleteFactor(id);
    load();
  };

  return (
    <>
      <h1>排放因子库管理</h1>

      <div className="card">
        <h2>{editingId ? `编辑因子 #${editingId}` : "新增因子"}</h2>
        <form className="entry" onSubmit={submit}>
          <div>
            <label>能源类型(英文标识)</label>
            <input
              required list="energy-types" value={form.energy_type}
              onChange={(e) => set("energy_type", e.target.value)}
              placeholder="如 electricity"
            />
            <datalist id="energy-types">
              {energyTypes.map((t) => <option key={t} value={t} />)}
            </datalist>
          </div>
          <div>
            <label>中文名称</label>
            <input required value={form.name_zh} onChange={(e) => set("name_zh", e.target.value)} />
          </div>
          <div>
            <label>范围</label>
            <select value={form.scope} onChange={(e) => set("scope", e.target.value)}>
              <option value={1}>范围一 · 直接排放</option>
              <option value={2}>范围二 · 外购能源</option>
              <option value={3}>范围三 · 其他间接</option>
            </select>
          </div>
          <div>
            <label>类别</label>
            <input required value={form.category} onChange={(e) => set("category", e.target.value)} placeholder="如 外购电力" />
          </div>
          <div>
            <label>活动数据单位</label>
            <input required value={form.unit} onChange={(e) => set("unit", e.target.value)} placeholder="如 kWh" />
          </div>
          <div>
            <label>因子值 (kgCO₂e/单位)</label>
            <input
              required type="number" min="0" step="any" value={form.factor_value}
              onChange={(e) => set("factor_value", e.target.value)}
            />
          </div>
          <div>
            <label>适用地区</label>
            <select value={form.region} onChange={(e) => set("region", e.target.value)}>
              {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <div>
            <label>适用年度</label>
            <input
              required type="number" min="1990" max="2100" value={form.year}
              onChange={(e) => set("year", e.target.value)}
            />
          </div>
          <div>
            <label>来源</label>
            <input value={form.source} onChange={(e) => set("source", e.target.value)} placeholder="如 生态环境部 2024 发布" />
          </div>
          <div>
            <label>备注</label>
            <input value={form.note} onChange={(e) => set("note", e.target.value)} />
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <button type="submit" disabled={previewing || saving}>
              {previewing ? "试算中…" : editingId ? "保存修改" : "新增因子"}
            </button>
            {editingId && (
              <button
                type="button" className="danger"
                onClick={() => { setEditingId(null); setForm(emptyForm); setImpact(null); }}
              >
                取消
              </button>
            )}
          </div>
        </form>
        {error && <p className="error">{error}</p>}
        <p className="muted" style={{ marginBottom: 0 }}>
          同一「能源类型 + 地区 + 年度」唯一;计算时优先匹配厂区所在地区的因子,无则回退「全国」,年度取不超过数据期间的最新值。
        </p>
      </div>

      <div className="card">
        <div style={{ display: "flex", gap: 12, marginBottom: 14 }}>
          <select value={filterType} onChange={(e) => setFilterType(e.target.value)} style={{ maxWidth: 220 }}>
            <option value="">全部能源类型</option>
            {energyTypes.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          <select value={filterRegion} onChange={(e) => setFilterRegion(e.target.value)} style={{ maxWidth: 160 }}>
            <option value="">全部地区</option>
            {REGIONS.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <table>
          <thead>
            <tr>
              <th>能源类型</th><th>范围</th><th>类别</th><th>单位</th>
              <th>因子值</th><th>地区</th><th>年度</th><th>来源</th><th></th>
            </tr>
          </thead>
          <tbody>
            {factors.map((f) => (
              <tr key={f.id}>
                <td>{f.name_zh}<span className="muted"> ({f.energy_type})</span></td>
                <td><span className={`badge s${f.scope}`}>范围{f.scope}</span></td>
                <td>{f.category}</td>
                <td>{f.unit}</td>
                <td>{f.factor_value}</td>
                <td>{f.region}</td>
                <td>{f.year}</td>
                <td className="muted">{f.source ?? "-"}</td>
                <td style={{ whiteSpace: "nowrap" }}>
                  <button className="danger" style={{ background: "#0f766e", marginRight: 6 }} onClick={() => startEdit(f)}>编辑</button>
                  <button className="danger" onClick={() => remove(f.id)}>删除</button>
                </td>
              </tr>
            ))}
            {factors.length === 0 && (
              <tr><td colSpan={9} className="muted">无匹配因子</td></tr>
            )}
          </tbody>
        </table>
      </div>

      {impact && (
        <div className="modal-mask">
          <div className="modal">
            <h2>确认因子变更影响</h2>
            <p>
              本次变更将影响 <b>{impact.affected_records}</b> 条能耗记录,
              这些记录的合计排放量由 <b>{fmt(impact.total_before_tco2e)}</b> tCO₂e
              变为 <b>{fmt(impact.total_after_tco2e)}</b> tCO₂e(
              <Delta value={impact.delta_tco2e} /> tCO₂e)。
            </p>

            {impact.by_year.length > 0 && (
              <table style={{ marginBottom: 14 }}>
                <thead>
                  <tr>
                    <th>数据年度</th><th>受影响记录</th>
                    <th>变更前 (tCO₂e)</th><th>变更后 (tCO₂e)</th><th>差值</th>
                  </tr>
                </thead>
                <tbody>
                  {impact.by_year.map((y) => (
                    <tr key={y.year}>
                      <td>{y.year}</td>
                      <td>{y.records}</td>
                      <td>{fmt(y.before_tco2e)}</td>
                      <td>{fmt(y.after_tco2e)}</td>
                      <td><Delta value={y.delta_tco2e} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}

            {impact.samples.length > 0 && (
              <>
                <p className="muted" style={{ marginBottom: 6 }}>
                  受影响记录抽样(前 {impact.samples.length} 条):
                </p>
                <table style={{ marginBottom: 14 }}>
                  <thead>
                    <tr>
                      <th>厂区</th><th>期间</th><th>能源类型</th>
                      <th>变更前因子</th><th>变更后因子</th>
                      <th>变更前 (tCO₂e)</th><th>变更后 (tCO₂e)</th>
                    </tr>
                  </thead>
                  <tbody>
                    {impact.samples.map((s) => (
                      <tr key={s.record_id}>
                        <td>{s.facility_name}</td>
                        <td>{s.period}</td>
                        <td>{s.energy_type}</td>
                        <td>{s.before_factor ?? "未匹配"}</td>
                        <td>{s.after_factor ?? "未匹配"}</td>
                        <td>{s.before_tco2e ?? "-"}</td>
                        <td>{s.after_tco2e ?? "-"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}

            <p className="muted">
              确认生效后,相关历史记录将按变更后的因子重新计算排放量。
            </p>
            {error && <p className="error">{error}</p>}
            <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
              <button type="button" className="ghost" disabled={saving}
                onClick={() => { setImpact(null); setPendingPayload(null); }}>
                返回修改
              </button>
              <button type="button" disabled={saving} onClick={confirmSave}>
                {saving ? "生效中…" : "确认生效"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
