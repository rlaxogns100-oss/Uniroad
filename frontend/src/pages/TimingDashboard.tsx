import { useState, useEffect } from 'react';
import { FrontendTimingLogger } from '../utils/timingLogger';

interface LLMCallDetail {
  call_id: string;
  model: string;
  durations: {
    total: number;
    prompt_preparation: number;
    api_request_send: number;
    api_wait: number;
    response_parsing: number;
    post_processing: number;
  };
  metadata: Record<string, any>;
}

interface AgentDetail {
  agent_name: string;
  total_duration: number;
  llm_calls_count: number;
  llm_calls_total_time: number;
  db_queries_count: number;
  db_queries_total_time: number;
  functions_count: number;
  functions_total_time: number;
  llm_calls: LLMCallDetail[];
  db_queries: Array<{ name: string; duration: number; rows: number }>;
}

interface TimingData {
  total_time: number;
  orchestration_time: number;
  sub_agents_time: number;
  final_agent_time: number;
  orchestration_details?: AgentDetail;
  sub_agents_details?: Record<string, AgentDetail>;
  final_agent_details?: AgentDetail;
  durations?: any;
}

interface TimingLog {
  timestamp: string;
  sessionId: string;
  requestId: string;
  total_time_ms: number;
  durations_ms: {
    session_preparation: number;
    ui_update: number;
    request_preparation: number;
    network_wait: number;
    orchestration: number;
    sub_agents: number;
    final_agent: number;
    streaming: number;
    parsing: number;
    rendering: number;
    saving: number;
    total: number;
  };
  backend_timing?: TimingData;
}

