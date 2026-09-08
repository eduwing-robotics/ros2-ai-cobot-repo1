# 휴대폰 기판 검사 인계 — 2026-09-06

작성: 2026-09-06T21:30:04.232091+09:00

오늘 상세는 [작업일지](../작업일지/2026-09-06.md). 휴대폰 동결 백업은 [phone_camera_20260906_213004](../vision_assembly/checkpoints/phone_camera_20260906_213004/README.md).

## 현재 상태

- 폰 SM-F936N / Android16 / serial R3CTA0K0T9L, scrcpy4.1 직접H264 USB 수신.
- 4K/30fps, camera0, zoom1, ROI[1040,465,800,450]→960×540.
- 25개슬롯표시 + 실제SMD5개만검사 + KST/5초배터리갱신.
- C03/04/05개별위치보정은사용자확인완료. 화면보정은로봇보정과독립이다.
- 전체25개조립성공기준은 `full_cycle_success_20260906`에별도동결돼있다.
- **마지막저장시점:MOVED, 영상수신은지속. 짧은LOCKED시험성공과장시간안정성을혼동하지말것.**
- 고정기준재획득후mm*평면추정가능. 높이보정OFF,실측높이없음,렌즈/크롭검증없음.
- phone작업에서는로봇/그리퍼/컨베이어명령을보내지않았다. 과거로봇위치는현재실측이아니다.

## 재개 명령

```bash
adb devices -l
pgrep -af '^/home/juchan-yoon/.local/opt/fr5-phone-venv/bin/python'
/home/juchan-yoon/.local/bin/fr5-phone-view
```

이미뷰어가실행중이면마지막명령을중복실행하지않는다. 새영상은초기5초대기후60프레임기준수집.

- O: 목표슬롯표시켜기/끄기. 끄면해당표시경로의검사도갱신되지않으므로검사중사용에주의.
- R: 현재네구멍으로기준재획득. 실제기판상태를먼저확인한다.
- Q/Esc: 뷰어닫기.
- GUI없이재획득이필요하면 `touch /home/juchan-yoon/.local/share/fr5-phone/request_reacquire` (뷰어가2초주기로소비). 카메라를재시작할필요없다.
- USB미인식이면잠금해제/USB디버깅허용확인. DroidCam은실행할필요없고동시카메라점유를피한다.

## 실행 파일과 자료

- 실행기: `/home/juchan-yoon/.local/bin/fr5-phone-view`
- 코드/설정/기록: `/home/juchan-yoon/.local/share/fr5-phone/`
- Python환경: `/home/juchan-yoon/.local/opt/fr5-phone-venv/` (system-site-packages, PyAV18.1.0, 시스템OpenCV4.6.0)
- scrcpy: `/home/juchan-yoon/.local/opt/scrcpy-linux-x86_64-v4.1/`
- `viewer.py`: directH264, 최신프레임만표시, 최초5초안정화, HUD/기준재획득.
- `board_overlay.py`: 원본라벨직접정합, 전체1도윤곽회전, 개별C03/04/05위치보정.
- `stable_board.py`:60프레임기준고정,가림/3프레임이동시숨김,MOVED수동재획득.
- `part_inspector.py`: SMD흰색실물윤곽검출,픽셀/각도오차,6프레임안정성,미검출값삭제.
- `phone_hud.py`: KST시각,배터리5초갱신,갱신오래됨/영상끊김표시.
- `metric_geometry.py`: mm*잠정평면변환,검증플래그에의해차단된높이광선보정.
- `view.json`, `reference_holes.json`, `slot_display_corrections.json`, `metric_config.json`, `phone_intrinsics_candidate.json`: 보존해야할설정.
- `c03_*validation.json`, `metric_geometry_test_result.json`: 실기/기하검증기록.
- `overlay_status.json`, `battery_status.json`, `locked_board.json`: 실행중상태; 영구캘리브레이션으로로드하지않음.
- `/tmp/fr5_phone_latest_raw.png`: 최근표시전영상, `/tmp/fr5_phone_mount_preview.jpg`:최근HUD영상.
- `/tmp/fr5_phone_lowlatency_status.json`, `/tmp/fr5_phone_lowlatency_server.log`:진단정보.

## 반드시 남겨 둘 제한과 다음 작업

1. 반복MOVED미해결: 실제움직임/OIS/초점/검출변화를분리. OIS ON관측. 표시고정으로물리정확도가확보된것아님.
2. 광학배율변경이나폰위치변경시ROI/정합/캘리브레이션재검증필요. 영상4K여도기판원본폭약300픽셀.
3. 구멍중심거리와SMD높이실측값요청은미응답상태. CAD3.02376mm를실측으로대체금지.
4. mm축은board X/Y, 픽셀축은화면right/down. 숫자비교시좌표계를혼동하지말것.
5. 높이보정은기능코드만준비됐고OFF. K후보의크롭/왜곡처리검증없음. PnP재투영RMS가작아도절대정확도보증아님.
6. 높이보정을나중에켜면현재HUD/하단의고정 `HEIGHT OFF` 문구도실제상태에연동하도록수정필요.
7. 실제부품센터/각도연속측정은SMD5개만지원. 각도는180도축대칭이며극성검사아님.
8. C03영상이동/회전/제거시험은통과했지만mm실측정답시험은없다. 나머지SMD실물개별검증도미완료.
9. 기존로봇레시피/Tool1/HandEye/기판배치보정은이번phone실험으로변경하지않는다.

## 복구

동결백업의 `phone_runtime/`는실행소스·설정·검증자료, `tools/`는scrcpy와Python환경사본, `tmp_evidence/`는당일임시증거, `repo_inputs/`는입력라벨/설정이다.
복구전현재파일과비교한다. 같은PC의원래절대경로를기준으로한실행기이며venv는시스템패키지를공유한다. 다른PC에서는환경재설치와카메라보정이필요하다.
`manifest.json`은파일내용/심볼릭링크대상의SHA256을기록한다. `verification.json`이최종검증결과다.
