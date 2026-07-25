---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/offline-operations.md"
translation_source_sha256: "c813dedc53caddaa170728bac2152dadca3175bb204ddb9e0cdbca72d7907763"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="offline-operations" data-pplx-source-anchor="true"></a>
# Opérations hors ligne

Le côté zéro-réseau de `pplx_export` : régénération hors ligne à partir de JSON brut, pipeline de reconstruction des relations, remplissage d'enrichissement d'index, machine d'état de suppression à distance et chaîne de détection answer_variants. Les sections conservent leur numérotation d'origine de la [vue d'ensemble de l'architecture](overview.md).

---

<a id="offline-regeneration-re-render" data-pplx-source-anchor="true"></a>
## Régénération hors ligne (re-rendu)

Après les corrections de la couche de rendu, régénérer tous les artefacts à partir du JSON brut **sans réseau**, de manière idempotente.
Implémentation : `commands/rerender_cmd.py` (monothread `rerender` rerender_cmd.py:105-190 ;
lots `cmd_rerender` rerender_cmd.py:193-212).

```mermaid
flowchart TD
    IN[("&lt;out&gt;/*/*/*/raw_entries.json<br/>glob all thread directories (rerender_cmd.py:199)")] --> CHK{"raw_entries.json exists?"}
    CHK -->|"no"| SKIP["skip (counted as skipped)"]
    CHK -->|"yes"| P1["parse_turn per entry (parsers.py:173)<br/>sort by created_us, re-number index<br/>(rerender_cmd.py:57-60)"]
    P1 --> P2["Conversation rebuilt<br/>metadata = thread_metadata (rerender_cmd.py:65-70)<br/>conv._plain = doc"]
    P2 --> P3{"raw_blocks.json exists?"}
    P3 -->|"yes"| P4["conv._blocks loaded (rerender_cmd.py:91)<br/>PerplexityAdapter(None).sub_agents builds sub_map<br/>(None-transport pure data assembly, rerender_cmd.py:84-88, 138)"]
    P3 -->|"no"| P5["sub_map = {}"]
    P4 --> P6{"mode in computer/council?"}
    P6 -->|"yes"| P7["attach_workflow_blocks (rerender_cmd.py:93)<br/>attach_stub_workflows (rerender_cmd.py:97)<br/>collect_unconsumed_background (rerender_cmd.py:101)"]
    P6 -->|"no"| P8
    P5 --> P8["render_conversation → conversation.md<br/>render_turn × N → turns/turn_NNNN.md<br/>(rerender_cmd.py:170, 189)"]
    P7 --> P8
    P8 --> TJ{"--thread-json?"}
    TJ -->|"no"| OUT(("done: other files untouched"))
    TJ -->|"yes"| TJ1["collect_interruptions(conv, sub_map) (rerender_cmd.py:150)<br/>answer_variants rebuilt with load_archived's same implementation (rerender_cmd.py:83)"]
    TJ1 --> TJ2{"compare the two keys<br/>interruptions / answer_variants<br/>against existing thread.json"}
    TJ2 -->|"content changed"| TJ3["add/remove the two keys in place, then write; all other fields kept as-is (round-trip indent=1)<br/>(rerender_cmd.py:141-169)<br/>warn + append jsonl registration when variants are added/changed<br/>(rerender_cmd.py:163-166, see §18)"]
    TJ2 -->|"no change"| TJ4["no write — avoids library-wide mtime/diff noise"]
```

Discipline :

- **Zéro réseau** : `PerplexityAdapter(None)` ne réutilise que des méthodes pures d'assemblage de données ; aucune méthode
  en ligne (get_thread, etc.) n'est jamais appelée.
- **Idempotent** : les artefacts ne dépendent que du brut + du moteur de rendu ; les réexécutions sont identiques octet par octet
  (garanti par les tests de régression instantanés, [§13](../development/testing-architecture.md)).
- **Autres fichiers inchangés** : les sources, report.md, assets restent en l'état ; thread.json n'est pas modifié par défaut —
  avec `--thread-json` seules les deux clés interruptions / answer_variants sont ajoutées ou supprimées.
- `--dry-run` liste uniquement les répertoires sans écrire de fichiers (rerender_cmd.py:204-206) ; `--limit N` prend les N premiers.

---

<a id="relations-offline-rebuild-pipeline" data-pplx-source-anchor="true"></a>
## Pipeline de reconstruction hors ligne des relations

