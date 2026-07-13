# 최소 제작비로 움직임 효과를 만드는 2D 스프라이트 방법론 조사

- 조사일: 2026-07-13 KST
- 조사 범위: Reddit, DCInside, 루리웹, OpenAI Community, Hacker News, Godot Forum, itch.io 및 공개 개발 블로그
- 문서 성격: 공개 웹에서 확인된 사례와 그 사례들로부터 도출되는 일반 방법론 정리
- 제외 범위: Asset Studio 적용 설계, 프로젝트별 채택안, 캐릭터별 제작안, 특정 방법의 도입 결정

---

## 1. 조사 목적

2D 게임에서 걷기·공격 같은 전통적인 프레임 애니메이션을 모든 캐릭터와 방향에 대해 제작하지 않고도, 적은 수의 원본 이미지와 엔진 변환·부분 애니메이션·VFX를 이용해 충분한 움직임과 피드백을 만드는 방법을 조사했다.

이번 조사는 다음 질문에 초점을 맞췄다.

1. 단일 이미지 또는 제한된 프레임으로 이동감을 만들 수 있는가?
2. 캐릭터 전체가 아니라 일부 요소만 움직여도 동작이 전달되는가?
3. 위치·회전·스케일·트윈·파티클 같은 엔진 기능이 프레임 애니메이션을 얼마나 대체할 수 있는가?
4. 차량·좌석·부유체 등 이동 수단이 복잡한 캐릭터 동작을 줄이는 데 어떤 역할을 하는가?
5. AI 이미지 모델과 이미지→비디오 모델은 게임용 스프라이트 애니메이션에서 어떤 한계를 보이는가?
6. 국내외 개발 커뮤니티에서 반복적으로 확인되는 작업량 절감 원리는 무엇인가?

---

## 2. 조사 및 판정 방법

### 2.1 검색 범주

검색어를 다음 범주로 나눠 조사했다.

- 단일 스프라이트: `single sprite animation`, `one frame idle`, `single image bobbing`
- 엔진 변환: `sprite wobble`, `squash stretch movement`, `tween sprite scale`, `procedural sprite animation`
- 부유·차량: `hover bob sprite`, `vehicle seat animation`, `vehicle enter animation shortcut`
- 부분 애니메이션: `static layer animation`, `mesh deformation sprite`, `inverse kinematics pixel art`
- VFX 대체: `particles vs sprite animation`, `VFX movement feedback`, `single sprite effect scaling`
- AI 스프라이트: `AI sprite sheet repeated poses`, `pixel animation consistency`, `image to video sprite failure`
- 한국어 검색: `스프라이트 한장 애니메이션`, `도트 프레임 작업량`, `트윈 스케일 애니메이션`, `스파인 프레임 애니메이션`, `움직임 없는 레이어`

### 2.2 증거 구분

각 자료는 다음 세 종류로 구분했다.

- **직접 사례:** 작성자가 실제 구현 방식이나 결과를 설명한 경우
- **직접 논의:** 개발자가 특정 문제와 해결법을 구체적으로 논의한 경우
- **일반화된 결론:** 여러 직접 사례에서 공통적으로 나타난 원리를 정리한 것

특정 프로젝트에서 무엇을 써야 한다는 선택이나 권고는 이 문서에 포함하지 않는다.

### 2.3 접근 한계

- Reddit와 DCInside는 직접 페이지 접근, 검색 인덱스 노출, 삭제 여부에 따라 확인 범위가 달라질 수 있다.
- 일부 Reddit 인용은 공개 검색 인덱스와 게시물 메타데이터를 대조해 확인했다.
- DCInside는 검색엔진에 공개적으로 노출된 본문·메타 설명을 중심으로 확인했다.
- 비공개 카페, 로그인 전용 게시물, 삭제 게시물은 포함하지 않았다.
- 검색 상단에 나타난 사례가 전체 커뮤니티의 다수 의견을 대표한다고 간주하지 않았다.
- ‘애니메이션 제작비를 줄이려고 차량으로 하체를 가렸다’고 개발자가 직접 명시한 강한 공개 사례는 이번 조사에서 확인하지 못했다. 차량·좌석 사례에서 직접 확인된 것은 승하차 생략, 좌석 부착, 차량 본체와 효과의 분리까지다.

---

## 3. 방법론 A: 단일 이미지의 상하 바빙

### 3.1 Reddit 사례

**출처:** r/gamemaker, 「Is this the best way to achieve a bobbing effect?」
https://www.reddit.com/r/gamemaker/comments/18afpbg/is_this_the_best_way_to_achieve_a_bobbing_effect/

게시물 댓글에서는 idle 스프라이트를 여러 프레임으로 만들지 않고 한 장만 사용한 뒤, 그리기 좌표의 Y 값에 주기적인 오프셋을 더하는 방식이 제안된다.

> “Use only 1 frame in idle sprite.”

> “Change frequency to higher number for faster bobbing. Change amplitude to higher number for larger bobbing amount.”

### 3.2 확인된 구조

- 원본 이미지: 1장
- 변화 요소: Y 좌표
- 제어 값: 진폭, 주기, 위상
- 부속물: 동일한 Y 오프셋을 공유하거나 별도 위상 사용 가능

### 3.3 일반적 결론

사인파 또는 트윈 기반 상하 이동은 형태 변화가 필요 없는 부유체, 유령, 드론, 코인, 아이콘, 탑승 장치 등에 지속적인 생동감을 부여할 수 있다. 이 방식은 스프라이트 내부의 관절이나 픽셀 구조를 바꾸지 않으므로 원본 이미지 일관성이 유지된다.

단, 지면을 밟는 인간형 캐릭터에 그대로 적용하면 실제 보행보다 ‘떠 있음’이나 ‘통통 튀는 이동’으로 읽힐 수 있다. 따라서 이 방법의 적합성은 대상의 설정과 실루엣에 의존한다.

---

## 4. 방법론 B: 좌우 기울기와 wobble

### 4.1 Reddit 사례

**출처:** r/gamemaker, 「How can I make a wobbling walk animation like this?」
https://www.reddit.com/r/gamemaker/comments/10ski6b/how_can_i_make_a_wobbling_walk_animation_like_this/

댓글에서는 이동 중 이미지의 회전각을 사인값으로 변화시키고, 정지 시 회전각을 0으로 보간하는 방식이 제안된다.

> “When the player is stationary lerp to 0, and when moving lerp to something like `sin(x) * 20`.”

### 4.2 확인된 구조

- 원본 이미지: 1장
- 변화 요소: 회전각
- 이동 중: 양·음의 작은 회전 반복
- 정지 시: 기본 각도로 복귀
- 보간: 즉시 전환보다 lerp 등을 이용한 완만한 변화

### 4.3 일반적 결론

좌우 기울기는 다리가 직접 보여야 하는 사실적 보행보다, 상자·통·기계·마스코트·바퀴 없는 장치처럼 하나의 덩어리로 읽히는 대상에 적합하다. 작은 회전만으로도 무게 이동, 뒤뚱거림, 불안정한 추진감을 전달할 수 있다.

회전 중심점이 잘못 잡히면 공중에서 빙글거리는 것처럼 보일 수 있으므로, 피벗 위치가 시각적 접지점 또는 질량 중심과 일치해야 한다.

---

## 5. 방법론 C: 속도 기반 squash & stretch

### 5.1 Reddit 사례

**출처:** r/Unity3D, 「Squash n Stretch makes the simplest movement feel good」
https://www.reddit.com/r/Unity3D/comments/8a6jzn/squash_n_stretch_makes_the_simplest_movement_feel/

작성자는 부모 Transform을 속도 방향으로 회전하고 속력의 크기에 따라 스케일을 변화시킨 뒤, 자식 그래픽의 방향을 보정하는 구현을 설명한다.

> “I’m rotating a parent transform to face along the velocity and scaling based on the magnitude while setting the child/graphic’s rotation to `Quaternion.identity` every frame.”

### 5.2 확인된 구조

- 출발 또는 고속 이동: 이동 방향으로 늘어남
- 정지 또는 충돌: 이동 방향으로 눌림
- 부모와 그래픽을 분리해 방향과 시각 왜곡을 독립 제어
- 추가 프레임 없이 Transform 값으로 계산

### 5.3 일반적 결론

squash & stretch는 단순한 위치 이동에 가속감, 충격감, 탄성을 추가한다. 원본 이미지가 한 장이어도 출발·정지·충돌 상태를 구분하기 쉬워진다.

픽셀아트에 적용할 때는 과도한 비정수 스케일과 보간으로 픽셀 크기가 불규칙해질 수 있다. 따라서 작은 변형값, nearest 계열 필터, 정수 단위 결과 보정이 필요하다는 기술적 주의점이 따른다.

---

## 6. 방법론 D: 정적 본체와 움직이는 부분의 분리

### 6.1 Reddit의 Free-Form Deformation 사례

**출처:** r/gamedev, 「A guide on procedural sprite animation」
https://www.reddit.com/r/gamedev/comments/4jii9a/a_guide_on_procedural_sprite_animation/

작성자는 Free-Form Deformation 방식으로 단일 이미지에 메시를 만들고 일부 정점에만 변환을 적용했다고 설명한다.

> “The technique is called Free-Form Deformation.”

> “During an update cycle, apply a chosen transformation to a subset of the vertices.”

> “In my case I only had to create a single sprite.”

### 6.2 국내 커뮤니티의 정적 레이어 재사용 논의

**출처:** DCInside 도트 마이너 갤러리, 「반복 프레임 애니메이션 질문」
https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=30643

공개 설명에는 움직이지 않는 레이어를 모든 프레임에 반복해서 넣어야 하는지, 정적인 부분을 유지한 채 움직이는 부분만 바꿀 수 있는지에 대한 질문이 나타난다.

> “움직임없는 레이어는 프레임 늘릴때도 계속 넣어줘야함?”

### 6.3 확인된 구조

- 정적 영역: 몸통, 차체, 장비 본체, 배경
- 동적 영역: 귀, 안테나, 천, 끈, 도구 끝, 작은 장식, 액체, 적재물
- 동적 영역만 메시 변형, 회전, 위치 이동 또는 소수 프레임 교체

### 6.4 일반적 결론

움직임의 존재를 전달하기 위해 전체 이미지를 매번 다시 그릴 필요는 없다. 실루엣에서 눈에 잘 띄는 작은 부속물 하나가 움직여도 대상 전체가 살아 있는 것처럼 읽힐 수 있다.

다만 메시 변형은 픽셀아트의 외곽선을 비정상적으로 늘이거나 관절을 휘게 만들 수 있다. 정제된 픽셀 스타일에서는 메시 왜곡보다 파츠 분리 후 피벗 회전 또는 제한된 프레임 교체가 더 예측 가능할 수 있다는 기술적 차이가 있다.

---

## 7. 방법론 E: 본·IK·컷아웃 재사용

### 7.1 2D 픽셀 캐릭터 IK 사례

**출처:** r/gamedev, 「Using inverse kinematics to procedurally animate…」
https://www.reddit.com/r/gamedev/comments/jwsl1m/using_inverse_kinematics_to_procedurally_animate/

공개 검색 스니펫에서 작성자는 미술 능력 대신 코딩 능력을 활용하기 위해 절차 애니메이션과 IK를 사용했다고 설명한다.

> “Using procedural animation and inverse kinematics is a super useful tool for someone with my skillset.”

### 7.2 국내 본 애니메이션 재사용 사례

**출처:** DCInside 인디 게임 개발 마이너 갤러리, 「[토끼마을 이야기] 2D 애니메이션 기능을 개선했어」
https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=156012

공개 설명에서는 캐릭터마다 뼈를 심는 리깅 비용이 있었지만, 이미 만든 애니메이션의 재활용은 가능했다고 설명한다.

> “캐릭터가 추가될 때마다 그 캐릭터에 뼈를 심는 리깅 작업을 해야 했어. 애니메이션의 경우 이미 만들어둔 애니메이션을 재활용하는 것이 가능했지만…”

**출처:** 루리웹, 「래토피아 개발일지 4 애니메이션」
https://bbs.ruliweb.com/community/board/300058/read/30576412

공개 설명에서는 Spine의 애니메이션 보간과 제작 과정을 확인할 수 있다.

> “스파인에서는 애니메이션 사이 보간처리가 자동으로 되어…”

### 7.3 Godot Skeleton2D 논의

**출처:** Godot Forum, 「State of Skeleton2D in Godot / bone 2D rigging / cutout animations」
https://forum.godotengine.org/t/state-of-skeleton2d-in-godot-bone-2d-rigging-cutout-animations/65393

토론에서는 Spine의 비용과 런타임 의존성, Godot 내장 Skeleton2D로 가능한 범위와 추가 작업량을 논의한다.

