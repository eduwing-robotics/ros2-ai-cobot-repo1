# 페이지 레일 아이콘

출처: [Siemens iX Icons](https://github.com/siemens/ix-icons) `@siemens/ix-icons` 3.5.0 — **MIT License**, Copyright (c) 2022 Siemens AG.

원본 512×512 SVG 를 52×52 PNG(26px 표시의 2배)로 변환하고 RGB 를 흰색으로 고정했다.
색은 이미지가 아니라 `-unity-background-image-tint-color` 가 정한다 — 그래야 활성 탭에서
`--c-accent` 를 따라간다. 이미지에 색을 구우면 모드 전환(MOCK 노랑 / REAL 파랑)을 못 따라간다.

| 파일 | iX 원본 | 쓰이는 곳 |
|---|---|---|
| `nav-monitor.png` | `monitoring.svg` | MONITOR 탭 |
| `nav-run.png` | `play.svg` | RUN 탭 |
| `nav-inspect.png` | `eye.svg` | INSPECT 탭 |
| `nav-manual.png` | `hand.svg` | MANUAL 탭 |
| `nav-quality.png` | `quality-report.svg` | QUALITY 탭 |
| `nav-setup.png` | `cogwheel.svg` | SETUP 탭 |
| `view-twin.png` | `maximize.svg` | TWIN 집중 |

이전에는 아이콘을 `VisualElement` 를 겹쳐 손으로 그렸다. 7개가 서로 굵기와 여백이 달랐고
새 항목을 넣을 때마다 좌표를 손으로 맞춰야 했다.
