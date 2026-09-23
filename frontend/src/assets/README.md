# Left/Right 칩 밀림 수정 (+ Top/Bottom 첫 클릭 수정 포함)

## 적용 경로

| 파일 | 복사 위치 |
|------|-----------|
| `ChordEditor.vue` | `frontend/src/components/ChordEditor.vue` |
| `chord-editor.css` | `frontend/src/assets/chord-editor.css` |
| `useLinesData.js` | `frontend/src/composables/chord-editor/useLinesData.js` |

```bash
cp ChordEditor.vue frontend/src/components/ChordEditor.vue
cp chord-editor.css frontend/src/assets/chord-editor.css
cp useLinesData.js frontend/src/composables/chord-editor/useLinesData.js
```

로컬 확인 후 직접 커밋·푸시하세요. GitHub에는 올리지 않았습니다.

## 변경 요약

### Left/Right (이번 수정)
- `item.t` = 이미지 절대 가로 위치 (OCR과 동일)
- `bumpLineLeft` / `bumpLineRight`는 **박스 경계만** 변경, 칩 `t` 재계산 삭제
- `chordLeftPct`는 `item.t`를 그대로 %로 표시 (줄 박스와 무관)
- 가장자리 칩을 넘지 못하도록 하는 제한만 유지

### Top/Bottom (이전 수정 포함)
- offset 초기화 `max(h/2, minChipGapNorm)`
- `.chord-line { min-height: 0 }`

### useLinesData
- 로드 시 `xStart`/`xEnd`를 전체폭으로 리셋하지 않음 (Left/Right 저장 유지)
- `t`는 절대 좌표로 정규화
