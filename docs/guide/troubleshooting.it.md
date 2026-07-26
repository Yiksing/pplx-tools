---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/troubleshooting.md"
translation_source_sha256: "6eb13cb35b2da72789c46ad4bf63ba5a3ab0eca92581d51589ad8181748be600"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="troubleshooting" data-pplx-source-anchor="true"></a>
# Risoluzione dei problemi

Formato FAQ: ogni voce è **problema → causa → soluzione**. Per il riferimento completo sulla semantica degli errori (codici di stato, stati terminali, disciplina dei tentativi) consulta [Risposte ed errori](../reference/api/api-responses-errors.md) e [Limitazione della frequenza ed errori](../architecture/rate-limiting-errors.md).

<a id="bare-requests-to-the-api-get-a-cloudflare-403" data-pplx-source-anchor="true"></a>
## Richieste dirette all'API ottengono un Cloudflare 403

**Problema**: uno script `curl` / script personalizzato contro gli endpoint REST `www.perplexity.ai` restituisce 403 con una pagina di sfida Cloudflare — anche con i cookie copiati dal browser — mentre gli stessi endpoint funzionano tramite lo strumento.

**Causa**: Cloudflare si trova davanti al sito, e `cf_clearance` / `__cf_bm` sono legati all'impronta TLS del browser. L'impronta di un client semplice non corrisponde, quindi la sfida scatta. Lo strumento funziona perché usa Python `urllib` con cookie importati dal browser e un `User-Agent` desktop-Chrome (`pplx_export/core/http/cookie_transport.py:29`). Cloudflare può anche restituire 403 sotto controllo della frequenza — in tal caso la risposta ha la stessa forma di sfida.

**Soluzione**:

- Non bypassare il trasporto dello strumento; esegui la chiamata tramite `pplx-export` / `pplx-ask` invece di script ad-hoc.
- All'interno dello strumento, una risposta 200 con un corpo non JSON (l'interstiziale Cloudflare) è classificata come errore di trasporto, non dato (`pplx_export/core/http/cookie_transport.py:133`).
- Se i 403 iniziano ad apparire all'interno dello strumento, rallenta (vedi [Limitazione della frequenza](rate-limiting.md)) e aggiorna i cookie; una sfida persistente significa rieffettuare il login nel browser.
- Tieni presente i due volti del 403: una sfida di controllo del rischio Cloudflare (si risolve rallentando) rispetto a un 403 a livello API (cookie scaduto — sollevato immediatamente senza backoff; vedi la sezione successiva). La pagina di progettazione mappa quest'ultimo ([rate-limiting-errors.md](../architecture/rate-limiting-errors.md)).

Contesto: [Autenticazione API](../reference/api/api-authentication.md).

<a id="401-errors-expired-cookies" data-pplx-source-anchor="true"></a>
## Errori 401 / cookie scaduti

**Problema**: i comandi falliscono con un errore di autenticazione — `AuthTransportError: 鉴权失败 401` da `pplx-export`, o `pplx-ask ask` esce con un suggerimento HTTP 401/403 di aggiornare il cookie.

**Causa**: il cookie di sessione è scaduto o è stato invalidato. `401`/`403` sono trattati come fallimenti di autenticazione e sollevati immediatamente — nessun backoff, perché il backoff non può auto-riparare una sessione morta (`pplx_export/core/http/cookie_transport.py:82`; `pplx_export/core/errors.py:68`). `batch` inoltre fallisce rapidamente dopo 3 fallimenti di autenticazione consecutivi in modo che un cookie morto non consumi l'intera coda.

**Soluzione**:

1. Rieffettua il login (o riapri il sito) nel browser in modo che i cookie di sessione vengano rinnovati.
2. Aggiorna la cache dei cookie dello strumento. La cache in `<out>/index/.cookies.json` viene riutilizzata entro una finestra di freschezza di 12 ore (`pplx_export/core/cookies/cache.py:22`), quindi dopo il rieffettuato login:
   - esegui una volta con `--cookies-from <browser>` per forzare una nuova importazione dal browser, oppure
   - elimina `<out>/index/.cookies.json` e lascia che la prossima esecuzione reimporti automaticamente.
3. Ogni esecuzione che viene convalidata con successo salva nuovamente la cache (`pplx_export/commands/common.py:150`), quindi le esecuzioni quotidiane rimangono fresche da sole.

Dettagli di configurazione: [Per iniziare](getting-started.md) · [Configurazione](configuration.md).

