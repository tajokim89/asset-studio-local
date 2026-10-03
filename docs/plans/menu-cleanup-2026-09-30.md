# 메뉴 정리 계획 — 2026-09-30

- 범위: index.html, styles/app.css, 작은 navigation 스크립트와 회귀 테스트.
- 기존 동작 잠금: test_motion_studio_static.py + test_ai_first_mode_shell_static.py, 수정 전 50개 통과(리더 실행).
- 불필요한 상시 노출: 메인 메뉴를 이미지 편집 / 애니메이션 / 결과로 정리하고 모션과 3D는 고급 도구에 둔다.
- 중복 방지: 기존 스프라이트 도구와 결과 DOM을 이동해 재사용한다. ID, 이벤트, 생성 엔진은 유지한다.
- 상단 밀도: 캔버스 크기/보기와 프로젝트 작업을 접이식 메뉴로 묶고 가져오기/내보내기/실행취소를 유지한다.
- 검증: 메뉴 전환 시 레이어/도구 상태 보존, 고급 작업공간 전환, 결과 복귀, 기본 테스트와 JS 구문 확인. 브라우저 시각 확인은 리더가 수행한다.

## 추가 정리 — AI 생성 패널

- 기준 검증 52개 통과 상태에서 두 번째 패스를 진행한다.
- 처음에는 종류/세부 유형, 요청 입력과 기본 생성 버튼만 보여준다.
- 스타일, 가족별 세부 설정, 출력 설정은 기본 닫힌 details 3개로 묶는다.
- 기존 ID와 가족별 hidden 토글을 그대로 유지하도록 원래 섹션을 감싼다.
- 참고 이미지 생성, 배치/자동 처리, QA는 세부 설정 안에 보존한다.
- 생성 버튼은 요청 바로 아래 배치하고 닫힌 details의 후손이 아님을 회귀 검사한다.

## 승인된 재구성 — 로컬 영상 생성

- 모션/3D 작업공간의 HTML, 로딩 스크립트/스타일, 메뉴를 실제 앱에서 제거한다. 사용자 모델/출력 파일은 삭제하지 않는다.
- 세 가지 작업공간과 세 가지 생성 유형(스프라이트/UI/오브젝트)만 남긴다.
- 스프라이트는 선택 레이어를 요청 시점에 이미지로 저장하고 H3 전용 비동기 작업으로 보낸다. 무참조 생성과 기존 walk 우회 분기는 사용하지 않는다.
- 직접 편집 가능한 최종 프롬프트와 선택적 Wizard, 모델/길이/프레임/FPS를 제공한다.
- UI/오브젝트는 자유 프롬프트 그대로 전달한다. 구 프로젝트 호환 DOM은 숨기고 새 요청에서 제외한다.
- 결과는 기존 결과 저장/채택 흐름과 프레임 미리보기를 재사용한다. 유료 생성 없이 요청/응답 mock과 구문 검사를 수행한다.

### 제거된 통합의 테스트 교체

다음 UI 존재 전제 테스트는 제거 확인 테스트로 교체했다. 독립 모듈 테스트는 보존한다.
- tests/test_motion_studio_static.py:test_directional_movement_exposes_compact_distance_speed_and_once_or_roundtrip_controls
- tests/test_motion_studio_static.py:test_motion_quick_direction_buttons_cover_all_eight_compass_directions
- tests/test_motion_studio_static.py:test_motion_quick_presets_offer_one_click_preview_and_explicit_apply_cancel
- tests/test_motion_studio_static.py:test_motion_playback_uses_the_existing_editor_canvas_without_a_duplicate_preview_canvas
- tests/test_motion_studio_static.py:test_layered_2d_rig_ui_uses_editor_layers_and_can_bake_a_sprite_sheet
- tests/test_motion_studio_static.py:test_motion_mode_keeps_editor_canvas_visible_and_exposes_only_simple_controls
- tests/test_motion_studio_static.py:test_motion_workspace_uses_shared_editor_image_layers_as_primary_source
- tests/test_motion_studio_static.py:test_korean_first_three_column_accessible_workspace_contract
- tests/test_motion_studio_static.py:test_motion_workspace_integrates_after_existing_workspace_and_load_order
- tests/test_3d_pixel_pipeline.py:test_pipeline_strict_qa_card_and_copy_are_present
- tests/test_3d_pixel_pipeline.py:test_pipeline_keeps_local_comfy_boundary_truthful_and_calls_real_generation
- tests/test_3d_pixel_pipeline.py:test_all_eight_directions_and_manual_review_checks_are_explicit
- tests/test_3d_pixel_pipeline.py:test_chairman_front_idle_is_the_one_click_sample_with_approved_pixel_result
- tests/test_3d_pixel_pipeline.py:test_real_glb_viewer_exposes_camera_gizmo_and_numeric_xyz_controls
- tests/test_3d_pixel_pipeline.py:test_model_import_rig_pose_pixelization_and_review_controls_are_present
- tests/test_3d_pixel_pipeline.py:test_pipeline_exposes_the_six_required_production_gates_in_order
- tests/test_3d_pixel_pipeline.py:test_pipeline_workspace_is_integrated_as_a_third_top_level_workspace

