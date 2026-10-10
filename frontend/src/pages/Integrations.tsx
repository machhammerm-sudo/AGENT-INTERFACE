const categories = [
  { name: "Kommunikation & Planung", example: "Google-Kalender (Thomas) — als Erstes geplant", status: "geplant" },
  { name: "Dokumentenverarbeitung & Texterkennung", example: "OCR für eingescannte Dokumente — als Erstes geplant", status: "geplant" },
  { name: "Buchhaltung & Finanzen", example: "Rechnungsprogramme, Banking", status: "später" },
  { name: "Kundenverwaltung (CRM)", example: "Kundendaten und Kontakthistorie", status: "später" },
  { name: "Speicher & Dateiablage", example: "Google Drive, Dropbox", status: "später" },
  { name: "Telefonie & Sprachkommunikation", example: "Anrufe tätigen und entgegennehmen", status: "später" },
  { name: "Zahlungsabwicklung", example: "Rechnungen verschicken, Zahlungseingänge prüfen", status: "später" },
  { name: "Physische / Sensor-Daten (IoT)", example: "Maschinen- oder Lagerbestands-Sensoren", status: "später" },
  { name: "Eigene Programmierschnittstelle", example: "Damit externe Systeme auf Nauteron zugreifen können", status: "später" },
];

export default function Integrations() {
  return (
    <div>
      <h1>Integrationen</h1>
      <p className="text-muted" style={{ marginTop: -10 }}>
        Die Integrationsebene ist von Anfang an erweiterbar angelegt. Hier siehst du, welche Art von
        Anbindung in Zukunft dazukommt — aktuell sind das noch Platzhalter.
      </p>
      {categories.map((c) => (
        <div key={c.name} className="card">
          <div className="flex-between">
            <div style={{ fontWeight: 600 }}>{c.name}</div>
            <span className={c.status === "geplant" ? "tag gold-text" : "tag"}>{c.status}</span>
          </div>
          <div className="text-muted" style={{ fontSize: "0.85rem", marginTop: 4 }}>
            {c.example}
          </div>
        </div>
      ))}
    </div>
  );
}
