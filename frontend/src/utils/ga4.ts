import ReactGA from "react-ga4";

const GA4_MEASUREMENT_ID = "G-JG5BXZD511";

/**
 * GA4 초기화
 */
export const initializeGA4 = () => {
  ReactGA.initialize(GA4_MEASUREMENT_ID);
};

/**
 * 페이지 뷰 추적
 */
export const trackPageView = (path: string) => {
  ReactGA.send({
    hitType: "pageview",
    page: path,
  });
};

/**
 * 커스텀 이벤트 추적
 */
export const trackEvent = (
  eventName: string,
  eventData?: Record<string, any>
) => {
  ReactGA.event(eventName, eventData);
};

/**
 * 주요 이벤트들
 */
export const GA4Events = {
  // 인증 관련
  LOGIN: "login",
  LOGOUT: "logout",
  SIGNUP: "signup",

  // 채팅 관련
  SEND_MESSAGE: "send_message",
  RECEIVE_MESSAGE: "receive_message",
  CHAT_SESSION_START: "chat_session_start",
  CHAT_SESSION_END: "chat_session_end",

  // 업로드 관련
  FILE_UPLOAD_START: "file_upload_start",
  FILE_UPLOAD_SUCCESS: "file_upload_success",
  FILE_UPLOAD_ERROR: "file_upload_error",
  FILE_UPLOAD_COMPLETE: "file_upload_complete",

  // 평가 관련
  EVALUATION_START: "evaluation_start",
  EVALUATION_PAUSE: "evaluation_pause",
  EVALUATION_RESUME: "evaluation_resume",
  EVALUATION_SKIP: "evaluation_skip",

  // 자동 답변 관련
  AUTO_REPLY_TEST: "auto_reply_test",
  AUTO_REPLY_SAVE: "auto_reply_save",
  AUTO_REPLY_DELETE: "auto_reply_delete",

  // 페이지 네비게이션
  NAVIGATE_TO_CHAT: "navigate_to_chat",
  NAVIGATE_TO_ADMIN: "navigate_to_admin",
  NAVIGATE_TO_UPLOAD: "navigate_to_upload",
  NAVIGATE_TO_AGENT: "navigate_to_agent",
  NAVIGATE_TO_AUTO_REPLY: "navigate_to_auto_reply",
};

/**
 * 파일 업로드 이벤트
 */
export const trackFileUpload = (
  schoolName: string,
  fileName: string,
  fileSize: number,
  status: "start" | "success" | "error"
) => {
  const eventName =
    status === "start"
      ? GA4Events.FILE_UPLOAD_START
      : status === "success"
        ? GA4Events.FILE_UPLOAD_SUCCESS
        : GA4Events.FILE_UPLOAD_ERROR;

  trackEvent(eventName, {
    school_name: schoolName,
    file_name: fileName,
    file_size: fileSize,
    timestamp: new Date().toISOString(),
  });
};

/**
 * 채팅 메시지 이벤트
 */
export const trackChatMessage = (
  messageType: "user" | "assistant",
  messageLength: number,
  schoolName?: string
) => {
  const eventName =
    messageType === "user"
      ? GA4Events.SEND_MESSAGE
      : GA4Events.RECEIVE_MESSAGE;

  trackEvent(eventName, {
    message_type: messageType,
    message_length: messageLength,
    school_name: schoolName || "unknown",
    timestamp: new Date().toISOString(),
  });
};

/**
 * 평가 중단/시작 이벤트
 */
export const trackEvaluationToggle = (isPaused: boolean) => {
  const eventName = isPaused
    ? GA4Events.EVALUATION_PAUSE
    : GA4Events.EVALUATION_RESUME;

  trackEvent(eventName, {
    evaluation_paused: isPaused,
    timestamp: new Date().toISOString(),
  });
};

/**
 * 평가 스킵 이벤트
 */
export const trackEvaluationSkip = (logId: string) => {
  trackEvent(GA4Events.EVALUATION_SKIP, {
    log_id: logId,
    timestamp: new Date().toISOString(),
  });
};

/**
 * 자동 답변 테스트 이벤트
 */
export const trackAutoReplyTest = (
  keyword: string,
  success: boolean,
  responseTime?: number
) => {
  trackEvent(GA4Events.AUTO_REPLY_TEST, {
    keyword: keyword,
    success: success,
    response_time_ms: responseTime || 0,
    timestamp: new Date().toISOString(),
  });
};