> “you have to do a lot of extra work but you can get the job done.”

### 7.4 일반적 결론

본·IK·컷아웃은 동일 체형에서 많은 행동을 재사용할 때 프레임 수 증가를 억제할 수 있다. 반면 초기 리깅, 파츠 분리, 피벗 설정, 관절 왜곡 수정 비용이 발생한다.

따라서 이 방법은 ‘항상 최소 노력’이 아니라, 반복 사용 횟수가 충분할 때 초기 비용을 회수하는 구조다. 픽셀아트에서는 회전된 파츠의 픽셀 계단과 관절 연결부가 어색해질 수 있어 별도의 보정 이미지가 필요할 수 있다.

---

## 8. 방법론 F: 차량·좌석과 승하차 생략

### 8.1 Reddit 사례

**출처:** r/gamedev, 「How do you handle vehicles animations?」
https://www.reddit.com/r/gamedev/comments/vy2q6w/how_do_you_handle_vehicules_animations/

댓글에서는 차량 승하차 애니메이션이 다양한 예외 상황과 보정 작업을 발생시키기 때문에 많은 게임이 승하차 과정을 순간 전환으로 처리하며, 탑승 후 캐릭터를 좌석 위치에 부착한다고 설명한다.

> “There’s a reason many games teleport you in/out of vehicles.”

> “You just attach the actor position to the ‘seat’.”

### 8.2 직접 확인된 내용

- 탑승자는 차량의 좌석 기준점에 부착 가능
- 복잡한 승하차 연결 애니메이션을 생략하는 사례가 있음
- 차량과 탑승자를 별도 객체로 관리할 수 있음
- 전환 애니메이션의 예외 처리와 수정 비용이 큼

### 8.3 확인되지 않은 내용

이번 검색에서는 다음 주장을 직접 뒷받침하는 공개 개발 사례를 찾지 못했다.

- ‘다리 애니메이션을 만들지 않기 위해 차량이 하체를 가리도록 디자인했다.’
- ‘부유 카트를 채택한 주된 이유가 스프라이트 프레임 절감이었다.’

따라서 하체 은폐형 차량 또는 부유체는 확인된 차량·좌석 분리 원리에서 파생 가능한 설계 아이디어이지만, 이번 조사에서 직접 검증된 커뮤니티 관행으로 표현해서는 안 된다.

---

## 9. 방법론 G: 캐릭터 본체 대신 VFX가 행동을 설명

### 9.1 Godot 파티클 논의

**출처:** r/godot, 「Particles 2D vs 2D sprite animations」
https://www.reddit.com/r/godot/comments/1joc7b1/particles_2d_vs_2d_sprite_animations/

질문에서는 우주선의 엔진 불꽃과 폭발을 스프라이트 애니메이션 또는 Particles2D로 만드는 선택을 논의한다. 댓글에서는 파티클이 프레임레이트상 더 부드럽게 보일 수 있으며, 두 방법을 혼합할 수 있다고 설명한다.

> “particles2d will probably look way smoother than animatedsprites because of your frame rate.”

> “just mix and match them up to your taste.”

### 9.2 국내 파티클·라이트 사례

**출처:** DCInside 인디 게임 개발 마이너 갤러리, 「인법, 작업물 몰아 올리기의 술...(gif 많음)」
https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=207227

공개 설명에서는 방어와 패리 효과에 파티클과 라이트를 추가한 뒤 시각적 화려함이 증가했다고 말한다.

> “방어, 패리 이펙트에 파티클+라이트를 넣음. 게임이 좀 더 화려해졌다.”

### 9.3 Godot Forum 사례

**출처:** Godot Forum, 「How does VFX work in Godot for a complete newbie?」
https://forum.godotengine.org/t/how-does-vfx-work-in-godot-for-a-complete-newbie/69356/2

답변에서는 첫 접근으로 파티클을 직접 실험해 볼 것을 권한다.

> “Play around with particles.”

### 9.4 일반적 결론

다음과 같은 정보는 캐릭터 본체의 세밀한 프레임 없이도 VFX로 전달할 수 있다.

- 추진 및 이동 방향
- 속도 증가와 감속
- 접촉과 충돌
- 공격 발생 지점
- 피격과 방어 성공
- 마법 또는 장치 활성화
- 작업 완료와 대상 제거

파티클·라이트·셰이더·화면 흔들림·히트스톱은 원본 캐릭터의 실루엣을 유지하면서 행동 피드백을 강화한다. 그러나 VFX 역시 종류와 해상도가 무제한으로 늘어나면 별도의 제작·관리 비용이 발생하므로, ‘무료 대체재’가 아니라 재사용 가능한 공통 효과로 볼 필요가 있다.

---

## 10. 방법론 H: 단일 이미지 VFX의 위치·스케일·알파 재사용

### 10.1 DCInside 사례

**출처:** DCInside 인디 게임 개발 마이너 갤러리, 「스프라이트 애니메이션 이펙트? 질문」
https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=151979

공개 설명에서는 스프라이트 한 장의 크기만 조절해 효과를 만들고, 에셋 수를 최소화한 상태에서 여러 모션으로 재사용하려는 질문이 확인된다.

> “스프라이트 한장으로 사이즈만 조절해서 효과내는 방법…”

> “에셋을 최소화 하고싶어서 이런 모션들을 여러종류 만들어서 쓰고싶거든.”

**출처:** DCInside 인디 게임 개발 마이너 갤러리, 「두트윈 이렇게쓰는거맞음??」
https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=167709

공개 설명에서는 단순한 스케일 변화에 DOTween 애니메이션을 사용하는 사례가 나타난다.

### 10.2 일반적 결론

링, 충격파, 먼지, 선택 표시, 부유광, 스캔선, 경고 표시처럼 형태 자체의 정확한 연속성이 중요하지 않은 효과는 한 장의 이미지에 다음 속성을 조합해 여러 상태를 만들 수 있다.

- scale
- rotation
- position
- opacity
- tint
- blend mode
- duration 및 easing

동일한 효과 이미지를 여러 행동에 재사용할 수 있다는 점이 프레임 기반 효과와 구별된다.

---

## 11. 제한 프레임과 프레임 제작비에 대한 국내 논의

### 11.1 프레임 수와 제작시간

**출처:** DCInside 도트 마이너 갤러리, 「도트 애니메이션은 보통 몇 프레임으로 만드나요?」
https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=32380

공개 설명에서는 한 컷 제작에 오랜 시간이 걸리고, 여러 프레임을 그리면서 반복 수정하기 어려운 문제가 제기된다.

> “한 컷 그리는데 8시간 걸리는 초보라 그려가면서 수정할 엄두가 안나네요.”

### 11.2 외주 단가 사례

**출처:** DCInside 도트 마이너 갤러리, 「도트 외주 단가 괜찮은지 봐줘」
https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=23662

공개 설명에는 300×300 크기의 캐릭터, 평상 모션 6프레임, 공격 모션 10프레임 등의 조건과 캐릭터당 비용이 언급된다.

이 사례는 고해상도, 프레임 수, 행동 종류가 외주비와 직접 연결된다는 점을 보여준다. 다만 개별 게시물의 견적이 전체 시장의 표준 단가를 대표한다고 볼 수는 없다.

### 11.3 의상과 행동의 곱셈 비용

**출처:** 루리웹, 「던파 기본 도트를 바꾸는게 어려운 이유가」
https://bbs.ruliweb.com/community/board/300780/read/50242163

> “도트겜 특성상 아바타 하나 나오면 저 모션에 맞게 다 찍어야함…”

이 논의는 방향, 행동, 장비, 의상 변형이 서로 곱해질 때 프레임 제작량이 급격히 늘어나는 문제를 설명한다.

### 11.4 일반적 결론

프레임 애니메이션의 총비용은 단순히 프레임 개수만으로 결정되지 않는다. 다음 요소가 곱셈 관계를 만든다.

`캐릭터 수 × 방향 수 × 행동 수 × 프레임 수 × 장비/의상 변형 수`

따라서 캐릭터와 장비 변형이 많은 게임일수록 공통 모션 재사용, 정적 레이어 분리, 엔진 변환, 공통 VFX의 상대적 이점이 커진다.

---

## 12. AI 전체 스프라이트 시트 생성의 한계

### 12.1 GPT Image 계열의 반복 포즈 문제

**출처:** OpenAI Community, 「Developing sprite sheets with gpt-image-2」
https://community.openai.com/t/developing-sprite-sheets-with-gpt-image-2/1379831

게시물에서는 전체 시트를 한 번에 생성할 경우 불완전한 결과와 반복 포즈가 발생할 수 있으며, 프레임별 작업이 더 나은 결과를 내는 경우가 있다고 설명한다.

> “If you ask the model to generate a full sprite sheet, it often produces incomplete results with repeated poses.”

> “Avoid generating a full sprite sheet all at once. Working frame by frame tends to produce better results.”

### 12.2 DALL·E 3 이소메트릭 시트 사례

**출처:** OpenAI Community, 「Create 2D isometric pixel art character animation」
https://community.openai.com/t/create-2d-isometric-pixel-art-character-animation/572395

사용자는 9~12개의 서로 다른 연속 포즈를 요구했지만 같은 스프라이트가 반복됐다고 보고한다.

> “But dall-e give me the same sprites.”

### 12.3 일반적 결론

이미지 모델은 정적인 한 장의 완성도와 여러 프레임의 시간적 연속성을 같은 수준으로 처리하지 못할 수 있다. 특히 다음 문제가 반복적으로 보고된다.

- 같은 포즈 반복
- 좌우 팔다리 구분 실패
- 방향 변화
- 장비 위치 변화
- 비율과 실루엣 변화
- 프레임 기준선 불일치
- 배경 또는 알파 불일치

‘격자 형태의 여러 캐릭터’를 생성했다고 해서 실제 애니메이션의 상반된 동작 단계가 만들어졌다고 볼 수는 없다.

---

## 13. 이미지→비디오 기반 픽셀 애니메이션의 한계

### 13.1 OpenAI Community 사용자 보고

**출처:** OpenAI Community, AI game development 토론
https://community.openai.com/t/ai-in-game-development-gamedev-tips-tools-techniques-and-gpt-llm-agent-integration/1372841/62

공개 검색 스니펫에서는 Sora와 Gemini를 이용한 픽셀 캐릭터 보행에서 캐릭터 형태가 중간에 무너지는 문제가 보고된다.

> “a character walking that doesn't just explode mid way?”

> “I've tried Sora as well as Gemini and they just can't do it.”

### 13.2 Hacker News의 단일 이미지 애니메이션 도구 피드백

**출처:** Hacker News, 단일 이미지 기반 게임 캐릭터 애니메이션 생성기 토론
https://news.ycombinator.com/item?id=44204181

프로젝트는 한 장의 이미지로 다양한 게임 캐릭터 애니메이션을 생성할 수 있다고 소개하지만, 댓글에는 AI 특유의 흐릿함, 비인간형 캐릭터의 실패, 원본 픽셀 스타일 변화에 대한 지적이 나타난다.

> “the sprites are low quality and AI generated… trademark AI ‘fuzziness.’”

### 13.3 Hacker News의 스프라이트 일관성 문제

**출처:** Hacker News
https://news.ycombinator.com/item?id=40395221

제작자는 일반 생성 모델을 이용한 스프라이트 제작에서 다음 문제를 설명한다.

> “It either gives you inconsistent character, or not aligned motions, or hard to remove the background.”

### 13.4 일반적 결론

이미지→비디오 모델은 연기, 불꽃, 천, 오라, 유체처럼 형태 변화가 허용되는 소재에는 참고가 될 수 있지만, 게임 스프라이트 본체에는 다음 조건이 필요해 더 엄격하다.

- 동일 실루엣
- 동일 픽셀 격자
- 동일 장비 위치
- 동일 팔레트
- 동일 기준선
- 시작·종료 프레임의 정확한 루프
- 투명 배경

자연스러운 영상처럼 보이는 것과 게임에서 반복 가능한 스프라이트 루프인 것은 서로 다른 품질 기준이다.

---

## 14. 절차적 스프라이트 도구 사례

### 14.1 SpookyGhost

**출처:** itch.io, SpookyGhost
https://encelo.itch.io/spookyghost

프로젝트는 자신을 다음과 같이 소개한다.

> “Open source procedural sprite animation.”

이 사례는 적은 수의 이미지 요소를 위치·회전·스케일·왜곡 등의 절차적 변환으로 움직이는 접근이 독립된 도구 형태로도 구현돼 있음을 보여준다.

### 14.2 일반적 결론

절차 애니메이션은 프레임 이미지를 완전히 제거하는 기술이라기보다, 소수의 이미지에 시간 변화 규칙을 부여하는 방식이다. 제작 비용은 이미지 프레임에서 리그, 피벗, 곡선, 파라미터 설정으로 이동한다.

