const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const userIdInput = document.getElementById("userId");
const loadProfileBtn = document.getElementById("loadProfileBtn");
const lastInputText = document.getElementById("lastInputText");
const tableError = document.getElementById("tableError");
const scoreTableBody = document.getElementById("scoreTableBody");
const extractorJson = document.getElementById("extractorJson");

const TABLE_ROWS = [
  { label: "한국사", key: "한국사", type: "korean_history" },
  { label: "국어", key: "국어", type: "korean" },
  { label: "수학", key: "수학", type: "math" },
  { label: "영어", key: "영어", type: "english" },
  { label: "탐구1", key: "탐구1", type: "inquiry" },
  { label: "탐구2", key: "탐구2", type: "inquiry" },
  { label: "제2외국어/한문", key: "제2외국어/한문", type: "second_language" },
];

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function resolveApiBase() {
  return window.location.origin;
}

function pretty(value) {
  return JSON.stringify(value, null, 2);
}

function getRowEntry(scores, row) {
  if (row.key === "제2외국어/한문") {
    return (
      scores["제2외국어/한문"] ||
      scores["제2외국어"] ||
      scores["한문"] ||
      {}
    );
  }
  return scores[row.key] || {};
}

function getSelectedValue(row, entry) {
  if (row.type === "korean_history") return "-";
  if (row.type === "korean" || row.type === "math") {
    return entry["선택과목"] || "미응시";
  }
  if (row.type === "english") {
    return entry["등급"] != null || entry["표준점수"] != null || entry["백분위"] != null
      ? "영어"
      : "미응시";
  }
  if (row.type === "inquiry") {
    return entry["과목명"] || "미응시";
  }
  return entry["과목명"] || "미응시";
}

function buildSelectCell(row, renderedValue) {
  if (row.type === "korean_history") {
    return `<span class="plain-cell">-</span>`;
  }

  return `<span class="plain-cell">${renderedValue}</span>`;
}

function scoreOrDash(value) {
  return value == null || value === "" ? "-" : escapeHtml(value);
}

function isSelectionEstimated(row, completedEntry, extractedEntry) {
  if (completedEntry?.["추정됨"]) return true;
  if (row.type === "korean" || row.type === "math") {
    const hasExtractedElective = extractedEntry["선택과목"] != null;
    const hasCompletedElective = completedEntry?.["선택과목"] != null;
    if (hasCompletedElective && !hasExtractedElective) return true;
  }
  if (row.type === "inquiry") {
    const hasExtractedInquiry = extractedEntry["선택과목"] != null || extractedEntry["과목명"] != null;
    const hasCompletedInquiry = completedEntry?.["과목명"] != null || completedEntry?.["선택과목"] != null;
    if (hasCompletedInquiry && !hasExtractedInquiry) return true;
  }
  if (row.type === "english") {
    const hasExtractedElective = extractedEntry["선택과목"] != null;
    const hasCompletedMetric =
      completedEntry?.["등급"] != null || completedEntry?.["표준점수"] != null || completedEntry?.["백분위"] != null;
    if (hasCompletedMetric && !hasExtractedElective) return true;
  }
  if (row.type === "second_language") {
    const hasExtractedSecond = extractedEntry["선택과목"] != null;
    if (!hasExtractedSecond) {
      return true;
    }
  }
  return false;
}

function getExtractorPrimaryType(extractedEntry) {
  if (!extractedEntry) return null;
  if (extractedEntry["표준점수"] != null) return "표준점수";
  if (extractedEntry["백분위"] != null) return "백분위";
  if (extractedEntry["등급"] != null) return "등급";
  return null;
}

