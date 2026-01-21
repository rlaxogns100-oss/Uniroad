import { useState, useCallback, useEffect, useMemo, useRef, memo } from 'react';
import ReactFlow, {
  Node,
  Edge,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  addEdge,
  Connection,
  Handle,
  Position,
  NodeProps,
  MarkerType,
} from 'reactflow';
import 'reactflow/dist/style.css';
import axios from 'axios';

// 전역 상태 (컴포넌트 외부)
const globalInputRefs: Record<string, HTMLTextAreaElement | null> = {};
let globalSetNodes: any = null;

// Input Node 컴포넌트 (컴포넌트 외부 정의 - 리렌더링 방지)
const InputNodeComponent = memo(({ id, data, selected }: NodeProps) => {
  const handleCheckboxChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const checked = e.target.checked;
    
    if (globalSetNodes) {
      globalSetNodes((nds: Node[]) =>
        nds.map((n) =>
          n.id === id && n.type === 'input'
            ? { ...n, data: { ...n.data, isActive: checked } }
            : n
        )
      );
    }
  };

  return (
    <div className={`px-4 py-3 rounded-lg shadow-lg border-2 min-w-[220px] ${data.isActive ? 'bg-green-100 border-green-500' : 'bg-green-50 border-green-300'} ${selected ? 'ring-4 ring-green-500 shadow-2xl' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-bold text-green-700">{data.label}</div>
        <input
          type="checkbox"
          checked={data.isActive || false}
          onChange={handleCheckboxChange}
          title="이 입력으로 실행"
          className="w-5 h-5 cursor-pointer accent-green-600"
          onClick={(e) => e.stopPropagation()}
        />
      </div>
      <textarea
        ref={(el) => {
          globalInputRefs[id] = el;
        }}
        defaultValue={data.value || ''}
        placeholder="메시지 입력..."
        className="w-full px-2 py-1 text-sm border rounded resize-none focus:ring-2 focus:ring-green-400 focus:outline-none"
        rows={3}
        onClick={(e) => e.stopPropagation()}
      />
      <Handle type="source" position={Position.Right} id="message" style={{ backgroundColor: '#22c55e', width: 14, height: 14, top: '50%' }} />
    </div>
  );
});

// Final Input Node 컴포넌트
const FinalInputNodeComponent = memo(({ id, data, selected }: NodeProps) => {
  return (
    <div className={`px-4 py-3 rounded-lg shadow-lg border-2 min-w-[220px] bg-purple-50 border-purple-400 ${selected ? 'ring-4 ring-purple-500 shadow-2xl' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="text-sm font-bold text-purple-700">Final Agent Input</div>
      </div>
      <div className="text-xs text-gray-600 mb-2">Final Agent 직접 테스트</div>
      <Handle type="source" position={Position.Right} id="output" style={{ backgroundColor: '#9333ea', width: 14, height: 14, top: '50%' }} />
    </div>
  );
});

// Node Types (컴포넌트 외부 정의 - 안정적 참조)
const staticNodeTypes = {
  input: InputNodeComponent,
  finalInput: FinalInputNodeComponent,
};

// @ts-ignore
const API_BASE = import.meta.env?.VITE_API_URL || 'http://localhost:8000';

interface AgentDef {
  id: string;
  name: string;
  description: string;
  type: string;
  color: string;
  inputs: string[];
  outputs: string[];
}

interface PromptVersion {
  version_id: string;
  name: string;
  description: string;
  created_at: string | null;
}

interface PromptInfo {
  key: string;
  name: string;
  current_version: string;
  versions: PromptVersion[];
}

// 결과 포맷팅
const formatResult = (value: any): string => {
  if (!value) return '';
  if (typeof value === 'string') return value;
  
  if (value.execution_plan || value.answer_structure) {
    let formatted = '';
    if (value.user_intent) formatted += `📝 의도: ${value.user_intent}\n\n`;
    if (value.execution_plan) {
      formatted += '🎯 실행 계획:\n';
      value.execution_plan.forEach((step: any) => {
        formatted += `  ${step.step}. ${step.agent}\n     쿼리: ${step.query}\n`;
      });
      formatted += '\n';
    }
    if (value.answer_structure) {
      formatted += '📋 답변 구조:\n';
      value.answer_structure.forEach((sec: any) => {
        formatted += `  ${sec.section}. [${sec.type}]\n`;
        if (sec.instruction) formatted += `     → ${sec.instruction}\n`;
      });
    }
    return formatted;
  }
  
  if (value.result || value.status) {
    let formatted = '';
    if (value.agent) formatted += `🤖 ${value.agent}\n`;
    if (value.status) formatted += `상태: ${value.status}\n`;
    if (value.query) formatted += `쿼리: ${value.query}\n\n`;
    if (value.result) formatted += `📄 결과:\n${value.result}`;
    if (value.sources?.length > 0) {
      formatted += `\n\n📚 출처: ${value.sources.join(', ')}`;
    }
    if (value.final_answer) {
      formatted += `\n\n✨ 최종 답변:\n${value.final_answer}`;
    }
    return formatted;
  }
  
  return JSON.stringify(value, null, 2);
};

const DEFAULT_AGENTS: AgentDef[] = [
  { id: 'orchestration', name: 'Orchestration Agent', description: '사용자 질문 분석, 실행 계획 수립', type: 'orchestration', color: '#6366f1', inputs: ['user_message', 'chat_history'], outputs: ['execution_plan', 'answer_structure'] },
  { id: 'final', name: 'Final Agent', description: 'Sub Agent 결과를 종합하여 최종 답변 생성', type: 'final', color: '#10b981', inputs: ['user_question', 'answer_structure', 'sub_agent_results'], outputs: ['final_answer'] },
  { id: 'seoul', name: '서울대 Agent', description: '서울대학교 입시 정보 검색', type: 'university', color: '#ef4444', inputs: ['query'], outputs: ['result', 'sources'] },
  { id: 'yonsei', name: '연세대 Agent', description: '연세대학교 입시 정보 검색', type: 'university', color: '#3b82f6', inputs: ['query'], outputs: ['result', 'sources'] },
  { id: 'korea', name: '고려대 Agent', description: '고려대학교 입시 정보 검색', type: 'university', color: '#dc2626', inputs: ['query'], outputs: ['result', 'sources'] },
  { id: 'skku', name: '성균관대 Agent', description: '성균관대학교 입시 정보 검색', type: 'university', color: '#059669', inputs: ['query'], outputs: ['result', 'sources'] },
  { id: 'kyunghee', name: '경희대 Agent', description: '경희대학교 입시 정보 검색', type: 'university', color: '#7c3aed', inputs: ['query'], outputs: ['result', 'sources'] },
  { id: 'consulting', name: '컨설팅 Agent', description: '합격 데이터 분석', type: 'consulting', color: '#f59e0b', inputs: ['query'], outputs: ['result', 'grade_info'] },
  { id: 'teacher', name: '선생님 Agent', description: '학습 계획 및 멘탈 관리 조언', type: 'teacher', color: '#ec4899', inputs: ['query'], outputs: ['result'] },
];

function createInitialPipeline(): { nodes: Node[], edges: Edge[] } {
  const nodes: Node[] = [
    { id: 'input-1', type: 'input', position: { x: 50, y: 300 }, data: { label: 'Chat Input', value: '', isActive: true } },
    { id: 'orchestration-1', type: 'agent', position: { x: 300, y: 280 }, data: { ...DEFAULT_AGENTS[0], label: 'Orchestration Agent' } },
    { id: 'seoul-1', type: 'agent', position: { x: 600, y: 50 }, data: { ...DEFAULT_AGENTS[2], label: '서울대 Agent' } },
    { id: 'yonsei-1', type: 'agent', position: { x: 600, y: 180 }, data: { ...DEFAULT_AGENTS[3], label: '연세대 Agent' } },
    { id: 'korea-1', type: 'agent', position: { x: 600, y: 310 }, data: { ...DEFAULT_AGENTS[4], label: '고려대 Agent' } },
    { id: 'skku-1', type: 'agent', position: { x: 600, y: 440 }, data: { ...DEFAULT_AGENTS[5], label: '성균관대 Agent' } },
    { id: 'kyunghee-1', type: 'agent', position: { x: 600, y: 570 }, data: { ...DEFAULT_AGENTS[6], label: '경희대 Agent' } },
    { id: 'consulting-1', type: 'agent', position: { x: 850, y: 180 }, data: { ...DEFAULT_AGENTS[7], label: '컨설팅 Agent' } },
    { id: 'teacher-1', type: 'agent', position: { x: 850, y: 440 }, data: { ...DEFAULT_AGENTS[8], label: '선생님 Agent' } },
    { id: 'final-1', type: 'agent', position: { x: 1100, y: 300 }, data: { ...DEFAULT_AGENTS[1], label: 'Final Agent' } },
    { id: 'output-1', type: 'output', position: { x: 1350, y: 300 }, data: { label: 'Output', value: null } },
  ];

  const edgeStyle = { strokeWidth: 2 };
  const markerEnd = { type: MarkerType.ArrowClosed as const };

  const edges: Edge[] = [
    { id: 'e-input-orch', source: 'input-1', target: 'orchestration-1', sourceHandle: 'message', targetHandle: 'user_message', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-seoul', source: 'orchestration-1', target: 'seoul-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-yonsei', source: 'orchestration-1', target: 'yonsei-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-korea', source: 'orchestration-1', target: 'korea-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-skku', source: 'orchestration-1', target: 'skku-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-kyunghee', source: 'orchestration-1', target: 'kyunghee-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-consulting', source: 'orchestration-1', target: 'consulting-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-teacher', source: 'orchestration-1', target: 'teacher-1', sourceHandle: 'execution_plan', targetHandle: 'query', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-seoul-final', source: 'seoul-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-yonsei-final', source: 'yonsei-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-korea-final', source: 'korea-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-skku-final', source: 'skku-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-kyunghee-final', source: 'kyunghee-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-consulting-final', source: 'consulting-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-teacher-final', source: 'teacher-1', target: 'final-1', sourceHandle: 'result', targetHandle: 'sub_agent_results', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-orch-final', source: 'orchestration-1', target: 'final-1', sourceHandle: 'answer_structure', targetHandle: 'answer_structure', ...edgeStyle, markerEnd, animated: true },
    { id: 'e-final-output', source: 'final-1', target: 'output-1', sourceHandle: 'final_answer', targetHandle: 'input', ...edgeStyle, markerEnd, animated: true },
  ];

  return { nodes, edges };
}

// localStorage에서 저장된 파이프라인 불러오기
const loadSavedPipeline = (): { nodes: Node[], edges: Edge[] } | null => {
  try {
    const saved = localStorage.getItem('agent-pipeline');
    if (saved) {
      const data = JSON.parse(saved);
      if (data.nodes && data.edges) {
        console.log('📂 Loaded saved pipeline from localStorage');
        return data;
      }
    }
  } catch (e) {
    console.error('Failed to load saved pipeline:', e);
  }
  return null;
};

export default function AgentAdminPage() {
  const initialPipeline = useMemo(() => loadSavedPipeline() || createInitialPipeline(), []);
  
  const [agents, setAgents] = useState<AgentDef[]>(DEFAULT_AGENTS);
  const [nodes, setNodes, onNodesChange] = useNodesState(initialPipeline.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialPipeline.edges);
  
  // nodes/edges 변경 시 localStorage에 저장
  useEffect(() => {
    const saveTimeout = setTimeout(() => {
      try {
        localStorage.setItem('agent-pipeline', JSON.stringify({ nodes, edges }));
        console.log('💾 Saved pipeline to localStorage');
      } catch (e) {
        console.error('Failed to save pipeline:', e);
      }
    }, 1000);
    return () => clearTimeout(saveTimeout);
  }, [nodes, edges]);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [isRunning, setIsRunning] = useState(false);
  const [promptContent, setPromptContent] = useState('');
  const [promptList, setPromptList] = useState<PromptInfo[]>([]);
  const [selectedPromptKey, setSelectedPromptKey] = useState('');
  const [selectedVersion, setSelectedVersion] = useState('default');
  const [showPromptEditor, setShowPromptEditor] = useState(false);
  const [showFullPromptModal, setShowFullPromptModal] = useState(false);
  const [showOutputModal, setShowOutputModal] = useState(false);
  const [newPromptName, setNewPromptName] = useState('');
  const copiedNodeRef = useRef<Node | null>(null);
  const [showQuestionModal, setShowQuestionModal] = useState(false);
  const [selectedQuestionName, setSelectedQuestionName] = useState<string>('');
  const [selectedQuestionContent, setSelectedQuestionContent] = useState<string>('');
  const [inputTextareaValue, setInputTextareaValue] = useState<string>('');
  const [outputModalContent, setOutputModalContent] = useState<any>(null);
  const [fontSize, setFontSize] = useState(14);
  const [nodeOutputData, setNodeOutputData] = useState<Record<string, any>>({});
  
  // Input 값을 ref로 관리 (포커스 유지)
  const inputRefs = useRef<Record<string, HTMLTextAreaElement | null>>({});
  const inputValuesRef = useRef<Record<string, string>>({});

  // 에이전트 노드
  const AgentNode = useCallback(({ data, selected }: NodeProps) => {
    const color = data.color || '#6366f1';
    const result = data.executionResult;
    const status = data.status;
    
    return (
      <div className={`px-4 py-3 rounded-lg shadow-lg border-2 min-w-[200px] bg-white ${selected ? 'ring-4 ring-blue-500 shadow-2xl scale-105' : ''} transition-all duration-200`} style={{ borderColor: color }}>
        {data.inputs?.map((input: string, idx: number) => (
          <Handle key={`input-${input}`} type="target" position={Position.Left} id={input} style={{ top: `${((idx + 1) / (data.inputs.length + 1)) * 100}%`, backgroundColor: color, width: 14, height: 14 }} />
        ))}
        <div className="text-sm font-bold mb-1 pb-1 border-b" style={{ color, borderColor: `${color}33` }}>{data.label}</div>
        <div className="text-xs text-gray-500 mb-2 line-clamp-2">{data.description}</div>
        {status && (
          <div className={`text-xs mb-2 px-2 py-1 rounded ${
            status === 'running' ? 'bg-yellow-100 text-yellow-700' : 
            status === 'success' ? 'bg-green-100 text-green-700' : 
            status === 'skipped' ? 'bg-gray-100 text-gray-600' :
            'bg-red-100 text-red-700'
          }`}>
            {status === 'running' ? '⏳ 실행 중' : status === 'success' ? '✅ 완료' : status === 'skipped' ? '⏭️ 스킵됨' : '❌ 오류'}
          </div>
        )}
        {result && status !== 'skipped' && (
          <div className="mt-2">
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOutputModalContent(result);
                setShowOutputModal(true);
              }}
              className="text-xs text-blue-500 hover:text-blue-700 px-2 py-1 border border-blue-300 rounded w-full mb-1"
            >
              📊 결과 전체보기
            </button>
            <div className="p-2 bg-gray-50 rounded border text-xs max-h-24 overflow-y-auto">
              <pre className="whitespace-pre-wrap text-xs">{formatResult(result).substring(0, 150)}...</pre>
            </div>
          </div>
        )}
        <div className="flex flex-wrap gap-1 mt-2">
          {data.outputs?.map((output: string) => (
            <span key={output} className="text-xs px-1.5 py-0.5 rounded" style={{ backgroundColor: `${color}20`, color }}>{output}</span>
          ))}
        </div>
        {data.outputs?.map((output: string, idx: number) => (
          <Handle key={`output-${output}`} type="source" position={Position.Right} id={output} style={{ top: `${((idx + 1) / (data.outputs.length + 1)) * 100}%`, backgroundColor: color, width: 14, height: 14 }} />
        ))}
      </div>
    );
  }, [setOutputModalContent, setShowOutputModal]);

  // 입력 노드 컴포넌트 (포커스 유지 개선)
  // globalSetNodes 설정 (외부 InputNode에서 사용)
  useEffect(() => {
    globalSetNodes = setNodes;
  }, [setNodes]);

  // 출력 노드 컴포넌트
  const OutputNode = useCallback(({ data, selected }: NodeProps) => {
    const displayText = formatResult(data.value);
    
    const handleFullScreen = (e: React.MouseEvent) => {
      e.stopPropagation();
      setOutputModalContent(data.value);
      setShowOutputModal(true);
    };

    return (
      <div className={`px-4 py-3 rounded-lg shadow-lg border-2 min-w-[250px] max-w-[400px] bg-blue-50 ${selected ? 'ring-4 ring-blue-500 shadow-2xl scale-105' : ''} transition-all duration-200`} style={{ borderColor: '#3b82f6' }}>
        <Handle type="target" position={Position.Left} id="input" style={{ backgroundColor: '#3b82f6', width: 14, height: 14 }} />
        <div className="flex items-center justify-between mb-2">
          <div className="text-sm font-bold text-blue-700">{data.label}</div>
          {data.value && (
            <button onClick={handleFullScreen} className="text-xs text-blue-500 hover:text-blue-700 px-2 py-1 border border-blue-300 rounded">전체화면</button>
          )}
        </div>
        <div className="max-h-[250px] overflow-y-auto">
          {data.value ? (
            <pre className="text-xs whitespace-pre-wrap bg-white p-2 rounded border">{displayText.substring(0, 800)}{displayText.length > 800 ? '\n...(더 보기: 전체화면)' : ''}</pre>
          ) : (
            <div className="text-xs text-gray-400 p-2 text-center">실행 결과가 여기에 표시됩니다</div>
          )}
        </div>
      </div>
    );
  }, [setOutputModalContent, setShowOutputModal]);

  // nodeTypes
  const nodeTypes = useMemo(() => ({
    agent: AgentNode,
    input: InputNodeComponent,  // 외부 정의된 안정적 컴포넌트
    output: OutputNode,
  }), [AgentNode, OutputNode]);

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await axios.get(`${API_BASE}/api/agent/agents`);
        setAgents(response.data.agents);
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };
    fetchAgents();
  }, []);

  const onConnect = useCallback((params: Connection) => {
    setEdges((eds) => addEdge({ ...params, markerEnd: { type: MarkerType.ArrowClosed }, style: { strokeWidth: 2 }, animated: true }, eds));
  }, [setEdges]);

  const addAgentNode = useCallback((agent: AgentDef) => {
    const newNode: Node = {
      id: `${agent.id}-${Date.now()}`,
      type: 'agent',
      position: { x: 400 + Math.random() * 200, y: 200 + Math.random() * 200 },
      data: { ...agent, label: agent.name, status: null },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes]);

  const addOutputNode = useCallback(() => {
    const count = nodes.filter(n => n.type === 'output').length + 1;
    const newNode: Node = {
      id: `output-${count}`,
      type: 'output',
      position: { x: 1350 + Math.random() * 100, y: 100 + Math.random() * 400 },
      data: { label: `Output ${count}`, value: null },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes, nodes]);

  const addInputNode = useCallback(() => {
    const count = nodes.filter(n => n.type === 'input').length + 1;
    const newNode: Node = {
      id: `input-${count}`,
      type: 'input',
      position: { x: 50 + Math.random() * 50, y: 100 + Math.random() * 400 },
      data: { label: `Input ${count}`, value: '', isActive: false },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes, nodes]);

  const addFinalInputNode = useCallback(() => {
    const count = nodes.filter(n => n.type === 'finalInput').length + 1;
    const newNode: Node = {
      id: `final-input-${count}`,
      type: 'finalInput',
      position: { x: 300 + Math.random() * 50, y: 100 + Math.random() * 400 },
      data: { 
        label: `Final Input ${count}`,
        user_question: '',
        answer_structure: '[]',
        sub_agent_results: '{}',
        notes: ''
      },
    };
    setNodes((nds) => [...nds, newNode]);
  }, [setNodes, nodes]);

  // 단일 노드 실행
  const runSingleNode = async (nodeId: string) => {
    const node = nodes.find(n => n.id === nodeId);
    if (!node || node.type !== 'agent') return;

    try {
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, status: 'running' } } : n
        )
      );

      const inputs: Record<string, any> = {};
      const incomingEdges = edges.filter(e => e.target === nodeId);
      
      for (const edge of incomingEdges) {
        const sourceNode = nodes.find(n => n.id === edge.source);
        if (sourceNode?.type === 'input') {
          const value = String(inputValuesRef.current[edge.source] || '').trim();
          if (value) {
            inputs.user_message = value;
            inputs.query = value;
            inputs.user_question = value;
          }
        } else if (sourceNode?.type === 'agent' && nodeOutputData[edge.source]) {
          const outputKey = edge.sourceHandle || 'result';
          inputs[edge.targetHandle || 'query'] = nodeOutputData[edge.source][outputKey];
        }
      }

      const response = await axios.post(
        `${API_BASE}/api/agent/agents/${node.data.id}/execute`,
        { agent_id: node.data.id, inputs },
        { timeout: 180000 }
      );

      const result = response.data.result;
      
      setNodeOutputData(prev => ({ ...prev, [nodeId]: result }));

      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, status: 'success', executionResult: result } } : n
        )
      );

      alert(`✅ ${node.data.label} 실행 완료`);
    } catch (error: any) {
      console.error('Single node execution failed:', error);
      setNodes((nds) =>
        nds.map((n) =>
          n.id === nodeId ? { ...n, data: { ...n.data, status: 'error' } } : n
        )
      );
      alert(`❌ 실행 실패: ${error.response?.data?.detail || error.message}`);
    }
  };

  const onNodeClick = useCallback(async (_: React.MouseEvent, node: Node) => {
    setShowPromptEditor(false);
    
    if (node.type === 'output' && node.data.value) {
      setSelectedNode(node);
      setOutputModalContent(node.data.value);
      setShowOutputModal(true);
      return;
    }
    
    if (node.type === 'agent') {
      try {
        const agentId = node.data.id;
        
        // 프롬프트 목록 불러오기
        const response = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}`);
        const prompts = response.data.prompts as PromptInfo[];
        setPromptList(prompts);
        
        if (prompts.length > 0) {
          // 노드에 저장된 프롬프트 정보 (없으면 기본값 사용)
          const promptKey = node.data.selectedPromptKey || prompts[0].key;
          const version = node.data.selectedVersion || 'default';
          
          // state 즉시 업데이트 (이전 노드 정보가 보이지 않도록)
          setSelectedPromptKey(promptKey);
          setSelectedVersion(version);
          
          // 노드 데이터에 저장 (처음 선택한 경우)
          if (!node.data.selectedPromptKey || !node.data.selectedVersion) {
            setNodes((nds) => nds.map((n) => 
              n.id === node.id 
                ? { ...n, data: { ...n.data, selectedPromptKey: promptKey, selectedVersion: version } }
                : n
            ));
          }
          
          // 프롬프트 내용 불러오기
          const contentResponse = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}/${promptKey}${version !== 'default' ? `?version=${version}` : ''}`);
          setPromptContent(contentResponse.data.content);
        }
        
        // 노드 선택은 마지막에 설정 (UI 업데이트 순서 보장)
        setSelectedNode(node);
      } catch (error) {
        console.error('Failed to load prompt:', error);
        setPromptContent('프롬프트를 불러올 수 없습니다.');
        setSelectedNode(node);
      }
    } else {
      setSelectedNode(node);
    }
  }, []);

  const handlePromptKeyChange = async (promptKey: string) => {
    if (!selectedNode || selectedNode.type !== 'agent') return;
    setSelectedPromptKey(promptKey);
    
    // 노드 데이터에 선택된 프롬프트 키 저장
    setNodes((nds) => nds.map((n) => 
      n.id === selectedNode.id 
        ? { ...n, data: { ...n.data, selectedPromptKey: promptKey, selectedVersion: 'default' } }
        : n
    ));
    
    try {
      const agentId = selectedNode.data.id;
      const contentResponse = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}/${promptKey}`);
      setPromptContent(contentResponse.data.content);
      setSelectedVersion('default');
    } catch (error) {
      console.error('Failed to load prompt:', error);
    }
  };

  const runPipeline = async () => {
    setIsRunning(true);
    setNodeOutputData({});
    
    setNodes((nds) => nds.map((node) => {
      if (node.type === 'agent') return { ...node, data: { ...node.data, status: null, executionResult: null } };
      if (node.type === 'output') return { ...node, data: { ...node.data, value: null } };
      return node;
    }));
    
    try {
      // 체크된 모든 Input 노드들 찾기
      const activeInputs = nodes.filter((n) => n.type === 'input' && n.data.isActive);
      
      if (activeInputs.length === 0) {
        alert('⚠️ 입력 노드의 체크박스를 선택해주세요.');
        setIsRunning(false);
        return;
      }

      // 최신 nodes 상태 출력
      console.log('🔍 All input nodes:', nodes.filter(n => n.type === 'input').map(n => ({ 
        id: n.id, 
        label: n.data.label,
        isActive: n.data.isActive, 
        value: n.data.value 
      })));
      
      console.log('🎯 Active input nodes:', activeInputs.map(n => ({ 
        id: n.id, 
        label: n.data.label,
        value: n.data.value 
      })));

      // 전역 ref에서 textarea 값 읽기 및 검증
      console.log('📋 Available global refs:', Object.keys(globalInputRefs));
      
      const inputsToRun: Array<{node: Node; value: string}> = [];
      for (const inputNode of activeInputs) {
        // 전역 ref에서 직접 값 읽기
        const textarea = globalInputRefs[inputNode.id];
        const inputValue = String(textarea?.value || '').trim();
        
        console.log(`🔍 Checking ${inputNode.id}:`, {
          hasRef: !!textarea,
          rawValue: textarea?.value,
          trimmed: inputValue
        });
        
        if (!inputValue) {
          alert(`⚠️ "${inputNode.data.label}" 노드에 메시지를 입력해주세요.`);
          setIsRunning(false);
          return;
        }
        
        inputsToRun.push({ node: inputNode, value: inputValue });
        console.log(`✅ Input ${inputNode.id}: "${inputValue}"`);
      }

      console.log(`🚀 ${inputsToRun.length}개 파이프라인 실행:`, inputsToRun.map(i => `${i.node.id}="${i.value}"`));

      // 체크된 Input에 연결된 에이전트만 실행 상태로 표시
      const activeInputIds = new Set(inputsToRun.map(i => i.node.id));
      const connectedAgentIds = new Set<string>();
      
      // 체크된 Input에서 연결된 모든 에이전트 찾기 (재귀적으로)
      const findConnectedAgents = (nodeId: string, visited: Set<string> = new Set()) => {
        if (visited.has(nodeId)) return;
        visited.add(nodeId);
        
        edges.filter(e => e.source === nodeId).forEach(edge => {
          const targetNode = nodes.find(n => n.id === edge.target);
          if (targetNode?.type === 'agent') {
            connectedAgentIds.add(targetNode.id);
            findConnectedAgents(targetNode.id, visited);
          }
        });
      };
      
      inputsToRun.forEach(({ node }) => findConnectedAgents(node.id));
      console.log('🔗 Connected agents:', Array.from(connectedAgentIds));

      setNodes((nds) => nds.map((node) => {
        if (node.type === 'agent') {
          if (connectedAgentIds.has(node.id)) {
            return { ...node, data: { ...node.data, status: 'running' } };
          }
          // 연결 안 된 에이전트는 상태 변경 없음
          return node;
        }
        return node;
      }));

      // 모든 Input에 대해 병렬로 파이프라인 실행
      const executionPromises = inputsToRun.map(async ({ node: inputNode, value: inputValue }) => {
        try {
          // 이 Input에서 연결된 에이전트만 포함
          const connectedToThisInput = new Set<string>();
          const findFromInput = (nodeId: string, visited: Set<string> = new Set()) => {
            if (visited.has(nodeId)) return;
            visited.add(nodeId);
            edges.filter(e => e.source === nodeId).forEach(edge => {
              const targetNode = nodes.find(n => n.id === edge.target);
              if (targetNode?.type === 'agent') {
                connectedToThisInput.add(targetNode.id);
                findFromInput(targetNode.id, visited);
              }
            });
          };
          findFromInput(inputNode.id);
          
          const agentNodes = nodes
            .filter((n) => n.type === 'agent' && connectedToThisInput.has(n.id))
            .map((n) => ({
              node_id: n.id,
              agent_id: n.data.id,
              inputs: {} as Record<string, any>,
            }));

          // 이 Input 노드에서 나가는 엣지들 찾기
          const inputEdges = edges.filter((e) => e.source === inputNode.id);
          inputEdges.forEach((edge) => {
            const targetNode = agentNodes.find((n) => n.node_id === edge.target);
            if (targetNode) {
              targetNode.inputs = { 
                user_message: inputValue, 
                query: inputValue, 
                user_question: inputValue 
              };
            }
          });

          // Agent 간 연결 (연결된 에이전트들 사이만)
          const connections = edges
            .filter((e) => 
              connectedToThisInput.has(e.source) &&
              connectedToThisInput.has(e.target)
            )
            .map((e) => ({
              from_node: e.source,
              from_output: e.sourceHandle || 'result',
              to_node: e.target,
              to_input: e.targetHandle || 'query',
            }));

          if (agentNodes.length === 0) {
            return { inputNodeId: inputNode.id, error: '실행할 에이전트 없음', results: {} };
          }

          console.log(`\n🔥 [${inputNode.id}] REQUEST DATA:`, {
            inputValue,
            agentNodes: agentNodes.map(n => ({ node_id: n.node_id, agent_id: n.agent_id, inputs: n.inputs })),
            connections: connections
          });

          let results: Record<string, any> = {};
          
          if (agentNodes.length === 1) {
            const agent = agentNodes[0];
            console.log(`📤 [${inputNode.id}] Single agent request:`, { agent_id: agent.agent_id, inputs: agent.inputs });
            const response = await axios.post(`${API_BASE}/api/agent/agents/${agent.agent_id}/execute`, { agent_id: agent.agent_id, inputs: agent.inputs }, { timeout: 180000 });
            results = { [agent.node_id]: response.data.result };
          } else {
            console.log(`📤 [${inputNode.id}] Pipeline request:`, { nodes: agentNodes, connections });
            const response = await axios.post(`${API_BASE}/api/agent/pipeline/execute`, { nodes: agentNodes, connections }, { timeout: 180000 });
            results = response.data.results || {};
          }
          
          console.log(`✅ [${inputNode.id}] Response received:`, Object.keys(results));
          
          return { inputNodeId: inputNode.id, results };
        } catch (err: any) {
          console.error(`Execution error for ${inputNode.id}:`, err);
          const errorMsg = err.response?.data?.detail || err.message || 'Unknown error';
          return { inputNodeId: inputNode.id, error: errorMsg, results: {} };
        }
      });

      // 모든 실행 완료 대기
      const allResults = await Promise.all(executionPromises);
      
      // 결과 병합 (마지막 성공한 결과를 사용)
      let results: Record<string, any> = {};
      let hasError = false;
      for (const execResult of allResults) {
        if (execResult.error) {
          hasError = true;
          alert(`❌ 실행 오류 (${execResult.inputNodeId}): ${execResult.error}`);
        }
        // 결과 병합
        results = { ...results, ...execResult.results };
      }
      
      if (!hasError && inputsToRun.length > 1) {
        alert(`✅ ${inputsToRun.length}개 파이프라인 실행 완료!`);
      }
      
      setNodeOutputData(results);
      
      setNodes((nds) =>
        nds.map((node) => {
          if (node.type === 'agent') {
            const nodeResult = results[node.id];
            const hasError = nodeResult?.error || nodeResult?.status === 'error' || results.error;
            const isSkipped = nodeResult?.status === 'skipped';
            return { ...node, data: { ...node.data, status: hasError ? 'error' : (isSkipped ? 'skipped' : (nodeResult ? 'success' : null)), executionResult: nodeResult } };
          }
          if (node.type === 'output') {
            const connectedEdge = edges.find((e) => e.target === node.id);
            let outputValue: any = null;
            
            if (connectedEdge) {
              outputValue = results[connectedEdge.source];
            }
            
            if (!connectedEdge && Object.keys(results).length > 0) {
              outputValue = results;
            }
            
            return {
              ...node,
              data: {
                ...node.data,
                value: outputValue,
              },
            };
          }
          return node;
        })
      );
      
    } catch (error: any) {
      console.error('Pipeline execution failed:', error);
      const errorMsg = error.response?.data?.detail || error.message;
      alert(`❌ 실행 실패: ${errorMsg}`);
    } finally {
      setIsRunning(false);
    }
  };

  const savePrompt = async (overwrite: boolean = false) => {
    if (!selectedNode || selectedNode.type !== 'agent') return;
    
    const agentId = selectedNode.data.id;
    const name = overwrite 
      ? (promptList.find(p => p.key === selectedPromptKey)?.versions?.find(v => v.version_id === selectedVersion)?.name || '현재 버전')
      : (newPromptName || `버전 ${new Date().toLocaleString('ko-KR')}`);
    
    try {
      if (overwrite && selectedVersion !== 'default') {
        // 기존 버전 덮어쓰기
        await axios.put(`${API_BASE}/api/agent/prompts/${agentId}/${selectedPromptKey}/${selectedVersion}`, { 
          content: promptContent, 
          name 
        });
        alert(`프롬프트가 업데이트되었습니다: ${name}`);
      } else {
        // 새 버전 생성
        const response = await axios.post(`${API_BASE}/api/agent/prompts/${agentId}/${selectedPromptKey}`, { 
          agent_id: agentId, 
          prompt_key: selectedPromptKey, 
          content: promptContent, 
          name 
        });
        alert(`새 프롬프트가 저장되었습니다: ${response.data.version_id}`);
        setSelectedVersion(response.data.version_id);
      }
      
      const promptsResponse = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}`);
      setPromptList(promptsResponse.data.prompts);
      setNewPromptName('');
    } catch (error) {
      console.error('Failed to save prompt:', error);
      alert('프롬프트 저장에 실패했습니다.');
    }
  };

  const selectVersion = async (versionId: string) => {
    if (!selectedNode || selectedNode.type !== 'agent') return;
    
    // 노드 데이터에 선택된 버전 저장
    setNodes((nds) => nds.map((n) => 
      n.id === selectedNode.id 
        ? { ...n, data: { ...n.data, selectedVersion: versionId } }
        : n
    ));
    
    try {
      const agentId = selectedNode.data.id;
      const response = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}/${selectedPromptKey}?version=${versionId}`);
      setPromptContent(response.data.content);
      setSelectedVersion(versionId);
      
      // 선택한 버전을 활성화
      if (versionId !== 'default') {
        await axios.put(`${API_BASE}/api/agent/prompts/${agentId}/${selectedPromptKey}/active`, null, {
          params: { version_id: versionId }
        });
        console.log(`✅ Activated version: ${versionId}`);
      }
    } catch (error) {
      console.error('Failed to load version:', error);
    }
  };

  const deletePrompt = async (versionId: string) => {
    if (!selectedNode || selectedNode.type !== 'agent') return;
    if (versionId === 'default') {
      alert('기본 프롬프트는 삭제할 수 없습니다.');
      return;
    }
    
    if (!confirm('이 프롬프트 버전을 삭제하시겠습니까?')) {
      return;
    }
    
    try {
      const agentId = selectedNode.data.id;
      await axios.delete(`${API_BASE}/api/agent/prompts/${agentId}/${selectedPromptKey}/${versionId}`);
      alert('프롬프트가 삭제되었습니다.');
      
      // 프롬프트 목록 새로고침
      const promptsResponse = await axios.get(`${API_BASE}/api/agent/prompts/${agentId}`);
      setPromptList(promptsResponse.data.prompts);
      
      // 삭제된 버전이 현재 선택된 버전이면 default로 변경
      if (selectedVersion === versionId) {
        selectVersion('default');
      }
    } catch (error) {
      console.error('Failed to delete version:', error);
      alert('프롬프트 삭제에 실패했습니다.');
    }
  };

  // Input 노드 선택 시 textarea 값 동기화
  useEffect(() => {
    if (selectedNode && selectedNode.type === 'input' && globalInputRefs[selectedNode.id]) {
      setInputTextareaValue(globalInputRefs[selectedNode.id].value || '');
    }
  }, [selectedNode]);

  useEffect(() => {
    const handleKeyboard = (e: KeyboardEvent) => {
      // Escape 키
      if (e.key === 'Escape') {
        if (showFullPromptModal) setShowFullPromptModal(false);
        if (showOutputModal) setShowOutputModal(false);
        if (showQuestionModal) setShowQuestionModal(false);
      }
      
      // Cmd/Ctrl + C (복사) - 선택된 모든 노드 복사
      if ((e.metaKey || e.ctrlKey) && e.key === 'c') {
        const selectedNodes = nodes.filter(n => n.selected);
        if (selectedNodes.length > 0) {
          copiedNodeRef.current = selectedNodes.length === 1 ? selectedNodes[0] : { multiple: selectedNodes } as any;
          console.log('📋 Copied nodes:', selectedNodes.map(n => n.id));
        }
      }
      
      // Cmd/Ctrl + V (붙여넣기)
      if ((e.metaKey || e.ctrlKey) && e.key === 'v' && copiedNodeRef.current) {
        const copied = copiedNodeRef.current;
        const newNodes: Node[] = [];
        const idMapping: Record<string, string> = {}; // oldId -> newId 매핑
        
        // 여러 노드 복사
        if ((copied as any).multiple) {
          const nodesToCopy = (copied as any).multiple as Node[];
          nodesToCopy.forEach((copiedNode: Node) => {
            const newId = getNextNodeId(copiedNode, nodes, newNodes);
            idMapping[copiedNode.id] = newId;
            
            const newNode: Node = {
              ...copiedNode,
              id: newId,
              selected: true,
              position: {
                x: copiedNode.position.x + 50,
                y: copiedNode.position.y + 50
              },
              data: { 
                ...copiedNode.data,
                status: null,
                executionResult: null,
                value: copiedNode.type === 'input' ? '' : copiedNode.data.value
              }
            };
            newNodes.push(newNode);
          });
          
          // 복사된 노드들 간의 연결(edges) 찾아서 복사
          const copiedNodeIds = new Set(nodesToCopy.map(n => n.id));
          const newEdges: Edge[] = [];
          
          edges.forEach((edge) => {
            // 소스와 타겟 모두 복사된 노드들에 포함된 경우에만 edge 복사
            if (copiedNodeIds.has(edge.source) && copiedNodeIds.has(edge.target)) {
              const newEdge: Edge = {
                ...edge,
                id: `e-${idMapping[edge.source]}-${idMapping[edge.target]}-${Date.now()}`,
                source: idMapping[edge.source],
                target: idMapping[edge.target]
              };
              newEdges.push(newEdge);
            }
          });
          
          // 노드와 엣지 모두 추가
          setNodes((nds) => [
            ...nds.map(n => ({ ...n, selected: false })),
            ...newNodes
          ]);
          
          if (newEdges.length > 0) {
            setEdges((eds) => [...eds, ...newEdges]);
            console.log('🔗 Pasted edges:', newEdges.map(e => `${e.source}->${e.target}`));
          }
        } else {
          // 단일 노드 복사
          const copiedNode = copied as Node;
          const newId = getNextNodeId(copiedNode, nodes, newNodes);
          const newNode: Node = {
            ...copiedNode,
            id: newId,
            selected: true,
            position: {
              x: copiedNode.position.x + 50,
              y: copiedNode.position.y + 50
            },
            data: { 
              ...copiedNode.data,
              status: null,
              executionResult: null,
              value: copiedNode.type === 'input' ? '' : copiedNode.data.value
            }
          };
          newNodes.push(newNode);
          
          // 기존 노드 선택 해제, 새 노드 추가
          setNodes((nds) => [
            ...nds.map(n => ({ ...n, selected: false })),
            ...newNodes
          ]);
        }
        
        console.log('📌 Pasted nodes:', newNodes.map(n => n.id));
      }
    };
    
    window.addEventListener('keydown', handleKeyboard);
    return () => window.removeEventListener('keydown', handleKeyboard);
  }, [showFullPromptModal, showOutputModal, showQuestionModal, nodes, edges, setNodes, setEdges]);

  // 노드 ID 자동 증가 함수
  const getNextNodeId = (node: Node, allNodes: Node[], newNodes: Node[] = []): string => {
    if (node.type === 'input' || node.type === 'output') {
      // input-1, input-2, ... 형식
      const prefix = node.type;
      
      // 기존 노드들과 새로 생성될 노드들의 번호 모두 확인
      const allNodesToCheck = [...allNodes, ...newNodes];
      const existingNumbers = allNodesToCheck
        .filter(n => n.id.startsWith(`${prefix}-`))
        .map(n => parseInt(n.id.split('-')[1]))
        .filter(n => !isNaN(n));
      
      const maxNumber = existingNumbers.length > 0 ? Math.max(...existingNumbers) : 0;
      return `${prefix}-${maxNumber + 1}`;
    } else {
      // agent 노드는 timestamp 사용
      return `${node.data.id}-${Date.now()}`;
    }
  };

  const currentVersions = promptList.find(p => p.key === selectedPromptKey)?.versions || [];

  // 노드 초기화 핸들러
  const resetToInitialPipeline = () => {
    if (confirm('모든 노드와 연결을 초기 상태로 되돌립니다. 계속하시겠습니까?')) {
      const initial = createInitialPipeline();
      setNodes(initial.nodes);
      setEdges(initial.edges);
      setSelectedNode(null);
      setNodeOutputData({});
      localStorage.removeItem('agent-pipeline');
      alert('✅ 초기 상태로 복원되었습니다');
    }
  };

  return (
    <div className="h-screen flex flex-col bg-gray-100">
      {showFullPromptModal && (
        <div className="fixed inset-0 bg-black bg-opacity-70 z-50">
          <div className="h-full flex">
            <div className="w-56 bg-gray-50 border-r p-3 overflow-y-auto">
              <div className="flex items-center justify-between mb-4">
                <div className="text-xs font-bold text-gray-700 uppercase">프롬프트 관리</div>
                <button onClick={() => setShowFullPromptModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
              </div>
              
              {promptList.length > 1 && (
                <>
                  <div className="text-xs font-semibold text-gray-600 mb-2 uppercase">프롬프트 타입</div>
                  {promptList.map((p) => (
                    <button key={p.key} onClick={() => handlePromptKeyChange(p.key)} className={`w-full text-left px-3 py-2 rounded text-sm mb-1 transition-colors ${selectedPromptKey === p.key ? 'bg-blue-500 text-white shadow-sm' : 'hover:bg-gray-200 text-gray-700'}`}>{p.name}</button>
                  ))}
                  <div className="border-t my-4"></div>
                </>
              )}
              
              <div className="text-xs font-semibold text-gray-600 mb-2 uppercase">저장된 버전</div>
              {currentVersions.map((v) => (
                <div key={v.version_id} className="flex items-center gap-1 mb-1">
                  <button onClick={() => selectVersion(v.version_id)} className={`flex-1 text-left px-3 py-2 rounded text-sm transition-colors ${selectedVersion === v.version_id ? 'bg-green-500 text-white shadow-sm' : 'hover:bg-gray-200 text-gray-700'}`}>
                    <div className="font-medium">{v.name}</div>
                    {v.created_at && <div className="text-xs opacity-80 mt-0.5">{new Date(v.created_at).toLocaleDateString('ko-KR')}</div>}
                  </button>
                  {v.version_id !== 'default' && (
                    <button onClick={(e) => { e.stopPropagation(); deletePrompt(v.version_id); }} className="px-2 py-2 text-red-500 hover:bg-red-50 rounded text-sm transition-colors" title="삭제">🗑️</button>
                  )}
                </div>
              ))}
            </div>
            <div className="flex-1 flex flex-col relative bg-white">
              <div className="absolute top-0 left-0 right-0 px-4 py-2 bg-gradient-to-b from-white to-transparent z-10 pointer-events-none">
                <div className="text-sm font-medium text-gray-600">{selectedNode?.data.label}</div>
              </div>
              <textarea value={promptContent} onChange={(e) => setPromptContent(e.target.value)} className="flex-1 w-full px-6 pt-12 pb-24 font-mono resize-none focus:outline-none" placeholder="프롬프트 내용..." style={{ fontSize: `${fontSize}px`, lineHeight: '1.6' }} />
              <div className="absolute bottom-6 left-6 right-6 flex flex-col gap-3">
                <div className="flex items-center gap-2">
                  <input 
                    type="text" 
                    value={newPromptName} 
                    onChange={(e) => setNewPromptName(e.target.value)} 
                    placeholder="새 버전 이름 (선택사항)" 
                    className="flex-1 px-3 py-2 border rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  />
                </div>
                <div className="flex gap-2 justify-end">
                  <div className="flex items-center gap-1 bg-white rounded-lg shadow-lg border px-2 py-1">
                    <button onClick={() => setFontSize(Math.max(10, fontSize - 2))} className="px-2 py-1 hover:bg-gray-100 rounded text-gray-600">A-</button>
                    <span className="text-xs text-gray-500 px-1">{fontSize}px</span>
                    <button onClick={() => setFontSize(Math.min(24, fontSize + 2))} className="px-2 py-1 hover:bg-gray-100 rounded text-gray-600">A+</button>
                    <button onClick={() => setFontSize(14)} className="px-2 py-1 hover:bg-gray-100 rounded text-xs text-gray-500">초기화</button>
                  </div>
                  <button onClick={() => setShowFullPromptModal(false)} className="px-4 py-2 bg-white border rounded-lg text-gray-700 hover:bg-gray-50 shadow-lg font-medium">닫기</button>
                  {selectedVersion !== 'default' && (
                    <button onClick={() => savePrompt(true)} className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 shadow-lg font-medium">현재 버전 저장</button>
                  )}
                  <button onClick={() => savePrompt(false)} className="px-4 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 shadow-lg font-medium">새 버전으로 저장</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {showQuestionModal && (
        <div className="fixed inset-0 bg-black bg-opacity-70 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full max-w-2xl flex flex-col max-h-[80vh]">
            <div className="flex items-center justify-between px-6 py-4 border-b">
              <h3 className="text-lg font-semibold text-gray-800">{selectedQuestionName}</h3>
              <button onClick={() => setShowQuestionModal(false)} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">&times;</button>
            </div>
            <div className="flex-1 p-6 overflow-y-auto">
              <textarea
                value={selectedQuestionContent}
                onChange={(e) => setSelectedQuestionContent(e.target.value)}
                className="w-full h-64 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-blue-500"
                placeholder="질문 내용..."
              />
            </div>
            <div className="px-6 py-4 border-t flex gap-2 justify-end">
              <button 
                onClick={() => {
                  if (globalInputRefs[selectedNode?.id || '']) {
                    globalInputRefs[selectedNode?.id || ''].value = selectedQuestionContent;
                    setInputTextareaValue(selectedQuestionContent);
                  }
                  setShowQuestionModal(false);
                }}
                className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600"
              >
                📥 불러오기
              </button>
              <button 
                onClick={() => {
                  const savedQuestions = JSON.parse(localStorage.getItem('saved-questions') || '{}');
                  savedQuestions[selectedQuestionName] = selectedQuestionContent;
                  localStorage.setItem('saved-questions', JSON.stringify(savedQuestions));
                  alert('질문이 업데이트되었습니다');
                  setNodes([...nodes]); // Force re-render
                }}
                className="px-4 py-2 bg-green-500 text-white rounded hover:bg-green-600"
              >
                💾 저장
              </button>
              <button 
                onClick={() => {
                  if (confirm('이 질문을 삭제하시겠습니까?')) {
                    const savedQuestions = JSON.parse(localStorage.getItem('saved-questions') || '{}');
                    delete savedQuestions[selectedQuestionName];
                    localStorage.setItem('saved-questions', JSON.stringify(savedQuestions));
                    setShowQuestionModal(false);
                    setNodes([...nodes]); // Force re-render
                  }
                }}
                className="px-4 py-2 bg-red-500 text-white rounded hover:bg-red-600"
              >
                🗑️ 삭제
              </button>
            </div>
          </div>
        </div>
      )}

      {showOutputModal && (
        <div className="fixed inset-0 bg-black bg-opacity-70 z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-lg shadow-2xl w-full h-full flex flex-col">
            <div className="flex items-center justify-between px-6 py-3 border-b">
              <h3 className="text-lg font-semibold text-gray-800">실행 결과</h3>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-sm">
                  <input type="checkbox" id="showRaw" onChange={(e) => {
                    const pre = document.getElementById('output-content');
                    if (pre && outputModalContent) {
                      pre.textContent = e.target.checked ? JSON.stringify(outputModalContent, null, 2) : formatResult(outputModalContent);
                    }
                  }} />
                  Raw JSON
                </label>
                <button onClick={() => setShowOutputModal(false)} className="text-gray-400 hover:text-gray-600 text-3xl leading-none">&times;</button>
              </div>
            </div>
            <div className="flex-1 overflow-auto p-6">
              <pre id="output-content" className="whitespace-pre-wrap font-mono" style={{ fontSize: `${fontSize}px`, lineHeight: '1.6' }}>
                {outputModalContent ? formatResult(outputModalContent) : '결과가 없습니다.'}
              </pre>
            </div>
            <div className="flex justify-end gap-2 px-6 py-4 border-t">
              <div className="flex items-center gap-1 bg-gray-100 rounded-lg px-2 py-1 mr-auto">
                <button onClick={() => setFontSize(Math.max(10, fontSize - 2))} className="px-2 py-1 hover:bg-gray-200 rounded text-gray-600">A-</button>
                <span className="text-xs text-gray-500 px-1">{fontSize}px</span>
                <button onClick={() => setFontSize(Math.min(24, fontSize + 2))} className="px-2 py-1 hover:bg-gray-200 rounded text-gray-600">A+</button>
              </div>
              <button 
                onClick={() => {
                  const pre = document.getElementById('output-content');
                  if (pre) {
                    navigator.clipboard.writeText(pre.textContent || '').then(() => {
                      alert('📋 클립보드에 복사되었습니다!');
                    }).catch(() => {
                      alert('❌ 복사에 실패했습니다.');
                    });
                  }
                }} 
                className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 font-medium"
              >
                📋 복사
              </button>
              <button onClick={() => setShowOutputModal(false)} className="px-6 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 font-medium">닫기</button>
            </div>
          </div>
        </div>
      )}

      <header className="bg-white border-b px-6 py-3 flex items-center justify-between shadow-sm">
        <div className="flex items-center gap-4">
          <a href="/" className="text-gray-500 hover:text-gray-700">&larr; 돌아가기</a>
          <h1 className="text-xl font-bold text-gray-800">Agent 관리</h1>
        </div>
        <div className="flex items-center gap-3">
          <button 
            onClick={resetToInitialPipeline} 
            disabled={isRunning}
            className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 ${isRunning ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-gray-500 text-white hover:bg-gray-600'}`}
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
            </svg>
            초기화
          </button>
          <button onClick={runPipeline} disabled={isRunning} className={`px-4 py-2 rounded-lg font-medium flex items-center gap-2 ${isRunning ? 'bg-gray-300 text-gray-500 cursor-not-allowed' : 'bg-green-500 text-white hover:bg-green-600'}`}>
            {isRunning ? (<><svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" /></svg>실행 중...</>) : (<><svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>파이프라인 실행</>)}
          </button>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden">
        <aside className="w-64 bg-white border-r overflow-y-auto">
          <div className="p-4">
            <h2 className="font-semibold text-gray-700 mb-3">에이전트 목록</h2>
            <p className="text-xs text-gray-500 mb-4">클릭하여 캔버스에 추가</p>
            <div className="space-y-2">
              {agents.map((agent) => (
                <button key={agent.id} onClick={() => addAgentNode(agent)} className="w-full text-left p-3 rounded-lg border hover:shadow-md transition-shadow" style={{ borderColor: agent.color }}>
                  <div className="font-medium text-sm" style={{ color: agent.color }}>{agent.name}</div>
                  <div className="text-xs text-gray-500 mt-1 line-clamp-2">{agent.description}</div>
                </button>
              ))}
            </div>
            <div className="mt-6 pt-4 border-t">
              <h3 className="font-semibold text-gray-700 mb-3">도구</h3>
              <div className="space-y-2">
                <button onClick={addInputNode} className="w-full text-left p-3 rounded-lg border border-green-300 hover:shadow-md transition-shadow bg-green-50">
                  <div className="font-medium text-sm text-green-600">+ Input 추가</div>
                  <div className="text-xs text-gray-500 mt-1">입력 노드 추가</div>
                </button>
                <button onClick={addOutputNode} className="w-full text-left p-3 rounded-lg border border-blue-300 hover:shadow-md transition-shadow bg-blue-50">
                  <div className="font-medium text-sm text-blue-600">+ Output 추가</div>
                  <div className="text-xs text-gray-500 mt-1">결과 확인용 노드 추가</div>
                </button>
                <button onClick={addFinalInputNode} className="w-full text-left p-3 rounded-lg border border-purple-300 hover:shadow-md transition-shadow bg-purple-50">
                  <div className="font-medium text-sm text-purple-600">+ Final Input 추가</div>
                  <div className="text-xs text-gray-500 mt-1">Final Agent 직접 테스트</div>
                </button>
              </div>
            </div>
          </div>
        </aside>

        <main className="flex-1 relative">
          <ReactFlow nodes={nodes} edges={edges} onNodesChange={onNodesChange} onEdgesChange={onEdgesChange} onConnect={onConnect} onNodeClick={onNodeClick} nodeTypes={nodeTypes} fitView className="bg-gray-50">
            <Background color="#e5e7eb" gap={20} />
            <Controls className="bg-white" />
          </ReactFlow>
        </main>

        <aside className="w-96 bg-white border-l overflow-y-auto">
          {selectedNode && selectedNode.type === 'agent' ? (
            <div className="p-4">
              <h2 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                <span className="w-3 h-3 rounded-full" style={{ backgroundColor: selectedNode.data.color }} />
                {selectedNode.data.label}
              </h2>
              <p className="text-sm text-gray-500 mb-4">{selectedNode.data.description}</p>
              
              <button 
                onClick={() => runSingleNode(selectedNode.id)}
                className="w-full mb-4 px-3 py-2 bg-indigo-500 text-white rounded text-sm hover:bg-indigo-600 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /></svg>
                이 노드만 실행
              </button>

              {nodeOutputData[selectedNode.id] && (
                <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-xs font-semibold text-green-800">📤 출력 데이터:</div>
                    <button
                      onClick={() => {
                        setOutputModalContent(nodeOutputData[selectedNode.id]);
                        setShowOutputModal(true);
                      }}
                      className="text-xs text-green-600 hover:text-green-800"
                    >
                      전체보기
                    </button>
                  </div>
                  <pre className="text-xs whitespace-pre-wrap text-green-900 max-h-48 overflow-y-auto">{formatResult(nodeOutputData[selectedNode.id]).substring(0, 500)}...</pre>
                </div>
              )}
              
              <div className="mb-4">
                <div className="text-xs font-medium text-gray-500 mb-1">입력</div>
                <div className="flex flex-wrap gap-1">
                  {selectedNode.data.inputs?.map((input: string) => (<span key={input} className="text-xs px-2 py-1 bg-gray-100 rounded">{input}</span>))}
                </div>
              </div>
              <div className="mb-4">
                <div className="text-xs font-medium text-gray-500 mb-1">출력</div>
                <div className="flex flex-wrap gap-1">
                  {selectedNode.data.outputs?.map((output: string) => (<span key={output} className="text-xs px-2 py-1 bg-gray-100 rounded">{output}</span>))}
                </div>
              </div>
              <div className="mb-4 p-3 bg-gray-50 rounded-lg border">
                <div className="text-xs font-semibold text-gray-700 mb-3 uppercase">프롬프트 관리</div>
                
                {promptList.length > 1 && (
                  <div className="mb-3">
                    <div className="text-xs font-medium text-gray-600 mb-1.5">프롬프트 타입</div>
                    <select value={selectedPromptKey} onChange={(e) => handlePromptKeyChange(e.target.value)} className="w-full px-3 py-2 border rounded text-sm bg-white">
                      {promptList.map((p) => (<option key={p.key} value={p.key}>{p.name}</option>))}
                    </select>
                  </div>
                )}
                
                <div>
                  <div className="text-xs font-medium text-gray-600 mb-1.5">저장된 버전</div>
                  <div className="flex gap-2">
                    <select value={selectedVersion} onChange={(e) => selectVersion(e.target.value)} className="flex-1 px-3 py-2 border rounded text-sm bg-white">
                      {currentVersions.map((v) => (<option key={v.version_id} value={v.version_id}>{v.name} {v.created_at ? `(${new Date(v.created_at).toLocaleDateString('ko-KR')})` : ''}</option>))}
                    </select>
                    {selectedVersion !== 'default' && (
                      <button onClick={() => deletePrompt(selectedVersion)} className="px-3 py-2 text-red-500 hover:bg-red-50 border border-red-300 rounded text-sm transition-colors" title="현재 버전 삭제">🗑️</button>
                    )}
                  </div>
                </div>
              </div>
              <div className="mb-4">
                <div className="flex items-center justify-between mb-1">
                  <div className="text-xs font-medium text-gray-500">프롬프트</div>
                  <div className="flex gap-2">
                    <button onClick={() => setShowFullPromptModal(true)} className="text-xs text-blue-500 hover:text-blue-700">큰 화면으로 보기</button>
                    <button onClick={() => setShowPromptEditor(!showPromptEditor)} className="text-xs text-gray-500 hover:text-gray-700">{showPromptEditor ? '접기' : '펼치기'}</button>
                  </div>
                </div>
                {showPromptEditor && (
                  <>
                    <textarea value={promptContent} onChange={(e) => setPromptContent(e.target.value)} className="w-full h-64 px-3 py-2 border rounded text-xs font-mono resize-none" placeholder="프롬프트 내용..." />
                    <div className="mt-2 space-y-2">
                      {selectedVersion !== 'default' && (
                        <button onClick={() => savePrompt(true)} className="w-full px-3 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600">현재 버전 저장</button>
                      )}
                      <button onClick={() => savePrompt(false)} className="w-full px-3 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600">새 버전으로 저장</button>
                    </div>
                  </>
                )}
              </div>
              <button onClick={() => { setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id)); setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id)); setSelectedNode(null); }} className="w-full px-3 py-2 border border-red-300 text-red-500 rounded text-sm hover:bg-red-50">노드 삭제</button>
            </div>
          ) : selectedNode && selectedNode.type === 'finalInput' ? (
            <div className="p-4">
              <h2 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                🎯 {selectedNode.data.label}
              </h2>
              <p className="text-xs text-gray-500 mb-4">Final Agent를 직접 테스트합니다</p>

              <div className="space-y-4">
                <div>
                  <label className="text-xs font-medium text-gray-700 mb-1 block">user_question (사용자 질문)</label>
                  <textarea
                    value={selectedNode.data.user_question || ''}
                    onChange={(e) => {
                      setNodes((nds) => nds.map((n) =>
                        n.id === selectedNode.id
                          ? { ...n, data: { ...n.data, user_question: e.target.value } }
                          : n
                      ));
                    }}
                    className="w-full h-20 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-purple-500"
                    placeholder="예: 서울대 26년 수시요강"
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-700 mb-1 block">answer_structure (JSON Array)</label>
                  <textarea
                    value={selectedNode.data.answer_structure || '[]'}
                    onChange={(e) => {
                      setNodes((nds) => nds.map((n) =>
                        n.id === selectedNode.id
                          ? { ...n, data: { ...n.data, answer_structure: e.target.value } }
                          : n
                      ));
                    }}
                    className="w-full h-32 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-purple-500 font-mono"
                    placeholder='[{"section": 1, "type": "empathy", "source_from": null, "instruction": "..."}]'
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-700 mb-1 block">sub_agent_results (JSON Object)</label>
                  <textarea
                    value={selectedNode.data.sub_agent_results || '{}'}
                    onChange={(e) => {
                      setNodes((nds) => nds.map((n) =>
                        n.id === selectedNode.id
                          ? { ...n, data: { ...n.data, sub_agent_results: e.target.value } }
                          : n
                      ));
                    }}
                    className="w-full h-40 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-purple-500 font-mono"
                    placeholder='{"Step1": {"agent": "서울대 agent", "status": "success", "result": "..."}}'
                  />
                </div>

                <div>
                  <label className="text-xs font-medium text-gray-700 mb-1 block">notes (추가 지시사항)</label>
                  <textarea
                    value={selectedNode.data.notes || ''}
                    onChange={(e) => {
                      setNodes((nds) => nds.map((n) =>
                        n.id === selectedNode.id
                          ? { ...n, data: { ...n.data, notes: e.target.value } }
                          : n
                      ));
                    }}
                    className="w-full h-20 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-purple-500"
                    placeholder="Final Agent에게 전달할 추가 지시사항"
                  />
                </div>
              </div>

              <button 
                onClick={async () => {
                  try {
                    const answer_structure = JSON.parse(selectedNode.data.answer_structure || '[]');
                    const sub_agent_results = JSON.parse(selectedNode.data.sub_agent_results || '{}');
                    
                    const response = await axios.post(`${API_BASE}/api/test/final-agent`, {
                      user_question: selectedNode.data.user_question,
                      answer_structure,
                      sub_agent_results,
                      notes: selectedNode.data.notes || ''
                    });
                    
                    setOutputModalContent(response.data);
                    setShowOutputModal(true);
                    alert('✅ Final Agent 실행 완료!');
                  } catch (error: any) {
                    console.error('Final Agent 실행 실패:', error);
                    alert(`❌ 실행 실패: ${error.response?.data?.detail || error.message}`);
                  }
                }}
                className="w-full mt-4 px-3 py-2 bg-purple-500 text-white rounded text-sm hover:bg-purple-600 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /></svg>
                Final Agent 실행
              </button>

              <button onClick={() => { setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id)); setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id)); setSelectedNode(null); }} className="w-full mt-2 px-3 py-2 border border-red-300 text-red-500 rounded text-sm hover:bg-red-50">노드 삭제</button>
            </div>
          ) : selectedNode && selectedNode.type === 'input' ? (
            <div className="p-4">
              <h2 className="font-semibold text-gray-700 mb-3 flex items-center gap-2">
                📝 {selectedNode.data.label}
              </h2>
              
              <div className="mb-4">
                <label className="text-xs font-medium text-gray-500 mb-2 block">질문 입력</label>
                <textarea
                  value={inputTextareaValue}
                  onChange={(e) => {
                    const newValue = e.target.value;
                    setInputTextareaValue(newValue);
                    if (globalInputRefs[selectedNode.id]) {
                      globalInputRefs[selectedNode.id].value = newValue;
                    }
                  }}
                  onFocus={() => {
                    // 포커스 시 globalInputRefs의 값으로 동기화
                    if (globalInputRefs[selectedNode.id]) {
                      setInputTextareaValue(globalInputRefs[selectedNode.id].value || '');
                    }
                  }}
                  className="w-full h-32 px-3 py-2 border rounded text-sm resize-none focus:ring-2 focus:ring-blue-500"
                  placeholder="질문을 입력하세요..."
                />
              </div>

              <button 
                onClick={() => runPipeline()}
                className="w-full mb-4 px-3 py-2 bg-blue-500 text-white rounded text-sm hover:bg-blue-600 flex items-center justify-center gap-2"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" /></svg>
                파이프라인 실행
              </button>

              <button 
                onClick={() => {
                  const currentValue = inputTextareaValue?.trim();
                  if (!currentValue) {
                    alert('질문을 입력해주세요');
                    return;
                  }
                  const name = prompt('질문 이름을 입력하세요', currentValue.substring(0, 30));
                  if (name) {
                    const savedQuestions = JSON.parse(localStorage.getItem('saved-questions') || '{}');
                    savedQuestions[name] = currentValue;
                    localStorage.setItem('saved-questions', JSON.stringify(savedQuestions));
                    alert('질문이 저장되었습니다');
                    setNodes([...nodes]); // Force re-render
                  }
                }}
                className="w-full mb-4 px-3 py-2 bg-green-500 text-white rounded text-sm hover:bg-green-600"
              >
                💾 질문 저장하기
              </button>

              <div className="border-t pt-4">
                <div className="text-xs font-semibold text-gray-600 mb-2">저장된 질문</div>
                <div className="space-y-1 max-h-96 overflow-y-auto">
                  {Object.entries(JSON.parse(localStorage.getItem('saved-questions') || '{}')).map(([name, question]) => (
                    <button
                      key={name}
                      onClick={() => {
                        setSelectedQuestionName(name);
                        setSelectedQuestionContent(question as string);
                        setShowQuestionModal(true);
                      }}
                      className="w-full text-left px-3 py-2 text-xs bg-gray-50 hover:bg-gray-100 rounded border"
                    >
                      <div className="font-medium">{name}</div>
                      <div className="text-gray-500 truncate mt-1">{(question as string).substring(0, 50)}...</div>
                    </button>
                  ))}
                </div>
              </div>

              <button onClick={() => { setNodes((nds) => nds.filter((n) => n.id !== selectedNode.id)); setEdges((eds) => eds.filter((e) => e.source !== selectedNode.id && e.target !== selectedNode.id)); setSelectedNode(null); }} className="w-full mt-4 px-3 py-2 border border-red-300 text-red-500 rounded text-sm hover:bg-red-50">노드 삭제</button>
            </div>
          ) : (
            <div className="p-4 text-center text-gray-400">
              <p>노드를 선택하면</p>
              <p>상세 정보가 표시됩니다</p>
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
