---
translation_kind: "machine"
translation_source_locale: "zh-CN"
translation_source_path: "docs/guide/incremental-sync.zh-CN.md"
translation_source_sha256: "ca6b70d4ac1b77d992fbc2d801238b670a1652dcf4ffc577e52d3f09fd404fee"
translation_model: "deepseek-v4-flash"
translation_prompt_version: "v1"
---

<a id="增量同步" data-pplx-source-anchor="true"></a>
# 증분 동기화

`pplx-export batch`는 고빈도 실행을 위해 설계되었습니다: 각 라운드마다 새로 추가되거나 변경된 대화만 내보내고, 중단된 실행으로 인한 간격을 자동으로 복구하며, 플랫폼에서 이미 내려간 스레드를 절대 다시 건드리지 않습니다. "무엇이 내보내졌는가"의 유일한 권위 있는 출처는 `index/batch_state.json`(`BatchState`, `pplx_export/core/state.py:63`)이며, 스레드 하나를 내보낼 때마다 업데이트됩니다—별도의 섀도 복사본을 유지하지 않습니다.

<a id="前置条件与基本用法" data-pplx-source-anchor="true"></a>
## 전제 조건 및 기본 사용법

```bash
pplx-export index --account alice   # 先刷新 index/library_alice.json
pplx-export batch --account alice   # 增量导出（早停 + 断点续跑）
```

인덱스가 없으면 `batch`는 실행을 거부합니다(`pplx_export/commands/batch_cmd.py:79-81`).
`--limit N`와 `--mode <mode>`는 계획 수립 전에 인덱스 행을 필터링합니다. `entryUUID`가 누락된 잘못된 행은 경고만 하고 건너뛰며, 전체 실행이 중단되지는 않습니다(`batch_cmd.py:95-100`).

<a id="增量计划如何工作" data-pplx-source-anchor="true"></a>
## 증분 계획의 작동 방식

1. **정렬.** 인덱스 행은 `lastUpdated` 기준으로 최신순으로 정렬됩니다(`batch_cmd.py:89`).
   완전히 새로운 대화와 "이어지는 이전 대화"(`lastUpdated`가 새로워져 위치가 위로 이동)는 모두 상단에 배치됩니다—
   이 순서는 조기 중단 안전성의 전제 조건입니다.
2. **분류.** `plan_incremental`(`pplx_export/hooks/incremental.py:36-87`)
   —`batch`와 `schedule`가 공유하는 순수 함수—는 각 행에 정확히 하나의 동작을 할당합니다:

   | 동작 | 조건 | batch 처리 |
   |---|---|---|
   | `new` | `batch_state`에서 해당 uuid를 본 적이 없음 | 내보내기 |
   | `updated` | `lastUpdated`가 기록된 값과 다르거나 `--force`가 있음 | 다시 내보내기 |
   | `done` | 상태가 `ok`이고 `lastUpdated`가 변경되지 않음 | 건너뛰기 |
   | `expired` | 이전 내보내기에서 플랫폼이 `ENTRY_EXPIRED`을 반환함 | 건너뛰기—최종 상태, 재시도 안 함 |
   | `deleted` | `sync-deleted`가 원격 삭제를 확인함 | 건너뛰기—최종 상태, 재시도 안 함 |

3. **조기 중단.** 기본값(`--full`도 `--force`도 없음)은 가장 긴 최종 상태 연속 구간(`done` / `expired` / `deleted`)을 꼬리에서 잘라내며, 잘라낸 개수는 `n_stopped`로 기록됩니다(`incremental.py:83-87`). 목록이 최신순이므로, 변경되지 않은 항목 아래에는 반드시 더 오래되고 변경되지 않은 항목만 있습니다—계속 스캔하는 것은 시간 낭비입니다.

   ```mermaid
   flowchart TD
       IDX["library 索引行<br/>按 lastUpdated 从新到旧排序"] --> PLAN["plan_incremental"]
       PLAN --> NEW["new → 导出"]
       PLAN --> UPD["updated → 重导"]
       PLAN --> DONE["done → 跳过"]
       PLAN --> TERM["expired / deleted → 跳过（终态）"]
       DONE --> STOP["早停：截掉尾部终态连续段"]
       TERM --> STOP
   ```

4. **실행.** 스레드를 내보낼 때마다 즉시 표시(`mark_ok` / `mark_error` /
   `mark_expired` / `mark_deleted`)하고, 각 항목 후에 상태 파일을 디스크에 기록합니다
   (`batch_cmd.py:154-201`); `KeyboardInterrupt`도 먼저 저장한 후 위로 전파합니다
   (`batch_cmd.py:158-161`). 쓰기는 원자적입니다—임시 파일에 `os.replace` 사용
   (`state.py:145-152`)—중단이 잘린 JSON을 남기지 않습니다.