---

## 15. 조사 결과에서 반복적으로 확인된 원리

### 15.1 전체가 아니라 움직임 신호를 만든다

여러 사례에서 ‘전체 캐릭터의 정확한 운동’을 그리는 대신, 사용자가 움직임을 인식하게 만드는 최소 신호를 제공한다.

- 상하 위치 변화
- 좌우 기울기
- 속도에 따른 늘어남과 눌림
- 그림자 변화
- 부속물의 흔들림
- 추진 입자
- 접촉 이펙트
- 색상 플래시

### 15.2 정적 실루엣을 보존한다

원본 이미지가 정적이어도 실루엣 주변의 변화가 있으면 움직임으로 읽힐 수 있다. 실루엣 자체를 매 프레임 다시 생성하지 않기 때문에 캐릭터 정체성, 장비, 비율의 일관성을 유지하기 쉽다.

### 15.3 프레임 비용을 엔진 파라미터로 이전한다

프레임 애니메이션이 이미지 제작 비용을 요구한다면, 절차 방식은 다음 설정 비용을 요구한다.

- 피벗
- 진폭
- 주기
- easing
- 속도 연동
- 파티클 수명
- 레이어 순서
- 그림자 위상

따라서 총비용이 0이 되는 것은 아니지만, 동일한 규칙을 여러 대상에 재사용할 수 있다는 차이가 있다.

### 15.4 반복 사용성이 비용 절감의 핵심이다

- 한 번 만든 바빙 함수를 여러 부유체에 사용
- 한 번 만든 피격 플래시를 여러 캐릭터에 사용
- 한 번 만든 파티클을 여러 작업과 충돌에 사용
- 한 번 만든 리그를 같은 체형에 사용

특정 대상 하나만을 위해 복잡한 절차 시스템을 만드는 경우에는 초기 비용이 오히려 커질 수 있다.

### 15.5 AI는 정적 원본과 소재 생성에 상대적으로 강하다

OpenAI Community와 HN 사례에서는 전체 시트의 시간적 일관성보다 단일 원본 이미지 제작이 상대적으로 안정적이라는 문제가 반복적으로 나타난다. 이에 따라 AI 출력과 엔진의 결정론적 변환을 분리하는 접근이 논리적으로 도출된다.

이 문장은 특정 프로젝트에서 반드시 그렇게 해야 한다는 채택안이 아니라, 조사 사례들에서 확인된 능력 차이를 요약한 것이다.

---

## 16. 방법별 비용과 한계 비교

| 방법 | 필요한 이미지 | 엔진 작업 | 강점 | 확인된 주요 한계 |
|---|---:|---:|---|---|
| 상하 바빙 | 1장 | 낮음 | 형태 보존, 반복 용이 | 지상 보행에는 부유처럼 보일 수 있음 |
| 좌우 wobble | 1장 | 낮음 | 덩어리형 대상의 이동감 | 피벗이 나쁘면 공중 회전처럼 보임 |
| squash & stretch | 1장 | 낮음~중간 | 출발·정지·충돌 강조 | 픽셀 스케일 왜곡 가능 |
| 부속물 분리 | 본체 1장 + 파츠 | 중간 | 본체 일관성 유지 | 파츠 연결부와 레이어 관리 필요 |
| 메시 변형 | 1장 또는 파츠 | 중간 | 유기적인 부분 움직임 | 픽셀 외곽선 왜곡 가능 |
| 본·IK·컷아웃 | 파츠 세트 | 높음 | 동작 재사용 가능 | 초기 리깅과 관절 보정 비용 |
| 공통 VFX | 효과 1장 또는 소수 프레임 | 낮음~중간 | 행동 피드백 강화, 재사용 | 과용 시 시각적 혼잡과 별도 관리비 |
| 차량 좌석 부착 | 차량과 탑승자 이미지 | 중간 | 승하차 연결 생략 가능 | 하체 은폐 목적의 직접 사례는 미확인 |
| AI 전체 시트 | 모델 출력 다수 | 후처리 높음 | 빠른 후보 생성 | 반복 포즈, 방향·정체성·장비 드리프트 |
| 이미지→비디오 | 동영상 출력 | 후처리 매우 높음 | 유동적 VFX 참고 | 게임용 픽셀 루프 일관성 부족 |

---

## 17. 확인된 사실과 미확인 주장

### 17.1 확인된 사실

- 단일 이미지에 Y 오프셋을 적용하는 바빙 구현 사례가 있다.
- 단일 이미지의 회전값으로 wobble 이동을 만드는 사례가 있다.
- 속도 기반 회전과 스케일로 단순 이동을 강화한 사례가 있다.
- 단일 스프라이트의 일부 메시 정점만 변형한 절차 애니메이션 사례가 있다.
- 본·IK·컷아웃은 초기 리깅 비용과 모션 재사용성을 함께 가진다.
- 차량 탑승자를 좌석 위치에 부착하고 복잡한 승하차를 생략하는 사례가 있다.
- 파티클·라이트·트윈은 캐릭터 프레임을 늘리지 않고 행동 피드백을 강화할 수 있다.
- 국내 커뮤니티에서도 한 장짜리 스프라이트의 스케일 변화와 정적 레이어 재사용 문제가 논의됐다.
- AI 전체 스프라이트 시트에서 같은 포즈 반복과 일관성 실패가 보고됐다.
- 이미지→비디오 기반 픽셀 애니메이션에서 형태 붕괴와 스타일 드리프트가 보고됐다.

### 17.2 이번 조사에서 확인하지 못한 주장

- 차량이나 부유체로 하체를 가리는 것이 널리 확립된 게임 애니메이션 비용 절감 관행이라는 주장
- 부유 카트가 일반적인 인간형 캐릭터 보행 대체 수단으로 커뮤니티에서 보편적으로 권장된다는 주장
- 생성형 AI가 정제된 픽셀 캐릭터의 여러 방향·여러 행동을 수동 검수 없이 안정적으로 완성한다는 주장
- 특정 프레임 수가 모든 픽셀 캐릭터와 행동에 최적이라는 주장
- 절차 애니메이션이 프레임 애니메이션보다 모든 상황에서 더 저렴하다는 주장

---

## 18. 출처 목록

### Reddit

1. Bobbing effect, r/gamemaker
   https://www.reddit.com/r/gamemaker/comments/18afpbg/is_this_the_best_way_to_achieve_a_bobbing_effect/
2. Wobbling walk, r/gamemaker
   https://www.reddit.com/r/gamemaker/comments/10ski6b/how_can_i_make_a_wobbling_walk_animation_like_this/
3. Squash & stretch movement, r/Unity3D
   https://www.reddit.com/r/Unity3D/comments/8a6jzn/squash_n_stretch_makes_the_simplest_movement_feel/
4. Procedural sprite animation, r/gamedev
   https://www.reddit.com/r/gamedev/comments/4jii9a/a_guide_on_procedural_sprite_animation/
5. Inverse kinematics for 2D pixel art, r/gamedev
   https://www.reddit.com/r/gamedev/comments/jwsl1m/using_inverse_kinematics_to_procedurally_animate/
6. Small bouncing animation, r/IndieDev
   https://www.reddit.com/r/IndieDev/comments/vytyuc/simple_walk_animation/
7. Particles2D vs sprite animations, r/godot
   https://www.reddit.com/r/godot/comments/1joc7b1/particles_2d_vs_2d_sprite_animations/
8. Vehicle animations, r/gamedev
   https://www.reddit.com/r/gamedev/comments/vy2q6w/how_do_you_handle_vehicules_animations/

### DCInside

9. 프레임 애니메이션은 장단점이 명확해요
   https://gall.dcinside.com/mgallery/board/view/?id=indiegame&no=210080
10. 토끼마을 이야기 2D 애니메이션 기능 개선
    https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=156012
11. 스프라이트 한 장으로 효과내기 질문
    https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=151979
12. DOTween 스케일 애니메이션 질문
    https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=167709
13. 도트 애니메이션 프레임 수 질문
    https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=32380
14. 반복 프레임의 정적 레이어 질문
    https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=30643
15. 도트 외주 단가 질문
    https://gall.dcinside.com/mgallery/board/view/?id=pixelart&no=23662
16. 파티클·라이트 작업 사례
    https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=207227

### 루리웹

17. 래토피아 개발일지 4 애니메이션
    https://bbs.ruliweb.com/community/board/300058/read/30576412
18. 던파 기본 도트를 바꾸기 어려운 이유
    https://bbs.ruliweb.com/community/board/300780/read/50242163

### OpenAI Community

19. Developing sprite sheets with gpt-image-2
    https://community.openai.com/t/developing-sprite-sheets-with-gpt-image-2/1379831
20. Create 2D isometric pixel art character animation
    https://community.openai.com/t/create-2d-isometric-pixel-art-character-animation/572395
21. AI in game development discussion
    https://community.openai.com/t/ai-in-game-development-gamedev-tips-tools-techniques-and-gpt-llm-agent-integration/1372841/62

### Hacker News

22. Single-image game character animation generator discussion
    https://news.ycombinator.com/item?id=44204181
23. Sprite consistency and animation generation discussion
    https://news.ycombinator.com/item?id=40395221

### Godot Forum 및 itch.io

24. Skeleton2D / bone rigging / cutout animations
    https://forum.godotengine.org/t/state-of-skeleton2d-in-godot-bone-2d-rigging-cutout-animations/65393
25. Tween Y-position bobbing discussion
    https://forum.godotengine.org/t/how-to-stop-moving-the-tween/123075/2
26. VFX for a complete newbie
    https://forum.godotengine.org/t/how-does-vfx-work-in-godot-for-a-complete-newbie/69356/2
27. SpookyGhost — open-source procedural sprite animation
    https://encelo.itch.io/spookyghost

---

## 19. 요약

공개 커뮤니티 사례에서 반복적으로 확인되는 방향은 ‘많은 프레임을 더 잘 생성하는 방법’에만 집중하지 않고, 다음 요소를 이용해 움직임을 인지시키는 것이다.

- 단일 이미지의 위치·회전·스케일 변화
- 정적 본체와 움직이는 부속물의 분리
- 공통 리그와 모션의 재사용
- 파티클·라이트·셰이더·트윈 기반 피드백
- 차량 좌석 부착과 복잡한 전환 생략
- AI가 만든 정적 원본과 엔진의 결정론적 움직임 분리

동시에, 모든 절차 방식이 자동으로 저비용인 것은 아니다. 리깅·메시·파츠 분리는 초기 비용이 있으며, 픽셀아트에서는 회전과 변형이 외곽선을 손상시킬 수 있다. 실제 비용 절감 여부는 동일한 규칙을 얼마나 많이 재사용할 수 있는지에 달려 있다는 점이 여러 사례에서 공통적으로 드러난다.

이 문서는 조사 결과와 일반 방법론을 바탕으로, 이어지는 심층 조사에서 범용 Asset Studio의 제작 모드와 출력 계약을 단계적으로 검토한다.

---

# 20. Asset Studio 방향 심층 조사

## 20.1 조사 진행 원칙

앞선 조사는 여러 방법론의 대표 사례를 한 문서에 모은 1차 조사였다. 이 절부터는 제품 방향을 성급히 일반화하지 않도록 방법론을 한 가지씩 분리해 다음 순서로 조사한다.

1. 단일 이미지 + Transform/Tween
2. 정적 본체 + 움직이는 파츠
3. 상태 교체형 스프라이트
4. VFX 주도형 동작
5. 리깅·페이퍼돌
6. 제한 프레임과 완전 프레임이 필요한 경계

각 항목은 공식 엔진·도구 문서, 실제 공개 코드, 개발자 커뮤니티 사례를 대조하고 다음을 분리해 기록한다.

- 직접 확인된 기능과 사례
- 잘 맞는 에셋 유형
- 실패하거나 품질이 저하되는 범위
- 범용 Asset Studio가 생성해야 할 이미지와 메타데이터
- 결정론적 미리보기와 QA 요구사항
- 해당 모드의 명시적 범위 밖

---

## 20.2 단일 이미지 + Transform/Tween

### 20.2.1 조사 범위

이 방식은 정적 스프라이트 한 장을 런타임에서 다음 속성으로 움직이는 패턴이다.

- position
- rotation
- scale X/Y
- opacity
- tint 또는 color modulation
- easing
- velocity-linked transform

본, 메시, 파츠 조립, 프레임별 그림 교체는 이 항목의 범위에서 제외했다.

### 20.2.2 추가 확인 출처

#### Godot Tween

- URL: https://docs.godotengine.org/en/stable/classes/class_tween.html
- 증거 유형: 공식 엔진 문서
- 확인 기능:
  - `tween_property()`를 이용한 위치·스케일·색상 보간
  - `set_trans()`와 `set_ease()`를 이용한 Sine, Bounce 등의 전환
  - physics frame과 idle frame 처리 방식 선택

