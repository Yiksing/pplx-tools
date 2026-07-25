---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/reference/api/api-responses-errors.md"
translation_source_sha256: "4a9de23e2a900f4922480decf1b89d417310b94ce8116649dd2b2dd5c77b6bde"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="api-response-structure-and-error-semantics" data-pplx-source-anchor="true"></a>
# Structure des réponses API et sémantique des erreurs

*Partie de la référence de l'API web Perplexity — carte complète à l'[index API](index.md).*

<a id="response-structure-essentials-parsing-discipline" data-pplx-source-anchor="true"></a>
## Éléments essentiels de la structure des réponses (discipline d'analyse)

- **Données brutes conservées dans les archives réussies** : `raw_entries.json` (brut) et
  `raw_blocks.json` (schématisé, lorsqu'il est récupéré) sont stockés avec les artefacts rendus ;
  l'analyse/le rendu peut être relancé hors ligne (`pplx-export re-render`)
  sans nouvelle récupération.
- **Extraction des champs centralisée** dans `sites/perplexity/parsers.py` (une dérive de schéma ne nécessite qu'un seul endroit modifié).
- Détection du mode (`normalize.detect_mode` ; arbre de décision dans [export-pipeline.md](../../architecture/export-pipeline.md)) : le signal de plus haute priorité est le
  champ **`search_mode`** de toute entrée (correspondance à la fin de [§3.9](api-rest-endpoints.md)) ; lorsque tous les signaux échouent, repli — computer = URL
  `/computer/tasks/` ou metadata.mode=="4" ou index mode ∈ {ASI,COMPUTER} ; council =
  une étape COUNCIL_RESEARCH existe ; deep-research = une étape RESEARCH_ANSWER existe (basé sur le contenu, sans se fier aux libellés chinois) ;
  sinon search.
- L'interface utilisateur computer réduit tout — **toujours se baser sur les entrées/blocs API** ; ne jamais utiliser le texte de l'interface comme limite de contenu.
- Canal double du sous-agent (découvert le 2026-07-19) : invite dans `workflow_payload.objective_chunks` schématisé ;
  étapes/conclusion dans `background_entries` brut ; liés via `workflow_payload.id` (`toolu_X`).
- Les éléments `WORKFLOW_ITEM_SOURCES` contiennent souvent `text_payload`
  (texte d'extraction de page du sous-agent / tableaux comparatifs ; 450 occurrences dans toute la bibliothèque, 408 dans les charges utiles imbriquées d'arrière-plan)
  en plus de `sources_payload.sources` (liste de liens) ;
  le même contenu apparaît à la fois dans le JSON d'étape intégré `text` de l'entrée d'arrière-plan brute et dans la charge utile imbriquée schématisée —
  les sous-agents ancrés rendus via le chemin brut préservent déjà le texte (vérification dans toute la bibliothèque le 2026-07-22 : 408/408 présents, aucun manquant).
- **`related_queries` / `related_query_items` (résolu le 2026-07-23)** : chaque entrée porte
  **des recommandations de questions suivantes** — suggestions de suivi que la plateforme génère pour une réponse terminée ; `related_queries` est un tableau de textes de recommandation,
  `related_query_items` les éléments structurés (uuid/upsell_type, etc.). Conclusion forensique : l'uuid d'un élément
  **n'est pas un uuid de fil** (0/988 correspondances croisées avec les uuid de fils de la bibliothèque), et les textes de recommandation n'ont aucun chevauchement avec les requêtes d'autres fils —
  **non résolvable en relations inter-fils pour l'instant** ; l'hypothèse d'"uuid de fils pré-alloués (matérialisés au clic)" reste non vérifiée.
  Les données sont naturellement préservées dans l'archive `raw_entries.json` (présentes dans plus de la moitié des fils d'une bibliothèque d'archive) ; aucune action de collecte supplémentaire nécessaire ;
  le graphe de relations ne construit aucune arête à partir de cela.

<a id="error-and-risk-control-semantics" data-pplx-source-anchor="true"></a>
## Sémantique des erreurs et du contrôle des risques

| Symptôme | Signification / traitement |
|---|---|
| 403 (avec page de défi cf) | Blocage Cloudflare (empreinte TLS / contrôle de débit) — reculer ; urllib + cookies de navigateur ne déclenchent généralement pas cela |
| 401 / 403 au niveau API (sans page de défi cf) | Cookie de session expiré/invalide — l'outil lève immédiatement, sans recul ; l'échec rapide du lot après 3 échecs d'authentification consécutifs (mettre à jour le cookie) |
| 429 | Limitation de débit — backoff exponentiel (implémenté dans l'outil) |
| 5xx (500/502/503/504) | Erreurs serveur transitoires (504 est souvent un délai d'attente Cloudflare) — reculer et réessayer (implémenté dans l'outil) |
| ENTRY_EXPIRED | Purgé par la plateforme (~3 mois) — terminal, ne pas réessayer |
| ENTRY_DELETED | Supprimé par l'utilisateur/à distance (également HTTP 400, code différent) — terminal `deleted`, ne pas réessayer |
| `_response_type: VIEW_COLLECTION_NOT_ALLOWED` (HTTP 200) | Le compte actuel ne peut pas voir l'espace — réessayer avec un compte qui le peut |
| `error_code: VIEW_THREAD_NOT_ALLOWED` (HTTP 403) | Le compte actuel ne peut pas voir le fil (testé le 2026-07-23 : sondage d'uuid de variante frère ; l'objet existe mais est inaccessible, pas "inexistant") |
| `status:"failed"` données vides | Même classe (la forme d'échec de get_collection) |

**Discipline de limitation de débit (anti-bannissement, exigence explicite de l'utilisateur)** : 10–20 s aléatoires entre les fils de lot, pas de concurrence, backoff 429/403, backoff-réessai 5xx ;
pagination ≥3 s ; nouvelle récupération schématisée ≥4 s ; récupération des métadonnées d'espace ≥3 s. Export d'un seul fil = 1–2 requêtes ≈ ouvrir la page une fois.

<a id="interruption-semantics-observed-values-2026-07-22-classification-source-of-truth-parsersclassify_wf_status" data-pplx-source-anchor="true"></a>
### Sémantique d'interruption — valeurs observées (2026-07-22 ; source de vérité de classification : `parsers.classify_wf_status`)

Le champ `locked_reason` : apparaît dans `thread_metadata` / `entries[]` / `background_entries[]`
(à la fois du côté brut et schématisé). Seule valeur observée :

| locked_reason | Signification | Distribution observée |
|---|---|---|
| `spending_limit_exceeded` | interruption de limite de dépenses (quota épuisé ; le flux de travail s'arrête au point d'interruption) | exactement un fil dans toute la bibliothèque (marqueurs à la fois dans raw_entries et raw_blocks) |

Champ de statut du flux de travail (`workflow_block.status` et `workflow_payload.status` imbriqué partagent la même énumération) valeurs observées :

| statut | Sémantique | Annotation de rendu (COMPLETED n'en reçoit aucune) |
|---|---|---|
| `WORKFLOW_COMPLETED` | achèvement normal | — |
| `WORKFLOW_AWAITING_NEXT_STEPS` | en attente des prochaines étapes ; avec `locked_reason=spending_limit_exceeded` c'est une **interruption de limite de dépenses** (le contenu s'arrête au point d'interruption) ; sans locked_reason, interrompu en attente de continuation | `⏸ 限额中断（内容截至中断点）` (⏸ limit-interrompu — le contenu s'arrête au point d'interruption) / `⏸ 中断待续` (⏸ interrompu, en attente de continuation) |
| `WORKFLOW_CANCELED` | annulé (abandon utilisateur/plateforme) | `⛔ 已取消` (⛔ annulé) |

- `WORKFLOW_CANCELED` observé 19 fois (16 principaux + 3 imbriqués), dans 7 fils computer
  (a5e8f481/cfca382d/f2e5957d/8417b02a/2dc5716d/356f833e/ed3714ff).
- Remarque : le statut de la charge utile d'ancrage de l'entrée principale peut être en retard (ancrage observé COMPLETED alors que l'arrière-plan était en fait CANCELED) —
  le vrai statut d'un sous-agent est le `workflow_block.status` côté arrière-plan.
- Les tâches d'arrière-plan interrompues ne produisent pas de notification d'achèvement subagent_result ; les charges utiles d'arrière-plan non consommées tombent dans l'annexe du fil
  (voir "cascade d'attribution" dans [subagents-interruptions.md](../../architecture/subagents-interruptions.md)).
- Réponses vides en mode computer (double-vérifié en 2026-07, irrécupérables) : en mode computer, certains tours ont une
  réponse vide simplement parce que le serveur n'en a pas — une nouvelle récupération API renvoie des données identiques à l'archive, et
  le développement de la barre "N étapes terminées" de l'interface utilisateur ne déclenche aucune requête de données (rendu pur côté client ; l'interface utilisateur et
  l'API partagent une source), donc l'API ne peut pas les récupérer. Seul un sous-ensemble de ces tours est lié à
  `locked_reason=spending_limit_exceeded` ; les autres ne portent aucun marqueur côté serveur.

<a id="side_by_side_metadata-answer-rewrite-variant-signal-settled-2026-07-23" data-pplx-source-anchor="true"></a>
### `side_by_side_metadata` : signal de variante de réécriture de réponse (résolu le 2026-07-23)

Chemin du champ : `entries[].side_by_side_metadata` (réponse `/rest/thread/<uuid>` brute).
Lorsque la plateforme génère plusieurs versions de réponse pour la même requête (expérience A/B ou réécriture), c'est la
seule trace laissée sur l'entrée actuellement active — **le corps de la variante remplacée (texte/étapes/citations) n'est pas dans la réponse API du fil** (cas réel
b2d2632b : la réponse n'a qu'1 entrée, 1 FINAL ; variante 2 complètement invisible).

Clés et valeurs observées (preuve : b2d2632b brut ; analyse de 2442 entrées dans toute la bibliothèque) :

```json
{
  "experiment_role": "override-default-model-class:qwen3_instruct-01f7f",
  "sibling_uuid": "00000000-0000-5000-8000-000000000000",
  "experiment_override": {"override-default-model-class": "qwen3_instruct"},
  "selection_status": "SELECTED",
  "execution_log": {}
}
```

| Clé | Sémantique (observée/hypothèse) |
|---|---|
| `sibling_uuid` | Pointe vers la **variante de réponse sœur** de la même requête (un autre identifiant d'entrée/contexte). 7 fils touchés dans toute la bibliothèque ; **l'investigation en ligne (2026-07-23) confirme un lien mort** : les `GET /rest/thread/<sibling_uuid>` des deux comptes renvoient 403 `VIEW_THREAD_NOT_ALLOWED` (pas 404/ENTRY_EXPIRED — le serveur le reconnaît comme un objet existant mais non visualisable), et ouvrir `/search/<sibling_uuid>` dans le navigateur (compte propriétaire) est redirigé SPA vers l'accueil — les variantes remplacées ne peuvent pas être récupérées via sibling_uuid |
| `selection_status` | `SELECTED` = la réponse de cette entrée est la version choisie pour l'affichage ; les instances du groupe de contrôle sont toutes `SELECTION_STATUS_UNSPECIFIED` |
| `experiment_role` | Rôle de l'expérience. Le groupe de contrôle porte un préfixe `[control]` (6 cas dans toute la bibliothèque : `[control]default-model-class:gpt41`, etc.) ; le cas réel n'a pas de préfixe (`override-default-model-class:qwen3_instruct-01f7f`, c'est-à-dire le groupe de traitement d'une expérience de remplacement de modèle) |
| `experiment_override` | Paramètres de remplacement de l'expérience (par exemple `override-default-model-class: qwen3_instruct`) ; observé uniquement sur les instances du groupe de traitement |
| `execution_log` | Observé comme un objet vide ; sémantique inconnue |

**Critères de restriction** (distinguer "réécriture authentique gardant les deux versions" du "contrôle A/B de routine") :
`sibling_uuid` non vide ET (`selection_status` non vide et pas `SELECTION_STATUS_UNSPECIFIED`,
OU `experiment_role` sans le préfixe `[control]`) → **seul b2d2632b est touché** parmi les 2442 entrées de la bibliothèque
(le seul cas réel confirmé ; précision/rappel sont tous deux 1 sur cette bibliothèque, mais n=1 ne peut pas être extrapolé).

Comportement de l'outil : `parsers.collect_answer_variants` extrait les occurrences ; `adapter.get_thread`
enregistre un avertissement + écrit `thread.json.answer_variants` (clé absente lorsqu'aucune occurrence) ;
`re-render --thread-json` ajoute/supprime sur place (idempotent). Preuve temporelle : le delta `created→updated` de l'entrée du cas réel
est de 53,66 s (généré à 17:13, puis réécrit/sélectionné), et la réécriture a avancé le `lastUpdated` au niveau du fil (un ré-export incrémental
peut déclencher une nouvelle récupération, mais la réponse récupérée contient toujours uniquement la réponse active ; les anciennes variantes sont irrécupérables).

**Journal de détection et flux de traitement (2026-07-23, `sites/perplexity/variant_log.py`)** :

- **Marqueur de journal** : chaque occurrence émet une seule ligne WARNING avec le marqueur uniforme et greppable `ANSWER_VARIANT_DETECTED`,
  incluant tous les champs de localisation et les conseils de traitement, formatée comme :
  `ANSWER_VARIANT_DETECTED thread=<full uuid> uuid8=<8 chars> title="…" entry=<entry_uuid> sibling=<sibling_uuid> selection_status=SELECTED experiment_role=… | action: …`
  Le chemin en ligne (`adapter.get_thread`) produit une sortie à chaque occurrence de récupération réelle ; hors ligne `re-render`
  **produit une sortie uniquement lorsque du contenu enregistré est ajouté/modifié** (les ré-exécutions idempotentes ne spamment pas) ; `batch` transmet également un rappel
  du nombre d'occurrences sur une ligne à la fin du résumé (sans casser le format de résumé existant).
- **Registre central** : `<out>/index/answer_variants_log.jsonl` (**un fichier suivi**, pas sous le
  `logs/` gitignoré) — un JSON par ligne (detected_at / source=online|offline /
  web_uuid / uuid8 / title / entry_uuid / sibling_uuid / selection_status /
  experiment_role), dédoublonné par (web_uuid, entry_uuid) ; les exportations/ré-rendus répétés n'ajoutent pas indéfiniment ;
  detected_at conserve l'heure de première observation.
- **Action recommandée en cas d'occurrence** : les frères sont empiriquement des liens morts (voir le tableau ci-dessus) ; la réponse alternative
  **ne peut généralement pas être récupérée via l'API** — confirmer rapidement manuellement si la réponse alternative est toujours obtenable (conversation sur la plateforme / mémoire de l'utilisateur / captures d'écran) ; si elle est obtenable,
  l'enregistrer manuellement comme un fichier `rewritten_answer_variant.md` dans le répertoire du fil ; sinon, `thread.json.answer_variants` +
  le registre jsonl sert d'enregistrement traçable final.
