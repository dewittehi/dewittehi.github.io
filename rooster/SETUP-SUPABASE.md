# Supabase instellen voor Ziekenhuis Rooster

Deze handleiding legt uit hoe je de gedeelde database opzet zodat alle medewerkers dezelfde data zien.

## Stap 1: Maak een Supabase-project aan

1. Ga naar [supabase.com](https://supabase.com) en maak een gratis account aan
2. Klik op **"New Project"**
3. Kies een naam (bijv. "ziekenhuis-rooster")
4. Kies een database-wachtwoord (bewaar dit goed)
5. Kies **regio: EU West (Frankfurt)** voor data binnen de EU
6. Klik op **"Create new project"** — wacht tot het project klaar is (~2 minuten)

## Stap 2: Maak de database-tabel aan

1. Ga in je Supabase-dashboard naar **SQL Editor** (linker menu)
2. Klik op **"New query"**
3. Plak de volgende SQL en klik op **"Run"**:

```sql
-- Maak de app_data tabel aan
CREATE TABLE app_data (
    key TEXT PRIMARY KEY,
    value JSONB NOT NULL DEFAULT '{}',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Schakel Row Level Security uit (de app gebruikt de anon key)
ALTER TABLE app_data DISABLE ROW LEVEL SECURITY;

-- Schakel Realtime in voor deze tabel
ALTER PUBLICATION supabase_realtime ADD TABLE app_data;
```

4. Je zou moeten zien: "Success. No rows returned" — dat is correct.

## Stap 3: Kopieer je project-URL en Anon Key

1. Ga naar **Settings** → **API** (linker menu)
2. Kopieer de **Project URL** (ziet er uit als `https://xxxxx.supabase.co`)
3. Kopieer de **anon public** key (een lange string die begint met `eyJ...`)

## Stap 4: Verbind de Rooster-app

1. Open de Rooster-app in je browser
2. Je ziet het verbindingsscherm
3. Plak de **Project URL** en **Anon Key**
4. Klik op **"Verbinden"**
5. Als alles goed gaat, zie je het login-scherm

## Stap 5: Deel met collega's

Alle medewerkers moeten dezelfde URL en Key invoeren. Je kunt dit op twee manieren doen:

- **Optie A:** Stuur de URL en Key per e-mail/chat naar je collega's. Zij voeren het eenmalig in bij de eerste keer openen.
- **Optie B:** Voeg de URL en Key vast toe in de HTML (zie hieronder). Dan hoeven collega's niets in te vullen.

### Optie B: URL en Key inbakken in de HTML

Open `roster-app.html` en zoek de regel:

```javascript
const APP_VERSION = '7.0';
```

Voeg daaronder toe:

```javascript
const SUPABASE_URL = 'https://xxxxx.supabase.co';  // jouw URL
const SUPABASE_KEY = 'eyJ...';  // jouw anon key
```

En in de `init()` functie, verander het begin naar:

```javascript
async function init() {
    document.getElementById('app-loading').classList.add('hidden');
    // Auto-connect met ingebakken configuratie
    if (SUPABASE_URL && SUPABASE_KEY) {
        try {
            initSupabaseClient(SUPABASE_URL, SUPABASE_KEY);
            await loadFromSupabase();
            startRealtimeSync();
            updateSyncIndicator();
            document.getElementById('app').classList.remove('hidden');
            showLoginView();
            return;
        } catch(e) { console.warn('Auto-connect failed:', e); }
    }
    // ... rest van de init functie
```

## Veiligheid

- De **anon key** is een publieke sleutel — het is veilig om deze in de HTML te hebben
- De data is echter leesbaar voor iedereen met de key. Voor een interne ziekenhuisapp op een intern domein is dit prima
- Wil je extra beveiliging? Schakel dan Row Level Security in en stel policies in. Zie de [Supabase docs](https://supabase.com/docs/guides/auth/row-level-security)

## Gratis limieten

Het gratis Supabase-plan biedt:
- 500 MB database-opslag
- 5 GB bandbreedte per maand
- 500.000 database-requests per maand
- Realtime: 200 gelijktijdige verbindingen

Dit is ruim voldoende voor een team van ~20 medewerkers.

## Problemen oplossen

**"Verbinding mislukt"**: Controleer of de URL en Key correct zijn, en of de `app_data` tabel is aangemaakt (stap 2).

**Data verschijnt niet bij collega's**: Controleer of iedereen dezelfde URL en Key gebruikt. Ververs de pagina (F5).

**"No rows returned" na SQL**: Dit is normaal — de tabel is aangemaakt maar nog leeg. De app vult automatisch data in bij de eerste verbinding.
