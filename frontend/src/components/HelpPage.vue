<template>
  <div class="help">
    <div class="help-head">
      <h1>사용법</h1>
      <p class="lead">
        기타 코드 악보 사진을 올리면 OCR로 코드를 읽고,<br />
        위치·내용을 보정한 뒤 원하는 Key로 조옮김합니다.
      </p>
    </div>

    <section class="card step">
      <div class="step-num">1</div>
      <div class="step-body">
        <h2>악보 업로드</h2>
        <ul>
          <li>홈 화면에서 <strong>업로드</strong> 또는 검색창 옆 버튼으로 이미지를 선택합니다.</li>
          <li>휴대폰으로 찍은 사진, 캡처 화면 모두 가능합니다.</li>
          <li>가능하면 <strong>코드가 잘 보이는 밝은 사진</strong>을 올려 주세요. (기울기·그림자는 OCR 정확도에 영향을 줍니다.)</li>
          <li>제목을 미리 입력해 두면 저장 시 편합니다.</li>
        </ul>
      </div>
    </section>

    <section class="card step">
      <div class="step-num">2</div>
      <div class="step-body">
        <h2>OCR · 코드 보정</h2>
        <ul>
          <li>업로드 후 <strong>코드 보정</strong> 화면으로 이동합니다.</li>
          <li>OCR이 읽은 코드가 악보 위에 표시됩니다. 100% 정확하지 않을 수 있습니다.</li>
          <li>
            <strong>잘못된 코드</strong>는 더블탭(더블클릭)해서 고치거나 삭제하고,
            <strong>빠진 코드</strong>는 추가,
            <strong>위치</strong>는 드래그·줄 단위로 맞춥니다.
          </li>
          <li>코드를 더블탭하면 이름을 고칠 수 있고, 그때 옆에 뜨는 × 버튼으로 삭제합니다. (드래그 중 실수로 지워지지 않도록 평소엔 × 표시가 숨겨져 있어요)</li>
          <li>코드 글자 크기도 조절할 수 있고, 여러 줄을 한번에 선택해 위치를 옮기는 도구도 있습니다.</li>
          <li><strong>저장</strong>을 누르면 제목을 확인한 뒤 자동으로 조옮김 화면으로 이동합니다.</li>
        </ul>
        <p class="tip">
          팁: OCR은 초안입니다. 연주할 Key만 맞추려면 핵심 코드 줄만 빠르게 손보면 됩니다.
        </p>
      </div>
    </section>

    <section class="card step">
      <div class="step-num">3</div>
      <div class="step-body">
        <h2>조옮김</h2>
        <ul>
          <li>반음 단위로 Key를 올리거나 내립니다. (예: +2, −1)</li>
          <li><strong>원곡(코드)</strong> 버튼을 누르면 몇 번을 옮겼든 상관없이 바로 원래 키로 돌아갑니다.</li>
          <li>결과는 <strong>원본 악보 위에 코드를 다시 그린 이미지</strong>로 바로 미리볼 수 있습니다.</li>
          <li>저장해 둔 곡은 홈 목록·검색에서 다시 열어 조옮김할 수 있습니다.</li>
          <li><strong>수정</strong> 버튼으로 코드 보정 화면에 돌아가 고친 뒤 다시 조옮김할 수 있습니다.</li>
          <li><strong>다운로드</strong> 버튼으로 현재 보이는 결과 이미지를 저장할 수 있습니다.</li>
        </ul>
        <p class="tip warn">
          ⚠️ <strong>삭제</strong> 버튼은 곡과 원본 이미지를 완전히 지웁니다. 되돌릴 수 없으니 주의해 주세요.
        </p>
      </div>
    </section>

    <section class="card step">
      <div class="step-num">4</div>
      <div class="step-body">
        <h2>목록 · 검색</h2>
        <ul>
          <li>저장한 곡은 제목 <strong>초성별 폴더</strong>로 정리됩니다. 폴더를 탭하면 그 안의 곡 목록으로 이동하고, 상단 경로를 눌러 다시 나올 수 있습니다.</li>
          <li>검색창에 제목(또는 일부)을 입력해 찾을 수 있습니다.</li>
          <li>같은 제목이 있으면 저장 시 기존 곡에 덮어쓸지, 별개의 새 곡으로 저장할지 선택할 수 있습니다.</li>
        </ul>
      </div>
    </section>

    <section class="card info">
      <h2>OCR 사용량</h2>
      <p>
        상단 <strong>OCR 배지</strong>는 이번 달 Google Vision OCR 호출 횟수입니다.
        월간 한도가 있으면 초과 시 새 OCR은 다음 달까지 제한될 수 있습니다.
        이미 저장·보정한 곡의 조옮김은 OCR 없이도 가능합니다.
      </p>
    </section>

    <section class="card info">
      <h2>홈 화면에 설치 (선택)</h2>
      <ul>
        <li>
          <strong>Android Chrome</strong>: 조건이 맞으면 「앱 설치」 배너 또는 주소창 설치 아이콘이 나타날 수 있습니다.
        </li>
        <li>
          <strong>iPhone Safari</strong>: 공유 버튼 → <strong>홈 화면에 추가</strong>.
          (카톡 등 인앱 브라우저에서는 안 보일 수 있으니 Safari로 열어 주세요.)
        </li>
      </ul>
    </section>

    <section class="card info">
      <h2>알아두면 좋은 점</h2>
      <ul>
        <li>오프라인에서는 앱 화면만 열리고, <strong>업로드·OCR·조옮김</strong>은 네트워크가 필요합니다.</li>
        <li>코드 인식은 자동 완성이 아니라 <strong>초안 + 수동 보정</strong>을 전제로 합니다.</li>
        <li>개인·팀용 도구로, 계정 로그인 없이 동작합니다. 공유·백업이 필요하면 별도 관리해 주세요.</li>
      </ul>
    </section>
  </div>
