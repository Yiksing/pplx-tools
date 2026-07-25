---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/getting-started.md"
translation_source_sha256: "d98ba1f32b1e75bff7b3d51ef17e833417ecaf283996152cfa3342455b6eca7a"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="getting-started" data-pplx-source-anchor="true"></a>
# Per iniziare

Da un checkout fresco al primo archivio locale: installare i due comandi, creare la
configurazione a livello utente, scegliere un canale di cookie e seguire una prima esportazione.

<a id="requirements" data-pplx-source-anchor="true"></a>
## Requisiti

- **Python ≥ 3.11**
- **[uv](https://docs.astral.sh/uv/)** — utilizzato per installare gli strumenti ed eseguire la suite di test
- **Un browser desktop con accesso a Perplexity** — gli strumenti riutilizzano i suoi cookie di sessione;
  nessun token viene mai memorizzato nella configurazione

La decifratura dei cookie utilizza `browser_cookie3`. Il rilevamento automatico copre Edge, Chrome, Firefox e
Safari; Brave, Chromium, Opera e Vivaldi funzionano tramite `--cookies-from`.

<a id="install" data-pplx-source-anchor="true"></a>
## Installazione

Nessun clone necessario — installare direttamente dall'URL git:

```bash
uv tool install git+https://github.com/Yiksing/pplx-tools.git
# PyPI-mirror alternative (e.g. mainland China):
# uv tool install --index-url https://mirrors.aliyun.com/pypi/simple git+https://github.com/Yiksing/pplx-tools.git
```

Da un clone locale (radice del repository):

```bash
uv tool install .            # or development mode: uv tool install --editable .
```

Questo installa due comandi: `pplx-export` (archiviazione) e `pplx-ask` (query
interattive). Verificare:

```bash
pplx-export --version
pplx-export --help           # overview with examples; each subcommand has its own --help
pplx-ask --help
```

`uvx --from . pplx-export` esegue un comando una tantum senza installazione.

<a id="create-the-user-level-config" data-pplx-source-anchor="true"></a>
## Creare la configurazione a livello utente

Il registro degli account (nome visualizzato / email / user_id) e lo spazio BOT sono dati
personali e **non vengono committati nel repository**; risiedono in un file TOML esterno.
Template: `config.example.toml` nella radice del repository.

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml   # personal data — keep it owner-only
# edit and fill in your real account values
```

1. Creare la directory di configurazione.
2. Copiare il template nel percorso predefinito.
3. `chmod 600` — il file contiene dati personali; mantenerlo di sola lettura per il proprietario.
4. Compilare `[accounts.<name>]` — la chiave è il nome utente dell'account (come appare negli
   URL dei thread / nella libreria); impostare `display_name`, `email`, `user_id` e scegliere un
   `default_account`.
5. Compilare `[bot_space]` — dove vengono raccolti i thread creati da `pplx-ask` dopo il
   completamento (uno spazio reale può essere creato con `pplx-ask space-create`).

**Alternativa automatica:** `pplx-export init` deriva questo file per te —
enumera i cookie di sessione per account nel tuo browser, interroga
`/api/auth/session` per l'email / nome visualizzato di ogni token, imposta
`default_account` sull'account attualmente attivo, abbina lo spazio BOT per
titolo e scrive il TOML atomicamente con permessi 0600 (un file esistente
viene sovrascritto solo con `--force`).

```bash
pplx-export init                     # discover accounts, write the default config path
pplx-export init --create-bot-space [TITLE]  # create the BOT space when no title matches (custom title optional)
pplx-export init --bot-title TITLE   # match/create a different space title (default BOT)
pplx-export init --config /path/to/config.toml   # write to a custom path
```

Flag: `--force` sovrascrive una configurazione esistente; `--create-bot-space [TITLE]`
crea lo spazio tramite API quando nessun titolo corrisponde (un'operazione di scrittura
sull'account; un TITLE esplicito guida sia l'abbinamento che la creazione); `--bot-title TITLE`
viene utilizzato sia per l'abbinamento che per la creazione. Nota che per
`init` — a differenza di ogni altro comando — `--config` è il percorso di **scrittura**, non
quello di caricamento. Dettagli completi: [pplx-export → init](pplx-export.md#init).

Il riferimento completo dei campi si trova in [Configurazione](configuration.md).

**Priorità di caricamento** (dalla più alta):

| # | Origine |
|---|--------|
| 1 | `--config PATH` |
| 2 | Variabile d'ambiente `PPLX_EXPORT_CONFIG` |
| 3 | `~/.config/pplx-export/config.toml` (predefinito) |

!!! note "Quando la configurazione manca"
    I comandi senza `--account` vengono eseguiti in modalità degradata — il controllo della proprietà dell'email viene
    saltato con un avviso (i comandi offline non sono interessati); un `--account` esplicito
    solleva un errore che punta a `config.example.toml`. Quando `--account` viene omesso,
    viene utilizzato `default_account` dalla configurazione.

<a id="choose-a-cookie-channel" data-pplx-source-anchor="true"></a>
## Scegliere un canale di cookie

Le credenziali provengono dai cookie di sessione di Perplexity del browser locale, letti
tramite `browser_cookie3` — inclusa l'enumerazione dei token multi-account e il passaggio
automatico. Quattro canali:

| Canale | Come | Note |
|---------|-----|-------|
| Rilevamento automatico (predefinito) | nessun flag | cache fresca di 12 ore, poi archivi del browser nell'ordine edge→chrome→firefox→safari |
| Browser nominato | `--cookies-from <browser>` | edge / chrome / firefox / safari / brave … |
| File di cookie | `--cookies /path/to/cookies.txt` | File cookie Netscape o JSON esportato |
| WebBridge | `--transport webbridge` | recupero dal contesto della pagina — il canale di fallback, utilizzato solo quando esplicitamente richiesto |

Su Linux, anche le installazioni di browser snap e flatpak vengono rilevate automaticamente — i loro percorsi
dei profili sono coperti dal registro integrato. La matrice Linux completa (portachiavi, ambienti
desktop, pacchetti della distribuzione):
[Risoluzione dei problemi → Decifratura cookie Linux](troubleshooting.md#linux-cookie-decryption).

```bash
pplx-export export <thread_url>                                 # default: auto-detect browser store
pplx-export export <thread_url> --cookies-from edge             # import from a specific browser
pplx-export export <thread_url> --cookies /path/to/cookies.txt  # use a cookie file
pplx-export export <thread_url> --transport webbridge           # WebBridge page context (explicit fallback)
```

Dopo aver ottenuto i cookie, lo strumento chiama `/api/auth/session` e stampa l'email dell'account
corrente in modo da poter confermare che l'account giusto è in uso — fare attenzione se `--account`
non concorda con l'account del cookie. Il design del trasporto/credenziali è coperto in
[Ask e account](../architecture/ask-and-accounts.md).

<a id="first-run" data-pplx-source-anchor="true"></a>
## Primo avvio

```bash
pplx-export index --account alice     # fetch the library index
pplx-export export <thread_url>       # export a single thread
pplx-export batch --account alice     # batch (incremental early-stop by default; --full for a full sweep)
pplx-export re-render --dry-run       # offline re-render, zero network
```

1. **`index`** recupera l'indice della libreria dell'account — il punto di ingresso su cui `batch` e
   gli altri comandi a livello di account si basano.
2. **`export`** archivia un thread dall'inizio alla fine: conserva le risposte API grezze
   (`raw_*.json`) insieme al Markdown in modo che il rendering possa essere riprodotto offline.
3. **`batch`** esegue una scansione dell'intera libreria. Si ferma presto una volta che tutto il rimanente è
   già archiviato (arresto anticipato incrementale), scrive checkpoint riprendibili e accetta
   `--full` per una scansione completa. Dettagli: [Sincronizzazione incrementale](incremental-sync.md).
4. **`re-render --dry-run`** dimostra il percorso offline: rigenera `conversation.md`
   + `turns/` dai file grezzi locali con zero traffico di rete. Usare `--dry-run` per scrivere i
   risultati. Vedere [Operazioni offline](../architecture/offline-operations.md).

Una volta che funziona, `pplx-ask ask "<prompt>"` esegue una query in streaming e archivia il
thread risultante automaticamente — vedere [pplx-ask](pplx-ask.md).

<a id="where-archives-land" data-pplx-source-anchor="true"></a>
## Dove finiscono gli archivi

Gli archivi vengono scritti in `./web_archive/` per impostazione predefinita (sovrascrivibile con `--out`): una
directory per thread.

| Percorso | Contenuto |
|------|---------|
| `conversation.md`, `turns/` | conversazione renderizzata |
| `thread.json` | metadati del thread + registro delle interruzioni |
| `sources.md` / `sources.json` | citazioni |
| `report.md` | rapporto di deep-research / council / study |
| `assets/` | risorse scaricate (modalità computer) |
| `raw_*.json` | risposte API grezze conservate — gli archivi riusciti possono essere ri-renderizzati offline senza dover recuperare nuovamente |

Il contratto completo della directory: [Struttura dell'archivio](archive-layout.md).

<a id="next-steps" data-pplx-source-anchor="true"></a>
## Passaggi successivi

- Qualcosa è andato storto? → [Risoluzione dei problemi](troubleshooting.md)
- Riferimento comando per comando → [pplx-export](pplx-export.md) ·
  [pplx-ask](pplx-ask.md) · [Comandi di manutenzione](maintenance-commands.md)
- Le cinque modalità di conversazione → [Modalità](modes.md)
