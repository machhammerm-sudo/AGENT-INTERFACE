import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { api, Agent, Message } from "../api";

interface UploadedFile {
  id: number;
  filename: string;
  content_type: string | null;
  agent_id: number | null;
  uploaded_at: string;
}

export default function AgentChat() {
  const { agentId } = useParams();
  const id = Number(agentId);

  const [agent, setAgent] = useState<Agent | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [showStructured, setShowStructured] = useState(false);
  const [subject, setSubject] = useState("");
  const [desiredOutcome, setDesiredOutcome] = useState("");

  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<Message[] | null>(null);

  const [files, setFiles] = useState<UploadedFile[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const bottomRef = useRef<HTMLDivElement>(null);

  function loadAgent() {
    api.agents.list().then((all) => setAgent(all.find((a) => a.id === id) ?? null));
  }

  function loadHistory() {
    api.chat.history(id).then(setMessages);
  }

  function loadFiles() {
    fetch(`/api/files?agent_id=${id}`)
      .then((r) => r.json())
      .then(setFiles);
  }

  useEffect(() => {
    loadAgent();
    loadHistory();
    loadFiles();
    setSearchResults(null);
    setSearchQuery("");
  }, [id]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function handleSend(e: React.FormEvent) {
    e.preventDefault();
    let finalMessage = draft.trim();
    if (showStructured) {
      const parts = [];
      if (subject.trim()) parts.push(`Betreff: ${subject.trim()}`);
      if (desiredOutcome.trim()) parts.push(`Gewünschtes Ergebnis: ${desiredOutcome.trim()}`);
      if (finalMessage) parts.push(finalMessage);
      finalMessage = parts.join("\n\n");
    }
    if (!finalMessage) return;

    setSending(true);
    setError(null);
    try {
      await api.chat.send(id, finalMessage);
      setDraft("");
      setSubject("");
      setDesiredOutcome("");
      loadHistory();
      loadAgent();
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setSending(false);
    }
  }

  async function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    const results = await api.chat.history(id, searchQuery.trim());
    setSearchResults(results);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const form = new FormData();
    form.append("file", file);
    await fetch(`/api/files?agent_id=${id}`, { method: "POST", body: form });
    if (fileInputRef.current) fileInputRef.current.value = "";
    loadFiles();
  }

  if (!agent) return <p className="text-muted">Lade Agent…</p>;

  const shown = searchResults ?? messages;

  return (
    <div>
      <Link to="/" className="text-muted" style={{ fontSize: "0.82rem" }}>
        ← Zurück zum Cockpit
      </Link>
      <h1 style={{ marginTop: 10 }}>{agent.name}</h1>
      <p className="text-muted" style={{ marginTop: -10 }}>{agent.role_title}</p>
      {!agent.is_active && (
        <div className="card" style={{ borderColor: "var(--text-muted)" }}>
          Dieser Agent ist pausiert. Aktiviere ihn auf der Agenten-Seite, um weiterzuschreiben.
        </div>
      )}

      <form onSubmit={handleSearch} style={{ marginBottom: 14 }}>
        <div className="flex-row">
          <input
            placeholder="In der Historie suchen…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button className="btn secondary" type="submit">
            Suchen
          </button>
          {searchResults && (
            <button
              type="button"
              className="btn secondary"
              onClick={() => {
                setSearchResults(null);
                setSearchQuery("");
              }}
            >
              Zurücksetzen
            </button>
          )}
        </div>
      </form>

      <div className="chat-window">
        {shown.length === 0 && <p className="empty-state">Noch keine Nachrichten.</p>}
        {shown.map((m) => (
          <div key={m.id} className={`chat-bubble ${m.role}`}>
            {m.content}
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      {error && (
        <p style={{ color: "var(--danger)", fontSize: "0.85rem" }}>{error}</p>
      )}

      <form onSubmit={handleSend} className="card">
        <div className="flex-between">
          <h3 style={{ margin: 0 }}>Nachricht</h3>
          <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0, textTransform: "none" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={showStructured}
              onChange={(e) => setShowStructured(e.target.checked)}
            />
            Strukturierte Felder
          </label>
        </div>

        {showStructured && (
          <>
            <label>Betreff</label>
            <input value={subject} onChange={(e) => setSubject(e.target.value)} />
            <label>Gewünschtes Ergebnis</label>
            <input value={desiredOutcome} onChange={(e) => setDesiredOutcome(e.target.value)} />
            <label>Zusätzlicher Text</label>
          </>
        )}

        <div className="chat-input-row" style={{ marginTop: showStructured ? 6 : 16 }}>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder={`Schreib ${agent.name} eine Nachricht…`}
          />
          <button className="btn" disabled={sending || !agent.is_active}>
            {sending ? "Sendet…" : "Senden"}
          </button>
        </div>
      </form>

      <section style={{ marginTop: 28 }}>
        <h2>Dateien für {agent.name}</h2>
        <div className="card">
          <input type="file" ref={fileInputRef} onChange={handleUpload} />
        </div>
        {files.length === 0 && <p className="empty-state">Noch keine Dateien hochgeladen.</p>}
        <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(200px, 1fr))" }}>
          {files.map((f) => (
            <div key={f.id} className="card">
              <div style={{ fontSize: "0.85rem", fontWeight: 600, marginBottom: 8 }}>{f.filename}</div>
              {f.content_type?.startsWith("image/") && (
                <img
                  src={`/api/files/${f.id}/download`}
                  alt={f.filename}
                  style={{ maxWidth: "100%", borderRadius: 8, marginBottom: 8 }}
                />
              )}
              {f.content_type === "application/pdf" && (
                <embed
                  src={`/api/files/${f.id}/download`}
                  type="application/pdf"
                  width="100%"
                  height="220"
                  style={{ borderRadius: 8, marginBottom: 8 }}
                />
              )}
              <a href={`/api/files/${f.id}/download`} target="_blank" rel="noreferrer" className="text-muted">
                Öffnen / herunterladen
              </a>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
