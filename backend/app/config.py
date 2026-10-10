import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

UPLOADS_DIR = DATA_DIR / "uploads"
UPLOADS_DIR.mkdir(exist_ok=True)

DATABASE_PATH = DATA_DIR / "nauteron.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Modelle: das "grosse" Modell führt die eigentlichen Gespräche,
# das "kleine" Modell übernimmt günstige Nebenaufgaben wie die
# automatische Kategorie-Zuordnung.
CHAT_MODEL = os.environ.get("NAUTERON_CHAT_MODEL", "claude-sonnet-5-5")
CLASSIFY_MODEL = os.environ.get("NAUTERON_CLASSIFY_MODEL", "claude-haiku-5-5")

# Wie viele vorherige Nachrichten eines Agenten-Gesprächs werden bei
# einer neuen Anfrage automatisch mitgeschickt (kurzes Gedächtnis).
# Die komplette Historie bleibt lokal gespeichert und durchsuchbar,
# wird aber NICHT automatisch komplett an die API gesendet.
RECENT_MESSAGES_WINDOW = int(os.environ.get("NAUTERON_RECENT_WINDOW", "20"))
