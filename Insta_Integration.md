# ERLEDIGT Schritt 1 war das:
- ~/.steamsecrets — Instagram-Credentials (INSTAGRAM_USER, INSTAGRAM_PASS) hinzugefügt. Die Projekt-Root .steamsecrets kann perspektivisch gelöscht werden.
- .gitignore — .steamsecrets, services/instagram_session.json und test.jpg werden jetzt ignoriert.
- services/instagram.py refactored:
- Keine hardcoded Credentials mehr — nutzt config.INSTAGRAM_USER / config.INSTAGRAM_PASS
Lazy Login via _get_client() Singleton — kein Login beim Import, erst beim ersten Aufruf
bere API: upload_photo(image_path, caption) und upload_story(image_path)
Test-Code (bildTest, storyTest, if __name__) entfernt
Logging + Exception-Handling beibehalten
Verifiziert: Config lädt die Credentials korrekt, Import hat keine Seiteneffekte.

- Du kannst jetzt z.B. aus app.py heraus einfach from services.instagram import upload_photo, upload_story nutzen.

# ERLEDIGT Schritt 2 soll:
- Automatische bild erstellung aus Wöchentlicher Rangliste im richtigen Format für Story und Post
- Automatische bild erstellung aus Monatlicher tlicher Rangliste im richtigen Format für Story und Post
- Die möglichkeit, beide Hochzuladen.

# ERLEDIGT Schritt 3 Soll:
- Bei Hochladen von Story/Post von Wöchentlichem oder Monatlichen Ranking automatisch; die richtige Caption bei dem Post einfügen, Ein Instatypischem text über das Storybild packen.
- Post soll alle bilder in einem Post enthalten, momentan jedes bild einzeln für einen post batch

# ERLEDIGT Schritt 4:
- Web-Trigger mit gleichem Auth-Mechanismus wie Snapshot (`SNAPSHOT_TOKEN`) eingebaut.
- Neue Endpunkte:
- `GET /api/instagram/weekly?token=...` (postet Wochen-Carousel + alle Stories)
- `GET /api/instagram/monthly?token=...` (postet Monats-Carousel + alle Stories)
- Response-Verhalten:
- `401` bei fehlendem/falschem Token: `{"error":"unauthorized"}`
- `200` bei Erfolg: Ergebnisobjekt mit `ok`, `period`, `post_uploaded`, `stories_uploaded`, `errors`
- `500` bei technischem Fehler: gleiches Ergebnisobjekt mit `ok=false` und Fehlern
- Upload-Logik zentralisiert in `services/instagram_jobs.py`, damit CLI-Skripte und API denselben Flow nutzen.
- Cron-Beispiele:
- `https://<deine-domain>/api/instagram/weekly?token=<SNAPSHOT_TOKEN>`
- `https://<deine-domain>/api/instagram/monthly?token=<SNAPSHOT_TOKEN>`


# Schritt 5 Soll:
- Lokales Projekt mit dem auf Pythonanywhere angleichen, Cron-Job einrichten.

= Hoffentlich Automatische Instaposts