<a id="linux-cookie-decryption" data-pplx-source-anchor="true"></a>
## Decifratura dei cookie su Linux

**Problema**: su Linux, il rilevamento automatico (o `--cookies-from chrome` & co.) non riesce a leggere il deposito dei cookie del browser anche se il browser ha effettuato l'accesso.

**Meccanismo**: i browser della famiglia Chromium su Linux crittografano il database dei cookie con una chiave conservata nel portachiavi del sistema operativo, letta in fase di esecuzione tramite l'API Secret Service D-Bus. `browser_cookie3` parla D-Bus tramite `jeepney` puro Python — già installato con lo strumento su Linux, niente altro da configurare — e ricade sulla password legacy `peanuts` quando nessun portachiavi risponde, che decifra solo i cookie che Chrome ha anche scritto senza un portachiavi. Quando il portachiavi esiste ma la ricerca D-Bus stessa fallisce a livello di trasporto (ad es. un bus di sessione che rifiuta l'autenticazione anonima), la catena di fallback di `browser_cookie3` non si attiva mai; lo strumento rileva quel caso e riprova una volta bypassando il portachiavi, usando la password predefinita di Chromium — la stessa chiave che Chromium stesso usa quando nessun portachiavi è disponibile (`pplx_export/core/cookies/loaders.py:62-104`, collegata nel percorso di caricamento in `loaders.py:136-153`). Firefox non necessita di tutto questo: il suo `cookies.sqlite` non è crittografato.

**La matrice**:

| Livello | Caso | Cosa succede |
|---|---|---|
| Browser | Firefox | Zero attrito — `cookies.sqlite` non è crittografato |
| Browser | Chromium + portachiavi raggiungibile | Funziona — la chiave viene recuperata tramite Secret Service |
| Browser | Chromium + nessun portachiavi | Percorso `peanuts` — funziona solo se Chrome ha anche scritto senza un portachiavi |
| Browser | Chromium + portachiavi irraggiungibile (fallimento a livello D-Bus) | Lo strumento riprova automaticamente con la password predefinita di Chromium — stessa portata del percorso `peanuts` |
| Metodo di installazione | Pacchetto nativo | Rilevato automaticamente (percorsi integrati di browser_cookie3) |
| Metodo di installazione | snap / flatpak | Rilevato automaticamente — il registro dei profili integrato copre i profili sotto `~/snap/<name>/...` risp. `~/.var/app/<app-id>/...` (`pplx_export/core/cookies/profiles.py:37-67`) |
| Ambiente desktop | GNOME | Di solito funziona subito (gnome-keyring) |
| Ambiente desktop | KDE | Abilita **Usa KWallet per l'interfaccia Secret Service** nelle impostazioni di KWallet |
| Ambiente desktop | Headless / minimale | Nessun bus di sessione D-Bus → percorso `peanuts` |
| Famiglia di distribuzioni | Debian / Ubuntu | Installa `libsecret-1-0` + `gnome-keyring` |
| Famiglia di distribuzioni | Fedora / RHEL | Installa `libsecret` + `gnome-keyring`; le installazioni minime/server spesso mancano completamente di un portachiavi — il fallimento più comune |
| Famiglia di distribuzioni | Arch | Stesso meccanismo, solo i nomi dei pacchetti differiscono |

Le installazioni in sandbox non necessitano di flag extra: il percorso nativo viene sondato per primo, poi i database dei cookie snap/flatpak del registro tramite un `cookie_file=` esplicito (`pplx_export/core/cookies/loaders.py:155-168`).

**Scenario → canale consigliato**:

| Scenario | Canale consigliato |
|---|---|
| Firefox installato | `--cookies-from firefox` — zero attrito |
| Desktop GNOME / KDE | Il rilevamento automatico funziona |
| Browser snap / flatpak | Rilevamento automatico — il registro lo copre; altrimenti `--cookies FILE` esportato tramite un'estensione del browser |
| Server headless | `--cookies FILE` — il fallback universale; `--transport webbridge` come ultima risorsa |

<a id="an-export-ran-under-the-wrong-account-multi-account" data-pplx-source-anchor="true"></a>
## Un'esportazione è stata eseguita con l'account sbagliato (multi-account)

**Problema**: i thread archiviati sono stati recuperati con la sessione dell'account sbagliato — ad es. un'esecuzione di `--account alice` ha recuperato dati come `bob`, o l'archivio mostra thread che non appartengono all'account previsto.

