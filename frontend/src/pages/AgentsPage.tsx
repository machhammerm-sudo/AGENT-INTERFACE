import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, Agent } from "../api";

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const [task, setTask] = useState("");
  const [creating, setCreating] = useState(false);

  const [contactDesc, setContactDesc] = useState("");
  const [contactSent, setContactSent] = useState(false);

  function load() {
    api.agents.list().then(setAgents);
  }
  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim() || !role.trim() || !task.trim()) return;
    setCreating(true);
    try {
      await api.agents.create({ name, role_title: role, core_task: task });
      setName("");
      setRole("");
      setTask("");
      load();
    } finally {
      setCreating(false);
    }
  }

  async function togglePause(agent: Agent) {
    await api.agents.update(agent.id, { is_active: !agent.is_active });
    load();
  }

  async function sendContactRequest(e: React.FormEvent) {
    e.preventDefault();
    if (!contactDesc.trim()) return;
    await api.contactRequests.create({ description: contactDesc });
    setContactDesc("");
    setContactSent(true);
  }

  return (
    <div>
      <h1>Agenten</h1>

      <section>
        <h2>Team</h2>
        <div className="grid agents">
          {agents.map((a) => (
            <div key={a.id} className="card">
              <div className="flex-between">
                <Link to={`/agenten/${a.id}`} style={{ color: "inherit", fontWeight: 600, textDecoration: "none" }}>
                  {a.name}
                </Link>
                {a.is_restricted && <span className="tag gold-text">Sicherheit</span>}
              </div>
              <div className="text-muted" style={{ fontSize: "0.82rem", margin: "6px 0 12px" }}>
                {a.role_title}
              </div>
              <p style={{ fontSize: "0.85rem", margin: "0 0 12px" }}>{a.core_task}</p>
              <button className="btn secondary" onClick={() => togglePause(a)}>
                {a.is_active ? "Pausieren" : "Aktivieren"}
              </button>
            </div>
          ))}
        </div>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Neuen Agenten anlegen</h2>
        <p className="text-muted" style={{ marginTop: -6 }}>
          Beschreibe in normaler Sprache, wer der Agent ist und was er tun soll — keine Vorlagen nötig.
        </p>
        <form onSubmit={handleCreate} className="card">
          <label>Name</label>
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="z.B. Sophie" />
          <label>Rolle / Schwerpunkt</label>
          <input value={role} onChange={(e) => setRole(e.target.value)} placeholder="z.B. Einkauf & Lieferanten" />
          <label>Kernaufgabe</label>
          <textarea
            value={task}
            onChange={(e) => setTask(e.target.value)}
            rows={3}
            placeholder="Beschreibe frei, was dieser Agent für dich übernehmen soll."
          />
          <button className="btn" style={{ marginTop: 16 }} disabled={creating}>
            Agent anlegen
          </button>
        </form>
      </section>

      <section style={{ marginTop: 32 }}>
        <h2>Kontaktanfrage für komplexere Agenten-Wünsche</h2>
        <p className="text-muted" style={{ marginTop: -6 }}>
          Für aufwendigere, individuelle Anfragen (z.B. von Kunden) gibt es hier bewusst keinen Self-Service.
          Deine Anfrage wird gespeichert, damit du das Beratungsgespräch (inkl. Kostenabschätzung) selbst führst.
        </p>
        <form onSubmit={sendContactRequest} className="card">
          <label>Worum geht es?</label>
          <textarea
            value={contactDesc}
            onChange={(e) => setContactDesc(e.target.value)}
            rows={3}
            placeholder="Beschreibe den Wunsch oder die Anfrage."
          />
          <button className="btn gold" style={{ marginTop: 16 }}>
            Anfrage speichern
          </button>
          {contactSent && (
            <p className="gold-text" style={{ marginTop: 10, fontSize: "0.85rem" }}>
              Gespeichert. Du findest sie wieder, wenn du das Gespräch führst.
            </p>
          )}
        </form>
      </section>
    </div>
  );
}
