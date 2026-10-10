# Nauteron Cockpit

Ein eigenes, lokal laufendes Interface für dein KI-Agenten-Team — als Ersatz für Slack.
Dieses Dokument erklärt die technischen Entscheidungen in einfacher Sprache und zeigt,
wie du das Grundgerüst auf deinem Laptop startest.

## Die Grundidee der Architektur

Die Anwendung besteht aus zwei Teilen, die beide auf deinem Laptop laufen:

1. **Das Backend** (`backend/`) — ein kleines Python-Programm, das:
   - mit der Anthropic-API spricht (deine sechs Agenten)
   - alles lokal in einer Datenbank-Datei speichert
   - der Weboberfläche die Daten liefert
2. **Das Frontend** (`frontend/`) — die Weboberfläche, die du im Browser siehst
   (auch auf dem Handy).

### Warum diese Werkzeuge?

| Entscheidung | Warum |
|---|---|
| **Python + FastAPI** fürs Backend | Weit verbreitet, gut dokumentiert, einfach um neue Funktionen (Kalender, OCR, CRM, …) zu erweitern. |
| **React** fürs Frontend | Eine Oberfläche für Laptop und Handy, kein separates Handy-Programm nötig. |
| **SQLite** als Datenbank | Eine einzelne Datei auf deiner Festplatte. Kein Datenbank-Server nötig, einfach zu sichern (Backup = Datei kopieren). |
| **Nur Anthropic-API, kein lokales KI-Modell** | Wie gewünscht — dein Laptop muss kein KI-Modell selbst rechnen, das spart Leistung und Akku. |

**Vorteil dieser Wahl:** Alles läuft bei dir, nichts in einer fremden Cloud (außer den
Anfragen an die Anthropic-API selbst). Einfach zu sichern, einfach zu verstehen, leicht
erweiterbar.
**Nachteil:** Du musst zwei Programme starten (Backend und Frontend), bis wir das später
eventuell zu einem einzigen Klick zusammenfassen.

### Wie die Historie gespeichert wird

Jede Unterhaltung mit einem Agenten wird komplett in der Datenbank gespeichert und ist
durchsuchbar. **Wichtig:** Bei einer neuen Nachricht werden nur die letzten ca. 20
Nachrichten des aktuellen Gesprächs automatisch an die KI geschickt — nicht die
komplette Historie. Das hält die laufenden API-Kosten stabil, auch wenn die Historie
mit der Zeit wächst. Die volle Historie kannst du jederzeit über das Suchfeld im
Chat gezielt durchsuchen.

### Zugriff vom Handy

Solange Laptop und Handy im selben WLAN sind: Backend und Frontend sind so eingestellt,
dass sie im Netzwerk erreichbar sind (nicht nur auf dem Laptop selbst). Du rufst dann
im Handy-Browser die lokale Netzwerk-Adresse deines Laptops auf (z.B. `http://192.168.1.23:5173`,
die genaue Adresse zeigt dir Vite beim Start an).

Für Zugriff von unterwegs (außerhalb deines WLANs) empfehlen wir als nächsten
Ausbauschritt **Tailscale** (kostenlos, sehr sicher): Es baut ein privates Netzwerk
zwischen deinen eigenen Geräten auf, ohne dass dein Laptop offen im Internet steht.

## Erstmaliges Einrichten

### Voraussetzungen

- Python 3.11 oder neuer
- Node.js 18 oder neuer
- Ein Anthropic-API-Schlüssel

### Backend einrichten

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Trage in `backend/.env` deinen echten API-Schlüssel ein:

```
ANTHROPIC_API_KEY=sk-ant-...
```

### Frontend einrichten

```bash
cd frontend
npm install
```

## Starten

### Windows: per Doppelklick (einfachster Weg)

Im Hauptordner liegen zwei Dateien:

- **`Setup-Nauteron.bat`** — nur **einmalig** nötig, beim allerersten Mal (oder nach
  einem Neu-Download des Projekts). Richtet Backend und Frontend komplett ein.
  Trag danach, falls noch nicht geschehen, deinen API-Schlüssel in `backend/.env` ein.
