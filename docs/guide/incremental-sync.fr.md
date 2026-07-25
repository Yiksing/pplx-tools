---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/incremental-sync.md"
translation_source_sha256: "35868edfb3e8e914afd9afa1b00370bffb9f8a50ca374691229f41d51ffa9b64"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="incremental-sync" data-pplx-source-anchor="true"></a>
# Synchronisation incrémentielle

`pplx-export batch` est conçu pour être exécuté fréquemment : chaque exécution exporte uniquement ce qui est nouveau ou modifié, comble les lacunes laissées par des exécutions interrompues et ne retouche jamais les fils que la plateforme a déjà retirés. La source unique de vérité pour « ce qui a été exporté » est `index/batch_state.json` (`BatchState`, `pplx_export/core/state.py:63`), mise à jour après chaque fil — il n'y a pas de copie fantôme séparée.

<a id="prerequisites-and-basic-usage" data-pplx-source-anchor="true"></a>
## Prérequis et utilisation de base

```bash
pplx-export index --account alice   # refresh index/library_alice.json first
pplx-export batch --account alice   # incremental export (early stop, resumable)
```

`batch` refuse de s'exécuter sans l'index (`pplx_export/commands/batch_cmd.py:79-81`). `--limit N` et `--mode <mode>` filtrent les lignes de l'index avant la planification ; les lignes sans `entryUUID` sont ignorées avec un avertissement au lieu de faire échouer l'exécution (`batch_cmd.py:95-100`).

<a id="how-the-incremental-plan-works" data-pplx-source-anchor="true"></a>
## Comment fonctionne le plan incrémentiel

1. **Tri.** Les lignes de l'index sont triées par `lastUpdated`, les plus récentes en premier (`batch_cmd.py:89`). Les nouvelles conversations et les anciennes reprises (dont `lastUpdated` vient de les remonter) se trouvent toutes en haut — cet ordre est ce qui rend l'arrêt précoce sûr.
2. **Classification.** `plan_incremental` (`pplx_export/hooks/incremental.py:36-87`) — une fonction pure partagée par `batch` et `schedule` — attribue à chaque ligne exactement une action :

   | action | condition | ce que fait le lot |
   |---|---|---|
   | `new` | uuid jamais vu dans `batch_state` | exporter |
   | `updated` | `lastUpdated` diffère de la valeur enregistrée, ou `--force` | ré-exporter |
   | `done` | statut `ok` et `lastUpdated` inchangé | ignorer |
   | `expired` | la plateforme a retourné `ENTRY_EXPIRED` lors d'une tentative précédente | ignorer — terminal, jamais réessayé |
   | `deleted` | `sync-deleted` a confirmé une suppression distante | ignorer — terminal, jamais réessayé |

3. **Arrêt précoce.** Par défaut (ni `--full` ni `--force`), la plus longue séquence finale d'entrées terminales (`done` / `expired` / `deleted`) est supprimée en bloc et comptée comme `n_stopped` (`incremental.py:83-87`). Comme la liste est triée des plus récentes aux plus anciennes, tout ce qui se trouve en dessous d'une entrée inchangée est nécessairement plus ancien et inchangé aussi — continuer à analyser ne ferait que perdre du temps.

   ```mermaid
   flowchart TD
       IDX["library index rows<br/>sorted by lastUpdated, newest first"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → export"]
       PLAN --> UPD["updated → re-export"]
       PLAN --> DONE["done → skip"]
       PLAN --> TERM["expired / deleted → skip (terminal)"]
       DONE --> STOP["early stop:<br/>trailing terminal run trimmed"]
       TERM --> STOP
   ```

4. **Exécution.** Chaque fil exporté est marqué immédiatement (`mark_ok` / `mark_error` / `mark_expired` / `mark_deleted`) et le fichier d'état est sauvegardé après chaque élément (`batch_cmd.py:154-201`) ; un `KeyboardInterrupt` sauvegarde également avant la propagation (`batch_cmd.py:158-161`). Les écritures sont atomiques — fichier temporaire plus `os.replace` (`state.py:145-152`) — donc une exécution interrompue ne laisse jamais de JSON tronqué.