export default function TimingDashboard() {
  const [logs, setLogs] = useState<TimingLog[]>([]);
  const [stats, setStats] = useState<any>(null);
  const [selectedLog, setSelectedLog] = useState<TimingLog | null>(null);
  const [expandedAgents, setExpandedAgents] = useState<Set<string>>(new Set());

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = () => {
    const timingLogs = FrontendTimingLogger.getTimingLogs();
    setLogs(timingLogs.reverse());
    
    const calculatedStats = FrontendTimingLogger.calculateStats();
    setStats(calculatedStats);
  };

  const clearLogs = () => {
    if (confirm('모든 타이밍 로그를 삭제하시겠습니까?')) {
      localStorage.removeItem('frontend_timing_logs');
      loadLogs();
    }
  };

  const formatMs = (ms: number) => {
    if (ms === undefined || ms === null) return '0ms';
    return ms >= 1000 ? `${(ms / 1000).toFixed(2)}s` : `${ms.toFixed(0)}ms`;
  };

  const formatSec = (sec: number) => {
    if (sec === undefined || sec === null) return '0.000s';
    return `${sec.toFixed(3)}s`;
  };

  const formatTime = (timestamp: string) => {
    return new Date(timestamp).toLocaleString('ko-KR');
  };

  const toggleAgent = (agentName: string) => {
    const newExpanded = new Set(expandedAgents);
    if (newExpanded.has(agentName)) {
      newExpanded.delete(agentName);
    } else {
      newExpanded.add(agentName);
    }
    setExpandedAgents(newExpanded);
  };

  const renderLLMCallDetails = (llmCall: LLMCallDetail) => (
    <div key={llmCall.call_id} className="ml-6 mt-2 p-3 bg-blue-50 rounded-lg text-sm">
      <div className="font-medium text-blue-700">📞 {llmCall.call_id}</div>
      <div className="mt-1 space-y-1 text-gray-600">
        <div className="flex justify-between">
          <span>프롬프트 준비:</span>
          <span className="font-mono">{formatSec(llmCall.durations.prompt_preparation)}</span>
        </div>
        <div className="flex justify-between">
          <span>API 요청 전송:</span>
          <span className="font-mono">{formatSec(llmCall.durations.api_request_send)}</span>
        </div>
        <div className="flex justify-between bg-yellow-100 px-2 py-1 rounded">
          <span className="font-medium">API 응답 대기:</span>
          <span className="font-mono font-bold">{formatSec(llmCall.durations.api_wait)}</span>
        </div>
        <div className="flex justify-between">
          <span>응답 파싱:</span>
          <span className="font-mono">{formatSec(llmCall.durations.response_parsing)}</span>
        </div>
        <div className="flex justify-between">
          <span>후처리:</span>
          <span className="font-mono">{formatSec(llmCall.durations.post_processing)}</span>
        </div>
        <div className="flex justify-between border-t pt-1 mt-1">
          <span className="font-medium">합계:</span>
          <span className="font-mono font-bold">{formatSec(llmCall.durations.total)}</span>
        </div>
      </div>
    </div>
  );

  const renderAgentDetails = (agent: AgentDetail, agentKey: string) => {
    const isExpanded = expandedAgents.has(agentKey);
    
    return (
      <div key={agentKey} className="border rounded-lg p-3 mb-2">
        <div 
          className="flex justify-between items-center cursor-pointer"
          onClick={() => toggleAgent(agentKey)}
        >
          <div className="flex items-center gap-2">
            <span className="text-lg">{isExpanded ? '▼' : '▶'}</span>
            <span className="font-medium">{agent.agent_name}</span>
          </div>
          <div className="flex gap-4 text-sm">
            <span className="text-blue-600">LLM: {formatSec(agent.llm_calls_total_time)}</span>
            <span className="text-green-600">DB: {formatSec(agent.db_queries_total_time)}</span>
            <span className="font-bold">총: {formatSec(agent.total_duration)}</span>
          </div>
        </div>
        
        {isExpanded && (
          <div className="mt-3 space-y-2">
            <div className="grid grid-cols-3 gap-2 text-sm">
              <div className="bg-blue-100 p-2 rounded">
                <div className="text-blue-700 font-medium">LLM 호출</div>
                <div className="text-2xl font-bold">{agent.llm_calls_count}회</div>
                <div className="text-gray-600">{formatSec(agent.llm_calls_total_time)}</div>
              </div>
              <div className="bg-green-100 p-2 rounded">
                <div className="text-green-700 font-medium">DB 쿼리</div>
                <div className="text-2xl font-bold">{agent.db_queries_count}회</div>
                <div className="text-gray-600">{formatSec(agent.db_queries_total_time)}</div>
              </div>
              <div className="bg-purple-100 p-2 rounded">
                <div className="text-purple-700 font-medium">함수 실행</div>
                <div className="text-2xl font-bold">{agent.functions_count}회</div>
                <div className="text-gray-600">{formatSec(agent.functions_total_time)}</div>
              </div>
            </div>
            
            {agent.llm_calls && agent.llm_calls.length > 0 && (
              <div className="mt-2">
                <div className="text-sm font-medium text-gray-700 mb-1">LLM 호출 상세:</div>
                {agent.llm_calls.map(renderLLMCallDetails)}
              </div>
            )}
            
            {agent.db_queries && agent.db_queries.length > 0 && (
              <div className="mt-2">
                <div className="text-sm font-medium text-gray-700 mb-1">DB 쿼리 상세:</div>
                {agent.db_queries.map((query, idx) => (
                  <div key={idx} className="ml-6 p-2 bg-green-50 rounded text-sm flex justify-between">
                    <span>🔍 {query.name}</span>
                    <span className="font-mono">{formatSec(query.duration)} ({query.rows}행)</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        <div className="flex justify-between items-center mb-6">
          <h1 className="text-3xl font-bold text-gray-900">⏱️ 초상세 타이밍 대시보드</h1>
          <div className="space-x-4">
            <button
              onClick={loadLogs}
              className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
            >
              새로고침
            </button>
            <button
              onClick={clearLogs}
              className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
            >
              로그 삭제
            </button>
          </div>
        </div>

        {/* 통계 요약 */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">총 요청 수</h3>
              <p className="text-3xl font-bold text-blue-600">{stats.count}</p>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">평균 총 시간</h3>
              <p className="text-3xl font-bold text-green-600">{formatMs(stats.total_time.avg)}</p>
              <p className="text-sm text-gray-500 mt-1">
                최소: {formatMs(stats.total_time.min)} | 최대: {formatMs(stats.total_time.max)}
              </p>
            </div>
            
            <div className="bg-white p-6 rounded-lg shadow">
              <h3 className="text-lg font-semibold text-gray-700 mb-2">평균 네트워크 대기</h3>
              <p className="text-3xl font-bold text-orange-600">{formatMs(stats.network_wait.avg)}</p>
              <p className="text-sm text-gray-500 mt-1">
                최소: {formatMs(stats.network_wait.min)} | 최대: {formatMs(stats.network_wait.max)}
              </p>
            </div>
          </div>
        )}

        {/* 로그 테이블 */}
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    시간
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    요청 ID
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    총 시간
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    네트워크
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    스트리밍
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    렌더링
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    상세
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {logs.map((log, index) => (
                  <tr key={index} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatTime(log.timestamp)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500 font-mono">
                      {log.requestId.substring(log.requestId.length - 20)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-blue-600">
                      {formatMs(log.total_time_ms)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatMs(log.durations_ms.network_wait)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatMs(log.durations_ms.streaming)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {formatMs(log.durations_ms.rendering)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm">
                      <button
                        onClick={() => setSelectedLog(log)}
                        className="text-blue-600 hover:text-blue-800 font-medium"
                      >
                        보기
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {logs.length === 0 && (
            <div className="text-center py-12 text-gray-500">
              측정된 타이밍 데이터가 없습니다.
            </div>
          )}
        </div>

        {/* 상세 모달 */}
        {selectedLog && (
          <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
            <div className="bg-white rounded-lg max-w-4xl w-full max-h-[90vh] overflow-y-auto p-6">
              <div className="flex justify-between items-center mb-4">
                <h2 className="text-2xl font-bold text-gray-900">⏱️ 초상세 타이밍 정보</h2>
                <button
                  onClick={() => setSelectedLog(null)}
                  className="text-gray-500 hover:text-gray-700 text-2xl"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-6">
                {/* 기본 정보 */}
                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">기본 정보</h3>
                  <div className="bg-gray-50 p-4 rounded space-y-1 text-sm">
                    <p><span className="font-medium">시간:</span> {formatTime(selectedLog.timestamp)}</p>
                    <p><span className="font-medium">세션 ID:</span> {selectedLog.sessionId}</p>
                    <p><span className="font-medium">요청 ID:</span> {selectedLog.requestId}</p>
                    <p><span className="font-medium">총 시간:</span> {formatMs(selectedLog.total_time_ms)}</p>
                  </div>
                </div>

                {/* 프론트엔드 단계별 시간 */}
                <div>
                  <h3 className="font-semibold text-gray-700 mb-2">프론트엔드 단계별 시간</h3>
                  <div className="space-y-2">
                    {Object.entries(selectedLog.durations_ms).map(([key, value]) => {
                      if (key === 'total') return null;
                      
                      const labels: {[key: string]: string} = {
                        session_preparation: '세션 준비',
                        ui_update: 'UI 업데이트',
                        request_preparation: '요청 준비',
                        network_wait: '네트워크 대기',
                        orchestration: '↳ Orchestration',
                        sub_agents: '↳ Sub Agents',
                        final_agent: '↳ Final Agent',
                        streaming: '스트리밍 수신 (전체)',
                        parsing: '파싱',
                        rendering: '렌더링',
                        saving: '저장',
                      };
                      
                      const percentage = ((value / selectedLog.total_time_ms) * 100).toFixed(1);
                      
                      return (
                        <div key={key} className="flex items-center">
                          <div className="w-40 text-sm text-gray-700">{labels[key] || key}</div>
                          <div className="flex-1 h-6 bg-gray-200 rounded-full overflow-hidden">
                            <div
                              className="h-full bg-blue-500 flex items-center justify-end pr-2"
                              style={{ width: `${Math.min(100, parseFloat(percentage))}%` }}
                            >
                              {parseFloat(percentage) > 10 && (
                                <span className="text-xs text-white font-medium">
                                  {formatMs(value as number)}
                                </span>
                              )}
                            </div>
                          </div>
                          <div className="w-20 text-right text-sm text-gray-600 ml-2">
                            {percentage}%
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* 백엔드 상세 타이밍 */}
                {selectedLog.backend_timing && (
                  <div>
                    <h3 className="font-semibold text-gray-700 mb-2">백엔드 초상세 타이밍</h3>
                    
                    {/* Orchestration Agent */}
                    {selectedLog.backend_timing.orchestration_details && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-blue-600 mb-2">1️⃣ Orchestration Agent</h4>
                        {renderAgentDetails(selectedLog.backend_timing.orchestration_details, 'orchestration')}
                      </div>
                    )}
                    
                    {/* Sub Agents */}
                    {selectedLog.backend_timing.sub_agents_details && 
                     Object.keys(selectedLog.backend_timing.sub_agents_details).length > 0 && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-green-600 mb-2">2️⃣ Sub Agents</h4>
                        {Object.entries(selectedLog.backend_timing.sub_agents_details).map(([key, agent]) => 
                          renderAgentDetails(agent as AgentDetail, key)
                        )}
                      </div>
                    )}
                    
                    {/* Final Agent */}
                    {selectedLog.backend_timing.final_agent_details && (
                      <div className="mb-4">
                        <h4 className="text-sm font-medium text-purple-600 mb-2">3️⃣ Final Agent</h4>
                        {renderAgentDetails(selectedLog.backend_timing.final_agent_details, 'final_agent')}
                      </div>
                    )}
                  </div>
                )}
              </div>

              <div className="mt-6 flex justify-end">
                <button
                  onClick={() => setSelectedLog(null)}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded hover:bg-gray-300"
                >
                  닫기
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