- **`Nauteron-Starten.bat`** — damit startest du die Anwendung ab jetzt **jedes Mal**.
  Einfach doppelklicken: Backend und Frontend starten automatisch in zwei Fenstern,
  und der Browser öffnet sich von selbst auf `http://localhost:5173`. Zum Beenden
  reicht es, die beiden schwarzen Fenster zu schließen.

### Eigenes Icon auf dem Desktop

Damit du nicht jedes Mal in den Projektordner navigieren musst, gibt es eine dritte
Datei: **`Desktop-Verknuepfung-erstellen.bat`**. Einmal doppelklicken, und auf deinem
Desktop erscheint eine Verknüpfung namens **"Nauteron"** mit dem Nauteron-"N"-Icon
(`assets/nauteron-icon.ico`) — die kannst du dir z.B. auch an die Windows-Taskleiste
anheften. Ein Doppelklick darauf startet das Cockpit genauso wie `Nauteron-Starten.bat`.

### Manuell (macOS/Linux, oder wenn du lieber selbst tippst)

Zwei Terminal-Fenster:

**Terminal 1 — Backend:**
```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Terminal 2 — Frontend:**
```bash
cd frontend
npm run dev
```

Dann im Browser öffnen: `http://localhost:5173`

Beim ersten Start legt das Backend automatisch die Datenbank an und befüllt sie mit
den sechs Agenten (Heidi, Lukas, Augusta, Thomas, Mathilda, Clara) und den neun
Kategorien.

## Was das Grundgerüst schon kann

- **Cockpit-Startbildschirm**: Weekly Agenda (empfohlene, teils blockierende offene
  Punkte mit Begründung) + Kurzstatus pro Agent (arbeitet / wartet auf dich / fertig).
- **Agenten per Freitext anlegen**, pausieren/aktivieren.
- **Kontaktanfrage-Funktion** für komplexere Agenten-Wünsche — bewusst kein
  automatisierter Self-Service.
- **Freier Chat** pro Agent, mit optional einblendbaren strukturierten Feldern
  (Betreff / gewünschtes Ergebnis).
- **Durchsuchbare Historie**, die nicht automatisch bei jeder Anfrage mitgeschickt wird.
- **Dateien hochladen** und einem Agenten zuordnen; Bilder und PDFs werden direkt im
  Tool angezeigt (mit kostenlosen Browser-Bordmitteln, keine Drittanbieter-Lizenzen).
- **Neun Kategorien**, automatische Zuordnung per günstigem KI-Aufruf (Haiku-Modell),
  manuell korrigierbar, Beschreibungen anpassbar.
- **Sicherheits-Agentin Clara** als sechster, zurückhaltender Agent — ist technisch als
  "eingeschränkt" markiert (`is_restricted`), ihr System-Prompt verbietet ihr
  ausdrücklich, kritische Sicherheitsentscheidungen autonom zu treffen.
- **Ziele & Fortschritt**: Monats-, Jahres- und langfristige Richtungs-Ziele, jeweils
  mit Begründung "warum wichtig"; Rückschau-Bereich für bereits Erreichtes und
  gesparte Zeit.
- **Integrationen-Übersicht** als Platzhalter für die neun geplanten Anbindungs-Kategorien.

## Was als Nächstes sinnvoll ist (gemeinsamer Ausbau)

- Google-Kalender-Anbindung für Thomas (erste echte Integration).
- OCR-Anbindung für eingescannte Dokumente.
- Die Weekly Agenda automatisch durch die Agenten befüllen lassen (aktuell nur über die API anlegbar).
- Clara aktiv Hinweise erzeugen lassen (Update-Check, Backup-Erinnerung, Protokoll
  auffälliger Aktivität) statt nur als Chat-Agentin bereitzustehen.
- Vorschau für Office-Dateien (Decks/Präsentationen) — aktuell werden Bilder und PDFs
  direkt angezeigt, für Decks braucht es noch eine kostenlose Konvertierung.
- Tailscale-Anleitung für Zugriff von unterwegs.
- Ein einziges Start-Skript, das Backend und Frontend zusammen hochfährt.
