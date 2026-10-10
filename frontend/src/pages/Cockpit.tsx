import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Agent, AgendaItem, Category } from "../api";

const statusLabel: Record<Agent["status"], string> = {
  working: "Arbeitet",
  waiting_for_user: "Wartet auf dich",
  done: "Fertig",
  paused: "Pausiert",
};

const statusPillClass: Record<Agent["status"], string> = {
  working: "pill pill-working",
  waiting_for_user: "pill pill-waiting",
  done: "pill pill-done",
  paused: "pill pill-paused",
};

export default function Cockpit() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [agenda, setAgenda] = useState<AgendaItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    Promise.all([api.agents.list(), api.agenda.list(), api.categories.list()])
      .then(([a, ag, c]) => {
        setAgents(a);
        setAgenda(ag);
        setCategories(c);
        setError(null);
      })
      .catch((e) => setError(String(e.message || e)))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function markDone(id: number) {
    await api.agenda.update(id, { is_done: true });
    load();
  }

  const categoryName = (id: number | null) =>
    id ? categories.find((c) => c.id === id)?.name : null;

  if (loading) return <p className="text-muted">Lade Cockpit…</p>;

  return (
    <div>
      <h1>Cockpit</h1>

      {error && (
        <div className="card" style={{ borderColor: "var(--danger)" }}>
          Etwas ist schiefgelaufen: {error}
        </div>
      )}

      <section>
        <h2>Weekly Agenda</h2>
        <p className="text-muted" style={{ marginTop: -6, marginBottom: 14 }}>
          Eine Empfehlung, worauf du als Nächstes schauen solltest — keine Pflichtliste.
        </p>
        {agenda.length === 0 && (
          <p className="empty-state">Aktuell keine offenen Punkte. Gute Lage.</p>
        )}
        {agenda.map((item) => (
          <div key={item.id} className={"card" + (item.is_blocking ? " gold-highlight" : "")}>
            <div className="flex-between">
              <div>
                <div style={{ fontWeight: 600 }}>
                  {item.is_blocking && <span className="blocking-marker">● Blockierend — </span>}
                  {item.title}
                </div>
                <div className="text-muted" style={{ marginTop: 4, fontSize: "0.85rem" }}>
                  {item.reason}
                </div>
                {categoryName(item.category_id) && (
                  <span className="tag" style={{ marginTop: 8, display: "inline-block" }}>
                    {categoryName(item.category_id)}
                  </span>
                )}
              </div>
              <button className="btn secondary" onClick={() => markDone(item.id)}>
                Erledigt
              </button>
            </div>
          </div>
        ))}
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Team-Status</h2>
        <div className="grid agents">
          {agents.map((agent) => (
            <Link
              key={agent.id}
              to={`/agenten/${agent.id}`}
              className="card"
              style={{ textDecoration: "none", color: "inherit", display: "block" }}
            >
              <div className="flex-between">
                <div style={{ fontWeight: 600 }}>{agent.name}</div>
                <span className={statusPillClass[agent.status]}>
                  {statusLabel[agent.status]}
                </span>
              </div>
              <div className="text-muted" style={{ fontSize: "0.82rem", marginTop: 6 }}>
                {agent.role_title}
              </div>
              {!agent.is_active && (
                <div className="tag" style={{ marginTop: 10 }}>
                  pausiert
                </div>
              )}
            </Link>
          ))}
        </div>
      </section>
    </div>
  );
}