공식 예제는 Sprite의 `modulate`와 `scale`을 직접 Tween 대상으로 사용한다. 따라서 정적 `Sprite2D`의 Transform과 색상·알파 채널을 런타임에서 보간하는 방식은 엔진이 직접 지원하는 표준 기능이다.

#### Godot Sprite2D

- URL: https://docs.godotengine.org/en/stable/classes/class_sprite2d.html
- 증거 유형: 공식 엔진 문서
- 확인 기능:
  - 단일 2D texture 표시
  - `centered`, `offset`, `flip_h`, `flip_v`, `region_rect`
  - 픽셀아트에서 반 픽셀 중심으로 인한 변형 가능성 경고
  - 2D vertex/transform pixel snap 사용 고려

이 문서는 정적 이미지 자체뿐 아니라 origin, offset, pixel snap이 Transform 품질을 좌우한다는 근거를 제공한다.

#### GameMaker draw_sprite_ext

- URL: https://manual.gamemaker.io/monthly/en/GameMaker_Language/GML_Reference/Drawing/Sprites_And_Tiles/draw_sprite_ext.htm
- 증거 유형: 공식 엔진 문서
- 직접 확인 문구:
  > “additional options to change the scale, blending, rotation and alpha of the sprite being drawn.”

`draw_sprite_ext(sprite, subimg, x, y, xscale, yscale, rot, colour, alpha)`는 단일 스프라이트를 그릴 때 위치, X/Y 스케일, 회전, 색상 블렌드와 알파를 함께 적용한다. 원본 리소스를 수정하지 않고 표시 방식만 바꾼다고 명시한다.

#### GameMaker direction

- URL: https://manual.gamemaker.io/monthly/en/GameMaker_Language/GML_Reference/Asset_Management/Instances/Instance_Variables/direction.htm
- 증거 유형: 공식 엔진 문서
- 확인 기능:
  - 속도가 0보다 클 때 인스턴스의 이동 방향을 각도로 표현
  - 0° right, 90° up, 180° left, 270° down 좌표 규약

이동 방향을 이미지 회전에 연결할 수 있지만 이미지의 기본 진행 방향과 엔진 각도 규약 사이의 `forward_angle_offset`이 별도로 필요하다.

#### Unity Transform

- URL: https://docs.unity3d.com/ScriptReference/Transform.html
- 증거 유형: 공식 엔진 문서
- 직접 확인 문구:
  > “Position, rotation and scale of an object.”

정적 SpriteRenderer가 붙은 GameObject도 일반 Transform을 통해 위치, 회전, 스케일을 런타임에서 제어할 수 있다. 부모 Transform이 개입할 경우 local/world 결과가 달라지는 점은 별도 규칙이 필요하다.

#### Juicy Breakout 실제 코드

- 저장소: https://github.com/grapefrukt/juicy-breakout
- 코드: https://github.com/grapefrukt/juicy-breakout/blob/master/src/com/grapefrukt/games/juicy/gameobjects/Ball.as
- 증거 유형: 실제 공개 게임 코드
- 확인 구현:
  - 속도 벡터를 `atan2`로 변환해 그래픽 회전
  - 속도 크기에 따라 scale X/Y 변화
  - scale clamp
  - 충돌 시 color transform
  - Back easing

이 사례는 velocity → rotation, speed → squash/stretch, collision → tint라는 런타임 레시피가 실제 코드로 구현된 근거다.

#### Juice FX

- URL: https://codemanu.itch.io/juicefx
- 증거 유형: 실제 인디 제작 도구와 사용 사례
- 확인 기능:
  - X/Y scale과 damping
  - skew와 rotation
  - sprite origin 변경
  - color flash, outline, blend/tint
- 직접 확인 문구:
  > “most animations in the game are just static sprites with some FX added with the tool.”

정적 스프라이트에 origin과 Transform 효과를 적용해 실제 게임 애니메이션의 상당 부분을 만든 사례다. 다만 이 도구는 결과를 GIF·시트·프레임으로 bake할 수도 있어, 런타임 recipe 포맷의 직접 근거와는 구분해야 한다.

#### Juice it or lose it

- URL: https://www.youtube.com/watch?v=Fy0aCDmgnxg
- 관련 소스: https://github.com/grapefrukt/juicy-breakout
- 증거 유형: 공개 개발자 발표와 실행 가능한 프로토타입
- 직접 확인 문구:
  > “A juicy game feels alive and responds to everything you do.”

단순 오브젝트에 Transform, 색상, easing, 입력·충돌 반응을 연쇄적으로 추가해 시각 피드백을 강화한 사례다. 화면 흔들림, 파티클, 사운드는 이번 단일 이미지 Transform 범위와 분리해야 한다.

### 20.2.3 잘 맞는 에셋 유형

- 투사체와 미사일
- 화살과 탄환
- 픽업 아이템과 코인
- 부유 오브젝트
- 단순 드론과 비행체
- 아이콘형 적
- 통, 상자, 표지판처럼 하나의 덩어리로 읽히는 오브젝트
- 버튼, 카드, UI 요소
- 단순한 환경 장식
- 충돌 또는 선택 반응이 필요한 정적 스프라이트

### 20.2.4 잘 맞지 않는 범위

- 인간형 보행
- 앞면과 뒷면의 실루엣이 달라지는 방향 전환
- 팔다리가 독립적으로 움직이는 공격
- 내부 관절이 필요한 행동
- 머리카락, 천, 촉수, 유체의 내부 움직임
- 큰 실루엣 변화
- 여러 파츠의 독립 동작

Transform은 이미지에 존재하지 않는 내부 자세나 새 실루엣을 만들 수 없다.

### 20.2.5 범용 Asset Studio의 제작 모드 결론

이 방식은 기존 `Actor Animation`의 하위 액션이 아니라 별도 제작 모드로 분리하는 것이 타당하다.

```text
Static Transform Sprite
```

이 모드의 역할은 애니메이션 프레임을 AI로 생성하는 것이 아니다.

> Transform으로 움직여도 깨지지 않는 정적 이미지를 생성하고, 피벗·방향·픽셀 정책·동작 레시피를 함께 패키징한다.

### 20.2.6 필수 이미지 및 좌표 메타데이터

#### 이미지

- 단일 RGBA 무손실 이미지
- source canvas W/H
- trim rect
- trim offset
- 충분한 투명 padding
- alpha mode
- color space
- pixels-per-unit 또는 reference scale

#### 기준점

- pivot/origin
- visual center
- bottom contact point
- canonical facing
- forward angle offset
- rotation-safe bounds

#### 픽셀 렌더링

- nearest 또는 linear filter
- mipmap 여부
- integer-position snapping
- integer-scale 권장 여부
- half-pixel pivot 허용 여부
- negative scale/flip 허용 여부

### 20.2.7 Transform recipe 계약

최소 계약은 다음을 포함해야 한다.

```json
{
  "mode": "static_transform",
  "duration": 0.8,
  "loop_mode": "ping_pong",
  "time_domain": "render",
  "pivot": { "x": 0.5, "y": 0.85 },
  "canonical_facing": "right",
  "forward_angle_offset": 0,
  "pixel_snap": true,
  "filter": "nearest",
  "channels": {
    "position_y": [-2, 2],
    "rotation_deg": [-2, 2],
    "scale_x": [1.0, 1.03],
    "scale_y": [1.0, 0.97],
    "opacity": [1.0, 1.0]
  },
  "easing": "sine_in_out"
}
```

추가로 다음 재생 규칙이 필요하다.

- restart / replace / blend / queue / ignore
- 완료 후 restore / hold
- loop seam 연속성
- scale, opacity, tint clamp
- local/world transform 공간
- transform 적용 순서

속도 연동 레시피는 다음 값을 별도로 가진다.

- velocity vector 또는 speed scalar
- zero-speed epsilon
- 정지 시 각도 유지/복귀/비활성 정책
- speed min/max
- speed → scale curve
- 최대 stretch/squash
- angular damping
- shortest-arc rotation
- spike clamp

### 20.2.8 결정론적 Preview와 QA

#### 고정 재생 조건

- fixed timestep
- 고정 시작 상태
- 고정 velocity fixture
- 고정 seed
- 특정 시각 `t` 직접 샘플링
- golden PNG sequence 비교

#### 필수 프리뷰

1. 피벗 십자선과 contact point
2. 원본 bounds, trim bounds, transform-safe bounds
3. nearest/linear 비교
4. pixel snap on/off 비교
5. 0°, 90°, 180°, 270° 회전
6. 허용 최대 임의 각도
7. 최대 scale과 clipping 검사
8. 체커보드·흰색·검정·유색 배경의 alpha/tint 검사
9. easing curve와 loop seam
10. zero speed, 저속, 최고속, 대각선, 급정지, 180° 반전
11. tween 중 재입력과 인터럽트

#### 자동 QA

- opacity `[0,1]`
- scale 허용 범위
- 음수/0 scale 허용 여부
- tint overflow
- 시작·종료 loop 오차
- fixed timestep 재현성
- worst-case bounds 초과
- zero velocity NaN
- shortest-angle interpolation
- physics/render mode 혼용
- 영구적인 scale·opacity 누적

### 20.2.9 최종 산출물

이 모드의 정식 산출물은 다음 묶음이다.

1. 정적 투명 PNG
2. 이미지·피벗·방향 manifest
3. Transform recipe
4. 엔진별 adapter 또는 import 예제
5. 결정론적 preview
6. QA 결과

GIF 또는 스프라이트시트는 시각 검증용으로 bake할 수 있지만 핵심 게임 자산 계약은 아니다.

### 20.2.10 명시적 범위 밖

- 새 프레임 생성
- 프레임별 그림 수정
- 본, IK, 메시 변형
- paper-doll과 다중 파츠
- 이미지 내부 눈·입·팔다리의 독립 움직임
- 방향별 새 실루엣 추론
- 파티클과 trail
- 카메라 흔들림
- shader wave/dissolve
- 물리 시뮬레이션 생성
- 콜라이더 자동 재설계

### 20.2.11 판정

`Static Transform Sprite`는 범용 Asset Studio에서 독립된 Production 레시피로 둘 가치가 높다. 공식 엔진 API와 실제 공개 게임 코드 모두 이 방식의 기술적 실현성과 재사용성을 뒷받침한다.

다만 성공 여부는 효과 종류의 수보다 다음 세 조건에 좌우된다.

1. 정확한 pivot과 canonical forward
2. 픽셀 스냅, 필터, alpha/color 규약
3. 고정 timestep, clamp, zero-velocity, interrupt 정책을 가진 결정론적 recipe

이 항목은 조사 완료로 판정한다.

---

## 20.3 정적 본체 + 움직이는 파츠

### 20.3.1 조사 범위

이 방식은 고정된 베이스 또는 몸체 한 장과 독립적으로 이동·회전하는 소수의 강체 파트를 조립하는 구조다.

- 포함: 몸통+머리, 차량+포탑, 상자+뚜껑, 기계+안테나·로터, 몸통+강체 팔·도구
- 제외: 전신 스켈레톤, IK, 메시 변형, 다수 장비 슬롯, VFX, 파트 변환 없이 이미지 전체만 교체하는 상태 스왑

### 20.3.2 확인 출처

#### Phaser Container

- URL: https://docs.phaser.io/phaser/concepts/gameobjects/container
- 증거 유형: 공식 문서
- 확인 내용:
  - 자식 위치는 Container 기준 상대 좌표
  - 부모 회전·위치가 자식에게 전파
  - 자식 배열 순서가 렌더 순서
  - 깊은 중첩은 처리 비용과 좌표 복잡도를 증가시킴

#### Godot Node2D

- URL: https://docs.godotengine.org/en/stable/classes/class_node2d.html
- 증거 유형: 공식 문서
- 직접 확인 문구:
  > “Use Node2D as a parent node to move, scale and rotate children in a 2D project. Also gives control of the node's render order.”

베이스를 부모 Node2D, 머리·포탑·뚜껑 등을 자식 Sprite2D로 구성할 수 있음을 직접 뒷받침한다.

#### PixiJS Scene Graph

- URL: https://pixijs.com/8.x/guides/concepts/scene-graph
- 증거 유형: 공식 문서
- 직접 확인 문구:
  > “If you have a game object that's made up of multiple sprites, you can collect them under a container to treat them as a single object in the world.”

여러 Sprite를 하나의 게임 오브젝트로 조립하고 부모 변환과 자식 로컬 변환을 분리하는 사용 사례를 명시한다.

#### libGDX Scene2D

