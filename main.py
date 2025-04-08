import os
import csv
import json
import requests
import time
import logging
from datetime import datetime, timedelta

# Logging config
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logging.info("🚀 Spuštěno")

# === CESTY ===
CONFIG_PATH = '/data/config.json'
TOKEN_PATH = '/data/out/tables/token_meta_ads.csv'
OUTPUT_DIR = '/data/out/tables/'



# === ACCOUNT IDS ===
account_ids_env = os.getenv("ACCOUNT_IDS", "").strip()
if not account_ids_env:
    raise ValueError("❌ Chybí variable ACCOUNT_IDS.")
account_ids = list(set([
    acc.strip() for acc in account_ids_env.split(",")
    if acc.strip().startswith("act_")
]))
if not account_ids:
    raise ValueError("❌ Žádné validní účty s prefixem 'act_'.")
logging.info(f"📦 Účty načtené z proměnné: {account_ids}")


# === TOKEN: načti pouze z token_meta_ads.csv ===
if not os.path.exists(TOKEN_PATH):
    raise ValueError("❌ Soubor token_meta_ads.csv neexistuje – nemám z čeho načíst access token. Získej ho jednorázově přes Graph API ulož do CSV.")

with open(TOKEN_PATH, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    row = next(reader, None)
    if not row:
        raise ValueError("❌ token_meta_ads.csv je prázdný – nelze načíst token.")

    fb_exchange_token = row.get('access_token', '').strip()
    client_id = row.get('client_id', '').strip()
    client_secret = row.get('client_secret', '').strip()
    refreshed_at_str = row.get('refreshed_at', '').strip()

    if not fb_exchange_token or not client_id or not client_secret:
        raise ValueError("❌ Chybí access_token, client_id nebo client_secret v token_meta_ads.csv.")




# === VYHODNOCENÍ PLATNOSTI TOKENU ===
refresh_cutoff_days = 40
force_refresh = os.getenv("FORCE_REFRESH", "").strip().lower() == "true"
should_refresh = True

if refreshed_at_str:
    try:
        refreshed_at_dt = datetime.strptime(refreshed_at_str, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        age_days = (now - refreshed_at_dt).days
        remaining_days = refresh_cutoff_days - age_days
        should_refresh = age_days >= refresh_cutoff_days
        logging.info(f"🕒 Token stáří: {age_days} dní | Zbývá: {max(0, remaining_days)} dní do refreshe")
    except ValueError:
        logging.warning("⚠️ Nevalidní čas v 'refreshed_at' – token bude obnoven.")

if force_refresh:
    logging.info("⚠️ FORCE_REFRESH=true → token bude obnoven bez ohledu na stáří.")
    should_refresh = True

# === FUNKCE NA REFRESH TOKENU ===
def refresh_access_token(client_id, client_secret, fb_exchange_token):
    url = 'https://graph.facebook.com/v17.0/oauth/access_token'
    payload = {
        'grant_type': 'fb_exchange_token',
        'client_id': client_id,
        'client_secret': client_secret,
        'fb_exchange_token': fb_exchange_token
    }
    for attempt in range(3):
        r = requests.get(url, params=payload)
        if r.status_code == 500:
            logging.warning(f"⚠️ Server error při obnově tokenu, pokus {attempt+1}/3. Čekám 10s...")
            time.sleep(10)
            continue
        r.raise_for_status()
        return r.json()['access_token']
    raise Exception("❌ Nepodařilo se obnovit token po 3 pokusech.")

# === PROVEĎ REFRESH TOKENU, POKUD POTŘEBA ===
if should_refresh:
    new_token = refresh_access_token(client_id, client_secret, fb_exchange_token)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with open(TOKEN_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['access_token', 'client_id', 'client_secret', 'refreshed_at'])
        writer.writeheader()
        writer.writerow({
            'access_token': new_token,
            'client_id': client_id,
            'client_secret': client_secret,
            'refreshed_at': now_str
        })
    logging.info(f"🔁 Token REFRESH proveden ({now_str})")
    access_token = new_token
else:
    logging.info("🔐 Token je čerstvý – není třeba obnovovat.")
    access_token = fb_exchange_token

# === FIELDS ===
fields_env = os.getenv("FIELDS", "").strip()
if not fields_env:
    raise ValueError("❌ Chybí variable FIELDS.")
field_string = fields_env
logging.info(f"🔧 Používám FIELDS: {field_string}")

# === FILTERING (dynamický __LAST_N_DAYS__) ===
filtering_env = os.getenv("FILTERING", "").strip()
days_back_env = os.getenv("DAYS_BACK", "").strip()

if filtering_env:
    try:
        parsed_filtering = json.loads(filtering_env)

        if isinstance(parsed_filtering, list):
            # Projdi všechny filtry a nahraď placeholder
            for f in parsed_filtering:
                if f.get("value") == "__LAST_N_DAYS__":
                    if days_back_env.isdigit():
                        days_back = int(days_back_env)
                        cutoff_timestamp = int(time.time()) - days_back * 86400
                        f["value"] = cutoff_timestamp
                        logging.info(f"🔧 Nahrazeno __LAST_N_DAYS__ → timestamp {cutoff_timestamp} ({days_back} dní zpět)")
                    else:
                        raise ValueError("❌ Chybí nebo neplatná proměnná DAYS_BACK (musí být celé číslo).")

            filtering = json.dumps(parsed_filtering, separators=(',', ':'))
            logging.info(f"🔧 Používám dynamický FILTERING: {filtering}")
        else:
            raise ValueError("❌ FILTERING není JSON pole.")

    except json.JSONDecodeError:
        raise ValueError("❌ FILTERING není validní JSON.")
else:
    filtering = ""
    logging.info("🧰 FILTERING není zadán – bude ignorován (žádný filtr nebude aplikován)")



# === OUTPUT FILE ===
output_filename = os.getenv("OUTPUT_FILE")
if not output_filename:
    raise ValueError("❌ Chybí environment variable OUTPUT_FILE.")
output_filename = output_filename.strip()
if not output_filename.endswith(".csv"):
    output_filename += ".csv"
output_path = os.path.join(OUTPUT_DIR, output_filename)

# === STAŽENÍ DAT ===
all_ads = []

for acc in account_ids:
    banner = "━" * 40
    logging.info(banner)
    logging.info(f"📥 ÚČET: {acc}")
    logging.info(f"🔑 Používám access token začínající: {access_token[:10]}...")
    logging.info(banner)

    base_url = f'https://graph.facebook.com/v12.0/{acc}/ads'
    url = base_url
    time.sleep(5)

    while url:
        max_retries = 5
        for attempt in range(max_retries):
            if url == base_url:
                req_params = {
                    'fields': field_string,
                    'limit': 100,
                    'access_token': access_token
                }
                if filtering:
                    req_params['filtering'] = filtering
            else:
                req_params = {}

            r = requests.get(url, params=req_params)

            if r.status_code == 400 and (
                '#80004' in r.text or
                '"code":17' in r.text or
                '"error_subcode":2446079' in r.text
            ):
                logging.warning(f"⚠️ API limit hit na účtu {acc}, pokus {attempt+1}/{max_retries}. Čekám 30s...")
                time.sleep(30)
                continue
            break

        if r.status_code != 200:
            logging.error(f"❌ Chyba při načítání dat z účtu {acc}: {r.text}")
            r.raise_for_status()

        data = r.json()
        for ad in data.get('data', []):
            ad['account_id'] = acc
            all_ads.append(ad)

            ad_id = ad.get('id', 'N/A')
            logging.info(f"📌 Reklama: {ad_id}")



        url = data.get('paging', {}).get('next')

# === PARSOVÁNÍ A UKLÁDÁNÍ ===
rows = []
for ad in all_ads:
    creative = ad.get('creative', {})
    asset_spec = creative.get('asset_feed_spec', {})
    cta_types = asset_spec.get('call_to_action_types', [])
    link_urls = asset_spec.get('link_urls', [])
    website_urls = [url.get('website_url') for url in link_urls if 'website_url' in url]

    rows.append({
        'id': ad.get('id'),
        'created_time': ad.get('created_time', ''),
        'updated_time': ad.get('updated_time', ''),
        'name': ad.get('name', ''),
        'call_to_action_types': ', '.join(cta_types),
        'website_urls': ', '.join(website_urls),
        'effective_status': ad.get('effective_status'),
        'account_id': ad.get('account_id')
    })

# === ULOŽENÍ DO CSV ===
with open(output_path, 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'id', 'created_time', 'updated_time', 'name',
        'call_to_action_types', 'website_urls',
        'effective_status', 'account_id'
    ])
    writer.writeheader()
    for row in rows:
        writer.writerow(row)

logging.info(f"💾 Výstupní soubor uložen jako: {output_path}")
logging.info(f"🎯 Hotovo! Staženo {len(rows)} reklam z {len(account_ids)} účtů.")
