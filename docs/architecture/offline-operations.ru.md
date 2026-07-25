---
translation_kind: "machine"
translation_source_locale: "en"
translation_source_path: "docs/architecture/offline-operations.md"
translation_source_sha256: "c813dedc53caddaa170728bac2152dadca3175bb204ddb9e0cdbca72d7907763"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="offline-operations" data-pplx-source-anchor="true"></a>
# Офлайн-операции

Сторона с нулевым сетевым доступом `pplx_export`: офлайн-регенерация из сырого JSON, конвейер перестроения связей, обратное заполнение обогащения индекса, конечный автомат удаленного удаления и цепочка обнаружения answer_variants. Разделы сохраняют свою исходную нумерацию из [обзора архитектуры](overview.md).

---

<a id="offline-regeneration-re-render" data-pplx-source-anchor="true"></a>
## Офлайн-регенерация (повторный рендеринг)

После исправлений слоя рендеринга регенерировать все артефакты из сырого JSON **с нулевым сетевым доступом**, идемпотентно. Реализация: `commands/rerender_cmd.py` (однопоточный `rerender` rerender_cmd.py:105-190; пакетный `cmd_rerender` rerender_cmd.py:193-212).

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

Дисциплина:

- **Нулевой сетевой доступ**: `PerplexityAdapter(None)` использует только чистые методы сборки данных; ни один онлайн-метод (get_thread и т.д.) никогда не вызывается.
- **Идемпотентность**: артефакты зависят только от сырых данных + рендерера; повторные запуски дают побайтово идентичные результаты (гарантируется регрессионными тестами снимков, [§13](../development/testing-architecture.md)).
- **Другие файлы не затрагиваются**: исходники, report.md, ассеты остаются без изменений; thread.json по умолчанию не изменяется — с `--thread-json` добавляются или удаляются только два ключа interruptions / answer_variants.
- `--dry-run` только перечисляет каталоги без записи файлов (rerender_cmd.py:204-206); `--limit N` берет первые N.

---

<a id="relations-offline-rebuild-pipeline" data-pplx-source-anchor="true"></a>
## Конвейер офлайн-перестроения связей

`cmd_relations` (misc_cmd.py:16) перестраивает граф связей бесед всей библиотеки из архивных сырых данных **с нулевым сетевым доступом**: он повторно использует конвейер офлайн-перестроения повторного рендеринга `load_archived_conversation` (rerender_cmd.py:34) для восстановления каждой беседы (разбор/сортировка/нумерация поворотов, прикрепление _plain/_blocks), заполняет `conv.sub_agents` на уровне беседы через `adapter.sub_agents` поток за потоком (misc_cmd.py:70-73; конвейер экспорта не заполняет это поле, models.py:178-182); запасной вариант ответа компьютера (`wf_block_answer`) обратно заполняет `turn.answer` на этом уровне, расширяя область сканирования ссылок (misc_cmd.py:74-79). Потоки без сырых данных деградируют до оболочки thread.json + conversation.md (могут быть обнаружены только ребра same_space / bare-uuid, misc_cmd.py:61-66).

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

Дисциплина принятия решений (2026-07-23): механизм `branch_of` подтвержден, но не имеет экземпляров в архиве — ребра не построены; `related_query` не может быть извлечен из существующих данных — ребра также не построены: лучше пропустить ребро, чем построить предположительное.
Наблюдаемый масштаб: 772 ребра / 21 кластер по всему архиву (same_space 559 / subagent_of 154 / same_prompt 49 / references 10).

---

<a id="search-mode-backfill-index-search_mode-enrichment" data-pplx-source-anchor="true"></a>
## search-mode-backfill (обогащение индекса search_mode)

`cmd_search_mode_backfill` (search_mode_backfill_cmd.py:81) обогащает авторитетное поле платформы `search_mode` в `index/library_<account>.json`: **сначала локальные сырые данные** (для архивных потоков извлекается из `entries[].search_mode` файла raw_entries.json, нулевой сетевой доступ); только потоки без локальных сырых данных прибегают к онлайн-загрузке потока. Запись объединяет и сохраняет существующие поля индекса (семантика обновления: ключи обогащения перезаписываются, все остальное сохраняется), идемпотентно и возобновляемо, с `--limit` для подмножеств.
Обогащенные строки индекса делают фильтр `--mode` пакетного режима авторитетным: `index_row_matches_mode` (batch_cmd.py:46) судит сначала по search_mode индекса (SEARCH_MODE_MAP, normalize.py:50), прибегая к эвристикам только когда он отсутствует.

