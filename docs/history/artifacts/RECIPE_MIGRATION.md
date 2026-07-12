# Legacy subtype recipe migration

`src/main.js`의 `ASSET_FAMILY_SUBTYPES` 32개를 새 recipe registry에 정확히 한 번씩 분류한 기록입니다. 이 문서는 기존 메뉴가 실제 지원 범위보다 넓어 보이는 문제를 줄이기 위한 migration 기준이며, `production`은 구현 완료가 아니라 검증 대상으로 채택된 canonical 진입점이라는 뜻입니다. 현재 recipe readiness는 모두 `contract_only`입니다.

## 분류 원칙

- `production`: Golden Job이 있는 recipe의 canonical legacy transport만 유지합니다.
- `alias`: 별도 생성 파이프라인이 필요 없고 동일 recipe의 의미상 variant로 안전하게 정규화되는 항목만 사용합니다.
- `lab`: 품질 검증이나 출력 계약이 부족한 항목입니다. Production 메뉴에는 노출하지 않고 실험 영역에 둡니다.
- `retired`: 제거 근거가 확인된 항목에만 사용합니다. 현재는 근거가 없어 0개입니다.

분류 결과는 Production 4개, alias 6개, Lab 22개, retired 0개입니다. `tile.autotile`은 대응 Lab recipe가 있지만 Golden Job이 없어 승격하지 않았습니다. UI icon은 정적 이미지처럼 보이더라도 UI 크기·가독성 계약이 object Golden Job과 달라 임의 alias 처리하지 않았습니다.

## 32개 migration map

| Legacy subtype | 분류 | Recipe | Variant | Action | 근거 |
| --- | --- | --- | --- | --- | --- |
| `sprite.character` | production | `actor-animation` | `character` | `use_recipe` | Actor recipe의 canonical transport |
| `sprite.monster` | alias | `actor-animation` | `monster` | `normalize_alias` | 동일한 identity/direction/action-beat pipeline 사용 |
| `sprite.npc` | alias | `actor-animation` | `npc` | `normalize_alias` | 동일한 identity/direction/action-beat pipeline 사용 |
| `sprite.effect` | production | `vfx-sequence` | `effect` | `use_recipe` | VFX recipe의 canonical transport |
| `tile.floor` | lab | — | — | `keep_lab` | topology/seam 검증 없음 |
| `tile.wall` | lab | — | — | `keep_lab` | topology/seam 검증 없음 |
| `tile.corner` | lab | — | — | `keep_lab` | adjacency 검증 없음 |
| `tile.door` | lab | — | — | `keep_lab` | passage connectivity 검증 없음 |
| `tile.terrain` | lab | — | — | `keep_lab` | terrain transition 검증 없음 |
| `tile.decal` | lab | — | — | `keep_lab` | overlap/export semantics 검증 없음 |
| `tile.autotile` | lab | `tile-autotile` | `autotile` | `keep_lab` | 대응 recipe는 있으나 Golden Job 없음 |
| `tile.tileset` | lab | — | — | `keep_lab` | composition/importer metadata 검증 없음 |
| `ui.main_panel` | lab | — | — | `keep_lab` | slicing/resizing 검증 없음 |
| `ui.inner_panel` | lab | — | — | `keep_lab` | slicing/resizing 검증 없음 |
| `ui.popup` | lab | — | — | `keep_lab` | composition/scalable layout 검증 없음 |
| `ui.card` | lab | — | — | `keep_lab` | composition/scalable layout 검증 없음 |
| `ui.button` | production | `ui-component` | `button` | `use_recipe` | UI button Golden Job 있음 |
| `ui.slot` | lab | — | — | `keep_lab` | state/item layout 검증 없음 |
| `ui.badge` | lab | — | — | `keep_lab` | readability/state 검증 없음 |
| `ui.hud_chip` | lab | — | — | `keep_lab` | readability/layout 검증 없음 |
| `ui.gauge` | lab | — | — | `keep_lab` | fill/state 검증 없음 |
| `ui.icon` | lab | — | — | `keep_lab` | UI 전용 sizing/readability 검증 없음 |
| `ui.cursor` | lab | — | — | `keep_lab` | hotspot/animation/state 검증 없음 |
| `object.item` | production | `static-transparent-object` | `item` | `use_recipe` | Static object Golden Job의 canonical transport |
| `object.equipment` | alias | `static-transparent-object` | `equipment` | `normalize_alias` | 단일 투명 object의 의미상 variant |
| `object.weapon` | alias | `static-transparent-object` | `weapon` | `normalize_alias` | 단일 투명 object의 의미상 variant |
| `object.loot` | alias | `static-transparent-object` | `loot` | `normalize_alias` | 단일 투명 item의 의미상 variant |
| `object.furniture` | lab | — | — | `keep_lab` | footprint/ground/scale 검증 없음 |
| `object.machine` | lab | — | — | `keep_lab` | state/interaction 검증 없음 |
| `object.prop` | alias | `static-transparent-object` | `prop` | `normalize_alias` | 비상호작용 단일 world object variant |
| `object.interactable` | lab | — | — | `keep_lab` | interaction states/metadata 검증 없음 |
| `object.destructible` | lab | — | — | `keep_lab` | damage/destruction states 검증 없음 |

## UI 전환 규칙

Production 화면은 canonical 4개 recipe만 직접 보여주고 alias는 별도 메뉴로 늘리지 않습니다. 기존 프로젝트를 열 때 alias는 해당 recipe와 `variant`로 정규화합니다. Lab 항목은 기존 draft를 읽기 위해 registry에 남기되, 해당 vertical slice와 Golden Job이 통과하기 전까지 Production 메뉴에서 숨깁니다. 제거 근거가 생긴 경우에만 `retired/remove`로 바꾸며, 그 변경은 migration test와 사용자 데이터 호환 정책을 함께 갱신해야 합니다.
