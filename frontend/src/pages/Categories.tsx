import { useEffect, useState } from "react";
import { api, Category } from "../api";

export default function Categories() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [draftName, setDraftName] = useState("");
  const [draftDesc, setDraftDesc] = useState("");

  function load() {
    api.categories.list().then(setCategories);
  }
  useEffect(load, []);

  function startEdit(c: Category) {
    setEditingId(c.id);
    setDraftName(c.name);
    setDraftDesc(c.description);
  }

  async function saveEdit(id: number) {
    await api.categories.update(id, { name: draftName, description: draftDesc });
    setEditingId(null);
    load();
  }

  return (
    <div>
      <h1>Kategorien</h1>
      <p className="text-muted" style={{ marginTop: -10 }}>
        Jede Aufgabe oder Entscheidung wird automatisch einer dieser neun Kategorien zugeordnet — du kannst
        die Zuordnung jederzeit manuell korrigieren und die Kategorien hier anpassen.
      </p>

      {categories.map((c) => (
        <div key={c.id} className="card">
          {editingId === c.id ? (
            <div>
              <label>Name</label>
              <input value={draftName} onChange={(e) => setDraftName(e.target.value)} />
              <label>Beschreibung</label>
              <textarea value={draftDesc} onChange={(e) => setDraftDesc(e.target.value)} rows={2} />
              <div style={{ marginTop: 12, display: "flex", gap: 8 }}>
                <button className="btn" onClick={() => saveEdit(c.id)}>
                  Speichern
                </button>
                <button className="btn secondary" onClick={() => setEditingId(null)}>
                  Abbrechen
                </button>
              </div>
            </div>
          ) : (
            <div className="flex-between">
              <div>
                <div style={{ fontWeight: 600 }}>
                  {c.name} {c.is_user_edited && <span className="tag">angepasst</span>}
                </div>
                <div className="text-muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
                  {c.description}
                </div>
              </div>
              <button className="btn secondary" onClick={() => startEdit(c)}>
                Bearbeiten
              </button>
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