<a id="中断后的缺口修复" data-pplx-source-anchor="true"></a>
## 중단 후 간격 복구

조기 중단은 절대 간격을 묻지 않습니다. 실패(상태 `error`)했거나 차례가 오지 않은 스레드는 최종 상태 접미사 **위**에 있으며, 다음 라운드에서 `updated` / `new`로 다시 계획되어 조기 중단 지점에 도달하기 전에 내보내집니다(`incremental.py:12-14`, `batch_cmd.py:206-208`). 항목별 디스크 기록과 결합하여, batch 실행은 언제든지 중단될 수 있으며 다시 실행하기만 하면 됩니다.

`batch_state.json` 자체가 손상된 경우, 조용히 비워지지 않습니다: 원본 파일의 이름이 `batch_state.json.corrupt-<timestamp>`로 변경되며, 기록된 최종 상태는 손실되지 않고 불필요한 재시도가 발생하지 않습니다(`state.py:68-81`).

<a id="-full-与-force" data-pplx-source-anchor="true"></a>
## `--full`와 `--force`

| 옵션 | 효과 | 최종 상태 | 적용 시나리오 |
|---|---|---|---|
| *(기본값)* | 꼬리 최종 상태 연속 구간에서 조기 중단 | 건너뛰기 | 매일 정기/예약 실행 |
| `--full` | 전체 스캔, 조기 중단 안 함; 변경되지 않은 스레드는 여전히 `done`에 따라 건너뜀 | 건너뛰기 | 정기적인 안전망, 또는 아카이브에 간격이 의심될 때 |
| `--force` | 변경되지 않은 스레드를 포함하여 모두 다시 내보내기 | 여전히 제외—재시도 안 함 | 파이프라인 수리 후 raw 데이터를 다시 가져와야 할 때 |

최종 상태가 `--force`에 의해 제외되는 것은 의도적입니다: 만료되었거나 원격에서 삭제된 스레드를 재시도하는 것은 요청과 백오프 예산만 낭비합니다(`batch_cmd.py:120-127`).

