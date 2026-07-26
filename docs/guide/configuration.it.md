---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/configuration.md"
translation_source_sha256: "39f85a86f94a3b326e9d3b9a74e9452a379a4745667b57c124c9512bfd1d9755"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="configuration" data-pplx-source-anchor="true"></a>
# Configurazione

pplx-export conserva i tuoi dati di identità — il registro degli account (nomi visualizzati, email di accesso, ID utente) e lo spazio BOT — in un file TOML a livello utente che risiede al di fuori del repository. Questa pagina copre dove si trova quel file, ogni campo che accetta, cosa succede quando manca e come il registro gestisce la gestione dei cookie multi-account.

<a id="why-the-config-lives-outside-the-repo" data-pplx-source-anchor="true"></a>
## Perché la configurazione risiede fuori dal repository

Il registro degli account e lo spazio BOT sono dati personali e **non vengono mai committati** nel repository (`pplx_export/config.py:7-12`). Il repository fornisce solo un template segnaposto, `config.example.toml`; i tuoi valori reali vanno in una copia privata. Tutto il resto di cui lo strumento ha bisogno — il dominio del sito, gli URL delle API, la radice dell'archivio predefinita — è una costante del codice (`pplx_export/config.py:50-58`), non una configurazione utente.

Il TOML contiene solo dati di identità. La selezione della fonte dei cookie e del trasporto sono flag CLI per invocazione, non campi di configurazione — vedi [Flag CLI, non campi di configurazione](#cli-flags-not-config-fields) più sotto.

<a id="location-and-load-priority" data-pplx-source-anchor="true"></a>
## Posizione e priorità di caricamento

`configure()` (`pplx_export/config.py:113`) risolve il percorso di configurazione con questa precedenza (`pplx_export/config.py:95-110`):

| Priorità | Fonte | Conta come esplicito |
|---|---|---|
| 1 | Flag CLI `--config PATH` | sì |
| 2 | Variabile d'ambiente `PPLX_EXPORT_CONFIG` | sì |
| 3 | `~/.config/pplx-export/config.toml` (percorso predefinito) | no |

"Esplicito" è rilevante per il comportamento di errore quando il file manca — vedi [modalità degradata](#missing-config-degraded-mode). Entrambe le voci CLI ricaricano la configurazione in modalità rigorosa dopo l'analisi degli argomenti (`pplx_export/cli.py:223`, `pplx_export/ask_cli.py:278`); il caricamento al momento dell'importazione (`pplx_export/config.py:174-179`) è tollerante ai guasti, quindi importare il pacchetto non fallisce mai su un file mancante.

<a id="creating-your-config" data-pplx-source-anchor="true"></a>
## Creare la tua configurazione

!!! tip "Alternativa automatica"
    `pplx-export init` può generare questo file automaticamente — scopre gli account con accesso dai cookie del tuo browser e scrive il TOML con permessi 0600. Vedi [pplx-export → init](pplx-export.md#init).

```bash
mkdir -p ~/.config/pplx-export
cp config.example.toml ~/.config/pplx-export/config.toml
chmod 600 ~/.config/pplx-export/config.toml
```

Poi modifica la copia. Il template usa segnaposto puri — copia la struttura, sostituisci ogni valore:

```toml
# Default account used when --account is not given (a key of [accounts.<name>] below)
default_account = "alice"

# Account registry: key = account username (the username in thread URLs / library)
[accounts.alice]
# Full display name: used for archive directory naming (web_archive/<display name>/…)
display_name = "Alice Example"
# Login email: verifies cookie ownership
email = "alice@example.com"
# Account uid (required for thread-viewed telemetry)
user_id = "00000000-0000-4000-8000-0000000000aa"

[accounts.bob]
display_name = "Bob Example"
email = "bob@example.com"
user_id = "00000000-0000-4000-8000-0000000000bb"

# BOT space: where threads created by pplx-ask are collected after completion
[bot_space]
uuid = "00000000-0000-4000-8000-0000000000b0"
slug = "bot-EXAMPLE"
```

Stile segnaposto: `alice`/`bob` sono nomi utente fittizi, le email usano `example.com` e gli UUID usano la forma `00000000-0000-4000-8000-…` con tutti zeri. Nel tuo file reale la chiave della tabella **deve essere il nome utente effettivo dell'account** così come appare negli URL dei thread e nella tua libreria.

!!! warning "Mantienilo privato"
    La configurazione reale contiene dati personali (email, ID utente). Il permesso raccomandato è `0o600`; non committarlo mai in alcun repository git (`config.example.toml:4-6`).

<a id="field-reference" data-pplx-source-anchor="true"></a>
## Riferimento dei campi

<a id="top-level" data-pplx-source-anchor="true"></a>
### Livello superiore

| Campo | Tipo | Significato |
|---|---|---|
| `default_account` | stringa | Chiave di una tabella `[accounts.<name>]`, usata quando `--account` non è fornito (`pplx_export/commands/common.py:84-85`). Vuoto/mancante = modalità degradata. |

### `[accounts.<name>]`

Una tabella per account; `<name>` è il nome utente dell'account. Il registro viene caricato in tre dizionari chiave per nome utente: `ACCOUNT_DISPLAY_NAMES`, `ACCOUNT_EMAIL`, `ACCOUNT_UID` (`pplx_export/config.py:65-75`).

| Campo | Tipo | Obbligatorio | Significato |
|---|---|---|---|
| `display_name` | stringa | no | Nome visualizzato completo, usato per la denominazione delle directory dell'archivio (`web_archive/<display name>/…`); ricade al nome utente quando omesso. Vedi [Struttura dell'archivio](archive-layout.md). |
| `email` | stringa | raccomandato | Email di accesso. Il trasporto verifica la proprietà del cookie rispetto ad essa, prevenendo "un'esportazione per l'account B che trasporta la sessione dell'account A" (`pplx_export/config.py:69-72`). In caso di mancata corrispondenza, lo strumento enumera i token di sessione per account nel browser e passa automaticamente — vedi [Modello cookie multi-account](#multi-account-cookie-model). |
| `user_id` | stringa | per telemetria `pplx-ask` | UID dell'account, richiesto dalla telemetria di visualizzazione thread (`pplx_export/config.py:73-75`). Leggilo da `GET /api/auth/linked-accounts`, che restituisce `user_id` / `email` / `display_name` di ogni account con accesso — vedi [Autenticazione API](../reference/api/api-authentication.md). |

### `[bot_space]`

Lo spazio BOT è il punto di raccolta per i thread creati da `pplx-ask` dopo il loro completamento (`pplx_export/config.py:76-79`). Crea lo spazio stesso con `pplx-ask space-create` (vedi [pplx-ask](pplx-ask.md)), poi registralo qui.

| Campo | Tipo | Significato |
|---|---|---|
| `uuid` | stringa | UUID dello spazio. `pplx-ask` sposta i thread completati qui (`pplx_export/ask_cli.py:156-158`); quando vuoto, il passaggio di spostamento viene saltato. |
| `slug` | stringa | Slug URL dello spazio. Caricato in `BOT_SPACE_SLUG` (`pplx_export/config.py:79`); la CLI runtime non lo legge — lo strumento di manutenzione delle fixture lo consuma, costruendo una coppia di sostituzione dell'identità da esso (`tests/scrub_fixtures.py:446-447`). |

<a id="cli-flags-not-config-fields" data-pplx-source-anchor="true"></a>
### Flag CLI, non campi di configurazione

Il TOML non ha impostazioni di trasporto o cookie. Queste vengono scelte per invocazione:

| Aspetto | Dove viene impostato |
|---|---|
| Percorso del file di configurazione | `--config PATH`, o `PPLX_EXPORT_CONFIG` |
| Fonte dei cookie | `--cookies-from BROWSER` / `--cookies FILE` |
| Trasporto | `--transport cookie\|webbridge` (solo `pplx-export`; predefinito `cookie`) |

Vedi [pplx-export](pplx-export.md) per il riferimento completo dei flag.

<a id="missing-config-degraded-mode" data-pplx-source-anchor="true"></a>
## Configurazione mancante: modalità degradata

Quando non viene caricato nulla, i registri a livello di modulo rimangono vuoti e `LOADED_CONFIG_PATH` è `None` (`pplx_export/config.py:83-85`). Comportamento per scenario (`resolve_cli_account`, `pplx_export/commands/common.py:51-90`):

| Scenario | Comportamento |
|---|---|
| Nessuna configurazione nel percorso predefinito, `--account` non fornito | Modalità degradata: viene registrato un avviso e i comandi vengono eseguiti con un account segnaposto (`username='default'`); il controllo di proprietà dell'email viene saltato. I comandi offline quotidiani non sono influenzati (`pplx_export/commands/common.py:86-90`). |
| Nessuna configurazione, `--account` esplicito | `SystemExit` che nomina l'ordine di ricerca e punta a `config.example.toml` (`pplx_export/commands/common.py:67-74`). |
| Configurazione caricata, `--account` non registrato | `SystemExit` che nomina il file caricato, chiedendo di aggiungere `[accounts.<name>]` (`pplx_export/commands/common.py:77-82`). |
| Percorso esplicito (`--config` / variabile d'ambiente) non esiste | `ConfigError` in modalità rigorosa (`pplx_export/config.py:140-146`). |
| Il file esiste ma non può essere analizzato | Sempre `ConfigError` — una configurazione corrotta non deve degradare silenziosamente (`pplx_export/config.py:147-150`). |
| `--account` omesso, configurazione caricata | Viene usato `default_account` (`pplx_export/commands/common.py:84-85`). |

Cosa coprono i "comandi offline" e come le esecuzioni degradate interagiscono con l'archivio è dettagliato in [Operazioni offline](../architecture/offline-operations.md).

<a id="multi-account-cookie-model" data-pplx-source-anchor="true"></a>
## Modello cookie multi-account

Con diversi account con accesso nello stesso browser, l'archivio contiene un cookie di sessione **per account**, e il campo `email` della configurazione dice allo strumento quale gli serve:

- Ogni account con accesso ha un cookie `__Secure-pplx.session.<uid>` (`ACCOUNT_SESSION_PREFIX`, `pplx_export/core/cookies/loaders.py:171`); il suffisso `<uid>` è l'`user_id` dell'account.
- L'account **attivo** è quello il cui token si trova attualmente in `__Secure-next-auth.session-token` (`ACTIVE_SESSION_COOKIE`, `pplx_export/core/cookies/loaders.py:172`). Cambiare account = scrivere il valore del cookie per account dell'account di destinazione in quel cookie — nessuna interfaccia browser necessaria (`pplx_export/core/cookies/loaders.py:180-187`).
- All'avvio, il trasporto sonda `GET https://www.perplexity.ai/api/auth/session` e confronta l'email restituita con `accounts.<name>.email` (`pplx_export/commands/common.py:126-130`).
- In caso di mancata corrispondenza, `_try_switch_account` (`pplx_export/commands/common.py:190-215`) enumera ogni token dell'account nel browser tramite `list_account_tokens` (`pplx_export/core/cookies/loaders.py:175-206`, preferendo le voci sul sottodominio `www.`), prova ciascuno in `__Secure-next-auth.session-token` e ricostruisce il trasporto al primo match.
- Se nessun token corrisponde, il comando termina nominando entrambe le email e chiedendo di effettuare l'accesso dell'account di destinazione nel browser prima (`pplx_export/commands/common.py:142-145`) — vedi [Risoluzione dei problemi](troubleshooting.md).
- Un account senza `email` registrato procede senza controllo, con un avviso che chiede di confermare personalmente l'accesso nel browser (`pplx_export/commands/common.py:146-149`).

Per il flusso completo di cambio e la semantica degli endpoint di sessione, vedi [Ask e account](../architecture/ask-and-accounts.md) e [Autenticazione API](../reference/api/api-authentication.md).

<a id="cookie-cache" data-pplx-source-anchor="true"></a>
## Cache dei cookie

Dopo la convalida riuscita, i cookie risolti vengono memorizzati nella cache in modo che le esecuzioni successive saltino il browser:

| Proprietà | Valore |
|---|---|
| Percorso | `<archive root>/index/.cookies.json` — segue `--out` (`pplx_export/commands/common.py:111`) |
| Freschezza | 12 ore (`CACHE_MAX_AGE_S = 12 * 3600`, `pplx_export/core/cookies/cache.py:22`); una cache obsoleta o corrotta viene trattata come assente |
| Contenuto | `fetched_at`, `source`, `account_email`, `cookies` (`pplx_export/core/cookies/cache.py:62-66`) |
| Scrittura | Atomica: file temporaneo creato con modalità `0o600`, poi `os.replace` (`pplx_export/core/cookies/cache.py:49-67`) |
| Git | Coperto da `.gitignore` (`**/index/.cookies.json`) |

Ordine di risoluzione dei cookie (`cookies.resolve`, `pplx_export/core/cookies/loaders.py:270-302`): `--cookies-from` esplicito → file `--cookies` esplicito → cache fresca → rilevamento automatico dei browser (edge → chrome → firefox → safari). La cache viene aggiornata dopo ogni convalida dell'account riuscita (`pplx_export/commands/common.py:150`).

<a id="protecting-your-files" data-pplx-source-anchor="true"></a>
## Proteggere i tuoi file

- `chmod 600` il tuo `config.toml` — contiene dati personali (email, ID utente).
- La cache dei cookie viene già scritta con modalità `0o600` dallo strumento; i cookie di sessione sono credenziali equivalenti all'accesso.
- Se crei manualmente un file di cookie per `--cookies`, applica anche `chmod 600` ad esso.

<a id="when-authentication-fails" data-pplx-source-anchor="true"></a>
## Quando l'autenticazione fallisce

Cookie scaduti, un account che il cambio automatico non trova, errori di permesso del portachiavi del browser e altri fallimenti di autenticazione sono coperti in [Risoluzione dei problemi](troubleshooting.md).