**Causa**: con diversi account collegati allo stesso browser, il token di sessione attivo (`__Secure-next-auth.session-token`) può appartenere a un account diverso da quello che hai preso di mira. Se `email` dell'account target non è registrato nella configurazione a livello utente, lo strumento non può rilevarlo e registra solo un avviso.

**Come lo strumento lo previene** (`pplx_export/commands/common.py:93`): all'avvio il trasporto chiama `GET /api/auth/session` e confronta l'email live con quella registrata. In caso di mancata corrispondenza, enumera automaticamente i cookie di sessione per account del browser (`__Secure-pplx.session.<user_id>`), sostituisce ciascuno nel token attivo e sonda la sessione fino a quando l'email target corrisponde (`pplx_export/commands/common.py:190`; `pplx_export/core/cookies/loaders.py:175`). Se nessun token corrisponde, il comando si interrompe con un errore chiaro — non procede mai silenziosamente con l'account sbagliato.

**Soluzione**:

- Registra `email` di ogni account sotto `[accounts.<name>]` (vedi [Configurazione](configuration.md)) e passa `--account` esplicitamente.
- Controlla la riga di log di avvio `[auth] cookie 来源 …，当前账户: …` — nomina l'email della sessione live prima che venga recuperato qualsiasi dato.
- Per verificare un archivio esistente, ogni `thread.json` del thread porta un campo `export_via` che registra quale account ha eseguito l'esportazione (`pplx_export/sites/perplexity/fs_writer.py:229`). `pplx-export sync-deleted` usa lo stesso campo per selezionare l'account per la verifica online.

Approfondimento del meccanismo: [Autenticazione API](../reference/api/api-authentication.md) · [Ask e account](../architecture/ask-and-accounts.md).

<a id="config-file-not-found-degraded-mode" data-pplx-source-anchor="true"></a>
## "File di configurazione non trovato" — modalità degradata

**Problema**: un avviso di avvio dice che non è stato trovato alcun file di configurazione a livello utente e il comando viene eseguito in modalità degradata; oppure un `--account alice` esplicito fallisce con un errore che punta a `config.example.toml`.

**Causa**: nessun file di configurazione in nessuna delle tre posizioni di ricerca — `--config PATH`, la variabile d'ambiente `PPLX_EXPORT_CONFIG`, o il valore predefinito `~/.config/pplx-export/config.toml` (`pplx_export/config.py:113`). Due casi correlati ma distinti: un **percorso di configurazione specificato esplicitamente** che non esiste solleva `ConfigError`; una configurazione corrotta (non analizzabile) solleva sempre `ConfigError` — una configurazione danneggiata non degrada mai silenziosamente.

**Effetti della modalità degradata**:

- Il registro degli account è vuoto, quindi la verifica della proprietà del cookie viene saltata con un avviso e i comandi vengono eseguiti come account segnaposto `default` (`pplx_export/commands/common.py:51`). Un `--account` esplicito invece genera un errore.
- `pplx-ask ask` salta lo spostamento automatico nello spazio BOT (`moved_to_bot` rimane `false` nel JSON del risultato) e la telemetria trasporta un ID utente vuoto; chiedere e archiviare funzionano comunque.
- Gli archivi finiscono nella cartella dell'account di fallback derivata dal nome utente.

**Soluzione**: copia `config.example.toml` in `~/.config/pplx-export/config.toml`, compila `[accounts.<name>]` (`display_name` / `email` / `user_id`), `[bot_space]` e `default_account` — vedi [Configurazione](configuration.md).

## ENTRY_EXPIRED vs ENTRY_DELETED

**Problema**: l'esportazione o la risincronizzazione di un thread segnala `ENTRY_EXPIRED` o `ENTRY_DELETED` e il thread non può più essere recuperato.

**Causa**: entrambi arrivano come HTTP 400 da `GET /rest/thread/<uuid>` con codici di errore diversi, ed entrambi sono terminali — il thread non esiste più sulla piattaforma:

| Codice | Significato | Mappatura nello strumento | Stato terminale |
|---|---|---|---|
| `ENTRY_EXPIRED` | La piattaforma ha eliminato il thread (~3 mesi di conservazione) | `EntryExpiredError` (`pplx_export/core/errors.py:24`) | `expired` |
| `ENTRY_DELETED` | Il thread è stato eliminato attivamente dall'utente / lato remoto (l'effetto a valle di `DELETE /rest/thread/delete_thread_by_entry_uuid`) | `EntryDeletedError`, una sottoclasse di `EntryExpiredError` (`pplx_export/core/errors.py:30`) | `deleted` |

