"use client";

import { FormEvent, useEffect, useState } from "react";
import { api, Facility } from "@/lib/api";

export default function FacilitiesPage() {
  const [facilities, setFacilities] = useState<Facility[]>([]);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [location, setLocation] = useState("");
  const [industry, setIndustry] = useState("");
  const [error, setError] = useState("");

  const load = () => api.listFacilities().then(setFacilities).catch((e) => setError(e.message));
  useEffect(() => { load(); }, []);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setError("");
    try {
      await api.createFacility({
        name, code,
        location: location || null,
        industry: industry || null,
      });
      setName(""); setCode(""); setLocation(""); setIndustry("");
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "提交失败");
    }
  };

  return (
    <>
      <h1>厂区管理</h1>
      <div className="card">
        <form className="entry" onSubmit={submit}>
          <div>
            <label>厂区名称</label>
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <div>
            <label>厂区编码</label>
            <input required value={code} onChange={(e) => setCode(e.target.value)} />
          </div>
          <div>
            <label>所在地</label>
            <input value={location} onChange={(e) => setLocation(e.target.value)} />
          </div>
          <div>
            <label>行业</label>
            <input value={industry} onChange={(e) => setIndustry(e.target.value)} />
          </div>
          <div>
            <button type="submit">新增厂区</button>
          </div>
        </form>
        {error && <p className="error">{error}</p>}
      </div>

      <div className="card">
        <table>
          <thead>
            <tr><th>编码</th><th>名称</th><th>所在地</th><th>行业</th></tr>
          </thead>
          <tbody>
            {facilities.map((f) => (
              <tr key={f.id}>
                <td>{f.code}</td>
                <td>{f.name}</td>
                <td>{f.location ?? "-"}</td>
                <td>{f.industry ?? "-"}</td>
              </tr>
            ))}
            {facilities.length === 0 && (
              <tr><td colSpan={4} className="muted">暂无厂区，请先新增</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
