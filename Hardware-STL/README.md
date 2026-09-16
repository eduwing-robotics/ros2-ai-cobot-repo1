# 🤖 Robot Assembly & Vision Inspection System

협동로봇과 비전 시스템을 활용한 **자동 조립 및 외관 검사 시스템**입니다.

본 프로젝트에서 저는 **하드웨어 설계 및 제작, 전체 작업 셀 구성​**을 담당했습니다.

---

## 👨‍💻 My Role

**박태진 | Hardware**

자동화 공정이 실제 환경에서 동작할 수 있도록 로봇 주변 장치와 작업 환경을 설계하고 제작했습니다.

주요 담당 영역은 다음과 같습니다.

- 자동화 작업 셀 구성
- 컨베이어 및 정지 구간 구성
- 부품 트레이 설계 및 제작
- 메인보드 고정 지그 제작
- 로봇 그리퍼 커스텀 핑거 설계
- RealSense D435 장착 브래킷 설계
- 하드웨어 3D 모델링 및 제작
- 로봇 / 비전 장비 / 컨베이어 배치

---

# 🔧 Hardware Design

## 1. Automation Cell

로봇의 조립 작업과 비전 검사가 하나의 공정으로 연결될 수 있도록 전체 작업 셀을 구성했습니다.

```text
Parts Tray
    ↓
Robot Pick & Place
    ↓
Mainboard Assembly
    ↓
Conveyor
    ↓
Vision Inspection
```

컨베이어에는 **조립 위치와 검사 위치에 대응하는 2개의 정지 구간**을 구성했습니다.

이를 통해

**부품 조립 → 제품 이송 → 외관 검사**

과정이 하나의 자동화 공정으로 이어질 수 있도록 설계했습니다.

---

## 2. Parts Tray

로봇이 부품을 안정적으로 Pick할 수 있도록 **부품 전용 트레이를 설계 및 제작**했습니다.

### Features

- 총 **25개 부품 고정**
- 각 부품 위치 고정
- 로봇 Pick 작업을 고려한 배치
- 3D 프린팅을 이용한 제작

부품의 위치가 일정하게 유지되도록 구성하여 로봇이 반복적으로 동일한 위치에서 부품을 집을 수 있는 작업 환경을 만들었습니다.

---

## 3. Mainboard Jig

조립 과정에서 메인보드의 위치가 움직이지 않도록 **전용 고정 지그를 설계 및 제작**했습니다.

```text
Robot
  ↓
Component
  ↓
┌─────────────────┐
│    Mainboard    │
│                 │
│       Jig       │
└─────────────────┘
```

로봇 조립 작업 시 대상 기판의 위치를 일정하게 유지할 수 있도록 구성했습니다.

---

## 4. Custom Gripper Finger

### DH PGEA-100-40

FAIRINO FR5에 장착된 전동 그리퍼를 실제 조립 작업에 사용할 수 있도록 **커스텀 그리퍼 핑거를 설계 및 제작**했습니다.

```text
Robot
  │
PGEA-100-40
  │
Custom Finger
  │
Component
```

부품 Pick & Place 작업에 적합하도록 파지 구조를 구성했습니다.

---

## 5. RealSense D435 Mount

로봇에 RGB-D 카메라를 장착하기 위한 **RealSense D435 전용 브래킷을 설계 및 제작**했습니다.

### Eye-in-Hand

```text
FR5 Robot
    │
End Effector
    ├── Gripper
    │
    └── RealSense D435
```

카메라가 로봇 말단부와 함께 이동할 수 있도록 구성하여 **Eye-in-Hand 비전 시스템을 위한 하드웨어 환경**을 구축했습니다.

---

# 🧊 3D Modeling & Fabrication

프로젝트에서 필요한 커스텀 하드웨어 부품을 직접 모델링하고 제작했습니다.

### Designed Parts

```text
├── Parts Tray
├── Mainboard Jig
├── Gripper Finger
└── RealSense D435 Mount
```

실제 로봇의 동작 범위와 주변 장비 위치를 고려하여 각 부품과 전체 작업 셀을 구성했습니다.

---

# ⚙️ Hardware

| Hardware | Purpose |
|---|---|
| FAIRINO FR5 | 6-Axis Collaborative Robot |
| DH PGEA-100-40 | Electric Gripper |
| Custom Gripper Finger | Component Pick & Place |
| Intel RealSense D435 | Eye-in-Hand RGB-D Camera |
| Galaxy S22 | Vision Inspection Camera |
| GoPro | Cell Monitoring |
| Conveyor | Product Transfer |
| Parts Tray | Component Positioning |
| Mainboard Jig | Mainboard Positioning |
| E-STOP | Emergency Stop |

---

# 🏭 Process

전체 시스템의 물리적인 공정 흐름은 다음과 같이 구성했습니다.

```text
[Parts Tray]

      ↓

[Robot Pick]

      ↓

[Mainboard Assembly]

      ↓

[Conveyor]

      ↓

[Inspection Position]

      ↓

[Vision Inspection]
```

로봇, 컨베이어, 비전 장비가 하나의 작업 셀에서 동작할 수 있도록 각각의 위치와 하드웨어 구조를 구성했습니다.

---

# 🎯 My Contribution

프로젝트에서 제가 집중한 부분은 **소프트웨어에서 계획된 자동화 공정을 실제 물리 환경에서 구현할 수 있도록 만드는 것**이었습니다.

단순히 장비를 배치하는 것에 그치지 않고,

**설계 → 3D 모델링 → 제작 → 장착 → 작업 셀 구성**

과정을 통해 로봇이 실제 부품을 조립하고 이후 검사 공정으로 전달할 수 있는 하드웨어 기반을 구축했습니다.

### Contribution Summary

```text
Automation Cell Design
        │
        ├── Conveyor Setup
        ├── Parts Tray
        ├── Mainboard Jig
        ├── Custom Gripper Finger
        └── RealSense D435 Mount
```

결과적으로

> **부품 이송 → 로봇 조립 → 컨베이어 이송 → 외관 검사**

로 이어지는 자동화 공정을 실제 하드웨어 환경에서 구현할 수 있도록 작업 셀을 구성했습니다.