- URL: https://libgdx.com/wiki/graphics/2d/scene2d/scene2d
- 증거 유형: 공식 문서
- 확인 내용:
  - Actor는 position, size, origin, scale, rotation, color를 가짐
  - Group 변환은 모든 child actor에 적용
  - 자식은 자신의 로컬 좌표계에서 작업

이 문서는 pivot/origin을 암묵적으로 이미지 중심에 두지 않고 명시적으로 저장해야 한다는 근거다.

#### Godot Sprite2D 픽셀 정렬 경고

- URL: https://docs.godotengine.org/en/stable/classes/class_sprite2d.html
- 증거 유형: 공식 문서
- 직접 확인 문구:
  > “For games with a pixel art aesthetic, textures may appear deformed when centered. This is caused by their position being between pixels.”

작은 파트의 피벗·소켓이 반 픽셀에 놓이면 흐림과 변형이 생길 수 있으므로 정수 좌표 검증이 필요하다.

#### Aseprite CLI

- URL: https://www.aseprite.org/docs/cli/
- 증거 유형: 공식 제작 도구 문서
- 확인 내용:
  - visible layer를 독립 이미지로 분리 출력
  - JSON에 레이어 계층 정보 기록
  - atlas edge extrusion
  - 레이어 수 × 프레임 수만큼 파일이 증가할 수 있음

2개 레이어 × 3프레임이 6개 파일을 생성하는 공식 예는 파트 분리가 언제나 노동을 줄이지 않는다는 반례다.

#### Unity 6 Transform Hierarchy

- URL: https://docs.unity3d.com/6000.0/Documentation/Manual/class-Transform.html
- 증거 유형: 해외 공식 엔진 문서
- 직접 확인 문구:
  > “A child GameObject moves, rotates, and scales exactly as its parent does.”
  > “These values are called local coordinates.”

자식 파트가 부모 베이스의 이동·회전·스케일을 상속하고, 자신의 값은 부모 기준 로컬 좌표로 저장된다는 근거다. 단, 이것은 런타임 계층을 뒷받침할 뿐 파트 제작과 조합 비용이 낮다는 보장은 아니다.

#### Aseprite Slices와 Pivot

- URL: https://www.aseprite.org/docs/slices/
- 증거 유형: 해외 공식 제작 도구 문서
- 직접 확인 문구:
  > “a pivot to specify the central/base location of the sprite inside the slice”

Slice별 bounds와 pivot을 JSON 스프라이트시트 데이터로 내보낼 수 있다. 따라서 Asset Studio의 파트별 기준점을 이미지 중심으로 추측하지 않고 명시적 메타데이터로 저장해야 한다. Slice 자체는 부모·자식 계층이나 리그를 정의하지 않으므로, assembly manifest는 별도로 필요하다.

#### 국내 실제 구현 사례: 몸체 분리와 장비 회전

- URL: https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=132750
- 증거 유형: 국내 개인 개발자의 공개 구현 기록
- 직접 확인 문구:
  > “그래서 머리/몸통/팔/다리/ 따로 분리해서 스프라이트를 만든다음에, 몸에 장비 이미지를 추가로 끼우고 회전시키는 방식으로 하면 나쁘지않더라.”

파트 분리와 장비 회전이 실제 프로젝트에서 교체 가능한 장비 표현에 쓰였다는 사례다. 다만 단일 개인 프로젝트 경험이므로 일반 성능 보장으로 확대하지 않는다.

#### 국내 실패 반례: 조합 폭증

- URL: https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=183813
- 증거 유형: 국내 개인 개발자의 공개 실패·비용 기록
- 직접 확인 문구:
  > “몸통 다 분리해서 적용하려고 하니까 gif 파일 개수가 진짜 상상이상이더라. 이거 애니메이션 마다 드로우 하는 코드도 쓰는데 진짜 개노가다였음.”
  > “이미 gif만 100개가 넘게 만들어버려서”

파트 수, 방향, 무기, 동작 조합을 동시에 늘리면 파일과 구현 노동이 폭증한다는 직접 반례다. 따라서 이 모드는 `base 1개 + 강체 파트 1~4개`로 제한하며 전신 분해형 범용 리그와 조합별 GIF 대량 생성은 제외한다.

#### 해외·국내 증거 종합

해외 공식 문서는 부모–자식 로컬 변환, 렌더 순서, 피벗, 정수 픽셀 정렬과 내보내기 계약을 뒷받침한다. 국내 실제 기록은 그 방식이 장비 교체에 유효할 수 있지만 범위를 넓히면 파일·코드 노동이 급격히 증가한다는 현장 경계를 제공한다.

### 20.3.3 적용 조건

다음 조건을 만족할 때만 이 모드를 사용한다.

- 정적 base/body 1개
- 독립 변환 파트 1~4개
- 파트 내부 굽힘과 메시 변형 없음
- 기본 계층 `root → part` 한 단계
- 불가피한 경우 최대 두 단계
- 각 파트는 제한된 translate/rotate/visibility만 사용

다음이 필요하면 full rigging 또는 다른 모드로 넘긴다.

- 다수 관절 체인
- IK와 목표 추적
- mesh deformation과 skin weight
- 본별 애니메이션 클립
- 다수 장비 슬롯
- 동적 깊이 교차
- 물리 관절

### 20.3.4 이미지 계약

각 파트는 독립 투명 RGBA 리소스로 출력한다.

```text
base.png
head.png
tool_arm.png
antenna.png
```

필수 조건:

- 동일 팔레트와 색공간
- alpha mode 명시
- nearest-neighbor 전제
- 투명 픽셀 RGB 정리 또는 atlas extrusion
- 공용 원본 캔버스 좌표 보존
- trim 시 source rect와 trim offset 기록
- 베이스에 움직이는 파트가 중복으로 구워지지 않음
- 파트에 베이스 잔상이 들어 있지 않음

제작본은 공용 캔버스 레이어로 유지하고 배포본은 trim된 PNG/atlas와 좌표 복원 데이터를 함께 출력하는 방식이 적합하다.

### 20.3.5 부모·자식 계약

```json
{
  "asset": "machine_small",
  "root": "base",
  "parts": [
    {
      "id": "base",
      "image": "base.png",
      "parent": null,
      "drawOrder": 0
    },
    {
      "id": "rotor",
      "image": "rotor.png",
      "parent": "base",
      "drawOrder": 20
    }
  ]
}
```

- ID는 파일명과 분리된 안정적인 식별자
- 부모 순환 참조 금지
- 숨은 제작 레이어는 runtime manifest에서 제외
- group path 보존

### 20.3.6 pivot, anchor, socket

세 개념을 분리해야 한다.

- `pivot`: 파트가 회전·스케일하는 중심
- `anchor`: 파트 자신의 연결점
- `socket`: 부모의 연결점

```json
{
  "id": "lid",
  "parent": "base",
  "pivotPx": [2, 11],
  "anchorPx": [2, 11],
  "parentSocket": "lid_hinge",
  "localPositionPx": [7, 4]
}
```

부모는 socket 좌표를 별도로 가진다.

```json
{
  "sockets": {
    "lid_hinge": [18, 9]
  }
}
```

기본 자세에서 anchor와 socket 오차는 0픽셀을 목표로 한다.

### 20.3.7 draw order와 occlusion

- 항상 베이스 뒤
- 항상 베이스 앞
- 제한된 앞/뒤 슬롯
- 접합부를 가리는 1~3픽셀 overlap

복잡한 각도별 깊이 교차나 실시간 메시 마스크는 이 모드의 범위 밖이다.

### 20.3.8 파트별 Transform 한계

```json
{
  "translationPx": {
    "min": [-1, -1],
    "max": [1, 1],
    "integerOnly": true
  },
  "rotationDeg": {
    "min": -35,
    "max": 35,
    "previewStep": 5
  },
  "scale": {
    "min": 1,
    "max": 1
  },
  "skewAllowed": false
}
```

기본 정책:

- translation 정수 픽셀
- scale 1 고정
- skew 금지
- rotation 파트별 제한
- 작은 파트는 검수된 제한 각도만 허용
- 비정수 좌표와 반 픽셀 경고

### 20.3.9 Assembly Preview

필수 프리뷰:

1. 기본 조립 자세
2. 각 파트 단독 보기
3. pivot, anchor, socket 표시
4. 부모 변환의 자식 전파
5. 최소·최대 회전 자세
6. draw order별 앞뒤 결과
7. 1× 실제 픽셀과 정수 확대
8. 체커보드·밝은색·어두운색 배경
9. trim 전후 조립 비교
10. 베이스만/파트만/최종 composite 비교

### 20.3.10 QA

자동 검사:

- 기본 자세 anchor/socket 오차
- 파트 경계의 투명 틈
- 회전 극값에서 드러나는 빈 구멍
- 중복 outline
- 투명 픽셀 halo
- atlas neighbor bleed
- trim offset 누락
- 반 픽셀 pivot/socket
- 비정수 transform
- nearest sampling 여부
- 1픽셀 선 두께 변화
- 회전 시 픽셀 군집 붕괴

### 20.3.11 패키지

```text
machine_small/
  manifest.json
  preview.png
  parts/
    base.png
    rotor.png
    antenna.png
  atlas/
    machine_small.png
    machine_small.json
  source/
    machine_small.aseprite
```

manifest에는 canvas, color space, sampling, atlas region, source rect, trim offset, parent, pivot, anchor, socket, 기본 transform, draw order, transform limits, alpha 규칙과 QA 결과가 포함돼야 한다.

### 20.3.12 반례와 비용 경계

파트 분리는 자동으로 생산성을 높이지 않는다.

- 파일·atlas entry 증가
- 이름과 경로 관리 증가
- 조립 manifest 증가
- 미리보기와 import 검증 증가
- 접합부 seam/halo 수정 증가

실제 독립 변환이 없는 에셋은 단일 정적 이미지로 유지해야 한다.

### 20.3.13 판정

범용 모델은 다음과 같다.

> 얕은 scene graph + 독립 RGBA Sprite + 명시적 pivot/socket + 고정 draw order + 제한된 강체 Transform

Asset Studio는 레이어를 PNG로 분리하는 데서 끝나면 안 된다. 런타임에서 정확히 재조립할 수 있도록 좌표, 피벗, 소켓, 순서, 변환 제한과 QA를 함께 출력해야 한다.

이 항목은 조사 완료로 판정한다.

---

## 20.4 상태 교체형 스프라이트

### 20.4.1 조사 범위

하나의 게임 오브젝트가 의미상 지속되는 상태에 따라 정적 스프라이트 한 장을 다른 한 장으로 교체하는 방식이다.

- 포함: `closed/open`, `intact/damaged/destroyed`, `empty/full`, `off/on`, `dry/wet`, `unbuilt/built`
- 제외: 걷기·공격처럼 시간 순서와 프레임 지속시간이 핵심인 애니메이션
- 제외: 전신 리깅, 장비 페이퍼돌 합성, 독립 수명의 VFX

### 20.4.2 해외 공식 근거

#### Unity SpriteRenderer.sprite

- URL: https://docs.unity3d.com/ScriptReference/SpriteRenderer-sprite.html
- 증거 유형: 해외 공식 엔진 API
- 직접 확인 문구:
  > “The Sprite to render.”
  > “The rendered sprite can be changed by specifying a different sprite in the sprite variable.”

동일 SpriteRenderer에 다른 Sprite를 할당해 런타임 표시 이미지를 교체할 수 있다. 단, 상태 ID·전이·충돌·상호작용은 관리하지 않으므로 의미 상태 모델은 별도 manifest가 필요하다.

#### Unity 2D Animation Sprite Resolver

- 현재 공식 URL: https://docs.unity3d.com/Packages/com.unity.2d.animation@10.0/manual/SL-Resolver.html
- 증거 유형: 해외 공식 패키지 문서
- 직접 확인 문구:
  > “allows you to change the Sprite rendered by that GameObject's Sprite Renderer component.”
  > “The component contains two properties - Category and Label”

Sprite 변형을 Category와 Label로 식별해 동일 GameObject가 렌더할 변형을 선택하는 공식 Sprite Swap 워크플로다. Category/Label은 범용 선택 키일 뿐 게임플레이 상태 머신은 아니므로 Asset Studio가 `state_id`, 기본 상태, 전이 조건을 별도로 정의해야 한다.

기존에 알려진 `SpriteResolver.html` 경로는 404였으며, 공식 패키지 목차가 가리키는 현재 `SL-Resolver.html`만 근거로 사용했다.

#### Godot Sprite2D.texture

- URL: https://docs.godotengine.org/en/stable/classes/class_sprite2d.html
- 증거 유형: 해외 공식 엔진 API
- 확인 내용:
  - `Texture2D texture`
  - `void set_texture(value: Texture2D)`
  - `Texture2D object to draw.`

