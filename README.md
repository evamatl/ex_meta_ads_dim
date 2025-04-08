
# Meta Ads Extractor (ex_meta_ads)

Tato komponenta stahuje data z Facebook / Meta reklamních účtů pomocí Marketing API. Podporuje více účtů, automatický refresh access tokenu a plně využívá prostředí Keboola (secrets, environment variables).
Nefunguje na nested dotazy.
---

## 🧠 Hlavní funkce

- ✅ Stahování dat z více Meta Ads účtů
- 🔁 Automatický refresh tokenu každých 40 dní
- 🔐 Uložení tokenu, client_id a client_secret do `token_meta_ads.csv`
- ⚠️ Detekce a čekání při překročení API limitu
- 💾 Výstup do CSV, připravený pro Keboola
- 🌱 Minimální závislosti (`requests` only)

---

## 📁 Struktura projektu

| Soubor / Složka             | Popis                                      |
|-----------------------------|--------------------------------------------|
| `main.py`                   | Hlavní skript komponenty                   |
| `requirements.txt`          | Závislosti (`requests`)                   |
| `.env`                      | Lokální proměnné pro testování             |
| `config.json`               | Počáteční config s klientem a tokenem      |
| `config.schema.json`        | Validace pro UI v Keboola                  |
| `token_meta_ads.csv`        | Persistentní token + client credentials    |
| `/data/out/tables/...`      | Výstupní tabulky pro Keboola               |

---

## 🧪 Lokální spuštění

1. Připrav `.env` soubor:

```env
ACCOUNT_IDS=act_123456789012345,act_987654321098765
FIELDS=id,name,effective_status
FILTERING=[{"field":"effective_status","operator":"IN","value":["ACTIVE"]}]
OUTPUT_FILE=meta_ads_output.csv
FORCE_REFRESH=true
```

2. Připrav `config.json` (jen při prvním běhu):

```json
{
  "parameters": {
    "client_id": "tvuj_client_id",
    "client_secret": "tvuj_client_secret",
    "fb_exchange_token": "krátkodobý_access_token"
  }
}
```

3. Spusť Docker kontejner:

```bash
docker run --rm \
  -v "$(pwd)/data:/data" \
  --env-file .env \
  ex_meta_ads
```

---

## ⚙️ Proměnné (Environment Variables)

| Název             | Popis                                     | Povinné |
|------------------|--------------------------------------------|---------|
| `ACCOUNT_IDS`     | Seznam účtů ve formátu `act_123,...`       | ✅ ano  |
| `FIELDS`          | Pole z Graph API (např. `id,name,status`)  | ✅ ano  |
| `FILTERING`       | JSON pole filtrů (volitelné, default ACTIVE) | ❌ ne   |
| `DAYS_BACK`       | počet dní pro FILTERING                    | ❌ ne   |
| `OUTPUT_FILE`     | Název výstupního CSV                       | ✅ ano  |
| `FORCE_REFRESH`   | `true/false` – vynucený refresh tokenu     | ❌ ne   |

---
V FILTERING můžeš použít "value": "__LAST_N_DAYS__" spolu s proměnnou DAYS_BACK=7, která se při běhu převede na aktuální timestamp.
Např. FILTERING=[{"field":"updated_time","operator":"GREATER_THAN","value":"__LAST_N_DAYS__"}]
----

## 🔐 Token handling

- Při prvním běhu se použije `fb_exchange_token` z `config.json`
- Access token se prodlouží a uloží do `token_meta_ads.csv`
- Každý další běh už token načítá a refreshuje automaticky
- Token se obnoví, pokud je starší než 40 dní (nebo `FORCE_REFRESH=true`)

---

## ✅ Příklady výstupu

```
📦 Účty načtené z proměnné: ['act_123456789012345']
🕒 Token stáří: 42 dní | Zbývá: 0 dní do refreshe
🔁 Token REFRESH proveden (2025-04-07 22:10:01)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📥 ÚČET: act_123456789012345
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📌 Reklama: 2384928374958324
📌 Reklama: 2384928374958325
💾 Výstupní soubor uložen jako: /data/out/tables/meta_ads_output.csv
🎯 Hotovo! Staženo 102 reklam z 1 účtů.
```

---

## 🚫 Omezení

- API limit 200 volání za hodinu na účet – skript čeká automaticky (`code 17`)
- Pouze `access_token`, bez plného OAuth flow
- Nepodporuje nested paging (např. insights → další volání)

---

## 📦 Deployment v Keboola

1. Nahraj skript jako vlastní komponentu
2. Nastav `config.schema.json` pro UI
3. Vlož `token_meta_ads.csv` do `/data/out/tables/`
4. Vytvoř proměnné přes UI nebo Orchestrace (např. `FIELDS`, `ACCOUNT_IDS`)

---

## 🔧 Autoři

- Who: eva.tesarova@cncenter.cz
- When: 4/2025

---

## ✅ Licence

Tato komponenta je open-source. Používej, upravuj, vylepšuj.
```