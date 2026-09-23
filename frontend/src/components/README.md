# Top/Bottom 첫 클릭 점프 수정
## 변경 요약

1. **getLineOffsets / ensureLineOffsets**  
   offset 미설정 시 `max(h/2, minChipGapNorm)`으로 채워 첫 클릭 점프 제거
2. **`.chord-line { min-height: 0 }`**  
   18px min-height로 인한 bottom 스냅 제거