## 일반 이미지 생성 추가

- 첫 탭과 기본 모드를 image/image로 추가하고 자유 프롬프트를 그대로 Hermes로 전달한다.
- 일반 이미지는 제공자 원본 해상도/알파를 보존하며 강제 도트화·배경 제거·512 리사이즈를 하지 않는다.
- 결과/프로젝트 가족 검증에 image를 추가하고 기존 네 가족 프로젝트를 기본 image 초안으로 안전하게 이행한다.
- 이미지 생성 결과를 새 선택 레이어로 채택하는 기존 동작을 유지하여 바로 스프라이트 원본으로 사용할 수 있게 한다.
- 활성 생성/미리보기 기본 프레임을 25로 맞추고 숨겨진 레거시 UI 동기화가 사용자의 그리드 값을 덮어쓰지 않도록 막는다. 숨긴 레거시 4/8프레임 계약 자체는 구 프로젝트용으로 보존한다.
- 유료 호출 없이 제공자 mock, 프로젝트 검증, 실제 프런트엔드 요청 함수 및 기본값 회귀 테스트로 확인한다.

## 명시적 기준 이미지 고정 — 2026-10-01

- 이미지 생성 탭에서 사용자가 ‘선택 레이어를 기준으로 지정’을 누를 때만 전체 이미지 바이트·이름·크기를 복사한다.
- 선택 변경, 레이어 삭제, 업로드, 가족 전환은 고정된 기준에 영향을 주지 않는다. 기준 변경/해제는 각각 명시적 버튼으로만 수행한다.
- 기준은 선택 사항이며 없으면 기존 텍스트 생성으로 동작한다. 마스크/영역은 입력에 포함하지 않는다.
- 세션 내 기준을 유지하고, 결과 기록에는 고정 당시 설명과 서버의 영구 원본 URL을 기록한다. 프로젝트 파일에 큰 base64 전용 스키마를 추가하지 않는다.
- 기준 A 고정 후 B 선택/삭제, 명시적 변경, 해제, 동일 바이트 전달과 새 레이어 결과 동작을 네트워크 없는 테스트로 잠근다.

## 캐릭터 액션 전용 작성기

- 주 화면은 ‘캐릭터 액션 만들기’와 ‘직접 프롬프트 입력’ 두 진입점만 제공한다.
- 기본/근접/원거리/방패 그룹별 문맥 설정과 장비 유효 조합을 별도 모달에서 선택한다. 기존 자유 작성기 DOM/API는 호환용으로 보존하되 새 진입점에서는 노출하지 않는다.
- 액션별 손 역할·캐릭터 기준 경로·체중 이동과 서로 다른 단계 시간을 순수 함수로 구성한다. 발사/장전 문구는 서로 충돌하지 않게 분리한다.
- 가져오기는 편집 가능한 최종 프롬프트만 변경한다. 사용자가 실제로 편집한 기존 문장만 확인하며 자동 생성 호출은 없다.
- 기본25프레임, 고정 기준 이미지 및 생성 전달 경로는 변경하지 않는다. 새 순수 함수/컨트롤 테스트와 기존 회귀 검사를 수행한다.
