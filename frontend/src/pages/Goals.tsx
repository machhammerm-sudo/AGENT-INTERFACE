import { useEffect, useState } from "react";
import { api, Goal, GoalLevel, Achievement } from "../api";

const levelLabel: Record<GoalLevel, string> = {
  month: "Monatsziel",
  year: "Jahresziel",
  long_term: "Langfristige Richtung (3-5-10 Jahre)",
};

const levelOrder: GoalLevel[] = ["month", "year", "long_term"];

export default function Goals() {
  const [goals, setGoals] = useState<Goal[]>([]);
  const [achievements, setAchievements] = useState<Achievement[]>([]);
  const [summary, setSummary] = useState<{ total_achievements: number; total_time_saved_hours: number } | null>(null);

  const [level, setLevel] = useState<GoalLevel>("month");
  const [title, setTitle] = useState("");
  const [why, setWhy] = useState("");
  const [targetDate, setTargetDate] = useState("");

  function load() {
    api.goals.list().then(setGoals);
    api.achievements.list().then(setAchievements);
    api.achievements.summary().then(setSummary);
  }
  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!title.trim() || !why.trim()) return;
    await api.goals.create({ level, title, why_important: why, target_date: targetDate || undefined });
    setTitle("");
    setWhy("");
    setTargetDate("");
    load();
  }

  async function markStatus(goal: Goal, status: Goal["status"]) {
    await api.goals.update(goal.id, { status });
    load();
  }

  return (
    <div>
      <h1>Ziele & Fortschritt</h1>
      <p className="text-muted" style={{ marginTop: -10 }}>
        Deine Ziele sind der Nordstern für das Team — die Agenten richten ihre Vorschläge daran aus.
      </p>

      {levelOrder.map((lvl) => (
        <section key={lvl} style={{ marginTop: 24 }}>
          <h2>{levelLabel[lvl]}</h2>
          {goals.filter((g) => g.level === lvl).length === 0 && (
            <p className="empty-state">Noch kein Ziel auf dieser Ebene.</p>
          )}
          {goals
            .filter((g) => g.level === lvl)
            .map((g) => (
              <div key={g.id} className={"card" + (g.status !== "active" ? "" : "")}>
                <div className="flex-between">
                  <div style={{ fontWeight: 600 }}>{g.title}</div>
                  <span className="tag">
                    {g.status === "active" ? "aktiv" : g.status === "achieved" ? "erreicht" : "verfehlt"}
                  </span>
                </div>
                <div className="text-muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
                  {g.why_important}
                </div>
                {g.target_date && (
                  <div className="text-muted" style={{ fontSize: "0.78rem", marginTop: 6 }}>
                    Zeithorizont: {g.target_date}
                  </div>
                )}
                {g.status === "active" && (
                  <div style={{ marginTop: 10, display: "flex", gap: 8 }}>
                    <button className="btn secondary" onClick={() => markStatus(g, "achieved")}>
                      Als erreicht markieren
                    </button>
                    <button className="btn secondary" onClick={() => markStatus(g, "missed")}>
                      Als verfehlt markieren
                    </button>
                  </div>
                )}
                {g.status === "missed" && (
                  <p className="gold-text" style={{ fontSize: "0.82rem", marginTop: 8 }}>
                    Das Team erkennt dieses verfehlte Ziel und sollte dir Gegensteuerungs-Vorschläge machen,
                    sobald du im Chat danach fragst.
                  </p>
                )}
              </div>
            ))}
        </section>
      ))}

      <section style={{ marginTop: 32 }}>
        <h2>Neues Ziel</h2>
        <form onSubmit={handleCreate} className="card">
          <label>Ebene</label>
          <select value={level} onChange={(e) => setLevel(e.target.value as GoalLevel)}>
            {levelOrder.map((lvl) => (
              <option key={lvl} value={lvl}>
                {levelLabel[lvl]}
              </option>
            ))}
          </select>
          <label>Was soll erreicht werden?</label>
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
          <label>Warum ist dir das wichtig?</label>
          <textarea value={why} onChange={(e) => setWhy(e.target.value)} rows={2} />
          <label>Zeithorizont (frei, optional)</label>
          <input
            value={targetDate}
            onChange={(e) => setTargetDate(e.target.value)}
            placeholder={level === "long_term" ? "z.B. 'in 5 Jahren'" : "z.B. 2026-11"}
          />
          <button className="btn" style={{ marginTop: 16 }}>
            Ziel speichern
          </button>
        </form>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Rückschau</h2>
        <p className="text-muted" style={{ marginTop: -6 }}>
          Was mit dem Team bereits erreicht wurde — als Ausgleich zur reinen To-Do-Sicht.
        </p>
        {summary && (
          <div className="card gold-highlight">
            <div className="flex-between">
              <div>
                <div style={{ fontWeight: 700, fontSize: "1.1rem" }}>{summary.total_achievements}</div>
                <div className="text-muted" style={{ fontSize: "0.8rem" }}>Erfolge</div>
              </div>
              <div>
                <div className="gold-text" style={{ fontWeight: 700, fontSize: "1.1rem" }}>
                  {summary.total_time_saved_hours} Std.
                </div>
                <div className="text-muted" style={{ fontSize: "0.8rem" }}>gesparte Zeit</div>
              </div>
            </div>
          </div>
        )}
        {achievements.length === 0 && (
          <p className="empty-state">Noch keine Erfolge eingetragen.</p>
        )}
        {achievements.map((a) => (
          <div key={a.id} className="card">
            <div style={{ fontWeight: 600 }}>{a.title}</div>
            <div className="text-muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>{a.description}</div>
            {a.time_saved_minutes > 0 && (
              <div className="gold-text" style={{ fontSize: "0.78rem", marginTop: 6 }}>
                ~{Math.round(a.time_saved_minutes / 60)} Std. gespart
              </div>
            )}
          </div>
        ))}
      </section>
    </div>
  );
}