같은 Sprite2D의 texture를 다른 Texture2D로 설정해 정적 상태 외형을 교체할 수 있다. 텍스처 크기, centered, offset이 다르면 전환 시 월드 위치가 튈 수 있으므로 공통 논리 캔버스와 피벗 규약이 필요하다.

#### Phaser Sprite Texture

- URL: https://docs.phaser.io/api-documentation/class/gameobjects-sprite
- 증거 유형: 해외 공식 엔진 API
- 확인 내용:
  - Sprite는 Texture Manager의 texture key 또는 instance를 렌더 리소스로 사용
  - 선택적 atlas frame 지정 가능
  - TextureCrop 상속 메서드에 `setFrame`, `setTexture` 포함

상태별 개별 텍스처와 단일 atlas 안의 상태별 frame 양쪽을 지원할 수 있다. 다만 setTexture는 렌더 리소스 선택일 뿐 상태 의미와 전이를 관리하지 않는다.

### 20.4.3 국내 지정 사례 재검증과 제외

지정된 국내 게시물 3개는 모두 접근 가능했지만, 실제 제목·본문이 기존에 알려진 설명과 일치하지 않았다. 근거를 꾸며 넣지 않고 제외한다.

#### 제외: DCInside `no=204060`

- URL: https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=204060
- 실제 제목: `방치형 게임 만들기 3일차`
- 실제 확인 내용: 메인 UI, 지도 계획, 손님 스프라이트, 마차 내부 표시, 설정과 스크롤바 작업
- 판정: 나무 성장 상태 교체를 공개 본문에서 입증할 수 없음

#### 제외: DCInside `no=211304`

- URL: https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=211304
- 실제 제목: `지금 소명문 쓰는 사람들은 공무원이 된다했어요 주장하는건데`
- 판정: 건물 업그레이드용 스프라이트 6종과 무관함

#### 제외: DCInside `no=188141`

- URL: https://gall.dcinside.com/mgallery/board/view/?id=game_dev&no=188141
- 실제 제목과 본문: `어제 한 거`, `권태기 옴`
- 판정: 공개 텍스트에서 2프레임 사망 표현을 입증할 수 없음
- 추가 경계: 2프레임 사망이 사실이어도 시간 순서가 있는 애니메이션이며 지속 상태 한 장 교체의 직접 근거가 아님

따라서 이 항목의 국내 지정 사례 채택 수는 0건이다. 확인되지 않은 국내 사례를 해외 공식 근거와 같은 강도로 취급하지 않는다.

### 20.4.4 AI 생성 원칙: 상태별 독립 생성 금지

상태 이미지를 각각 독립 프롬프트로 생성하면 다음 드리프트가 발생하기 쉽다.

- 실루엣과 비례 변화
- 카메라 각도와 facing 변화
- 피벗과 바닥 접점 변화
- outline 두께 변화
- 팔레트와 광원 방향 변화
- 상태와 무관한 디테일 변화

따라서 AI는 먼저 잠긴 canonical base를 만들고, 각 상태는 그 기준 이미지를 입력으로 삼는 constrained edit 또는 구조 보존 변형으로 생성해야 한다.

잠금 항목:

- logical canvas
- pivot와 ground contact
- facing와 투시
- 외곽 실루엣의 불변 영역
- 팔레트 profile
- outline 규칙
- 광원 방향
- 상태별로 변경 가능한 영역 mask

### 20.4.5 상태 스키마

```yaml
asset:
  asset_id: chest_iron
  schema_version: 1

  canonical_base:
    logical_canvas: [64, 64]
    pivot: [32, 56]
    pixels_per_unit: 16
    facing: front
    palette_profile: project_default

  default_state: closed

  states:
    - id: closed
      visual:
        texture: chest_iron_closed.png
        source_rect: [0, 0, 64, 64]
        render_offset: [0, 0]
      collision:
        shape: rect
        rect: [13, 31, 38, 25]
      interaction:
        openable: true
        lootable: false

    - id: open
      visual:
        texture: chest_iron_open.png
        source_rect: [0, 0, 64, 64]
        render_offset: [0, 0]
      collision:
        shape: rect
        rect: [13, 31, 38, 25]
      interaction:
        openable: false
        lootable: true

  transitions:
    - from: closed
      to: open
      trigger: interact_open
      presentation: instant
```

### 20.4.6 필수 계약

#### Canonical Base

자산 전체에 대해 다음을 하나로 고정한다.

- 논리 캔버스 크기
- 좌표계와 픽셀 밀도
- pivot와 ground contact
- facing
- 팔레트 profile
- nearest-neighbor sampling

상태별 투명 여백이 달라도 엔진에서 차지하는 논리 공간은 동일해야 한다.

#### State ID와 Default State

- 안정적인 기계 ID 사용: `intact`, `damaged`, `destroyed`
- 표시명과 파일명에서 분리
- 정확히 하나의 default state 필수
- 상태 ID 중복 금지

#### 전이 그래프

각 전이는 다음을 가진다.

- `from`
- `to`
- 논리 trigger
- 표현 방식: `instant`, `transition_clip`, `vfx`
- 선택적 gameplay event

선언되지 않은 전이는 기본 금지한다. fallback을 허용하려면 명시적으로 선언한다.

#### 상태별 Visual

- texture 또는 atlas frame
- source rect
- render offset
- 선택적 z-order 보정
- 상태별 palette/material override

#### 상태별 Collision

- collider shape와 좌표
- solid 여부
- navigation 영향
- hit target

렌더 이미지가 바뀐다고 충돌체가 자동으로 맞는다고 가정하지 않는다.

#### 상태별 Interaction

- 클릭 영역
- 사용·수확·대화 가능 여부
- gameplay tags
- 상태별 action 목록

### 20.4.7 Atlas Naming

권장 키:

```text
<asset_id>/<state_id>
chest_iron/closed
chest_iron/open
chest_iron/destroyed
```

파일명은 바뀔 수 있어도 manifest의 asset ID와 state ID는 안정적으로 유지한다.

### 20.4.8 Deterministic Preview

Studio는 다음 보기를 제공해야 한다.

1. 상태 목록 단독 선택
2. 전이 그래프 순회
3. 모든 상태를 같은 월드 좌표에 빠르게 교체
4. 1× 실제 픽셀 크기와 정수 확대
5. 체커보드·밝은색·어두운색 배경
6. visual과 collision overlay 동시 보기
7. interaction 영역 overlay
8. contact sheet
9. 상태 A/B onion 또는 difference overlay

빠른 상태 순회는 위치 흔들림 검사용이며 애니메이션 데이터로 취급하지 않는다.

### 20.4.9 Validation

자동 검사:

- state ID 중복
- default state 누락 또는 복수 지정
- 참조 texture/atlas frame 누락
- 전이의 from/to가 실제 상태를 가리키는지
- 도달 불가능 상태
- 의도치 않은 순환
- logical canvas 불일치
- pivot·ground contact 점프
- 비정수 offset
- facing과 scale 불일치
- outline 두께 드리프트
- 팔레트와 광원 방향 드리프트
- collider가 논리 캔버스를 벗어남
- visual silhouette와 collider의 심각한 불일치
- 필수 interaction metadata 누락

### 20.4.10 정적 상태 교체의 경계

정적 state swap은 전환 전후 상태가 일정 시간 유지되고 중간 동작이 중요하지 않을 때 적합하다.

다음은 별도 표현이 필요하다.

- 성장, 붕괴, 문 열림처럼 중간 실루엣이 중요한 경우
  - 2~4개의 transition frame 또는 transition clip
- 폭발, 섬광, 파편, 연기처럼 본체 상태와 수명이 다른 경우
  - 별도 VFX 자산
- 걷기, 공격, 사망처럼 시간 순서와 프레임 지속시간이 의미를 갖는 경우
  - 완전한 animation clip
- 전환 도중 판정 창이나 충돌체가 변하는 경우
  - 타임라인 이벤트와 프레임별 충돌 metadata

최종 `dead`, `open`, `destroyed` 이미지는 애니메이션 종료 후 유지되는 상태로 포함할 수 있다. 그러나 그 상태에 도달하는 동작 자체를 무조건 즉시 스왑으로 대체해서는 안 된다.

### 20.4.11 판정

상태 교체형 스프라이트는 다음 조건에서 범용적으로 유효하다.

> 잠긴 canonical base + 의미 상태 ID + 공통 논리 좌표계 + 상태별 visual/collision/interaction + 명시적 전이

엔진의 texture 교체 API만으로는 제품 기능이 완성되지 않는다. Asset Studio는 상태 의미와 전이, 좌표 일관성, 충돌·상호작용까지 함께 패키징해야 한다.

국내 지정 사례는 검증 실패로 채택하지 않았고, 해외 공식 문서가 입증하는 범위 안에서만 결론을 내린다.

이 항목은 조사 완료로 판정한다.

---

## 20.5 VFX 주도형 동작

### 20.5.1 조사 범위

정적 또는 최소 프레임 본체 위에 별도 효과를 재생해 동작의 힘, 방향, 접촉, 속도와 잔류감을 보완하는 방식이다.

- 포함: 먼지, 섬광, 연기, 불꽃, 파편, 충격파, 잔상, trail, glow, screen shake cue
- 제외: 본체의 anticipation·contact·recovery 실루엣을 전부 효과로 감추는 방식
- 제외: 상태별 정적 이미지 교체만 있는 방식
- 제외: 전신 리깅과 장비 페이퍼돌

### 20.5.2 해외 공식 근거

#### Unity Particle System Main Module

- URL: https://docs.unity3d.com/Manual/PartSysMainModule.html
- 증거 유형: 해외 공식 엔진 문서
- 직접 확인 기능:
  - `Duration`: 시스템 실행 길이
  - `Looping`: duration 종료 후 반복
  - `Start Lifetime`: 파티클 초기 수명
  - `Start Speed`: 파티클 초기 속도
  - `Simulation Space`: local, world 또는 custom object 기준
  - `Max Particles`: 동시에 존재할 수 있는 최대 파티클 수
  - `Auto Random Seed=false`: 매 재생마다 동일한 결과
  - `Random Seed`: 반복 가능한 효과 생성

이 문서는 VFX recipe가 단순 이미지 한 장이 아니라 수명, 속도, 공간, 동시 개수, seed를 포함해야 한다는 근거다.

#### Unity Particle System Modules

- URL: https://docs.unity3d.com/Manual/ParticleSystemModules.html
- 증거 유형: 해외 공식 엔진 문서
- 확인 기능:
  - Emission: 방출 시점과 비율
  - Shape: 방출 영역
  - Color over Lifetime
  - Size over Lifetime
  - Noise
  - Collision
  - Trails

효과의 appearance와 behavior를 분리된 모듈로 표현할 수 있다. Asset Studio 역시 texture와 emitter recipe를 분리해 내보내야 한다.

#### Godot GPUParticles2D

- 공식 원문 저장소: https://github.com/godotengine/godot-docs/blob/master/classes/class_gpuparticles2d.rst
- 문서 URL: https://docs.godotengine.org/en/stable/classes/class_gpuparticles2d.html
- 증거 유형: 해외 공식 엔진 문서
- 확인 속성:
  - `amount`
  - `lifetime`
  - `one_shot`
  - `local_coords`
  - `randomness`
  - `seed`
  - `fixed_fps`
  - `visibility_rect`

Godot 문서 사이트의 Cloudflare 검증 때문에 공식 GitHub 원문으로 속성을 교차 확인했다. 수량·수명·단발 여부·공간·난수·고정 업데이트·가시 범위가 VFX 계약의 핵심임을 뒷받침한다.

#### Godot ParticleProcessMaterial

- 공식 원문 저장소: https://github.com/godotengine/godot-docs/blob/master/classes/class_particleprocessmaterial.rst
- 문서 URL: https://docs.godotengine.org/en/stable/classes/class_particleprocessmaterial.html
- 증거 유형: 해외 공식 엔진 문서
- 확인 기능:
  - emission shape
  - direction
  - gravity와 가속 계열
  - scale curve
  - color와 color ramp
  - collision mode
  - lifetime에 따른 curve/gradient 변화

하나의 VFX는 방출 형상, 운동, 크기, 색, 충돌을 가진 recipe로 모델링해야 하며 PNG만 출력해서는 재현되지 않는다.

#### Phaser ParticleEmitter

- URL: https://docs.phaser.io/api-documentation/class/gameobjects-particles-particleemitter
- 증거 유형: 해외 공식 엔진 API
- 확인 기능:
  - lifespan
  - frequency와 flow mode
  - `frequency=-1`인 explode mode
  - `explode()`
  - `startFollow(target, offsetX, offsetY)`
  - emit zones와 death zones
  - duration와 stopAfter

지속 emitter와 단발 burst를 구분하고, 본체 target 또는 socket을 따라가는 방식이 실제 API에 존재한다.

