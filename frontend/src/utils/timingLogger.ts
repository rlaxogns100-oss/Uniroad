/**
 * 프론트엔드 타이밍 측정 유틸리티
 * 
 * 사용자 입력부터 답변 렌더링까지의 각 단계별 시간을 측정합니다.
 */

export interface FrontendTiming {
  sessionId: string;
  requestId: string;
  input_start: number;
  session_ready: number;
  ui_updated: number;
  request_start: number;
  first_log_received: number;
  // 백엔드 단계별 시간
  orch_start: number;
  orch_complete: number;
  subagent_start: number;
  subagent_complete: number;
  final_start: number;
  final_complete: number;
  // 프론트엔드 완료 시간
  result_received: number;
  parse_complete: number;
  render_complete: number;
  save_complete: number;
  total_complete: number;
}

export interface BackendTimingData {
  total_time: number;
  orchestration_time: number;
  sub_agents_time: number;
  final_agent_time: number;
  orchestration_details?: any;
  sub_agents_details?: Record<string, any>;
  final_agent_details?: any;
  durations?: any;
}

export class FrontendTimingLogger {
  private sessionId: string;
  private requestId: string;
  private timing: Record<string, any>;
  private backendTiming: BackendTimingData | null = null;

  constructor(sessionId: string, question: string) {
    this.sessionId = sessionId;
    this.requestId = `${sessionId}:${question.substring(0, 30)}:${Date.now()}`;
    this.timing = {
      sessionId,
      requestId: this.requestId,
      input_start: performance.now(),
    };
  }

  /**
   * 백엔드에서 받은 타이밍 정보를 저장합니다.
   */
  setBackendTiming(timing: BackendTimingData) {
    this.backendTiming = timing;
  }

  mark(checkpoint: keyof FrontendTiming, value?: number) {
    this.timing[checkpoint as string] = value ?? performance.now();
  }

  /**
   * 로그 메시지를 분석하여 자동으로 단계별 시간을 기록합니다.
   * @param log 백엔드에서 받은 로그 메시지
   */
  markFromLog(log: string) {
    const now = performance.now();
    
    // Orchestration Agent 시작
    if (log.includes('Orchestration Agent 실행') || log.includes('🎯 Orchestration Agent')) {
      if (!this.timing['orch_start']) {
        this.timing['orch_start'] = now;
      }
    }
    
    // Orchestration Agent 완료 (처리 시간 로그 또는 결과 로그)
    if (log.includes('Orchestration 결과:') || log.includes('⏱️ 처리 시간:')) {
      if (!this.timing['orch_complete']) {
        this.timing['orch_complete'] = now;
      }
    }
    
    // Sub Agents 시작
    if (log.includes('Sub Agents 실행') || log.includes('🤖 Sub Agents')) {
      if (!this.timing['subagent_start']) {
        this.timing['subagent_start'] = now;
      }
    }
    
    // Sub Agents 완료
    if (log.includes('총 Sub Agents 처리 시간:') || log.includes('Step1_Result') || log.includes('StepN_Result')) {
      if (!this.timing['subagent_complete']) {
        this.timing['subagent_complete'] = now;
      }
    }
    
    // Final Agent 시작
    if (log.includes('Final Agent 실행') || log.includes('📝 Final Agent')) {
      if (!this.timing['final_start']) {
        this.timing['final_start'] = now;
      }
    }
    
    // Final Agent 완료 (섹션 수 로그 또는 처리 시간 로그)
    if (log.includes('최종 답변 길이:') || log.includes('관련 청크 수:')) {
      if (!this.timing['final_complete']) {
        this.timing['final_complete'] = now;
      }
    }
  }

  getElapsed(start: keyof FrontendTiming, end: keyof FrontendTiming): number {
    const startTime = this.timing[start as string];
    const endTime = this.timing[end as string];
    if (startTime === undefined || endTime === undefined) {
      return 0;
    }
    return (endTime as number) - (startTime as number);
  }

  calculateDurations() {
    return {
      // 프론트엔드 준비 단계
      session_preparation: this.getElapsed('input_start', 'session_ready'),
      ui_update: this.getElapsed('session_ready', 'ui_updated'),
      request_preparation: this.getElapsed('ui_updated', 'request_start'),
      network_wait: this.getElapsed('request_start', 'first_log_received'),
      
      // 백엔드 처리 단계 (상세)
      orchestration: this.getElapsed('orch_start', 'orch_complete'),
      sub_agents: this.getElapsed('subagent_start', 'subagent_complete'),
      final_agent: this.getElapsed('final_start', 'final_complete'),
      
      // 백엔드 전체 스트리밍 시간 (기존)
      streaming: this.getElapsed('first_log_received', 'result_received'),
      
      // 프론트엔드 후처리 단계
      parsing: this.getElapsed('result_received', 'parse_complete'),
      rendering: this.getElapsed('parse_complete', 'render_complete'),
      saving: this.getElapsed('render_complete', 'save_complete'),
      
      // 전체 시간
      total: this.getElapsed('input_start', 'total_complete'),
    };
  }

