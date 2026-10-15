import { useEffect, useRef, useState } from "react";
import {
  api, BenchmarkRun, DocCustomer, DocFieldResult, DocumentDetail, LiveMetrics,
  PlanDocument, PrivacySettings, SampleCheck, WeeklyHistoryPoint,
} from "../api";

const statusPillClass: Record<string, string> = {
  green: "pill pill-done",
  yellow: "pill pill-waiting",
  red: "pill",
};

const statusLabel: Record<string, string> = {
  green: "Sicher",
  yellow: "Bitte prüfen",
  red: "Nicht gefunden",
};

export default function Documents() {
  const [customers, setCustomers] = useState<DocCustomer[]>([]);
  const [customerId, setCustomerId] = useState<number | null>(null);
  const [newCustomerName, setNewCustomerName] = useState("");

  const [privacy, setPrivacy] = useState<PrivacySettings | null>(null);
  const [documents, setDocuments] = useState<PlanDocument[]>([]);
  const [detail, setDetail] = useState<DocumentDetail | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  function loadCustomers() {
    api.documents.customers.list().then((list) => {
      setCustomers(list);
      if (!customerId && list.length > 0) setCustomerId(list[0].id);
    });
  }
  useEffect(loadCustomers, []);

  function loadDocuments(cid: number) {
    api.documents.list(cid).then(setDocuments);
  }

  useEffect(() => {
    if (customerId == null) return;
    api.documents.privacy.get(customerId).then(setPrivacy);
    loadDocuments(customerId);
    setDetail(null);
  }, [customerId]);

  async function createCustomer(e: React.FormEvent) {
    e.preventDefault();
    if (!newCustomerName.trim()) return;
    const created = await api.documents.customers.create(newCustomerName);
    setNewCustomerName("");
    loadCustomers();
    setCustomerId(created.id);
  }

  async function togglePrivacy(key: "contribute_anonymized_structure_data" | "allow_cloud_escalation") {
    if (customerId == null || !privacy) return;
    const updated = await api.documents.privacy.update(customerId, { [key]: !privacy[key] });
    setPrivacy(updated);
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await api.documents.upload(file, customerId);
      setDetail(result);
      if (customerId != null) loadDocuments(customerId);
    } catch (err: any) {
      setError(err.message || String(err));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function openDocument(id: number) {
    const result = await api.documents.get(id);
    setDetail(result);
  }

  async function refreshDetail() {
    if (detail) {
      const result = await api.documents.get(detail.document.id);
      setDetail(result);
    }
  }

  return (
    <div>
      <h1>Dokumente</h1>
      <p className="text-muted" style={{ marginTop: -10 }}>
        Eingescannte Pläne hochladen - Titelblock-Felder werden automatisch erkannt, rein lokal.
        Grün heißt sicher erkannt, gelb braucht einen kurzen Blick, rot wurde nicht gefunden.
      </p>

      <section>
        <h2>Kunde</h2>
        <div className="flex-row">
          <select
            value={customerId ?? ""}
            onChange={(e) => setCustomerId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— kein Kunde —</option>
            {customers.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
          <form onSubmit={createCustomer} className="flex-row">
            <input
              placeholder="Neuer Kunde…"
              value={newCustomerName}
              onChange={(e) => setNewCustomerName(e.target.value)}
              style={{ width: 180 }}
            />
            <button className="btn secondary" type="submit">Anlegen</button>
          </form>
        </div>
      </section>

      {customerId != null && privacy && (
        <section className="card" style={{ marginTop: 16 }}>
          <h3 style={{ marginTop: 0 }}>Datenschutz für diesen Kunden</h3>
          <label style={{ display: "flex", alignItems: "center", gap: 8, textTransform: "none" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={privacy.allow_cloud_escalation}
              onChange={() => togglePrivacy("allow_cloud_escalation")}
            />
            Bei unsicheren Feldern darf ein einzelner Bildausschnitt an Claude geschickt werden (Cloud-Hilfe)
          </label>
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, textTransform: "none" }}>
            <input
              type="checkbox"
              style={{ width: "auto" }}
              checked={privacy.contribute_anonymized_structure_data}
              onChange={() => togglePrivacy("contribute_anonymized_structure_data")}
            />
            Anonymisierte Strukturdaten zur Verbesserung des Systems beitragen (noch ohne Funktion)
          </label>
          <p className="text-muted" style={{ fontSize: "0.78rem", marginTop: 10, marginBottom: 0 }}>
            Beides ist standardmäßig aus. Ohne das erste Häkchen bleibt ein unsicheres Feld gelb oder rot,
            statt an die Cloud geschickt zu werden.
          </p>
        </section>
      )}

      <section style={{ marginTop: 24 }}>
        <h2>Plan hochladen</h2>
        <div className="card">
          <input type="file" ref={fileInputRef} onChange={handleUpload} accept=".pdf,.png,.jpg,.jpeg,.tif,.tiff,.bmp" />
          {uploading && <p className="text-muted" style={{ marginTop: 10 }}>Liest den Plan aus…</p>}
          {error && <p style={{ color: "var(--danger)", marginTop: 10 }}>{error}</p>}
        </div>
      </section>

      {documents.length > 0 && (
        <section style={{ marginTop: 24 }}>
          <h2>Bisherige Pläne</h2>
          <div className="grid" style={{ gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))" }}>
            {documents.map((d) => (
              <div key={d.id} className="card" style={{ cursor: "pointer" }} onClick={() => openDocument(d.id)}>
                <div style={{ fontWeight: 600, fontSize: "0.88rem" }}>{d.filename}</div>
                <div className="text-muted" style={{ fontSize: "0.78rem", marginTop: 4 }}>
                  {d.status} · {new Date(d.uploaded_at).toLocaleString("de-DE")}
                </div>
              </div>
            ))}
          </div>
        </section>
      )}

      {detail && (
        <section style={{ marginTop: 28 }}>
          <h2>Prüfen: {detail.document.filename}</h2>
          <img
            src={api.documents.regionImageUrl(detail.document.id)}
            alt="Erkannter Titelblock-Bereich"
            style={{ maxWidth: "100%", border: "1px solid var(--petrol-line)", borderRadius: 8, marginBottom: 16 }}
          />
          {detail.fields.map((f) => (
            <FieldReviewCard
              key={f.field_key}
              documentId={detail.document.id}
              field={f}
              onChanged={refreshDetail}
            />
          ))}
        </section>
      )}

      {customerId != null && <QualitySection customerId={customerId} />}

      <BenchmarkSection />
    </div>
  );
}

function QualitySection({ customerId }: { customerId: number }) {
  const [metrics, setMetrics] = useState<LiveMetrics | null>(null);
  const [history, setHistory] = useState<WeeklyHistoryPoint[]>([]);
  const [checks, setChecks] = useState<SampleCheck[]>([]);

  function load() {
    api.documents.metrics.get(customerId).then(setMetrics);
    api.documents.metrics.history(customerId).then(setHistory);
    api.documents.sampleChecks.list(customerId).then(setChecks);
  }
  useEffect(load, [customerId]);

  async function resolve(id: number, verdict: "correct" | "incorrect") {
    await api.documents.sampleChecks.resolve(id, verdict);
    load();
  }

  return (
    <section style={{ marginTop: 32 }}>
      <h2>Erkennungsqualität bei echten Plänen</h2>
      <p className="text-muted" style={{ marginTop: -6 }}>
        Anteil der Felder, die ohne menschliche Korrektur richtig erkannt wurden - keine Werte, nur Zählwerte.
      </p>

      {metrics && metrics.overall_n > 0 ? (
        <div className="card gold-highlight">
          <div className="flex-between">
            <div>
              <div style={{ fontWeight: 700, fontSize: "1.2rem" }}>
                {Math.round(metrics.overall_correct_rate * 100)}%
              </div>
              <div className="text-muted" style={{ fontSize: "0.8rem" }}>richtig ohne Korrektur ({metrics.overall_n} Felder)</div>
            </div>
            <div>
              <div className="gold-text" style={{ fontWeight: 700, fontSize: "1.2rem" }}>
                {metrics.estimated_undetected_error_rate != null
                  ? `${Math.round(metrics.estimated_undetected_error_rate * 100)}%`
                  : "—"}
              </div>
              <div className="text-muted" style={{ fontSize: "0.8rem" }}>
                geschätzte unbemerkte Fehlerquote ({metrics.estimated_undetected_n} Stichproben)
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="empty-state">Noch keine Daten für diesen Kunden.</p>
      )}

      {history.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Verlauf je Woche</h3>
          {history.map((h) => (
            <div key={h.week} className="flex-between" style={{ fontSize: "0.85rem", padding: "4px 0" }}>
              <span className="text-muted">{h.week}</span>
              <span>{Math.round(h.correct_rate * 100)}% ({h.n})</span>
            </div>
          ))}
        </div>
      )}

      {checks.length > 0 && (
        <div className="card">
          <h3 style={{ marginTop: 0 }}>Stichprobenkontrolle</h3>
          <p className="text-muted" style={{ fontSize: "0.82rem", marginTop: -4 }}>
            Ein zufälliger Anteil grüner Felder wird dir hier zur kurzen Gegenprüfung vorgelegt.
          </p>
          {checks.map((c) => (
            <div key={c.id} className="flex-between" style={{ padding: "6px 0" }}>
              <span style={{ fontSize: "0.85rem" }}>
                Dokument #{c.document_id} · Feld "{c.field_key}"
              </span>
              <div style={{ display: "flex", gap: 8 }}>
                <button className="btn secondary" onClick={() => resolve(c.id, "correct")}>Richtig</button>
                <button className="btn secondary" onClick={() => resolve(c.id, "incorrect")}>Falsch</button>
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function BenchmarkSection() {
  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [running, setRunning] = useState(false);
  const [open, setOpen] = useState(false);

  function load() {
    api.documents.benchmark.history().then(setRuns);
  }
  useEffect(() => {
    if (open) load();
  }, [open]);

  async function runNow() {
    setRunning(true);
    try {
      await api.documents.benchmark.run();
      load();
    } finally {
      setRunning(false);
    }
  }

  return (
    <section style={{ marginTop: 32 }}>
      <div className="flex-between">
        <h2 style={{ margin: 0 }}>Prüfstand (Entwickleransicht)</h2>
        <button className="btn secondary" onClick={() => setOpen(!open)}>
          {open ? "Einklappen" : "Anzeigen"}
        </button>
      </div>
      {open && (
        <div style={{ marginTop: 12 }}>
          <button className="btn" onClick={runNow} disabled={running}>
            {running ? "Läuft…" : "Jetzt laufen lassen"}
          </button>
          {runs.map((r) => (
            <div key={r.id} className="card" style={{ marginTop: 12 }}>
              <div className="text-muted" style={{ fontSize: "0.78rem" }}>
                {new Date(r.run_at).toLocaleString("de-DE")} · {r.plan_count} Testpläne
              </div>
              <div className="flex-row" style={{ marginTop: 6 }}>
                <span>Trefferquote: <strong>{Math.round(r.overall_hit_rate * 100)}%</strong></span>
                <span>Falsch-grün: <strong className={r.false_green_rate > 0 ? "gold-text" : ""}>{Math.round(r.false_green_rate * 100)}%</strong></span>
                <span>Ohne Ergebnis: <strong>{Math.round(r.no_result_rate * 100)}%</strong></span>
              </div>
            </div>
          ))}
          {runs.length === 0 && <p className="empty-state" style={{ marginTop: 12 }}>Noch kein Lauf gespeichert.</p>}
        </div>
      )}
    </section>
  );
}

function FieldReviewCard({
  documentId, field, onChanged,
}: { documentId: number; field: DocFieldResult; onChanged: () => void }) {
  const [correctValue, setCorrectValue] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [busy, setBusy] = useState(false);

  async function confirm() {
    setBusy(true);
    try {
      await api.documents.reviewField(documentId, field.field_key, {
        action: "confirm", candidate_index: selectedIndex,
      });
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function correct(e: React.FormEvent) {
    e.preventDefault();
    if (!correctValue.trim()) return;
    setBusy(true);
    try {
      await api.documents.reviewField(documentId, field.field_key, {
        action: "correct", corrected_value: correctValue,
      });
      setCorrectValue("");
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={"card" + (field.status === "green" ? "" : "")}>
      <div className="flex-between">
        <div style={{ fontWeight: 600 }}>{field.label}</div>
        <span className={statusPillClass[field.status]}>{statusLabel[field.status]}</span>
      </div>

      {field.reviewed ? (
        <p className="text-muted" style={{ fontSize: "0.85rem", marginTop: 8 }}>
          {field.human_action === "confirmed" ? "Bestätigt: " : "Korrigiert: "}
          <strong>{field.corrected_value ?? field.chosen_value}</strong>
        </p>
      ) : (
        <>
          {field.candidates.length === 0 ? (
            <p className="empty-state" style={{ marginTop: 8 }}>Kein Wert gefunden.</p>
          ) : (
            <div style={{ marginTop: 10 }}>
              {field.candidates.map((c, i) => (
                <label key={i} style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6, textTransform: "none" }}>
                  <input
                    type="radio"
                    style={{ width: "auto" }}
                    name={`${field.field_key}-candidate`}
                    checked={selectedIndex === i}
                    onChange={() => setSelectedIndex(i)}
                  />
                  <span>{c.value}</span>
                  <span className="tag">{c.match_type}</span>
                  <span className="text-muted" style={{ fontSize: "0.75rem" }}>
                    {Math.round(c.assignment_confidence * 100)}%
                  </span>
                </label>
              ))}
              <button className="btn secondary" onClick={confirm} disabled={busy} style={{ marginTop: 6 }}>
                Markierten Kandidaten bestätigen
              </button>
            </div>
          )}

          <img
            src={api.documents.fieldCropUrl(documentId, field.field_key)}
            alt={`Ausschnitt ${field.label}`}
            style={{ display: "block", marginTop: 12, maxWidth: "100%", border: "1px solid var(--petrol-line)", borderRadius: 6 }}
            onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
          />

          <form onSubmit={correct} className="flex-row" style={{ marginTop: 12 }}>
            <input
              placeholder="Richtigen Wert eintragen…"
              value={correctValue}
              onChange={(e) => setCorrectValue(e.target.value)}
            />
            <button className="btn secondary" type="submit" disabled={busy}>Korrigieren</button>
          </form>
        </>
      )}
    </div>
  );
}