`cmd_relations` (misc_cmd.py:16) reconstruit le graphe des relations de conversation à l'échelle de la bibliothèque à partir des
archives de données brutes **sans réseau** : il réutilise le pipeline de reconstruction hors ligne du re-rendu
`load_archived_conversation` (rerender_cmd.py:34) pour restaurer chaque Conversation (analyse/tri/numérotation des tours, rattachement _plain/_blocks), remplit le champ `conv.sub_agents` au niveau conversation via
`adapter.sub_agents` fil par fil (misc_cmd.py:70-73 ; le pipeline d'export ne remplit pas
ce champ, models.py:178-182) ; le repli de réponse computer (`wf_block_answer`) remplit
`turn.answer` à cette couche, élargissant la surface de balayage des références (misc_cmd.py:74-79). Les fils
sans données brutes se dégradent en une coque thread.json + conversation.md (seules les arêtes same_space / bare-uuid
peuvent être détectées, misc_cmd.py:61-66).

```mermaid
flowchart LR
    RAW["web_archive/*/*/*/raw_entries.json<br/>+ raw_blocks.json"] --> LA["load_archived_conversation<br/>(rerender_cmd.py:34, zero network)"]
    LA --> SUB["adapter.sub_agents → conv.sub_agents<br/>(misc_cmd.py:70-73)"]
    LA --> FB["wf_block_answer backfills turn.answer<br/>(misc_cmd.py:74-79)"]
    SUB --> BE["build_edges (relations.py:200)"]
    FB --> BE
    BE --> SS["same_space: same space<br/>dst = space:&lt;slug&gt;"]
    BE --> SP["same_prompt: first-query normalized equality<br/>(normalize_query, relations.py:111)<br/>in-cluster chaining by created_us (not cliques)<br/>query_source distinguishes scheduled-task reruns<br/>from manual resends (parsers.py:209-215)"]
    BE --> RF["references: answer text / citation URLs<br/>referencing other archived threads (incl. bare uuids)"]
    BE --> SA["subagent_of: main thread → subagent run<br/>dst = toolu_X run id (not a thread uuid)<br/>archived subagent threads recorded in evidence"]
    SS --> OUT[("web_archive/relations/<br/>edges.jsonl + graph.md")]
    SP --> OUT
    RF --> OUT
    SA --> OUT
```

Discipline de décision (2026-07-23) : le mécanisme `branch_of` est confirmé mais n'a aucune instance
dans l'archive — aucune arête construite ; `related_query` ne peut pas être analysé à partir des données existantes — aucune arête
construite non plus : plutôt manquer une arête que d'en construire une supposée.
Échelle observée : 772 arêtes / 21 clusters dans l'archive (same_space 559 / subagent_of 154 /
same_prompt 49 / references 10).

---

<a id="search-mode-backfill-index-search_mode-enrichment" data-pplx-source-anchor="true"></a>
## search-mode-backfill (enrichissement search_mode de l'index)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) enrichit le champ faisant autorité sur la plateforme
`search_mode` dans `index/library_<account>.json` : **brut local d'abord** (pour les fils
archivés, extrait de `entries[].search_mode` de raw_entries.json, zéro réseau) ; seuls les fils
sans brut local se replient sur une récupération en ligne du fil. L'écriture fusionne et préserve les champs
d'index existants (sémantique d'actualisation : les clés d'enrichissement écrasent, tout le reste est conservé), idempotent
et reprenable, avec `--limit` pour les sous-ensembles.
Les lignes d'index enrichies rendent le filtre `--mode` du lot faisant autorité :
`index_row_matches_mode` (batch_cmd.py:46) juge d'abord par search_mode de l'index
(SEARCH_MODE_MAP, normalize.py:50), ne tombant dans les heuristiques que lorsqu'il est manquant.

---

<a id="sync-deleted-remote-deletion-state-machine" data-pplx-source-anchor="true"></a>
## sync-deleted machine d'état de suppression à distance

