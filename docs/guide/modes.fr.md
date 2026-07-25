---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/guide/modes.md"
translation_source_sha256: "dda1cfaf9d60ef912d922e65babafb68ec80cd1cdf046d661960d0de47ab77ff"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="conversation-modes" data-pplx-source-anchor="true"></a>
# Modes de conversation

Les conversations Perplexity se déclinent en cinq modes : `search` / `deep-research` / `computer` /
`council` / `study`. Le mode est détecté par fil lors de l'exportation ; il détermine quelles réponses
API sont récupérées, ce qui atterrit dans le répertoire du fil, et quel
[chemin d'archive](archive-layout.md) le fil obtient (`<account>/<mode>/…`). Le mode détecté est
enregistré dans `thread.json` (clé `mode`) et utilisé par le filtrage `pplx-export batch --mode`.
`pplx-ask` peut également *créer* de nouveaux fils dans quatre des cinq modes (tous sauf
`computer`) — voir [pplx-ask](pplx-ask.md).

<a id="the-five-modes-at-a-glance" data-pplx-source-anchor="true"></a>
## Les cinq modes en un coup d'œil

| Mode | Nom UI / modèle | Contenu des tours | Citations | Produits | Blocs schématisés récupérés |
|---|---|---|---|---|---|
| `search` | "Best" (`pplx_pro` ; labs `STUDIO`/`pplx_beta` correspondent aussi ici) | Requête + Réponse, étapes textuelles | au niveau du tour + `sources.*` à l'échelle du fil | — | Non (`raw_blocks.json` absent) |
| `deep-research` | "Deep research" (`pplx_alpha`, fixe, pas de sélecteur) | étapes de recherche incl. `RESEARCH_ANSWER` | oui | `report.md` (rapport complet) | Oui |
| `computer` | Computer (`pplx_asi_opus`, `pplx_asi_opus_thinking`) | `workflow_block` complet : narration, appels d'outils, invites/étapes de sous-agent, citations par étape | par étape + tour + fil | fichiers versionnés dans `assets/` + exécutions de sous-agents | Oui |
| `council` | model council (`pplx_agentic_research` ; trois modèles par défaut) | étape `COUNCIL_RESEARCH` ; workflow `LLM_COUNCIL` imbriqué de chaque modèle intégré dans `<details>` (cycles de recherche, toutes les sources, réponse complète par modèle) | par modèle + agrégé | réponses par modèle comparées côte à côte | Oui |
| `study` | Study (`pplx_study`) | étapes/citations via blocs (vérifié pour contenir également des ressources) | oui | ressources lorsqu'elles sont présentes | Oui |

<a id="how-the-mode-is-decided" data-pplx-source-anchor="true"></a>
## Comment le mode est décidé

L'autorité de détection est le champ **`entry.search_mode`** de la plateforme
(`SEARCH_MODE_MAP`, `normalize.py:50-59`), collecté sur toutes les entrées
(`normalize.py:106-115`). Il a été vérifié par rapport à la configuration officielle du modèle
(`GET /rest/models/config/v2`) : `default_models.search=pplx_pro` (UI "Best"),
`default_models.research=pplx_alpha` (UI "Deep research"), et les valeurs correspondent une à une aux
modes de conversation :

| Valeur `search_mode` | Mode |
|---|---|
| `ASI` | `computer` |
| `AGENTIC_RESEARCH` | `council` |
| `STUDY` | `study` |
| `RESEARCH` | `deep-research` |
| `SEARCH`, `STUDIO` | `search` |

Règles de conflit (`detect_mode`, `normalize.py:66-128`) :

- **Changement de mode à l'intérieur d'un même fil** (entrées en désaccord) : prendre le plus élevé par spécificité —
  **computer > council > study > deep-research > search** (`_MODE_SPECIFICITY`,
  `normalize.py:63`) — et `log.warning`.
- **Conflit avec des signaux en aval** (noms d'étapes / `display_model`) : `search_mode` gagne,
  `log.warning` (`normalize.py:120-123`).
- **`search_mode` totalement absent** → la chaîne d'origine : l'URL contient `/computer/tasks/` ou
  `metadata.mode == '4'` ou le mode d'index ∈ `ASI`/`COMPUTER` → `computer` ; une étape `COUNCIL_RESEARCH`
  → `council` ; une étape `RESEARCH_ANSWER` → `deep-research` ; signal `display_model` redondant
  (`DISPLAY_MODEL_MODE`, `normalize.py:32-37`) gagne en cas de conflit ; rien ne correspond →
  `search` par défaut.
- **Tous les signaux manquants ne concluent pas à search** : le pipeline récupère toujours les blocs
  schématisés (`adapter.py:83-89`) afin qu'une dérive du champ de la plateforme ne puisse pas supprimer silencieusement `raw_blocks.json`.

!!! note "Pourquoi `pplx_alpha` n'est pas un indice de détection"
    `pplx_alpha` est le modèle dédié à RESEARCH — c'est la *cible* que le classifieur doit
    détecter, pas une preuve pour la détection, donc il est délibérément exclu du tableau de correspondance
    (commentaire `normalize.py:15-31`).

L'arbre de décision complet avec chaque branche : [Export pipeline — mode detection](../architecture/export-pipeline.md).

<a id="where-sub-agent-payloads-land" data-pplx-source-anchor="true"></a>
## Où atterrissent les charges utiles des sous-agents

Les exécutions Computer/Council lancent des workflows de sous-agents en arrière-plan. Chaque
`workflow_payload` d'arrière-plan est rendu dans **exactement un endroit, jamais deux fois** ; au niveau de l'utilisateur, les
trois points d'atterrissage possibles sont :

1. **Ancré — à l'intérieur du tour initiateur** : le tour qui a démarré le sous-agent porte un
   identifiant de charge utile correspondant, donc l'exécution s'affiche en ligne dans le processus de travail de ce tour
   (`turns/turn_NNNN.md`), avec invite, étapes, réponse et sources.
2. **Tour factice — section "子代理工作" (Travail de sous-agent)** : un tour factice `subagent_result` dans une
   fenêtre de complétion de 10 secondes absorbe la charge utile ; la réponse n'est pas rétro-remplie.
3. **Annexe du fil — fin de `conversation.md`** : tout ce qui reste (les exécutions interrompues
   ne produisent pas de notification de complétion, donc les deux premiers niveaux manquent nécessairement) est archivé
   textuellement sous "## 后台任务（未归入轮次）" (Tâches d'arrière-plan (non attribuées aux tours)) — pas
   de devinette d'attribution temporelle, tout statut accepté.

Règles de correspondance, structures de données et garanties de consommation unique :
[Sub-agents & interruptions](../architecture/subagents-interruptions.md).

<a id="interruptions-non-completed-workflows" data-pplx-source-anchor="true"></a>
## Interruptions : workflows non COMPLETED

Les workflows qui ne se sont pas terminés sont annotés en ligne partout où ils sont rendus — dans les en-têtes
de processus de travail, les en-têtes de sous-agent et les résumés `<details>` imbriqués. Les trois annotations
(`parsers.classify_wf_status`, `parsers.py:263-284`) :

| Annotation | Condition | Signification |
|---|---|---|
| `⏸ 限额中断（内容截至中断点）` (limit-interrupted — le contenu s'arrête au point d'interruption) | `WORKFLOW_AWAITING_NEXT_STEPS` + `locked_reason=spending_limit_exceeded` | limite de dépenses épuisée ; le workflow s'est arrêté en cours d'exécution |
| `⏸ 中断待续` (interrupted, pending continuation) | `WORKFLOW_AWAITING_NEXT_STEPS` sans `locked_reason` | interrompu, peut être continué sur la plateforme |
| `⛔ 已取消` (canceled) | `WORKFLOW_CANCELED` | annulé par l'utilisateur ou la plateforme |

- `COMPLETED` n'est jamais annoté (les fils sains obtiennent zéro diff) ; les futures valeurs de statut inconnues
  restent silencieuses.
- Chaque cas annoté est également enregistré dans `thread.json.interruptions` comme
  `{location, kind, headline, status}` — les emplacements ressemblent à `turn_0007`,
  `turn_0011/subagent`, `turn_0024/subagent_stub`, `background_unassigned`
  (`parsers.py:535-583` ; clé absente sur les fils sains).
- **La reprise n'a pas besoin de cas particulier** : lorsque vous continuez un fil interrompu sur la
  plateforme, son `lastUpdated` change, la prochaine exportation incrémentielle le récupère à nouveau, et les
  annotations disparaissent simplement une fois le workflow terminé. Voir
  [Incremental sync](incremental-sync.md).

Valeurs de statut observées et distribution : [API responses & errors](../reference/api/api-responses-errors.md) ;
machine à états : [Sub-agents & interruptions](../architecture/subagents-interruptions.md).

<a id="answer-rewrite-variants-answer_variants" data-pplx-source-anchor="true"></a>
## Variantes de réécriture de réponse (answer_variants)

Lorsque la plateforme réécrit une réponse (expériences A/B), la variante remplacée est invisible dans
l'API — seule la réponse sélectionnée est renvoyée, tandis que la sœur perdante laisse une trace dans
`entries[].side_by_side_metadata` et peut être purgée ultérieurement (liens morts de sœurs confirmés :
403 `VIEW_THREAD_NOT_ALLOWED`). L'outil rend observable "une réécriture a eu lieu" :

- **Enregistrement** : les correspondances à critères restreints sont écrites dans `thread.json.answer_variants`
  (`fs_writer.py:247-252` ; clé absente sans correspondances) et ajoutées au registre central
  `index/answer_variants_log.jsonl`, dédupliquées par (thread, entry) et idempotentes
  (`variant_log.py:76`).
- **Alertes** : une ligne WARNING unique et greppable `ANSWER_VARIANT_DETECTED` avec des champs
  de localisation complets (thread uuid/uuid8, entry_uuid, sibling_uuid, selection_status, experiment_role) sur
  chaque correspondance en ligne ; `re-render` réenregistre hors ligne et avertit uniquement lorsque du contenu est ajouté ou
  modifié, donc les réexécutions à l'échelle de la bibliothèque restent silencieuses ; le résumé du lot ajoute un compteur ⚠.
- **Réarchivage manuel** : les variantes sœurs sont empiriquement des liens morts, donc la réponse
  alternative ne peut généralement **pas être récupérée via l'API**. En cas de correspondance, confirmez rapidement la réponse
  alternative à la main (interface utilisateur de la plateforme, vos propres enregistrements, captures d'écran) ; si vous l'obtenez, enregistrez-la comme
  `rewritten_answer_variant.md` dans le répertoire du fil. Sinon,
  `thread.json.answer_variants` plus le registre jsonl sont le dernier enregistrement traçable.

Chaîne de détection et réenregistrement hors ligne : [Offline operations](../architecture/offline-operations.md) ;
sémantique des champs et preuves de liens morts : [API responses & errors](../reference/api/api-responses-errors.md).

<a id="rendering-fidelity-principles" data-pplx-source-anchor="true"></a>
## Principes de fidélité du rendu

Quel que soit le mode, le rendu suit le même contrat de fidélité :

- **Réponses complètes, jamais tronquées** — l'ancienne limite `[:4000]` a été supprimée car elle coupait
  les phrases en plein milieu (`render.py:645-647`).
- **Tableaux jamais tronqués** — `WORKFLOW_ITEM_TABLE` rend chaque ligne et colonne, en échappant
  `|` et les sauts de ligne dans les en-têtes et les cellules afin que la structure Markdown survive
  (`render.py:211-243`).
- **Citations complètes** — trois canaux de collecte (`entry.sources` + `FINAL.web_results` +
  `WORKFLOW_ITEM_SOURCES`), dédupliqués par URL dans `sources.*` ; rien de cité n'est supprimé.
- **Le JSON brut de l'API est la limite du contenu** — tout ce qui est rendu provient de
  `raw_entries.json` / `raw_blocks.json` ; ce que l'API ne renvoie pas (par exemple, une variante de réponse
  remplacée) ne peut pas être rendu, et est signalé via des registres au lieu d'être inventé.
- **L'interface utilisateur plie, l'archive développe** — les détails que l'interface utilisateur web cache derrière des plis et des clics
  (narration du workflow Computer et E/S des outils, exécutions par modèle du council, étapes des sous-agents) sont
  rendus en intégralité ; les blocs `<details>` maintiennent le plan du document lisible sans perdre
  d'informations (`render.py:46`, `render.py:404-413`).
- **Robustesse structurelle** — les blocs de code sont dimensionnés à leur contenu (`_fence_for`,
  `render.py:28-43`) afin que la sortie d'outil contenant ses propres blocs ne puisse pas inverser l'appariement, et
  les délimiteurs LaTeX sont normalisés en `$$` / `$` avec les segments de code protégés
  (`normalize_math_delims`).

Comment les réponses brutes conservées rendent tout cela régénérable hors ligne :
[Export pipeline](../architecture/export-pipeline.md) et [Offline operations](../architecture/offline-operations.md).

<a id="see-also" data-pplx-source-anchor="true"></a>
## Voir aussi

- [Archive layout](archive-layout.md) — où les fichiers de chaque mode atterrissent
- [pplx-ask](pplx-ask.md) — création de nouveaux fils dans chaque mode
- [Incremental sync](incremental-sync.md) — récupération des fils continués
- [Export pipeline](../architecture/export-pipeline.md) — arbre de décision complet de détection de mode
- [Sub-agents & interruptions](../architecture/subagents-interruptions.md) — cascade d'attribution et machine à états
- [API responses & errors](../reference/api/api-responses-errors.md) — valeurs de champ observées