---

<a id="sync-deleted-remote-deletion-state-machine" data-pplx-source-anchor="true"></a>
## sync-deleted конечный автомат удаленного удаления

`cmd_sync_deleted` (sync_deleted_cmd.py:262) идентифицирует потоки, "удаленные пользователем/удаленно на стороне платформы", и записывает конечное состояние, наряду с expired. Определение кандидата — это **разность объединения всех учетных записей индексов**: архивный ok-поток считается кандидатом только когда он исчез из **всех** файлов `index/library_*.json` (поток export_via из разных учетных записей появляется только в индексе своего владельца, поэтому разность одной учетной записи дала бы ложное срабатывание; find_candidates, sync_deleted_cmd.py:148); отсутствующие/нечитаемые индексы безопасно пропускаются с записью причины. По умолчанию офлайн-пробный запуск только перечисляет кандидатов (без сети, без изменений файлов); `--online` проверяет поток за потоком с помощью GET: `ENTRY_DELETED` / `ENTRY_EXPIRED` / 404 → удаление подтверждено, `state.mark_deleted` (state.py:136) + надгробие thread.json (mark_thread_json_remote_deleted, sync_deleted_cmd.py:215).

```mermaid
stateDiagram-v2
    [*] --> ok : archived (batch_state = ok)
    ok --> candidate : gone from the union of all account indexes<br/>(find_candidates, sync_deleted_cmd.py:148)
    candidate --> skipped : index missing/unreadable<br/>safely skipped, reason recorded
    candidate --> listed : offline dry-run lists only<br/>(no network, no file changes)
    listed --> deleted : --online verifies one by one<br/>ENTRY_DELETED / ENTRY_EXPIRED / 404<br/>(_confirm_deleted, sync_deleted_cmd.py:247)
    deleted --> [*] : terminal mark_deleted (state.py:136) + thread.json tombstone<br/>plan_incremental trims it like expired<br/>(incremental.py:74-75, 84)
```

Наслоение типов ошибок: `EntryDeletedError` наследует `EntryExpiredError` (проверка на 400 с телом, содержащим ENTRY_DELETED, выполняется до ENTRY_EXPIRED, cookie_transport.py:93-98); пакетный режим должен перехватывать подкласс перед родителем (batch_cmd.py:163-174 перед 175-183), иначе удаленное будет ошибочно записано как expired. Сам API удаления: `DELETE /rest/thread/delete_thread_by_entry_uuid` (read_write_token берется из первого непустого `entries[].read_write_token`; проверено на практике: 10/10 удалений успешны на самостоятельно созданных тестовых потоках и потоках BOT-space).

---

<a id="the-answer_variants-answer-rewrite-variant-detection-chain" data-pplx-source-anchor="true"></a>
## Цепочка обнаружения вариантов ответа answer_variants

Варианты, замененные в рамках "перезаписи ответа / A-B экспериментов" платформы, невидимы на стороне API — выбранный ответ виден, в то время как проигравший собрат оставляет только след в `entries[].side_by_side_metadata` и может быть удален платформой (мертвые ссылки собратьев доказаны: 403 VIEW_THREAD_NOT_ALLOWED + SPA-редирект на домашнюю страницу; см. [справочник API §5.2](../reference/api/api-responses-errors.md)). Цепочка обнаружения делает "произошла перезапись" наблюдаемым и отслеживаемым:

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

- **Суженные критерии**: принимаются только авторитетные сигналы side_by_side_metadata; записываются полные поля локализации (полный uuid потока + uuid8, заголовок, entry_uuid, sibling_uuid, selection_status, experiment_role) плюс руководство по обработке; формат в `format_detection` (variant_log.py:53).
- **Идемпотентность**: jsonl дедуплицируется по (web_uuid, entry_uuid); дублирующиеся регистрации из онлайн-пути (source=online) и офлайн-пути (source=offline) не создают дублирующихся строк; повторный рендеринг предупреждает только при изменении содержимого варианта, так что библиотечные повторные запуски не засоряют.
- **Поток обработки**: при обнаружении вручную подтвердить альтернативный ответ как можно скорее и записать его (альтернатива может быть удалена платформой и не может быть восстановлена через API); полный поток описан в [справочнике API §5.2](../reference/api/api-responses-errors.md).