`cmd_sync_deleted` (sync_deleted_cmd.py:262) identifie les fils « supprimés par l'utilisateur/à distance
côté plateforme » et enregistre un état terminal, ainsi que expiré. La détermination des candidats est une
**différence d'union de tous les index de comptes** : un fil archivé ok est considéré comme candidat uniquement
lorsqu'il a disparu de **tous** les fichiers `index/library_*.json` (un export_via
inter-compte apparaît uniquement dans l'index de son propriétaire, donc une différence mono-compte serait un faux positif ;
find_candidates, sync_deleted_cmd.py:148) ; les index manquants/illisibles sont ignorés en toute sécurité avec
la raison enregistrée. L'essai à blanc hors ligne par défaut liste uniquement les candidats (pas de réseau, pas de
modification de fichier) ; `--online` vérifie fil par fil avec GET : `ENTRY_DELETED` / `ENTRY_EXPIRED` /
404 → suppression confirmée, `state.mark_deleted` (state.py:136) + une pierre tombale thread.json
(mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Superposition des types d'erreur : `EntryDeletedError` hérite de `EntryExpiredError` (la vérification d'un 400 avec un
corps contenant ENTRY_DELETED a lieu avant ENTRY_EXPIRED, cookie_transport.py:93-98) ; le lot
doit attraper la sous-classe avant la classe parente (batch_cmd.py:163-174 avant 175-183), sinon supprimé
serait mal enregistré comme expiré. L'API de suppression elle-même :
`DELETE /rest/thread/delete_thread_by_entry_uuid`
(read_write_token pris du premier `entries[].read_write_token` non vide ;
vérifié en pratique 10/10 suppressions réussies sur des fils de test auto-créés et des fils de l'espace BOT).

---

<a id="the-answer_variants-answer-rewrite-variant-detection-chain" data-pplx-source-anchor="true"></a>
## La chaîne de détection des variantes de réponse answer_variants

Les variantes remplacées dans les « answer rewrite / A-B experiments » de la plateforme sont invisibles côté API
— la réponse sélectionnée est visible, tandis que la sœur perdante ne laisse qu'une trace dans
`entries[].side_by_side_metadata`, et peut être purgée par la plateforme (les liens morts des sœurs sont
prouvés : 403 VIEW_THREAD_NOT_ALLOWED + une redirection SPA vers la page d'accueil ; voir
[la référence API §5.2](../reference/api/api-responses-errors.md)). La chaîne de détection rend « une réécriture a eu lieu » observable
et traçable :

```mermaid
flowchart LR
    E["entries[].side_by_side_metadata<br/>narrowed criteria"] --> CAV["parsers.collect_answer_variants<br/>(parsers.py:589)"]
    CAV --> AD["adapter.get_thread warns on online hits<br/>(adapter.py:141-147)"]
    CAV --> RR["re-render offline rebuild<br/>warns only on additions/changes (rerender_cmd.py:163-166)"]
    AD --> LOG["variant_log.warn_detections (variant_log.py:65)<br/>single WARNING line ANSWER_VARIANT_DETECTED (variant_log.py:45)<br/>full locating fields + handling guidance, grep-able"]
    RR --> LOG
    AD --> TJ["thread.json.answer_variants registration<br/>(fs_writer.py:247-252)"]
    RR --> TJ
    TJ --> JSONL[("index/answer_variants_log.jsonl<br/>append_registry (variant_log.py:76)<br/>dedup by (web_uuid, entry_uuid), idempotent")]
    LOG --> B["batch summary surfaces ⚠ hit-thread count<br/>(batch_cmd.py:214-223)"]
    JSONL --> B
```

- **Critères resserrés** : seuls les signaux faisant autorité de side_by_side_metadata sont acceptés ;
  les champs de localisation complets sont enregistrés (uuid complet du fil + uuid8, titre, entry_uuid, sibling_uuid,
  selection_status, experiment_role) ainsi que des conseils de traitement ; le format est dans
  `format_detection` (variant_log.py:53).
- **Idempotent** : le jsonl déduplique par (web_uuid, entry_uuid) ; les enregistrements en double provenant des chemins
  en ligne (source=online) et hors ligne (source=offline) ne produisent pas de lignes en double ; le re-rendu
  n'avertit que lorsque le contenu de la variante change, donc les réexécutions à l'échelle de la bibliothèque ne spamment pas.
- **Flux de traitement** : sur un hit, confirmer manuellement la réponse alternative dès que possible et
  l'enregistrer (l'alternative peut être purgée par la plateforme et ne peut pas être récupérée via l'API) ;
  le flux complet est dans [la référence API §5.2](../reference/api/api-responses-errors.md).