  getSummary() {
    const durations = this.calculateDurations();
    
    return {
      timestamp: new Date().toISOString(),
      sessionId: this.sessionId,
      requestId: this.requestId,
      total_time_ms: durations.total,
      durations_ms: durations,
      raw_timing: this.timing,
      backend_timing: this.backendTiming,
    };
  }

  printSummary() {
    const durations = this.calculateDurations();
    
    console.group('⏱️ 프론트엔드 타이밍 측정');
    console.log('📋 세션 ID:', this.sessionId);
    console.log('🆔 요청 ID:', this.requestId);
    console.log('⏰ 총 소요 시간:', `${durations.total.toFixed(0)}ms`);
    console.log('');
    
    console.log('📊 프론트엔드 단계:');
    console.log('  1. 세션 준비:', `${durations.session_preparation.toFixed(0)}ms`);
    console.log('  2. UI 업데이트:', `${durations.ui_update.toFixed(0)}ms`);
    console.log('  3. 요청 준비:', `${durations.request_preparation.toFixed(0)}ms`);
    console.log('  4. 네트워크 대기:', `${durations.network_wait.toFixed(0)}ms`);
    console.log('');
    
    console.log('🔧 백엔드 처리 단계 (상세):');
    console.log(`  5a. Orchestration Agent: ${durations.orchestration.toFixed(0)}ms`);
    console.log(`  5b. Sub Agents: ${durations.sub_agents.toFixed(0)}ms`);
    console.log(`  5c. Final Agent: ${durations.final_agent.toFixed(0)}ms`);
    console.log(`  5. 전체 스트리밍: ${durations.streaming.toFixed(0)}ms`);
    console.log('');
    
    console.log('🎨 프론트엔드 후처리:');
    console.log('  6. 파싱:', `${durations.parsing.toFixed(0)}ms`);
    console.log('  7. 렌더링:', `${durations.rendering.toFixed(0)}ms`);
    console.log('  8. 저장:', `${durations.saving.toFixed(0)}ms`);
    
    // 백엔드 처리 비율 계산
    if (durations.streaming > 0) {
      const total_backend = durations.streaming;
      const orch_pct = (durations.orchestration / total_backend * 100).toFixed(1);
      const sub_pct = (durations.sub_agents / total_backend * 100).toFixed(1);
      const final_pct = (durations.final_agent / total_backend * 100).toFixed(1);
      
      console.log('');
      console.log('📈 백엔드 처리 비율:');
      console.log(`  Orchestration: ${orch_pct}%`);
      console.log(`  Sub Agents: ${sub_pct}%`);
      console.log(`  Final Agent: ${final_pct}%`);
    }
    
    console.groupEnd();
  }

  logToLocalStorage() {
    try {
      const summary = this.getSummary();
      const existingLogs = localStorage.getItem('frontend_timing_logs');
      const logs = existingLogs ? JSON.parse(existingLogs) : [];
      
      logs.push(summary);
      
      // 최근 100개만 유지
      if (logs.length > 100) {
        logs.shift();
      }
      
      localStorage.setItem('frontend_timing_logs', JSON.stringify(logs));
    } catch (error) {
      console.error('타이밍 로그 저장 실패:', error);
    }
  }

  /**
   * 로컬스토리지에서 타이밍 로그 가져오기
   */
  static getTimingLogs(): any[] {
    try {
      const logs = localStorage.getItem('frontend_timing_logs');
      return logs ? JSON.parse(logs) : [];
    } catch (error) {
      console.error('타이밍 로그 읽기 실패:', error);
      return [];
    }
  }

  /**
   * 타이밍 로그 통계 계산
   */
  static calculateStats() {
    const logs = FrontendTimingLogger.getTimingLogs();
    
    if (logs.length === 0) {
      return null;
    }

    const totalTimes = logs.map((log: any) => log.total_time_ms);
    const networkWaits = logs.map((log: any) => log.durations_ms.network_wait);
    const streamings = logs.map((log: any) => log.durations_ms.streaming);

    const avg = (arr: number[]) => arr.reduce((a, b) => a + b, 0) / arr.length;
    const min = (arr: number[]) => Math.min(...arr);
    const max = (arr: number[]) => Math.max(...arr);

    return {
      count: logs.length,
      total_time: {
        avg: avg(totalTimes),
        min: min(totalTimes),
        max: max(totalTimes),
      },
      network_wait: {
        avg: avg(networkWaits),
        min: min(networkWaits),
        max: max(networkWaits),
      },
      streaming: {
        avg: avg(streamings),
        min: min(streamings),
        max: max(streamings),
      },
    };
  }
}
