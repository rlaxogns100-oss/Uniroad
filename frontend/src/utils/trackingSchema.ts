export const TrackingEventNames = {
  pageView: 'page_view',
  authModalView: 'auth_modal_view',
  loginClick: 'login_click',
  signupClick: 'signup_click',
  oauthClick: 'oauth_click',
  loginCompleted: 'login_completed',
  signupCompleted: 'signup_completed',
  landingCtaClick: 'landing_cta_click',
  firstInteraction: 'first_interaction',
  featureCardClick: 'feature_card_click',
  exampleQuestionClick: 'example_question_click',
  chatFirstMessage: 'chat_first_message',
  chatMessageSent: 'chat_message_sent',
  chatBlockedAuthRequired: 'chat_blocked_auth_required',
  schoolRecordEntryClick: 'school_record_entry_click',
  schoolRecordPdfUploadStarted: 'school_record_pdf_upload_started',
  schoolRecordPdfUploadSucceeded: 'school_record_pdf_upload_succeeded',
  schoolRecordPdfUploadFailed: 'school_record_pdf_upload_failed',
  schoolRecordSaved: 'school_record_saved',
  schoolRecordAnalysisRequested: 'school_record_analysis_requested',
  scoreLinkEntryClick: 'score_link_entry_click',
  scoreInputModeSelected: 'score_input_mode_selected',
  scoreAutofillStarted: 'score_autofill_started',
  scoreSaved: 'score_saved',
  scoreRecommendationRequested: 'score_recommendation_requested',
  paywallView: 'paywall_view',
  paymentCtaClick: 'payment_cta_click',
  paymentMethodModalView: 'payment_method_modal_view',
  paymentMethodModalDismissed: 'payment_method_modal_dismissed',
  paymentMethodSelected: 'payment_method_selected',
  paymentStarted: 'payment_started',
  paymentCompleted: 'payment_completed',
  paymentFailed: 'payment_failed',
  paymentValidationFailed: 'payment_validation_failed',
  paymentInfoCopied: 'payment_info_copied',
  referralCodeApplied: 'referral_code_applied',
  sidebarOpen: 'sidebar_open',
  newChatClick: 'new_chat_click',
  myRecordLinkClick: 'my_record_link_click',
  thinkingModeToggle: 'thinking_mode_toggle',
  accountDeleteClick: 'account_delete_click',
  paywallDismissed: 'paywall_dismissed',
  schoolRecordReportGenerated: 'school_record_report_generated',
  schoolRecordReportDownloaded: 'school_record_report_downloaded',
  schoolRecordReportFailed: 'school_record_report_failed',
  schoolRecordVisualReportStarted: 'school_record_visual_report_started',
  schoolRecordVisualReportDownloaded: 'school_record_visual_report_downloaded',
  schoolRecordVisualReportFailed: 'school_record_visual_report_failed',
} as const

export const AuthTrigger = {
  Thinking: 'thinking',
  ThinkingMode: 'thinking_mode',
  SchoolRecord: 'school_record',
  SchoolRecordAnalysis: 'school_record_analysis',
  SchoolRecordLink: 'school_record_link',
  ScoreLink: 'score_link',
  SchoolGradeInput: 'school_grade_input',
  SidebarLogin: 'sidebar_login',
  HeaderLogin: 'header_login',
  RateLimitPrompt: 'rate_limit_prompt',
  AuthExpired: 'auth_expired',
  GuestLimit: 'guest_limit',
} as const

export const PaywallReason = {
  DailyLimit: 'daily_limit',
  DeepAnalysis: 'deep_analysis',
  SchoolRecordConsult: 'school_record_consult',
  Thinking: 'thinking',
  ManualUpgrade: 'manual_upgrade',
  SubscriptionManage: 'subscription_manage',
} as const

export const PaymentMethod = {
  ApprovalWidget: 'approval_widget',
  BankTransfer: 'bank_transfer',
  TossSimplePay: 'toss_simple_pay',
  TossBilling: 'toss_billing',
  PayApp: 'payapp',
  Gumroad: 'gumroad',
  ReferralCode: 'referral_code',
} as const

export type TrackingEventName =
  (typeof TrackingEventNames)[keyof typeof TrackingEventNames]

export type AuthTriggerValue = (typeof AuthTrigger)[keyof typeof AuthTrigger]
export type PaywallReasonValue = (typeof PaywallReason)[keyof typeof PaywallReason]
export type PaymentMethodValue = (typeof PaymentMethod)[keyof typeof PaymentMethod]