#### Aseprite CLI

- URL: https://www.aseprite.org/docs/cli/
- 증거 유형: 해외 공식 제작 도구 문서
- 확인 기능:
  - `--layer`: 특정 VFX layer만 분리 출력
  - `--tag`: 지정 애니메이션 tag의 frame만 출력
  - `--sheet`와 `--data`: sprite sheet와 JSON metadata
  - `--shape-padding`, `--border-padding`, `--extrude`: atlas bleed 방지

프레임 기반 픽셀 VFX도 본체와 분리된 layer/tag로 관리하고 atlas+JSON으로 패키징할 수 있다.

### 20.5.3 해외 실제 구현과 반례

#### Godot 공식 2D Particles Demo

- 저장소: https://github.com/godotengine/godot-demo-projects/tree/master/2d/particles
- Asset Library: https://godotengine.org/asset-library/asset/2724
- 증거 유형: 해외 공식 오픈소스 데모
- README 직접 확인 문구:
  > “This demo showcases how 2D particle systems work in Godot.”
  > “It uses `GPUParticles2D` nodes with `ParticleProcessMaterial` materials.”

실제 scene에는 fire, smoke, spark, flipbook texture가 각각 분리돼 있고 emission shape, gravity, scale curve, color ramp, additive blend와 particle flipbook 설정이 별도 resource로 구성돼 있다.

#### Godot Dodge the Creeps Player

- 파일: https://github.com/godotengine/godot-demo-projects/blob/master/2d/dodge_the_creeps/player.tscn
- 증거 유형: 해외 공식 오픈소스 구현
- 확인 내용:
  - 본체 이동은 방향별 2프레임 `AnimatedSprite2D`
  - 별도 `GPUParticles2D` Trail이 자식 노드로 존재
  - Trail은 `z_index=-1`, `amount=10`, 별도 scale curve와 color ramp 사용

이 구조는 중요한 반례다.

> Trail VFX는 걷는 본체의 최소 프레임을 보강하지만 본체 프레임을 대체하지 않는다.

본체의 방향, 발 위치, 접촉 자세가 읽혀야 하는 동작에서 먼지·trail만 추가해도 실루엣 문제는 해결되지 않는다.

### 20.5.4 VFX가 잘 맞는 에셋과 동작

- 고정 기계의 증기 배출
- 횃불·용광로의 불꽃과 연기
- 채굴·타격 순간의 접촉 섬광과 파편
- 차량 정지·출발의 먼지
- 짧은 대시의 잔상과 trail
- 상자 개봉의 작은 glow와 별가루
- 피격 지점의 flash와 impact ring
- 파괴 상태 진입 시 파편 burst
- 환경 오브젝트의 눈·재·빗방울

### 20.5.5 부적합 경계

다음 정보가 본체 실루엣에서 읽혀야 하면 VFX만으로 대체하지 않는다.

- 공격 anticipation 방향
- 무기 접촉 위치와 판정 시점
- recovery와 취소 가능 시점
- 보행 중 발 접지와 방향
- 상호작용 대상과 손 위치
- 피격 후 자세 변화
- 문·뚜껑·레버의 실제 기계적 이동

이 경우 최소 transition frame, 움직이는 파트 또는 완전 애니메이션이 먼저 필요하며 VFX는 보조로 붙인다.

### 20.5.6 Asset Studio 출력 계약

```yaml
vfx:
  id: impact_dust_small
  schema_version: 1
  trigger_event: hit_contact
  attachment:
    target: owner
    socket: impact
    offset_px: [0, 0]
    simulation_space: world
  playback:
    mode: burst
    duration_ms: 280
    lifetime_ms: [180, 320]
    amount: 8
    seed_policy: fixed
    seed: 12041
  emission:
    shape: point
    direction_deg: [-155, -25]
    speed_px_s: [24, 48]
  visual:
    texture: vfx_dust_01.png
    blend_mode: normal
    palette_profile: project_dust
    draw_order: 30
  budget:
    max_alive: 16
    pool_size: 8
  collision:
    affects_gameplay: false
```

### 20.5.7 분리 자산 구조

```text
impact_dust_small/
  manifest.json
  preview.png
  textures/
    dust_01.png
    dust_02.png
  flipbooks/
    impact_flash.png
    impact_flash.json
  recipes/
    emitter.json
```

본체 texture와 VFX texture를 같은 이미지로 굽지 않는다. VFX는 독립 수명과 draw order를 가지며 필요할 때 별도 pooling과 culling이 가능해야 한다.

### 20.5.8 Attachment와 Socket

필수 필드:

- target asset 또는 owner
- socket ID
- 정수 offset
- local/world/custom simulation space
- follow 여부
- owner 삭제 후 생존 정책

정책 예:

- `local`: 본체와 함께 이동하는 glow, 엔진 불꽃
- `world`: 발밑 먼지, 폭발 연기, 떨어지는 파편
- `custom`: 차량 속도나 바람장을 따르는 효과

### 20.5.9 Trigger와 Event

효과는 의미 event에 연결한다.

- `attack_anticipation`
- `attack_contact`
- `hit_confirmed`
- `foot_contact`
- `dash_start`
- `state_destroyed`
- `interaction_complete`

프레임 번호를 직접 하드코딩하기보다 animation marker 또는 gameplay event ID에 연결한다. 상태 교체형에서는 transition trigger와 연결할 수 있다.

### 20.5.10 Determinism

- 고정 seed preview 지원
- runtime random과 deterministic replay 모드 분리
- fixed timestep 또는 fixed FPS 선택
- 동일 seed, recipe, trigger에서 동일 결과 검증
- burst와 continuous emitter 구분

QA와 네트워크 replay에는 fixed seed를 사용하고, 일반 플레이에서는 허용 범위 안의 random seed를 선택할 수 있다.

### 20.5.11 Blend와 Palette

- `normal`, `additive`, 제한적 `screen`만 명시 지원
- 픽셀 프로젝트 팔레트 profile 지정
- 반투명 색 단계 상한
- nearest sampling
- premultiplied alpha 여부 명시
- 밝은 배경과 어두운 배경 모두에서 halo 검사

additive 효과는 검은 배경에서만 검수하면 과도한 백색 섬광과 배경 소실을 놓칠 수 있다.

### 20.5.12 Draw Order와 Collision Independence

- 본체 뒤 먼지
- 본체 위 접촉 섬광
- UI 아래 월드 VFX
- foreground 파편의 상한

시각 VFX는 기본적으로 gameplay collision과 분리한다. 실제 판정은 본체의 hitbox/hurtbox 또는 gameplay event가 담당한다. 시각 파티클 충돌이 필요하면 별도 비용 등급과 fallback을 둔다.

### 20.5.13 Budget와 Pooling

필수 예산:

- emitter당 max alive
- 장면 전체 max alive
- burst당 particle 수
- texture/flipbook 메모리
- draw order와 blend mode별 overdraw 등급
- pool size
- off-screen 정책
- 저사양 fallback

Unity의 `Max Particles`와 Godot의 `amount`, `visibility_rect`는 무제한 방출이 아닌 명시적 상한과 culling이 필요하다는 근거다.

### 20.5.14 Preview

필수 미리보기:

1. 본체 없이 VFX만
2. 본체와 조합
3. local/world simulation 비교
4. 고정 seed 반복 재생
5. 최소·최대 random 범위
6. 1× 실제 픽셀과 정수 확대
7. 체커보드·밝은색·어두운색·복잡한 배경
8. draw order 전후 비교
9. 저사양 budget fallback
10. 다중 동시 재생 스트레스 프리뷰
11. VFX off 비교

`VFX off`에서도 핵심 동작과 판정 시점이 읽히는지 확인한다.

### 20.5.15 QA

자동 검사:

- texture와 flipbook frame 누락
- socket 누락과 정수 offset 위반
- local/world space 오설정
- duration보다 lifetime이 과도하게 긴 잔류 파티클
- owner 삭제 후 고아 emitter
- atlas clipping과 padding 부족
- 투명 halo와 premultiplied alpha 불일치
- 과도한 additive overdraw
- palette 이탈
- 화면 전체를 덮는 섬광 빈도
- 광과민성 위험이 있는 반복 flash
- 복잡한 배경에서 contact cue 소실
- 본체 실루엣을 가리는 연기·파편
- max alive와 scene budget 초과
- deterministic seed 재현 실패

### 20.5.16 판정

VFX 주도형은 다음 구조로 채택한다.

> 최소한 읽히는 본체 동작 + 분리된 VFX texture/flipbook + event/socket 기반 emitter recipe + 명시적 수명·공간·seed·budget

VFX는 정적 또는 저프레임 자산의 힘과 반응성을 크게 높일 수 있다. 그러나 anticipation, contact, recovery처럼 gameplay 판독에 필요한 본체 자세를 대신할 수 없다.

따라서 제품은 VFX를 **대체 수단이 아니라 보강 수단**으로 취급해야 한다. `VFX off` 상태에서도 핵심 행동이 읽히지 않으면 최소 transition frame 또는 완전 애니메이션으로 승격한다.

이 항목은 조사 완료로 판정한다.

---

## 20.6 리깅·페이퍼돌

### 20.6.1 조사 범위

이 항목은 다음 두 체계를 함께 다루되 구분한다.

- skeletal rigging: 본 계층과 rest pose, weight 또는 강체 attachment를 사용해 다수 관절을 애니메이션
- paper-doll / sprite swap: 같은 rig와 slot 위에서 몸·의상·장비 attachment를 교체

다음 단순 모드와는 다르다.

- `base 1개 + 강체 파트 1~4개`
- 한두 개 socket과 고정 draw order
- mesh deformation 없음
- 범용 장비 조합 없음

본 수, slot 수, skin 조합과 animation clip이 지속적으로 늘어나면 단순 파츠 모드가 아니라 이 리깅 모드로 분류해야 한다.

### 20.6.2 해외 공식 근거

#### Godot Skeleton2D

- 문서 URL: https://docs.godotengine.org/en/stable/classes/class_skeleton2d.html
- 공식 원문: https://github.com/godotengine/godot-docs/blob/master/classes/class_skeleton2d.rst
- 증거 유형: 해외 공식 엔진 문서
- 직접 확인 문구:
  > “The parent of a hierarchy of Bone2Ds, used to create a 2D skeletal animation.”
  > “It holds a reference to each Bone2D's rest pose and acts as a single point of access to its bones.”

Skeleton2D는 Bone2D 계층, 본별 rest pose, 선택적 IK modification stack을 관리한다. 즉 리깅 manifest에는 계층과 rest transform이 필수다.

#### Godot Bone2D

- 문서 URL: https://docs.godotengine.org/en/stable/classes/class_bone2d.html
- 공식 원문: https://github.com/godotengine/godot-docs/blob/master/classes/class_bone2d.rst
- 증거 유형: 해외 공식 엔진 문서
- 직접 확인 문구:
  > “A joint used with Skeleton2D to control and animate other nodes.”
  > “These rest poses are relative to the bone's parent.”

본의 rest pose가 부모 기준이며, Polygon2D mesh를 제어할 수 있음을 명시한다.

#### Godot 2D Skeletons Tutorial

- 문서 URL: https://docs.godotengine.org/en/stable/tutorials/animation/2d_skeletons.html
- 공식 원문: https://github.com/godotengine/godot-docs/blob/master/tutorials/animation/2d_skeletons.rst
- 증거 유형: 해외 공식 제작 절차
- 확인 절차:
  - 캐릭터 조각마다 Polygon2D 생성
  - Skeleton2D 아래 Bone2D 계층 생성·이름 지정
  - skeleton rest pose 설정
  - bone 목록을 polygon과 수동 동기화
  - polygon에 bone weight 할당
  - 본 추가·삭제·이름 변경 시 동기화와 rest pose 재설정 필요

직접 확인 문구:
  > “You will not be able to paint weights yet.”
  > “This step is done only once and manually (unless you modify the skeleton by adding/removing/renaming bones).”

리깅은 이미지 생성만으로 끝나지 않고 수동 구조·weight 검증이 필요한 제작 체계라는 직접 근거다.

#### Unity Sprite Skin

- URL: https://docs.unity3d.com/Packages/com.unity.2d.animation@10.0/manual/SpriteSkin.html
- 증거 유형: 해외 공식 엔진 패키지 문서
- 직접 확인 내용:
  > “the Sprite Skin deforms that Sprite by using the bones that were rigged and weighted to the Sprite in the Skinning Editor.”

Sprite Skin은 rigged·weighted bone으로 Sprite mesh를 변형한다. 각 Sprite의 Bone entry는 올바른 GameObject Transform과 연결돼야 하며 Root Bone과 Bones 목록을 관리한다.

#### Unity Sprite Library