참고: [`status`](maintenance-commands.md#status): 네트워크를 사용하지 않는 출력 상태 장부와 동일한 `plan_incremental` 의미론으로 계산된 변경 계획(new/updated/조기 중단 수).

`lastUpdated` 비교는 소수 초 부분의 후행 0을 제거합니다(`.18033Z`와 `.180330Z`는 동일하게 판단; `state.py:23-55`). 플랫폼이 가끔 후행 0을 누락하기 때문입니다—정확한 문자열 비교는 "변경됨"으로 잘못 판단하여 중복 내보내기를 유발할 수 있습니다.

<a id="终态expired-与-deleted" data-pplx-source-anchor="true"></a>
## 최종 상태: `expired`와 `deleted`

| | `expired` | `deleted` |
|---|---|---|
| 의미 | 플랫폼이 해당 스레드를 제거함(약 3개월 보존 기간); 내보내기 시도가 `ENTRY_EXPIRED` 반환 | 사용자/원격 삭제, `sync-deleted`를 통해 확인됨 |
| 기록자 | `batch` 자체(`mark_expired`, `state.py:131-134`) | `pplx-export sync-deleted --online`(`mark_deleted`, `state.py:136-143`) |
| 재시도? | 절대 안 함—`--force`도 안 함 | 절대 안 함—`--force`도 안 함 |
| 증거 | `ENTRY_EXPIRED` 응답 | `note` 필드: 인덱스에서 사라짐 + `GET /rest/thread/<uuid>` → `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 |

<a id="sync-deleted确认远端删除" data-pplx-source-anchor="true"></a>
### sync-deleted: 원격 삭제 확인

```bash
pplx-export sync-deleted --account alice            # 离线 dry-run：只列候选
pplx-export sync-deleted --account alice --online   # 逐候选在线验证
```

1. **후보 판정(오프라인, 네트워크 없음).** `batch_state`에서 상태가 `ok`인 스레드 중, **모든** `index/library_*.json` 계정 인덱스의 `entryUUID` 합집합에서 사라진 경우, 원격 삭제 의심 후보가 됩니다(`pplx_export/commands/sync_deleted_cmd.py:148-212`).
   계정 간 합집합이 필요합니다: `bob`가 소유하고 공유 공간을 통해 `alice`가 내보낸 스레드는 `alice` 자신의 인덱스에 절대 나타나지 않습니다—단일 계정 diff는 이 모든 스레드를 잘못 보고합니다. 모든 인덱스를 사용할 수 없는 경우, 후보는 모두 안전하게 건너뛰고 그 이유를 정직하게 기록합니다.
2. **기본 dry-run.** `--online`가 없으면 후보만 나열—네트워크 연결 없음, 파일 변경 없음.
3. **`--online` 확인.** 각 후보에 대해 `GET /rest/thread/<uuid>`를 수행하며, 후보의 `thread.json`에 있는 `export_via` 계정을 사용합니다(cookie 자동 전환):

   | 결과 | 처리 |
   |---|---|
   | `ENTRY_DELETED` / `ENTRY_EXPIRED` / HTTP 404 | 확인: `batch_state`가 최종 상태 `deleted`로 표시(`note`에 이유 기록), 각 스레드 디렉토리의 `thread.json`에 `remote_deleted` 타임스탬프를 제자리에 추가 |
   | 스레드가 여전히 존재함 | 오보: 정직하게 보고(인덱스가 완전히 새로고침되지 않았을 수 있음—`index` 재실행 후 재확인), 상태 변경 안 함 |
   | 5xx / 네트워크 오류 | 상태 변경 안 함, 다음 라운드로 넘김 |
   | 연속 3회 401/403 | fail-fast 중단—cookie 만료 시 백오프가 자가 치유되지 않으며, 빈 회전이 활성 스레드를 잘못 표시할 수 있음(`sync_deleted_cmd.py:333-337`) |

   확인 표시는 항목별로 디스크에 기록됩니다: `--online` 실행이 중단되어도 확인된 항목이 손실되지 않으며, 재실행은 멱등적입니다(`sync_deleted_cmd.py:254-256`).

<a id="墓碑原则" data-pplx-source-anchor="true"></a>
## 툼스톤 원칙

!!! warning "로컬 아카이브는 절대 삭제하지 않음"
    이 저장소는 내보낸 대화의 백업 아카이브(backup of record)입니다. `sync-deleted`는 오직
    "식별 + 표시"(tombstone)만 수행합니다: **어떤 아카이브 파일도 절대 삭제하거나 이동하지 않습니다.** 확인은 두 곳만 변경합니다—`batch_state`의 상태와 `thread.json`의 하나의 표시 키:

    ```json
    "remote_deleted": "2026-07-23T10:20:30Z"
    ```

    이 표시는 멱등적입니다: 이미 `remote_deleted` 키가 있으면 다시 쓰지도 않고 원래 시간을 덮어쓰지도 않습니다(`sync_deleted_cmd.py:215-244`).

<a id="幂等与离线重渲" data-pplx-source-anchor="true"></a>
## 멱등성 및 오프라인 재렌더링

- 인덱스가 변경되지 않은 상태에서 `batch`를 다시 실행하면 아무것도 내보내지 않습니다: 모든 행이 `done`로 분류되고 실행이 조기 중단 지점에서 멈춥니다.
  상태 쓰기는 원자적이며, 표시는 스레드별로 이루어지며, 삭제 확인을 반복해도 `remote_deleted`가 중복으로 기록되지 않습니다.
- 아카이브는 raw API 페이로드(`raw_entries.json` / `raw_blocks.json`)를 저장하므로, 렌더링 결과물은
  언제든지 네트워크 없이 재생성할 수 있습니다:

  ```bash
  pplx-export re-render                 # 全量重建 conversation.md + turns/
  pplx-export re-render --dry-run       # 只列出将处理的线程目录
  pplx-export re-render --thread-json   # 同时同步 interruptions / answer_variants 键
  ```

  `re-render`는 현재 렌더러로 raw JSON을 다시 파싱합니다
  (`pplx_export/commands/rerender_cmd.py:105-190`): `conversation.md`와
  `turns/turn_*.md`를 다시 쓰고, 현재 라운드 번호보다 높은 번호의 잔여 라운드 파일을 삭제하며, sources, assets,
  `report.md`와 `thread.json`는 그대로 둡니다. 렌더링 계층 수정은 이렇게 제로 요청으로 전체 아카이브에 적용됩니다.

<a id="另见" data-pplx-source-anchor="true"></a>
## 참고

- [pplx-export.md](pplx-export.md) — `batch` 전체 명령어 참조(`--mode`, `--limit`, 간격 매개변수)
- [maintenance-commands.md](maintenance-commands.md) — `sync-deleted`, `re-render` 및 각 backfill 명령어
- [archive-layout.md](archive-layout.md) — `batch_state.json`와 `thread.json`의 위치
- [rate-limiting.md](rate-limiting.md) — 스레드 간격, 백오프, 인증 fail-fast
- [../architecture/export-pipeline.md](../architecture/export-pipeline.md) — 전체 내보내기 파이프라인
- [../architecture/offline-operations.md](../architecture/offline-operations.md) — 오프라인 재구축 파이프라인 상세
- [../architecture/rate-limiting-errors.md](../architecture/rate-limiting-errors.md) — 오류 분류 및 최종 상태 처리