</template>

<style scoped>
.help {
  max-width: 640px;
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
}

.help-head {
  margin-bottom: 0.35rem;
}

.help-head h1 {
  margin: 0 0 0.4rem;
  font-size: 1.45rem;
  font-weight: 800;
  letter-spacing: -0.02em;
}

.lead {
  margin: 0;
  color: var(--text-muted, #5c6578);
  font-size: 0.95rem;
  line-height: 1.55;
}

.card {
  background: var(--surface, #fff);
  border: 1px solid var(--border, #e2e6ef);
  border-radius: var(--radius, 12px);
  box-shadow: var(--shadow, 0 1px 3px rgba(16, 24, 40, 0.06));
  padding: 1rem 1.15rem;
}

.step {
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.step-num {
  flex-shrink: 0;
  width: 1.85rem;
  height: 1.85rem;
  border-radius: 50%;
  background: linear-gradient(145deg, #2563eb, #0f766e);
  color: #fff;
  font-weight: 800;
  font-size: 0.95rem;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 0.1rem;
}

.step-body h2,
.info h2 {
  margin: 0 0 0.45rem;
  font-size: 1.05rem;
  font-weight: 750;
}

.step-body ul,
.info ul {
  margin: 0;
  padding-left: 1.15rem;
  color: var(--text, #1a1d26);
  font-size: 0.92rem;
  line-height: 1.6;
}

.step-body li,
.info li {
  margin-bottom: 0.3rem;
}

.step-body li:last-child,
.info li:last-child {
  margin-bottom: 0;
}

.info p {
  margin: 0;
  font-size: 0.92rem;
  line-height: 1.6;
  color: var(--text, #1a1d26);
}

.tip {
  margin: 0.65rem 0 0;
  padding: 0.55rem 0.75rem;
  border-radius: 8px;
  background: var(--primary-soft, #eff4ff);
  border: 1px solid #bfdbfe;
  color: #1e40af;
  font-size: 0.85rem;
  line-height: 1.45;
}

.tip.warn {
  background: #fef2f2;
  border-color: #fca5a5;
  color: #b91c1c;
}

@media (max-width: 480px) {
  .step {
    gap: 0.7rem;
  }
  .lead br {
    display: none;
  }
}
</style>
