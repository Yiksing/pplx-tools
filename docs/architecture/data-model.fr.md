---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/data-model.md"
translation_source_sha256: "ebbd890c8e9a8cb69494f0010e99d6d70af5012ad421eb3a62958335a7f25908"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="data-model-and-directory-contract" data-pplx-source-anchor="true"></a>
# Modèle de données et contrat de répertoire

<a id="data-model-coremodelspy" data-pplx-source-anchor="true"></a>
## Modèle de données (core/models.py)

Toutes les données JSON brutes du site sont mappées par les analyseurs dans ces dataclasses ; les composants en aval (render/writer/relations) ne dépendent que de cette couche. `Conversation._blocks/_plain` sont des montures de fidélité des réponses brutes (repr=False).

```mermaid
classDiagram
    class Account {
        +str username
        +str display_name
        +str plan
        +folder (property: display_name or username)
    }
    class Space {
        +str uuid / title / slug / emoji
        +int n_threads
    }
    class Conversation {
        +str web_uuid (web entryUUID)
        +str psc_uuid (platform context_uuid, nullable)
        +str url / title / author / export_via
        +str mode (default search)
        +str last_updated
        +int thread_access
        +list~Turn~ turns
        +list~Citation~ citations (aggregated, deduped by url)
        +list~Asset~ assets
        +Report report
        +dict metadata (thread_metadata verbatim)
        +list~dict~ unconsumed_bgs (attribution waterfall ③ appendix)
        +list~dict~ answer_variants (answer-rewrite variant registration, offline-operations.md)
        +list~SubAgent~ sub_agents (filled by relations offline rebuild, offline-operations.md §15)
        +dict _blocks (schematized fidelity; writer persists raw_blocks.json)
        +dict _plain (plain fidelity; writer persists raw_entries.json)
        +str exported_at
        +n_turns (property)
    }
    class Turn {
        +int index (re-numbered after created_us sort)
        +str uuid / context_uuid / query / author
        +int created_us / updated_us
        +list~Step~ steps (parsed from plain text)
        +str answer (extract_answer)
        +list~Citation~ citations (turn-level dedupe)
        +list~SubAgent~ sub_agents
        +dict wf_block (schematized workflow block, mounted by adapter)
        +list~dict~ stub_wfs (stub-turn-associated background payloads, mounted by parsers)
        +dict metadata (report_info / locked_reason / wf_status, filled by parsers)
    }
    class Step {
        +str step_type (INITIAL_QUERY / FINAL / ASI_TOOL_* / RESEARCH_ANSWER / CODE ...)
        +dict content
        +str timestamp / tool_name / title / icon / step_id
    }
    class SubAgent {
        +str sub_id (workflow_payload.id, toolu_X)
        +str headline / prompt (objective_chunks concatenation)
        +list~Step~ steps / str answer / list~Citation~ sources
        +str status (background-side true workflow status)
        +str locked_reason
    }
    class Citation {
        +str name / url / snippet / timestamp
        +str category (default web)
        +int turn_index
    }
    class Asset {
        +str uuid / asset_type / filename / url
        +str version (default v1) / int n_versions / str created_at
        +bool final / str downloaded_to
    }
    class Report {
        +str title / file_name / url / content_md
    }
    class RelationEdge {
        +str src_uuid / dst_uuid / kind / evidence
    }

    Conversation "1" --> "*" Turn
    Conversation "1" --> "0..1" Report
    Conversation "1" --> "*" Asset
    Conversation "1" --> "0..1" Space
    Turn "1" --> "*" Step
    Turn "1" --> "*" SubAgent
    Turn "1" --> "*" Citation
    SubAgent "1" --> "*" Step
    SubAgent "1" --> "*" Citation
```

Notes de responsabilité (numéros de ligne relatifs à `core/models.py`) :