function isMetricEstimated(metricKey, row, completedEntry, extractedEntry) {
  const completedValue = completedEntry?.[metricKey];
  if (completedValue == null) return false;
  if (extractedEntry?.[metricKey] != null) return false;

  if (completedEntry?.["추정됨"]) return true;

  const primaryType = getExtractorPrimaryType(extractedEntry);
  if (!primaryType) return true;

  if (primaryType === "등급") {
    return metricKey === "표준점수" || metricKey === "백분위";
  }
  if (primaryType === "표준점수") {
    return metricKey === "등급" || metricKey === "백분위";
  }
  if (primaryType === "백분위") {
    return metricKey === "표준점수";
  }

  return false;
}

function formatCell(value, estimated, emptyFallback = "-") {
  const base = value == null || value === "" ? emptyFallback : escapeHtml(value);
  const tag = estimated ? ' <span class="estimated-inline">(추정됨)</span>' : "";
  return `${base}${tag}`;
}

function renderScoreTable(scores, extractedScores = {}) {
  const completedScores = scores || {};
  const rows = TABLE_ROWS.map((row) => {
    const entry = getRowEntry(completedScores, row);
    const extractedEntry = getRowEntry(extractedScores || {}, row);
    const entryEstimated = !!entry?.["추정됨"];
    const selectionEstimated = isSelectionEstimated(row, entry, extractedEntry);
    const selected = getSelectedValue(row, entry);
    const stdScore =
      row.type === "english" || row.type === "korean_history"
        ? "-"
        : formatCell(entry["표준점수"], isMetricEstimated("표준점수", row, entry, extractedEntry));
    const percentile =
      row.type === "english" || row.type === "korean_history"
        ? "-"
        : formatCell(entry["백분위"], isMetricEstimated("백분위", row, entry, extractedEntry));
    const grade = formatCell(entry["등급"], isMetricEstimated("등급", row, entry, extractedEntry));
    const selectionFallback = row.type === "second_language" ? "미응시" : "-";
    const selection = formatCell(
      selected === "-" ? "" : selected,
      selectionEstimated,
      selectionFallback
    );

    return `
      <tr>
        <td>${escapeHtml(row.label)}</td>
        <td>${buildSelectCell(row, selection)}</td>
        <td>${stdScore}</td>
        <td>${percentile}</td>
        <td>${grade}</td>
      </tr>
    `;
  }).join("");

  scoreTableBody.innerHTML = rows;
}

function renderResult(data) {
  tableError.textContent = "";
  renderScoreTable(data.completed_scores || {}, data.extracted_scores || {});
  extractorJson.textContent = pretty(data.extracted_scores || {});
}

function setLastInputText(value) {
  const text = (value || "").trim();
  lastInputText.textContent = text || "아직 입력 없음";
}

async function callChatApi(payload) {
  const base = resolveApiBase();
  const response = await fetch(`${base}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`API ${response.status}: ${detail}`);
  }
  return response.json();
}

async function loadProfile(userId) {
  const base = resolveApiBase();
  const response = await fetch(`${base}/api/profile/${encodeURIComponent(userId)}`);
  if (!response.ok) {
    const detail = await response.text();
    throw new Error(`조회 실패 ${response.status}: ${detail}`);
  }
  return response.json();
}


chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const user_id = (userIdInput.value || "").trim();
  const message = (chatInput.value || "").trim();
  if (!user_id || !message) return;

  setLastInputText(message);
  chatInput.value = "";

  try {
    const result = await callChatApi({ user_id, message });
    renderResult(result);
  } catch (error) {
    tableError.textContent = `오류: ${error.message}`;
  }
});

loadProfileBtn.addEventListener("click", async () => {
  const user_id = (userIdInput.value || "").trim();
  if (!user_id) return;

  try {
    const profile = await loadProfile(user_id);
    setLastInputText(profile.latest_message || "");
    renderScoreTable(profile.completed_scores || {}, profile.extracted_scores || {});
    extractorJson.textContent = pretty(profile.extracted_scores || {});
    tableError.textContent = "";
  } catch (error) {
    tableError.textContent = `조회 오류: ${error.message}`;
  }
});

renderScoreTable({});
extractorJson.textContent = pretty({});