- URL: https://docs.unity3d.com/Packages/com.unity.2d.animation@10.0/manual/SL-Asset.html
- 증거 유형: 해외 공식 패키지 문서
- 확인 내용:
  - Sprite를 Category로 그룹화
  - 각 Sprite에 고유 Label 부여
  - Sprite Library와 Resolver를 사용해 visual variant 선택

Category를 slot 또는 부위, Label을 attachment variant로 매핑할 수 있다.

#### Unity Sprite Resolver

- URL: https://docs.unity3d.com/Packages/com.unity.2d.animation@10.0/manual/SL-Resolver.html
- 증거 유형: 해외 공식 패키지 문서
- 직접 확인 문구:
  > “allows you to change the Sprite rendered by that GameObject's Sprite Renderer component.”
  > “The component contains two properties - Category and Label”

페이퍼돌의 런타임 attachment 선택 근거다. 단, 호환성·가림 순서·뼈 매핑은 자동으로 보장하지 않는다.

#### Spine Skins

- URL: https://esotericsoftware.com/spine-skins
- 증거 유형: 해외 전문 2D 리깅 도구 공식 문서
- 직접 확인 문구:
  > “Skins allow a skeleton's animations to be reused with different sets of attachments.”

Skin placeholder는 slot 아래에 있으며 현재 활성 skin이 실제 attachment를 제공한다. 애니메이션을 특정 의상 이미지와 분리해 재사용하는 구조를 뒷받침한다.

#### Spine Slots

- URL: https://esotericsoftware.com/spine-slots
- 증거 유형: 해외 전문 도구 공식 문서
- 직접 확인 문구:
  > “A slot is parented to a bone … a container for attachments, where only one attachment (or none) can be visible at any given time.”

Slot은 bone에 붙고 attachment 가시성과 draw order를 관리한다. 페이퍼돌 manifest에 bone, slot, attachment를 별도 계층으로 저장해야 한다.

#### Spine Attachments

- URL: https://esotericsoftware.com/spine-attachments
- 증거 유형: 해외 전문 도구 공식 문서
- 확인 attachment 유형:
  - region image
  - mesh
  - bounding box
  - clipping polygon
  - path
  - point attachment

Point attachment는 projectile·particle spawn 지점으로도 쓰인다. visual attachment와 hit detection, clipping, VFX socket은 같은 개념이 아니므로 타입을 분리해야 한다.

#### Aseprite 제작 원본

- URL: https://www.aseprite.org/docs/cli/
- 증거 유형: 해외 공식 제작 도구 문서
- 적용 범위:
  - layer별 body/equipment source 분리
  - tag별 animation source 분리
  - sheet+JSON export
  - layer hierarchy 보존

Aseprite는 source image authoring 근거이며 bone·weight·skin runtime schema를 제공하는 리깅 도구는 아니다.

### 20.6.3 해외 실제 구현과 비용 반례

#### Godot 공식 Skeleton2D Demo

- 저장소: https://github.com/godotengine/godot-demo-projects/tree/master/2d/skeleton
- Asset Library: https://godotengine.org/asset-library/asset/2731
- 증거 유형: 해외 공식 오픈소스 구현
- README 직접 확인 문구:
  > “This demo shows how to create a rigged and animated character in 2D using Godot's Skeleton2D node.”
  > “There are several movement-related animations.”

실제 `player/player.tscn` 확인 결과:

- 장면 파일 1,978줄
- Skeleton2D 아래 Hip, Chest, Head, Chin, Arms, Forearms, Hands, Legs, LowerLegs, Feet 등 다수 Bone2D
- AnimationPlayer와 AnimationTree
- animation마다 본별 position·rotation track 다수
- 하나의 본 경로 변경이 여러 clip track에 영향을 줄 수 있음

이 사례는 리깅이 단순 파츠 모드보다 별도 schema·editor·migration·검증을 요구한다는 직접 반례다.

### 20.6.4 조합 폭증 모델

페이퍼돌 비용은 단순히 이미지 개수만으로 결정되지 않는다.

```text
검증 조합 ≈ body type × facing × slot × attachment × animation clip × draw-order case
```

실제 모든 조합을 파일로 생성하지 않더라도 다음 호환성 검증은 남는다.

- attachment가 요구 bone을 갖는가
- slot 크기와 pivot가 맞는가
- 팔 앞/뒤 가림이 맞는가
- 무기와 손 socket이 모든 clip에서 붙는가
- 긴 치마·망토가 다리와 교차하지 않는가
- body type별 silhouette가 clipping을 일으키지 않는가
- 장비 교체 후 collider와 VFX socket이 유효한가

따라서 무제한 자유 조합을 기본 약속하면 안 된다.

### 20.6.5 엄격한 Eligibility Gate

다음 조건 중 여러 개가 참일 때만 full rig mode를 허용한다.

- 5개 이상의 관절 파트가 여러 clip에서 재사용됨
- 캐릭터 외형 variant가 다수 존재
- 장비 교체가 핵심 게임 시스템
- 동일 animation을 여러 skin이 공유해야 함
- 본 기반 socket이 projectile/VFX/gameplay에 필요
- 프로젝트가 rig 수정과 migration 비용을 감당할 수 있음
- 대상 엔진 runtime adapter가 확정됨

다음이면 simple rigid-part 또는 frame animation을 사용한다.

- 파트 1~4개
- 애니메이션 1~3개
- 장비 교체 없음
- 픽셀 실루엣이 각도별로 크게 바뀜
- deformation이 픽셀 군집을 깨뜨림
- engine-independent PNG만 필요한 경우

### 20.6.6 Rig Schema

```yaml
rig:
  id: worker_humanoid_v1
  schema_version: 1
  coordinate_system:
    logical_canvas: [128, 128]
    pixels_per_unit: 16
    origin: [64, 112]
  bones:
    - id: root
      parent: null
      rest_position: [0, 0]
      rest_rotation_deg: 0
      rest_scale: [1, 1]
    - id: hand_r
      parent: forearm_r
      rest_position: [8, 0]
      rest_rotation_deg: 0
      rest_scale: [1, 1]
  slots:
    - id: weapon_r
      bone: hand_r
      draw_order: 40
      default_attachment: none
  skins:
    - id: base_worker
      attachments:
        torso: torso_default
        head: head_default
  clips:
    - id: idle
      duration_ms: 800
      loop: true
```

### 20.6.7 Bones와 Rest Pose

본별 필수 데이터:

- stable bone ID
- parent bone ID
- rest position, rotation, scale
- 길이와 방향
- 상속 정책
- transform limits
- optional IK/constraint

검증:

- 순환 계층 금지
- root 정확히 하나
- parent 누락 금지
- NaN과 비정수 bake 좌표 금지
- rest pose 변경 시 rig version 증가
- bone rename은 migration map 필수

### 20.6.8 Slots, Sockets, Attachments

구분:

- bone: 변환 계층
- slot: attachment 선택과 draw order
- socket/point: gameplay·projectile·VFX 위치
- attachment: region, rigid image, mesh, collider, clipping mask

각 slot은 다음을 가진다.

- bone binding
- allowed attachment type
- default attachment
- draw-order band
- palette/material policy
- compatibility tags

### 20.6.9 Skins와 Compatibility Matrix

```yaml
compatibility:
  body_type_a:
    head: [head_a_01, head_a_02]
    torso: [shirt_a_01, armor_a_02]
    weapon_r: [sword_small, hammer_small]
```

금지 조합도 명시한다.

- body type 불일치
- 필요한 bone 누락
- slot 크기 초과
- 특정 clip에서 clipping 발생
- draw-order variant 미지원

런타임에서 처음 발견하게 두지 말고 export 전에 조합 행렬을 검증한다.

### 20.6.10 Draw Order와 Occlusion

필수:

- 기본 slot order
- clip별 제한적 draw-order key
- facing별 order profile
- front/back hand와 weapon variant
- clipping mask 범위

각 프레임마다 임의 z-sort를 허용하면 디버깅과 engine adapter가 복잡해진다. 지원 가능한 order profile을 제한한다.

### 20.6.11 Pivot, Mesh, Weights

rigid attachment:

- 정수 pivot
- 단일 bone binding
- pixel-perfect 회전 제한

mesh attachment:

- vertex와 UV
- bone indices와 normalized weights
- weight influence 상한
- clipping polygon
- deformation bounds

픽셀아트 기본 정책:

- rigid attachment 우선
- scale과 skew 제한
- mesh deformation은 opt-in
- weight 영향 본 수 제한
- 1×에서 pixel cluster가 깨지면 bake-to-frames로 전환

### 20.6.12 Animation Clips와 Events

clip 필수 데이터:

- clip ID
- duration과 loop
- bone tracks
- slot attachment keys
- draw-order keys
- event markers
- root motion 정책
- collision profile

이벤트 예:

- `foot_contact`
- `attack_contact`
- `projectile_spawn`
- `vfx_emit`
- `equipment_visibility`

### 20.6.13 Bake-to-Frames

rig runtime과 별도로 다음 출력을 지원한다.

```text
baked/
  idle.png
  idle.json
  walk.png
  walk.json
```

사용 조건:

- 대상 엔진에 rig runtime이 없음
- 네트워크 replay보다 렌더 결정성이 중요
- 픽셀 변형 품질을 프레임별로 수정해야 함
- 모바일에서 runtime deformation 비용을 줄여야 함
- engine adapter coupling을 피해야 함

bake 후에도 event, frame duration, pivot와 collision metadata를 유지해야 한다.

### 20.6.14 Engine Adapters

core manifest와 engine adapter를 분리한다.

```text
rig_core.json
adapters/
  godot/
  unity/
  spine-runtime/
baked/
```

adapter 책임:

- 좌표계와 각도 변환
- bone/slot object 생성
- texture atlas binding
- animation clip 변환
- draw-order와 clipping 매핑
- event callback 매핑
- runtime version 호환

core schema가 특정 엔진 class name에 종속되면 다른 엔진 export가 어려워진다.

### 20.6.15 Deterministic Preview

필수 보기:

1. rest pose
2. bone hierarchy와 이름
3. slot과 attachment
4. weight heatmap
5. clip loop
6. 모든 event marker
7. facing별 draw order
8. skin과 장비 조합 matrix
9. runtime rig와 baked frame 비교
10. 1× 실제 픽셀과 정수 확대
11. collider, clipping, socket overlay
12. engine adapter preview

### 20.6.16 Pixel-Art QA

자동·반자동 검사:

- 반 픽셀 bone·pivot
- 비정수 최종 transform
- nearest sampling 누락
- 회전 시 1픽셀 선 소실
- mesh deformation에 의한 pixel cluster 균열
- joint seam과 빈 구멍
- 중복 outline
- 장비와 몸 clipping
- slot draw-order pop
- rest pose와 첫 frame 불일치
- bake 결과와 runtime 결과 차이
- collider와 visual drift
- socket가 손·총구에서 이탈
- skin 교체 후 필수 attachment 누락

### 20.6.17 Versioning과 Migration

rig schema version을 자산 version과 분리한다.

breaking change:

- bone ID 변경·삭제
- parent 변경
- rest pose 변경
- slot 의미 변경
- attachment type 변경
- clip event ID 변경

필수 migration:

- old bone ID → new bone ID
- old slot ID → new slot ID
- attachment compatibility 재검증
- 기존 animation track remap
- baked cache 무효화

### 20.6.18 AI의 역할과 수동 검증

AI가 도울 수 있는 것:

- canonical character sheet에서 파트 mask 제안
- bone과 slot 이름 초안
- 장비 attachment variant 생성
- 기존 skin에 맞춘 constrained image edit
- clipping 위험 조합 우선순위 추천
- rig를 bake한 프레임의 시각적 오류 탐지

AI가 단독 확정하면 안 되는 것:

- rest pose
- bone parent hierarchy
- weight painting
- draw-order profile
- equipment compatibility
- attack contact event
- hitbox와 socket
- pixel cluster 품질 승인

최종 rig validation은 실제 engine adapter와 대표 animation·skin 조합을 재생해 수동 승인해야 한다.

### 20.6.19 판정

리깅·페이퍼돌은 다음과 같은 독립 하위 제품으로 취급한다.

> versioned rig schema + bone/rest pose + slot/skin/attachment + animation/event + compatibility matrix + engine adapter + bake-to-frames

단순 `base + 파트 1~4개` 기능에 본과 skin을 조금씩 덧붙이는 방식으로 구현하면 경계가 무너진다. 리깅은 편집기, 데이터 모델, migration, engine runtime 검증이 모두 필요한 별도 체계다.

범용 Asset Studio의 기본값은 simple rigid-part 또는 frame animation이어야 한다. full rig mode는 eligibility gate를 통과한 프로젝트에만 명시적으로 활성화한다.

이 항목은 조사 완료로 판정한다.