- **`Turn.wf_block`** (models.py:127) : le bloc de workflow schématisé de computer/council, monté par `parsers.attach_workflow_blocks` par uuid d'entrée (parsers.py:231-256) ; le rendu et le repli de réponse (`_turn_answer`, render.py:489) en dépendent ; writer est en lecture seule.
- **`Turn.stub_wfs`** (models.py:131) : charges utiles d'arrière-plan associées aux tours de résultat de sous-agent via la fenêtre de 10 s (monté par parsers.match_stub_workflows).
- **`Turn.metadata`** (models.py:134) : trois clés — `report_info` (étape RESEARCH_ANSWER, parsers.py:199-204), `locked_reason` (parsers.py:205-208), `wf_status` (parsers.py:256).
- **`Conversation.unconsumed_bgs`** (models.py:165-170) : la source de données du troisième niveau de repli de la cascade d'attribution, `[{wp, locked_reason, updated, bg_uuid}]`, rendue en annexe à la fin de conversation.md.
- **`Conversation.answer_variants`** (models.py:171-177) : enregistrement des variantes de réécriture de réponse (source de données de thread.json.answer_variants) ; `parsers.collect_answer_variants` (parsers.py:589) extrait de `entries[].side_by_side_metadata` avec des critères de restriction — chaîne de détection dans [§18](offline-operations.md).
- **`Conversation.sub_agents`** (models.py:178-182) : liste d'exécution des sous-agents au niveau de la conversation, remplie par `adapter.sub_agents` uniquement lors de la reconstruction hors ligne `cmd_relations` ; le pipeline d'exportation ne remplit pas ce champ (writer rend avec un sub_map local ; relations lit ici) — voir [§15](offline-operations.md).
- **`Conversation._blocks/_plain`** (models.py:183-190) : fidélité de la réponse brute ; `fs_writer` les persiste textuellement sous forme de raw_*.json (fs_writer.py:257-266) ; `get_report/get_assets/sub_agents` and offline re-render all read from them. `PerplexityAdapter(None)` peut être construit avec un transport None pour réutiliser l'assemblage de données pures (rerender_cmd.py:138).
- **Double ID** : `web_uuid` = web entryUUID (URL du thread) ; `psc_uuid` = UUID de la plateforme `past_session_contexts`, pris du premier tour non vide de `context_uuid` (adapter.py:99).

---

<a id="write-boundaries-and-directory-contract" data-pplx-source-anchor="true"></a>
## Limites d'écriture et contrat de répertoire

<a id="the-web_archive-thread-archive-tool-generated-content-files-not-hand-edited" data-pplx-source-anchor="true"></a>
### L'archive de threads web_archive (générée par l'outil ; fichiers de contenu non modifiés manuellement)

```
web_archive/
├── <account display name>/               # author_folder → _safe_folder cleanup
│   │                                     #   (fs_writer.py:40-51; spaces kept, e.g. "Alice Example")
│   ├── <mode>/                           # search | deep-research | computer | council | study
│   │   └── <YYYY-MM-DD>_<title-slug>_<uuid8>/     # thread_dir_for (fs_writer.py:58-72)
│   │       ├── thread.json               # metadata + interruptions / answer_variants (optional keys) + report_info + psc_uuid
│   │       ├── conversation.md           # compact: per-turn Query/Answer + background appendix (render.py:641)
│   │       ├── turns/turn_NNNN.md        # full: complete work-process detail (render.py:596)
│   │       ├── sources.json / sources.md # thread-wide citations (deduped by url)
│   │       ├── report.md                 # deep-research report (exists only when there is one)
│   │       ├── raw_entries.json          # plain response fidelity (always present)
│   │       ├── raw_blocks.json           # schematized fidelity (absent for search)
│   │       └── assets/
│   │           ├── assets_manifest.json  # versioned manifest (uuid/type/version/destination)
│   │           └── files/                # downloaded bodies (resolve_ext decides extensions)
│   └── ...
├── index/                                # state and indexes (see 14.2)
├── relations/                            # edges.jsonl + graph.md (rebuilt by the relations command)
├── crosscheck/                           # cross-validation reports (manual/review artifacts)
└── <account 2>/ ...
```

