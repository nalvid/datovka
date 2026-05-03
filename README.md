# datovka

Python CLI a knihovna pro práci s českými datovými schránkami (ISDS).

Balíček umí:
- připojit se do testovacího i produkčního prostředí
- vypsat informace o schránce a seznam přijatých zpráv
- stáhnout originální zprávu jako `.zfo`
- vypsat metadata ze ZFO, rozbalit embedded soubory a exportovat tělo zprávy do `txt` nebo `html`

## Instalace

Projekt je určený pro instalaci z GitHub repozitáře, ne z PyPI.

Po naklonování repozitáře:

```bash
python -m pip install .
```

Pro vývojové kontroly:

```bash
python -m pip install -r requirements.txt
```

## Konfigurace

CLI načítá credentials v tomto pořadí:

1. proměnné prostředí `DATOVKA_USERNAME`, `DATOVKA_PASSWORD`
2. soubor zadaný přes `--env-file`
3. automaticky `.env` v aktuálním adresáři

Pokud `.env` neexistuje a nejsou nastavené proměnné prostředí, CLI skončí chybou.

Příklad `.env`:

```env
DATOVKA_USERNAME=your_username
DATOVKA_PASSWORD=your_password
```

Výchozí prostředí je testovací. Produkci zapne `-p` nebo `--production`.

## CLI

```bash
datovka --help
datovka info --env-file .\.env -p
datovka list --days 30 --limit 100 --env-file .\.env -p
datovka download 1686215149 -o downloads --env-file .\.env -p
datovka inspect downloads\message_1686215149.zfo
datovka extract downloads\message_1686215149.zfo -o extracted
```

### Důležité přepínače

| Přepínač | Význam |
|---|---|
| `-p`, `--production` | použije produkční ISDS |
| `--env-file PATH` | načte credentials z konkrétního env souboru |
| `--log-level LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |

### `download` workflow

`download` podporuje navazující práci nad staženým ZFO:

| Přepínač | Význam |
|---|---|
| `--inspect` | po stažení vypíše metadata ze ZFO |
| `--extract` | po stažení rozbalí embedded soubory |
| `--extract-output DIR` | cílový adresář pro `--extract` |
| `--body-format txt|html` | exportuje tělo zprávy |
| `--body-output FILE` | cílový soubor pro export těla |

Příklad:

```bash
datovka download 1686215149 \
  -o downloads \
  --env-file .\.env \
  -p \
  --inspect \
  --extract \
  --extract-output extracted \
  --body-format html \
  --body-output body\message_1686215149.html
```

## ZFO

Stažená zpráva je uložená jako `.zfo`, tedy podepsaný kontejner s XML payloadem a embedded soubory.

Offline příkazy:
- `inspect` vypíše metadata a embedded soubory
- `extract` rozbalí embedded soubory
- `download --body-format txt|html` exportuje tělo zprávy do čitelného formátu

Pro práci se ZFO musí být v systému dostupný `openssl`.

## Použití jako knihovna

```python
from datovka import DatovkaClient

client = DatovkaClient("username", "password", test_env=False)

if client.connect() and client.authenticate():
    info = client.get_databox_info()
    print(info["databox_id"])

    messages = client.get_received_messages(days=30, limit=50)
    for message in messages:
        print(message["message_id"], message["subject"])
```

## Implementační poznámky

Balíček používá oficiální WSDL/XSD přibalené v `datovka/wsdl/` a správné endpointy ISDS:

| Oblast | Endpoint |
|---|---|
| informace o zprávách | `/DS/dx` |
| operace se zprávami | `/DS/dz` |
| informace o přihlášení a schránce | `/DS/DsManage` |

## Vývoj

Smoke test:

```bash
python tests/test_datovka.py
```

Příklady použití jsou v adresáři `examples/`.

## Oficiální zdroje

- https://www.mojedatovaschranka.cz/
- https://info.mojedatovaschranka.cz/info/cs/74.html

## Licence

MIT
