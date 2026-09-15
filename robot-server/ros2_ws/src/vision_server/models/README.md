# YOLO model

학습이 끝난 모델을 이 폴더에 `best.pt`라는 이름으로 둔다.

```text
vision_server/models/best.pt
```

모델 클래스 순서는 `config/dataset.yaml`과 같아야 한다. 모델이 없을 때
`part_detector`는 종료되지 않고 `/vision/status`에 `model_loaded=false`를
발행한다.
