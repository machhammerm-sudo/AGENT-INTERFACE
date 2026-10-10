"""Erstbefuellung der Datenbank: die sechs Agenten und die neun Kategorien.
Wird beim Start der Anwendung automatisch ausgefuehrt, aber nur wenn die
jeweilige Tabelle noch leer ist - bestehende Daten werden nie ueberschrieben."""

from sqlalchemy.orm import Session

from .models import Agent, AgentStatus, Category

DEFAULT_AGENTS = [
    dict(
        name="Heidi",
        role_title="Organisation & Kommunikation",
        core_task=(
            "Behaelt Termine, Absprachen und interne wie externe Kommunikation im "
            "Blick, bereitet Entscheidungen verstaendlich auf und sorgt dafuer, "
            "dass nichts Wichtiges untergeht."
        ),
        color_accent="blue",
    ),
    dict(
        name="Lukas",
        role_title="Analyse & Strategie",
        core_task=(
            "Wertet Zahlen, Trends und Marktinformationen aus und leitet daraus "
            "strategische Empfehlungen und Prioritaeten ab."
        ),
        color_accent="blue",
    ),
    dict(
        name="Augusta",
        role_title="Prozesse & Effizienz",
        core_task=(
            "Durchleuchtet Ablaeufe im Tagesgeschaeft und schlaegt vor, wie Dinge "
            "einfacher, schneller oder mit weniger Aufwand erledigt werden koennen."
        ),
        color_accent="blue",
    ),
    dict(
        name="Thomas",
        role_title="Technologie & Infrastruktur",
        core_task=(
            "Kuemmert sich um technische Werkzeuge, Anbindungen (z.B. Kalender) "
            "und sorgt dafuer, dass die technische Basis reibungslos funktioniert."
        ),
        color_accent="blue",
    ),
    dict(
        name="Mathilda",
        role_title="Qualitaet & Freigabe",
        core_task=(
            "Prueft Ergebnisse der anderen Agenten auf Qualitaet und Konsistenz, "
            "bevor sie als erledigt gelten, und gibt eine klare Einschaetzung ab."
        ),
        color_accent="blue",
    ),
    dict(
        name="Clara",
        role_title="Sicherheit & Schutz",
        core_task=(
            "Beobachtet laufend Software-Updates, Zugriffsschutz, Datenschutz, "
            "ungewoehnliches Verhalten, Backups und den Schutz vor eingeschleusten "
            "Anweisungen (Prompt Injection). Warnt verstaendlich und mit klarer "
            "Risikoeinschaetzung, trifft aber selbst KEINE kritischen "
            "Sicherheitsentscheidungen - jede riskante Aktion braucht deine "
            "ausdrueckliche Freigabe."
        ),
        color_accent="gold",
        is_restricted=True,
    ),
]

DEFAULT_CATEGORIES = [
    dict(
        key="interne_kommunikation",
        name="Interne Kommunikation",
        description="Abstimmung, Absprachen und Informationsfluss innerhalb des eigenen Teams.",
    ),
    dict(
        key="externe_kommunikation",
        name="Externe Kommunikation",
        description="Austausch mit Partnern, Behoerden, Oeffentlichkeit oder sonstigen Aussenstehenden.",
    ),
    dict(
        key="lead_generierung",
        name="Lead-Generierung",
        description="Neue potenzielle Kundinnen und Kunden finden und ansprechen.",
    ),
    dict(
        key="umsatzgenerierung",
        name="Umsatzgenerierung",
        description="Dinge, die direkt zu Angeboten, Abschluessen oder Einnahmen fuehren.",
    ),
    dict(
        key="selbststrukturierung",
        name="Selbststrukturierung",
        description="Eigene Organisation, Planung und Ordnung im Alltag und im Unternehmen.",
    ),
    dict(
        key="schneller_einfacher",
        name="Schnelleres / einfacheres Arbeiten",
        description="Massnahmen, die bestehende Ablaeufe beschleunigen oder vereinfachen.",
    ),
    dict(
        key="produktentwicklung",
        name="Produktentwicklung",
        description="Weiterentwicklung oder Neugestaltung von Produkten und Leistungen.",
    ),
    dict(
        key="risiko_absicherung",
        name="Risiko / Absicherung",
        description="Absicherung gegen Risiken - rechtlich, finanziell, technisch oder sicherheitsbezogen.",
    ),
    dict(
        key="kundenbeziehung",
        name="Kundenbeziehung / Bestandskunden-Pflege",
        description="Pflege und Staerkung bestehender Kundenbeziehungen.",
    ),
]


def seed_defaults(db: Session) -> None:
    if db.query(Agent).count() == 0:
        for data in DEFAULT_AGENTS:
            agent = Agent(
                **data,
                status=AgentStatus.DONE,
                is_active=True,
                is_builtin=True,
            )
            db.add(agent)

    if db.query(Category).count() == 0:
        for data in DEFAULT_CATEGORIES:
            db.add(Category(**data))

    db.commit()
