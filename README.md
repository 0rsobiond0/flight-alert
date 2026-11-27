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

## Esecuzione

```bash
PYTHONPATH=src .venv/bin/python -m flight_alert --once --dry-run
```

Il worker usa una fonte pubblica configurata esplicitamente e non esegue bypass di CAPTCHA, Tor, rotazione IP o scraping aggressivo. La prima versione accetta un payload strutturato validato: se non è configurata una fonte compatibile, il ciclo non produce offerte e lo segnala nei log; è preferibile a notificare prezzi non verificabili. L’elenco delle destinazioni è quindi best-effort, non esaustivo.

## Installazione nel LXC

1. Copiare il progetto in `/opt/flight-alert`.
2. Creare l'utente di servizio `flight-alert` e l'ambiente virtuale.
3. Creare `/etc/flight-alert/flight-alert.env` con permessi `0600`, impostando `DRY_RUN=true` per il primo test.
4. Copiare i file `deploy/*.service` e `deploy/*.timer` in `/etc/systemd/system/`.
5. Eseguire `systemctl daemon-reload` e `systemctl start flight-alert.service`.
6. Verificare `journalctl -u flight-alert.service`.
7. Solo dopo la verifica, impostare `DRY_RUN=false` e configurare token/chat Telegram.
8. Abilitare il timer con `systemctl enable --now flight-alert.timer`.

Il database va conservato in `/var/lib/flight-alert/offers.db` e incluso nei backup del container. I prezzi devono sempre essere ricontrollati nel link prima dell'acquisto.