<a id="gap-healing-after-interrupted-runs" data-pplx-source-anchor="true"></a>
## Comblement des lacunes après des exécutions interrompues

L'arrêt précoce n'enterre jamais une lacune. Les fils qui ont échoué (statut `error`) ou qui n'ont jamais été atteints se trouvent **au-dessus** du suffixe terminal, donc la prochaine exécution les replanifie comme `updated` / `new` et les exporte avant d'atteindre le point d'arrêt précoce (`incremental.py:12-14`, `batch_cmd.py:206-208`). Combiné avec les sauvegardes d'état par élément, un lot peut être interrompu à tout moment et simplement relancé.

Si `batch_state.json` lui-même est corrompu, il n'est pas silencieusement vidé : l'original est renommé en `batch_state.json.corrupt-<timestamp>` afin que les états terminaux enregistrés ne soient pas perdus et inutilement réessayés (`state.py:68-81`).

<a id="-full-and-force" data-pplx-source-anchor="true"></a>
## `--full` et `--force`

| drapeau | effet | états terminaux | quand l'utiliser |
|---|---|---|---|
| *(par défaut)* | arrêt précoce sur la séquence terminale | ignorés | chaque exécution régulière / planifiée |
| `--full` | analyse complète, pas d'arrêt précoce ; les fils inchangés sont toujours ignorés comme `done` | ignorés | filet de sécurité périodique, ou quand des lacunes d'archive sont suspectées |
| `--force` | ré-exporter tout, même les fils inchangés | toujours exclus — jamais réessayés | après des corrections de pipeline qui doivent récupérer les données brutes |

Les états terminaux sont exclus de `--force` par conception : réessayer un fil expiré ou supprimé à distance ne fait que gaspiller des requêtes et du budget de backoff (`batch_cmd.py:120-127`).