<a id="web_archiveindex-state-files-tool-managed-do-not-hand-edit" data-pplx-source-anchor="true"></a>
### Fichiers d'état web_archive/index/ (gérés par l'outil, ne pas modifier manuellement)

| Fichier | Writer | Sémantique |
|---|---|---|
| `library_<account>.json` | `cmd_index` (index_cmd.py) | index des threads du compte (GraphQL) ; fusion incrémentale par défaut (`--full` réécrit) ; contient également `last_full_index_at` / `incremental_runs_since_full` ; entrée pour les index batch/planification/espace |
| `batch_state.json` | `BatchState` (state.py) | point de contrôle : uuid → statut (ok/error/expired/deleted) + lastUpdated ; écritures atomiques ; fichiers corrompus automatiquement sauvegardés sous `.corrupt-<ts>` |
| `.cookies.json` | `CookieCache` (common.py:111, 150) | cache de cookies (fraîcheur 12 h), avec source et email du compte ; écriture atomique : fichier temporaire créé avec 0o600 puis os.replace (cookies/cache.py:59-67 — informations d'identification de session lisibles uniquement par le propriétaire ; dans le périmètre de gitignore) |
| `space_<slug>.json` | `cmd_space_index` (spaces_cmd.py:106-167) | liste de tous les threads par espace (incluant le mappage double ID context_uuid) |
| `space_meta.json` | `cmd_spaces --fetch-meta` (spaces_cmd.py:299-330) | cache propriétaire/membre de l'espace (réutilisé lors de la reconstruction des index, évitant une nouvelle récupération) |
| `credit_usage_<account>.json` | `cmd_usage_backfill` (usage_backfill_cmd.py:17) | utilisation de crédit par thread (idempotent et reprenable, vidé tous les 25 entrées) |
| `cron_snippet.txt` | `cmd_schedule` (scheduler.py:48-78) | extrait d'invocation cron (chemins absolus) |
| `answer_variants_log.jsonl` | `variant_log.append_registry` (variant_log.py:76) | registre central des variantes de réécriture de réponse (dédoublonné par thread+entrée, idempotent ; fichier suivi, pas logs/) — chaîne de détection dans [§18](offline-operations.md) |
| `logs/` | `--log-file` (common.py:218-229) | journaux DEBUG complets (gitignorés) |

<a id="the-spaces-index-layer-repository-root-tool-generated" data-pplx-source-anchor="true"></a>
### La couche d'index spaces/ (racine du dépôt, générée par l'outil)

`cmd_spaces` reconstruit en agrégeant `index/library_*.json` (spaces_cmd.py:259-389) : un `<slug>.md` par espace (agrégation des comptes participants + en-tête propriétaire/membre + tableau des threads + backlinks vers les emplacements d'exportation) plus le registre `spaces.json`. **Remarque** : le répertoire de sortie est `spaces/` relatif au CWD (spaces_cmd.py:332) — il ne suit pas `--out` ; les informations des comptes participants sont agrégées purement localement, tandis que les propriétaires/membres proviennent du cache `index/space_meta.json`. Ne pas modifier manuellement — la prochaine reconstruction écrase.

<a id="hand-editable-vs-tool-managed" data-pplx-source-anchor="true"></a>
### Modifiable manuellement vs géré par l'outil

- **Modifiable manuellement** : le [document de conception du système](overview.md), la [référence API](../reference/api/api-authentication.md), le README du projet et autres documents de spécification, et les rapports de révision `web_archive/crosscheck/` (documents de spécification et artefacts de révision).
- **Géré par l'outil (ne pas modifier manuellement les fichiers de contenu)** : tous les artefacts dans les répertoires de threads `web_archive/`, `index/`, `spaces/`, `relations/` — lorsque des modifications sont nécessaires, modifiez l'outil et réexécutez (les corrections de rendu passent par un nouveau rendu, les corrections de données par la commande de remblayage correspondante), en conservant une source unique d'artefacts reproductibles.