**Cosa significa per il tuo archivio**:

- Nessuno dei due stati viene mai ritentato — né dalla sincronizzazione incrementale, né con `--force`. Il segno terminale vive in `<out>/index/batch_state.json`.
- Il tuo **archivio locale non viene mai eliminato o spostato** dallo strumento — la copia nel repository è il backup. Il comando di esportazione registra lo stato terminale ed esce correttamente (`pplx_export/commands/export_cmd.py:51`).
- Poiché la relazione di sottoclasse è deliberata, i percorsi di codice che conoscono solo `EntryExpiredError` trattano comunque `ENTRY_DELETED` come terminale; i percorsi consapevoli (batch / export / sync-deleted / search-mode-backfill) lo classificano precisamente come `deleted`.
- Consiglio pratico: esporta tempestivamente. Oltre la cancellazione di ~3 mesi, anche i collegamenti alle fonti di artefatti/report scadono irrecuperabilmente.

Correlati: [Sincronizzazione incrementale](incremental-sync.md) · [Risposte ed errori](../reference/api/api-responses-errors.md).

<a id="assets-that-cannot-be-downloaded-toolu_-handles" data-pplx-source-anchor="true"></a>
## Asset che non possono essere scaricati (gestione `toolu_`)

**Problema**: alcune voci in `assets/assets_manifest.json` hanno versioni contrassegnate `"no_download_channel": true` e nessun file corrispondente esiste sotto `assets/files/`.

**Causa**: gli handle dell'area di lavoro cloud con prefisso `toolu_` (DOC_FILE / CODE_FILE / UNKNOWN senza un URL) non hanno un canale di download API: `GET /rest/assets/<asset_uuid>/data` restituisce 404 `ASSET_NOT_FOUND` per loro, e `file-repository/download` rifiuta handle `file:repo/...` (400). Questo è un **confine noto di completezza dell'archivio**, non un bug nell'esportazione. `pplx-export assets-backfill` contrassegna queste versioni `no_download_channel` e le salta (`pplx_export/commands/assets_backfill_cmd.py:356`).

**Soluzione**:

- Niente da scaricare oggi — il flag è il record deliberato del confine.
- Il contenuto spesso sopravvive in linea: il testo di estrazione della pagina del sottoagente e i payload dei passaggi sono conservati nel JSON grezzo del thread (`raw_entries.json` / `raw_blocks.json`) e nel `turns/` renderizzato — controlla lì prima.
- `file-repository/list-files` è tracciato come un potenziale percorso di recupero futuro; vedi [Roadmap di scoperta API](../reference/api/api-discovery-roadmap.md).

Struttura del manifest: [Struttura dell'archivio](archive-layout.md).

<a id="where-are-the-logs" data-pplx-source-anchor="true"></a>
## Dove sono i log?

**Console**: progresso a livello INFO per impostazione predefinita; `-v` / `--verbose` passa a DEBUG (tracciamento delle richieste, decisioni interne); avvisi ed errori sono sempre mostrati.

**File**: passa `--log-file` per catturare il flusso DEBUG completo (`pplx_export/core/logging.py:45`):

- `--log-file` senza un valore finisce in `<out>/index/logs/<cmd>-<timestamp>.log` (`pplx_export/commands/common.py:218`) — ad es. `pplx-ask-ask-20260723-120000.log`.
- `--log-file PATH` scrive nel percorso specificato.

**Altri file di stato utili per la diagnosi** (sotto `<out>/index/`):

| File | Contenuto |
|---|---|
| `.cookies.json` | Cache dei cookie (freschezza 12 ore; scritta atomicamente con 0o600 — è una credenziale equivalente al login, mantienila privata) |
| `batch_state.json` | Stato di esportazione per thread, inclusi i segni terminali `expired` / `deleted` |
| `answer_variants_log.jsonl` | Registro delle varianti di riscrittura delle risposte |
| `library_*.json` | Istantanee dell'indice della libreria per account |

<a id="see-also" data-pplx-source-anchor="true"></a>
## Vedi anche

- [Per iniziare](getting-started.md) — configurazione iniziale e importazione dei cookie
- [Configurazione](configuration.md) — account, spazio BOT, modalità degradata
- [pplx-ask](pplx-ask.md) — la CLI di interrogazione interattiva
- [pplx-export](pplx-export.md) — la CLI di archiviazione
- [Limitazione della frequenza](rate-limiting.md) — disciplina di pacing e backoff