Voir aussi [`status`](maintenance-commands.md#status) : un rapport sans réseau de l'état du compte et du plan de changement calculé avec la même sémantique `plan_incremental` (`new`/`updated`/compteur d'arrêt précoce).

La comparaison `lastUpdated` normalise les zéros de fin dans la partie des fractions de seconde (`.18033Z` est égal à `.180330Z` ; `state.py:23-55`), car la plateforme les supprime parfois — une comparaison exacte de chaînes jugerait à tort « modifié » et provoquerait des exportations en double.

<a id="terminal-states-expired-and-deleted" data-pplx-source-anchor="true"></a>
## États terminaux : `expired` et `deleted`

| | `expired` | `deleted` |
|---|---|---|
| signification | la plateforme a purgé le fil (fenêtre de rétention ~3 mois) ; la tentative d'exportation a retourné `ENTRY_EXPIRED` | suppression par l'utilisateur/à distance, confirmée par `sync-deleted` |
| enregistré par | `batch` lui-même (`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online` (`mark_deleted`, `state.py:136-143`) |
| réessayé ? | jamais — même pas avec `--force` | jamais — même pas avec `--force` |
| preuve | la réponse `ENTRY_EXPIRED` | champ `note` : absence dans l'index + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted-confirming-remote-deletions" data-pplx-source-anchor="true"></a>
### sync-deleted : confirmation des suppressions distantes

```bash
pplx-export sync-deleted --account alice            # offline dry-run: list candidates only
pplx-export sync-deleted --account alice --online   # confirm each candidate online
```

1. **Candidats (hors ligne, zéro réseau).** Tout fil avec le statut `ok` dans `batch_state` qui est absent de l'union `entryUUID` de **tous** les index de compte `index/library_*.json` est un candidat suspect de suppression distante (`pplx_export/commands/sync_deleted_cmd.py:148-212`). L'union sur tous les comptes est nécessaire : un fil appartenant à `bob` mais exporté par `alice` via un espace partagé n'apparaît jamais dans l'index de `alice` lui-même — une différence sur un seul compte produirait des faux positifs pour tout cet ensemble. Lorsqu'aucun index utilisable n'existe du tout, chaque candidat est ignoré en toute sécurité avec la raison enregistrée.
2. **Simulation par défaut.** Sans `--online`, la commande liste uniquement les candidats — pas de réseau, pas de modifications de fichiers.
3. **Confirmation `--online`.** Chaque candidat est vérifié avec `GET /rest/thread/<uuid>`, en utilisant le compte `export_via` du candidat depuis `thread.json` (le cookie change automatiquement) :

   | résultat | issue |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | confirmé : `batch_state` marque terminal `deleted` (le `note` enregistre la raison), et chaque `thread.json` de ce fil reçoit un horodatage `remote_deleted` à sa place |
   | le fil existe toujours | faux positif : signalé tel quel (l'index n'est peut-être pas entièrement actualisé — relancez `index` et vérifiez à nouveau), rien n'a changé |
   | 5xx / erreur réseau | aucun changement d'état ; le candidat est laissé pour le prochain tour |
   | 3 erreurs 401/403 consécutives | abandon rapide — un cookie expiré ne peut pas se guérir lui-même, et continuer marquerait à tort des fils actifs (`sync_deleted_cmd.py:333-337`) |

   Les marques confirmées sont persistées par élément, donc une exécution `--online` interrompue ne perd rien et les relances sont idempotentes (`sync_deleted_cmd.py:254-256`).

<a id="the-tombstone-principle" data-pplx-source-anchor="true"></a>
## Le principe de la pierre tombale

!!! warning "Les archives locales ne sont jamais supprimées"
    Cette archive est la sauvegarde de référence des conversations exportées.
    `sync-deleted` *identifie et marque* (pierre tombale) uniquement : il **ne supprime ni ne déplace jamais de fichier d'archive**. La confirmation change exactement deux choses — le statut `batch_state` et une clé de marqueur dans `thread.json` :

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    Le tampon est idempotent : une clé `remote_deleted` existante n'est ni réécrite ni écrasée (`sync_deleted_cmd.py:215-244`).

<a id="idempotence-and-offline-re-render" data-pplx-source-anchor="true"></a>
## Idempotence et régénération hors ligne

- Relancer `batch` sur un index inchangé n'exporte rien : chaque ligne est classée comme `done` et l'exécution s'arrête au point d'arrêt précoce. Les écritures d'état sont atomiques, les marques sont par fil, et les suppressions reconfirmées ne dupliquent jamais le tampon `remote_deleted`.
- L'archive conserve les charges utiles brutes de l'API (`raw_entries.json` / `raw_blocks.json`), donc les fichiers rendus peuvent être régénérés à tout moment sans accès réseau :

  ```bash
  pplx-export re-render                 # rebuild conversation.md + turns/ everywhere
  pplx-export re-render --dry-run       # only list the thread directories
  pplx-export re-render --thread-json   # also sync interruptions / answer_variants keys
  ```

  `re-render` réanalyse le JSON brut avec le moteur de rendu actuel (`pplx_export/commands/rerender_cmd.py:105-190`) : `conversation.md` et `turns/turn_*.md` sont réécrits, les fichiers de tour obsolètes numérotés au-dessus du nombre de tours actuel sont supprimés, et les sources, ressources, `report.md` et `thread.json` sont laissés intacts. C'est ainsi que les corrections du moteur de rendu se déploient sur l'ensemble de l'archive sans une seule requête.

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [pplx-export.md](pplx-export.md) — référence complète de la commande `batch` (`--mode`, `--limit`, délais)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` et les commandes de rattrapage
- [archive-layout.md](archive-layout.md) — où se trouvent `batch_state.json` et `thread.json`
- [rate-limiting.md](rate-limiting.md) — cadencement entre les fils, backoff, abandon rapide sur erreur d'authentification
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — le pipeline d'exportation complet
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — le pipeline de régénération hors ligne en détail
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — taxonomie des erreurs et gestion des états terminaux
