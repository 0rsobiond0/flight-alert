# Flight Alert

Bot Python per cercare offerte voli da Milano (MXP, BGY, LIN) e inviare notifiche Telegram.

## Stato

Il progetto è in sviluppo. La ricerca browser usa Playwright solo su fonti pubbliche consentite; non usa Tor, rotazione IP, bypass CAPTCHA o prenotazioni automatiche.

## Sviluppo locale

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test]'
PYTHONPATH=src .venv/bin/pytest -q
```

Durante i test usare `DRY_RUN=true`. Non inserire token Telegram nel repository.
