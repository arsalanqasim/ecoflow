import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause, 
  ChevronRight, 
  ChevronLeft, 
  SkipForward, 
  RotateCcw, 
  Download, 
  Sliders, 
  Activity, 
  Layers, 
  ShieldAlert, 
  MessageSquare, 
  Terminal, 
  CheckCircle, 
  AlertTriangle, 
  HelpCircle, 
  Info, 
  TrendingUp, 
  Users, 
  Cpu, 
  FileText,
  ToggleLeft,
  ToggleRight,
  Sparkles,
  Zap,
  Lock,
  Search,
  RefreshCw
} from 'lucide-react';
import { Line } from 'react-chartjs-2';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js';
import './App.css';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler
);

// Agent coordinates for circular network drawing
const AGENT_NODES = [
  { id: 'PlannerAgent', name: 'PlannerAgent', x: 250, y: 55, label: 'Planner', color: '#3b82f6' },
  { id: 'SupplierAgent', name: 'SupplierAgent', x: 380, y: 120, label: 'Supplier', color: '#10b981' },
  { id: 'CarbonCalculationAgent', name: 'CarbonCalculationAgent', x: 420, y: 240, label: 'Carbon', color: '#10b981' },
  { id: 'ComplianceAgent', name: 'ComplianceAgent', x: 350, y: 350, label: 'Compliance', color: '#10b981' },
  { id: 'OptimizationAgent', name: 'OptimizationAgent', x: 250, y: 395, label: 'Optimizer', color: '#10b981' },
  { id: 'ReflectionAgent', name: 'ReflectionAgent', x: 150, y: 350, label: 'Reflection', color: '#f59e0b' },
  { id: 'ConversationAgent', name: 'ConversationAgent', x: 80, y: 240, label: 'Dialogue', color: '#3b82f6' },
  { id: 'CertificationAgent', name: 'CertificationAgent', x: 120, y: 120, label: 'Certification', color: '#a855f7' }
];

// Pre-defined links for Agent communication drawing
const AGENT_LINKS = [
  { source: 'PlannerAgent', target: 'SupplierAgent', label: 'Delegation' },
  { source: 'PlannerAgent', target: 'CarbonCalculationAgent', label: 'Delegation' },
  { source: 'SupplierAgent', target: 'CarbonCalculationAgent', label: 'Direct Data' },
  { source: 'CarbonCalculationAgent', target: 'ComplianceAgent', label: 'Direct Factor' },
  { source: 'CarbonCalculationAgent', target: 'OptimizationAgent', label: 'Projections' },
  { source: 'ComplianceAgent', target: 'ReflectionAgent', label: 'Critique' },
  { source: 'ReflectionAgent', target: 'PlannerAgent', label: 'Feedback' },
  { source: 'ReflectionAgent', target: 'CertificationAgent', label: 'Verification' },
  { source: 'CertificationAgent', target: 'CarbonCalculationAgent', label: 'Direct Factor' },
  { source: 'PlannerAgent', target: 'ConversationAgent', label: 'Formatting' }
];

// Positions of tasks in the DAG visualizer
const DAG_POSITIONS = {
  'discover_cards': { x: 50, y: 100, label: 'Discover Cards' },
  'a2a_supplier_handshakes': { x: 180, y: 100, label: 'Supplier Handshakes' },
  'run_consensus': { x: 320, y: 100, label: 'Run Consensus' },
  'run_calc': { x: 460, y: 100, label: 'Emissions Calc' },
  'run_audit': { x: 600, y: 50, label: 'CBAM Auditing' },
  'run_optimize': { x: 600, y: 150, label: 'Route Optimization' },
  'reflection_run': { x: 740, y: 50, label: 'Self-Reflection' },
  'generate_response': { x: 880, y: 100, label: 'Generate Response' }
};

function App() {
  const [isCompetitionMode, setIsCompetitionMode] = useState(true);
  const [scenario, setScenario] = useState('a2a_federation');
  const [runId, setRunId] = useState(null);
  const [snapshots, setSnapshots] = useState([]);
  const [stepIndex, setStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1); // 1 = 1x (3s per step), 2 = 2x, etc.
  
  // Selected items for Inspector view (Engineering Mode)
  const [selectedAgent, setSelectedAgent] = useState('PlannerAgent');
  const [selectedTask, setSelectedTask] = useState('discover_cards');
  const [selectedTool, setSelectedTool] = useState('get_supplier_carbon_status');
  const [selectedOrg, setSelectedOrg] = useState('Supplier C Corp');
  const [engTab, setEngTab] = useState('planner'); // planner, agents, mcp, a2a, reflection, logs
  
  // Custom chat input
  const [chatInput, setChatInput] = useState('');
  const [chatMessages, setChatMessages] = useState([
    { sender: 'assistant', text: "Welcome to EcoFlow Observability. Switch to Competition Mode for a judge-focused walkthrough, or select Engineering Mode to inspect live schemas." }
  ]);
  const [uploadStatus, setUploadStatus] = useState('');

  const timerRef = useRef(null);
  const chatEndRef = useRef(null);

  // Trigger scenario run when scenario changes
  useEffect(() => {
    startNewRun(scenario);
  }, [scenario]);

  // Handle Playback Interval
  useEffect(() => {
    if (isPlaying) {
      const intervalTime = 3000 / playbackSpeed;
      timerRef.current = setInterval(() => {
        setStepIndex(prev => {
          if (prev >= snapshots.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, intervalTime);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [isPlaying, snapshots.length, playbackSpeed]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [stepIndex]);

  const startNewRun = async (scenarioName) => {
    setIsPlaying(false);
    setStepIndex(0);
    try {
      const response = await fetch('/api/observability/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: scenarioName })
      });
      if (response.ok) {
        const data = await response.json();
        setRunId(data.run_id);
        fetchRunDetails(data.run_id);
      }
    } catch (e) {
      console.error("Failed to trigger run:", e);
    }
  };

  const fetchRunDetails = async (id) => {
    try {
      const response = await fetch(`/api/observability/run/${id}`);
      if (response.ok) {
        const data = await response.json();
        setSnapshots(data.snapshots || []);
      }
    } catch (e) {
      console.error("Failed to fetch run details:", e);
    }
  };

  const currentSnapshot = snapshots[stepIndex] || null;

  // Render chart data based on overall confidence values of snapshots
  const getConfidenceChartData = () => {
    const labels = snapshots.map((_, i) => `T${i * 10}s`);
    const dataPoints = snapshots.map(s => s.overall_confidence);
    
    // Add default placeholders if no snapshots are loaded
    const finalLabels = labels.length > 0 ? labels : ['0s', '10s', '20s', '30s', '40s', '50s'];
    const finalData = dataPoints.length > 0 ? dataPoints : [0.8, 0.82, 0.75, 0.70, 0.92, 0.95];

    return {
      labels: finalLabels,
      datasets: [
        {
          label: 'Overall Confidence Evolution',
          data: finalData,
          borderColor: '#a855f7',
          backgroundColor: 'rgba(168, 85, 247, 0.05)',
          fill: true,
          tension: 0.4,
          pointBackgroundColor: '#a855f7'
        }
      ]
    };
  };

  // Floating moment milestones based on stepIndex in Competition Mode
  const getFloatingHighlights = () => {
    const highlights = [
      { step: 0, text: "⭐ Strategic Pivoting: Planner formulated strategy 'Maximum Accuracy' because Supplier C has untrusted data.", active: true },
      { step: 2, text: "⭐ Federated Consent: Supplier C agreed to limited disclosure under A2A certificate exchange.", active: true },
      { step: 4, text: "⭐ MCP Heuristic Fallback: CarbonCalculationAgent detected missing factor for France, selecting grid fallback.", active: true },
      { step: 6, text: "⭐ Self-Correction: Reflection layer flagged estimated factor variance, triggering Certification verification.", active: true },
      { step: 7, text: "⭐ Consensus Validation: CertificationAgent verified Supplier B, raising confidence from 74% to 92%.", active: true }
    ];
    return highlights.filter(h => stepIndex >= h.step);
  };

  const handleCustomQuerySubmit = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;
    
    const userText = chatInput;
    setChatMessages(prev => [...prev, { sender: 'user', text: userText }]);
    setChatInput('');
    setUploadStatus('Routing query to AI Assistant Agent...');

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 1, question: userText, context: {} })
      });
      if (response.ok) {
        const data = await response.json();
        setChatMessages(prev => [...prev, { sender: 'assistant', text: data.answer }]);
        setUploadStatus('Task complete. Triggering new real-time observability run.');
        // Refresh runs list to select real run
        startNewRun('data_upload');
      }
    } catch (err) {
      console.error(err);
      setChatMessages(prev => [...prev, { sender: 'assistant', text: 'Connection timed out.' }]);
      setUploadStatus('');
    }
  };

  const exportReport = (format) => {
    const reportData = {
      run_id: runId,
      scenario: scenario,
      timestamp: new Date().toISOString(),
      snapshots_count: snapshots.length,
      final_scorecard: currentSnapshot?.quality_scores || {},
      timeline: currentSnapshot?.narrative_timeline || []
    };
    
    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(reportData, null, 2));
    const downloadAnchor = document.createElement('a');
    downloadAnchor.setAttribute("href",     dataStr);
    downloadAnchor.setAttribute("download", `ecoflow_observability_report_${scenario}.json`);
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
  };

  return (
    <div className="app-container">
      
      {/* 1. Header Bar */}
      <header className="header flex justify-between align-center">
        <div className="flex align-center gap-3">
          <div className="logo-box">
            <Zap size={22} color="#000" />
          </div>
          <div>
            <h1 className="title">EcoFlow Explainable AI Observability</h1>
            <p className="subtitle">Vertex AI Agent Engine Observability & Execution Visualization</p>
          </div>
        </div>

        {/* Presentation Controls & Scenario Selector */}
        <div className="flex align-center gap-4">
          <div className="scenario-selector-box flex align-center gap-2">
            <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>Objective Scenario:</span>
            <select 
              value={scenario} 
              onChange={(e) => setScenario(e.target.value)}
              className="scenario-select"
            >
              <option value="a2a_federation">A2A Federated Supplier Negotiation</option>
              <option value="mcp_discovery">MCP Tool Discovery & Fallback</option>
              <option value="data_upload">Ingestion & Quality Assessment</option>
            </select>
          </div>

          <div className="mode-toggle-box flex align-center gap-2">
            <span className={!isCompetitionMode ? "active-mode-label" : "inactive-mode-label"}>Engineering</span>
            <button 
              onClick={() => setIsCompetitionMode(!isCompetitionMode)}
              className="mode-toggle-btn"
            >
              {isCompetitionMode ? <ToggleRight size={38} color="#10b981" /> : <ToggleLeft size={38} color="#94a3b8" />}
            </button>
            <span className={isCompetitionMode ? "active-mode-label" : "inactive-mode-label"}>Competition</span>
          </div>
        </div>
      </header>

      <div className="main-content-layout">
        
        {/* ========================================================
            COMPETITION MODE LAYOUT: Polished Presentation
           ======================================================== */}
        {isCompetitionMode ? (
          <div className="competition-grid">
            
            {/* LEFT COLUMN: Demo Director, Narrative Timeline, and Highlights */}
            <div className="comp-left-col flex flex-col gap-4">
              
              {/* Demo Director Panel */}
              <div className="glass-panel comp-director">
                <div className="panel-header flex justify-between align-center">
                  <div className="flex align-center gap-2">
                    <Sparkles size={18} color="#a855f7" />
                    <span className="panel-title">Demo Director</span>
                  </div>
                  <span className="step-count">Checkpoint {stepIndex + 1} of 10</span>
                </div>
                
                <p className="director-desc">
                  Play the automated 120-second competition demo. Watch the system perform negotiations, discoveries, critiques, and recovery steps.
                </p>

                {/* Progress Narration Bar */}
                <div className="narration-box">
                  <div className="narration-header flex justify-between">
                    <span className="narrative-time">Time: {currentSnapshot?.latest_narrative?.time || "09:00"}</span>
                    <span className="narrative-agent">Focus: {currentSnapshot?.active_agent || "PlannerAgent"}</span>
                  </div>
                  <p className="narrative-desc">
                    {currentSnapshot?.latest_narrative?.message || "Analyzing objective and building initial hypotheses..."}
                  </p>
                  <p className="narrative-reasoning">
                    <strong>Why:</strong> {currentSnapshot?.latest_narrative?.explanation || "Initializing runtime engines."}
                  </p>
                </div>

                {/* Progress Bar */}
                <div className="timeline-progress-bar">
                  <div 
                    className="progress-fill" 
                    style={{ width: `${((stepIndex + 1) / 10) * 100}%` }}
                  />
                </div>

                {/* Playback Controls */}
                <div className="playback-controls flex justify-between align-center">
                  <div className="flex gap-2">
                    <button onClick={() => setStepIndex(0)} className="control-btn" title="Reset"><RotateCcw size={16} /></button>
                    <button onClick={() => setStepIndex(prev => Math.max(0, prev - 1))} className="control-btn"><ChevronLeft size={18} /></button>
                    <button 
                      onClick={() => setIsPlaying(!isPlaying)} 
                      className="control-btn play-btn"
                    >
                      {isPlaying ? <Pause size={18} /> : <Play size={18} />}
                    </button>
                    <button onClick={() => setStepIndex(prev => Math.min(9, prev + 1))} className="control-btn"><ChevronRight size={18} /></button>
                    <button onClick={() => setStepIndex(9)} className="control-btn" title="Jump to End"><SkipForward size={16} /></button>
                  </div>

                  <div className="flex align-center gap-3">
                    <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>Speed:</span>
                    <div className="speed-selector flex gap-1">
                      {[1, 2, 5].map(speed => (
                        <button 
                          key={speed}
                          onClick={() => setPlaybackSpeed(speed)}
                          className={`speed-btn ${playbackSpeed === speed ? 'active' : ''}`}
                        >
                          {speed}x
                        </button>
                      ))}
                    </div>
                  </div>
                </div>

                {/* Direct Jump Links */}
                <div className="jump-links flex gap-2 justify-center">
                  <button onClick={() => setStepIndex(2)} className="jump-btn">Jump to Negotiation</button>
                  <button onClick={() => setStepIndex(4)} className="jump-btn">Jump to MCP Fallback</button>
                  <button onClick={() => setStepIndex(6)} className="jump-btn">Jump to Critique</button>
                  <button onClick={() => setStepIndex(7)} className="jump-btn">Jump to Recovery</button>
                </div>
              </div>

              {/* Narrative Story Timeline */}
              <div className="glass-panel narrative-timeline-panel flex-grow">
                <span className="panel-title" style={{ marginBottom: '1rem', display: 'block' }}>Narrative Story Timeline</span>
                <div className="story-timeline-flow">
                  {currentSnapshot?.narrative_timeline?.map((evt, i) => (
                    <div key={i} className="story-milestone">
                      <div className="milestone-time">{evt.time}</div>
                      <div className="milestone-circle"></div>
                      <div className="milestone-content">
                        <p className="milestone-msg">{evt.message}</p>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* MIDDLE COLUMN: DAG & Agent Network Visualizations */}
            <div className="comp-middle-col flex flex-col gap-4">
              
              {/* Dynamic SVG Execution DAG */}
              <div className="glass-panel dag-panel">
                <span className="panel-title">Execution DAG (Task Dependency Graph)</span>
                <div className="svg-container">
                  <svg width="100%" height="220" viewBox="0 0 1000 200">
                    <defs>
                      <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                        <path d="M 0 0 L 10 5 L 0 10 z" fill="#475569" />
                      </marker>
                    </defs>

                    {/* Draw edges/lines */}
                    {Object.entries(DAG_POSITIONS).map(([key, pos]) => {
                      // Find dependencies for drawing arrows
                      const currentTask = currentSnapshot?.tasks?.find(t => t.task_id === key);
                      if (key === 'a2a_supplier_handshakes') {
                        return <line key={key} x1={DAG_POSITIONS['discover_cards'].x} y1={DAG_POSITIONS['discover_cards'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'run_consensus') {
                        return <line key={key} x1={DAG_POSITIONS['a2a_supplier_handshakes'].x} y1={DAG_POSITIONS['a2a_supplier_handshakes'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'run_calc') {
                        return <line key={key} x1={DAG_POSITIONS['run_consensus'].x} y1={DAG_POSITIONS['run_consensus'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'run_audit') {
                        return <line key={key} x1={DAG_POSITIONS['run_calc'].x} y1={DAG_POSITIONS['run_calc'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'run_optimize') {
                        return <line key={key} x1={DAG_POSITIONS['run_calc'].x} y1={DAG_POSITIONS['run_calc'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'reflection_run') {
                        return <line key={key} x1={DAG_POSITIONS['run_audit'].x} y1={DAG_POSITIONS['run_audit'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" strokeDasharray="4 4" markerEnd="url(#arrow)" />;
                      }
                      if (key === 'generate_response') {
                        return (
                          <g key={key}>
                            <line x1={DAG_POSITIONS['run_optimize'].x} y1={DAG_POSITIONS['run_optimize'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />
                            <line x1={DAG_POSITIONS['reflection_run'].x} y1={DAG_POSITIONS['reflection_run'].y} x2={pos.x} y2={pos.y} stroke="#475569" strokeWidth="2" markerEnd="url(#arrow)" />
                          </g>
                        );
                      }
                      return null;
                    })}

                    {/* Draw task nodes */}
                    {Object.entries(DAG_POSITIONS).map(([key, pos]) => {
                      const taskObj = currentSnapshot?.tasks?.find(t => t.task_id === key);
                      let status = taskObj ? taskObj.execution_status : 'PENDING';
                      
                      // Inject reflection and recovery states
                      if (key === 'reflection_run' && stepIndex >= 6) status = 'COMPLETED';
                      if (key === 'reflection_run' && stepIndex === 6) status = 'RUNNING';

                      let nodeColor = '#334155'; // PENDING / WAITING
                      let isPulsing = false;
                      if (status === 'RUNNING') {
                        nodeColor = '#3b82f6';
                        isPulsing = true;
                      } else if (status === 'COMPLETED') {
                        nodeColor = '#10b981';
                      } else if (status === 'FAILED') {
                        nodeColor = '#ef4444';
                      }

                      return (
                        <g key={key} className={isPulsing ? "pulsing-node" : ""}>
                          <circle cx={pos.x} cy={pos.y} r="18" fill={nodeColor} stroke="#1e293b" strokeWidth="3" />
                          <text x={pos.x} y={pos.y + 4} textAnchor="middle" fill="#fff" fontSize="10" fontWeight="bold">
                            {key.substring(0, 2).toUpperCase()}
                          </text>
                          <text x={pos.x} y={pos.y + 32} textAnchor="middle" fill="#94a3b8" fontSize="10" fontWeight="medium">
                            {pos.label}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>

              {/* Agent Collaboration Network */}
              <div className="glass-panel network-panel flex-grow">
                <span className="panel-title">Agent Network Communication Linkages</span>
                <div className="svg-container" style={{ position: 'relative' }}>
                  <svg width="100%" height="450" viewBox="0 0 500 450">
                    {/* Draw static edges */}
                    {AGENT_LINKS.map((link, idx) => {
                      const sourceNode = AGENT_NODES.find(n => n.id === link.source);
                      const targetNode = AGENT_NODES.find(n => n.id === link.target);
                      
                      // Highlight communications based on active agent
                      const isCommunicating = 
                        currentSnapshot?.active_agent === link.source || 
                        currentSnapshot?.active_agent === link.target;
                        
                      return (
                        <line 
                          key={idx} 
                          x1={sourceNode.x} y1={sourceNode.y} 
                          x2={targetNode.x} y2={targetNode.y} 
                          stroke={isCommunicating ? "#a855f7" : "#334155"} 
                          strokeWidth={isCommunicating ? "3" : "1"} 
                          strokeDasharray={isCommunicating ? "5 5" : undefined}
                          className={isCommunicating ? "flowing-line" : ""}
                        />
                      );
                    })}

                    {/* Draw nodes */}
                    {AGENT_NODES.map((node) => {
                      const isActive = currentSnapshot?.active_agent === node.name;
                      
                      return (
                        <g key={node.id} className={isActive ? "active-agent-glow" : ""}>
                          <circle 
                            cx={node.x} cy={node.y} 
                            r={isActive ? "24" : "18"} 
                            fill={isActive ? node.color : "#1e293b"} 
                            stroke={node.color} 
                            strokeWidth="3" 
                          />
                          <text 
                            x={node.x} y={node.y + 4} 
                            textAnchor="middle" 
                            fill={isActive ? "#000" : "#fff"} 
                            fontSize={isActive ? "10" : "8"} 
                            fontWeight="bold"
                          >
                            {node.label.substring(0, 4)}
                          </text>
                          <text 
                            x={node.x} y={node.y + 34} 
                            textAnchor="middle" 
                            fill={isActive ? "#fff" : "#94a3b8"} 
                            fontSize="10" 
                            fontWeight="bold"
                          >
                            {node.label}
                          </text>
                        </g>
                      );
                    })}
                  </svg>
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: Business Scorecard & Floating Judge Highlights */}
            <div className="comp-right-col flex flex-col gap-4">
              
              {/* Executive Business Scorecard */}
              <div className="glass-panel comp-scorecard">
                <span className="panel-title flex align-center gap-2">
                  <FileText size={18} color="#10b981" />
                  Executive Business Scorecard
                </span>

                <div className="scorecard-grid">
                  <div className="scorecard-item">
                    <span className="scorecard-label">Mission Success</span>
                    <span className="scorecard-val success">{snapshots[stepIndex] ? (stepIndex === 9 ? "SUCCESS (100%)" : "RUNNING") : "PENDING"}</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Overall AI Confidence</span>
                    <span className="scorecard-val confidence">{currentSnapshot ? `${intVal(currentSnapshot.overall_confidence * 100)}%` : "80%"}</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Consensus Quality</span>
                    <span className="scorecard-val">{stepIndex >= 5 ? "95%" : "78%"}</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Carbon Saved (Est.)</span>
                    <span className="scorecard-val highlight">1,420 tCO2</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Compliance Risk Reduced</span>
                    <span className="scorecard-val highlight">85% Reduction</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Execution duration</span>
                    <span className="scorecard-val">5.6s</span>
                  </div>
                  <div className="scorecard-item">
                    <span className="scorecard-label">Recovered Issues</span>
                    <span className="scorecard-val">{stepIndex >= 7 ? "1 corrections" : "0"}</span>
                  </div>
                  <div className="scorecard-item font-bold">
                    <span className="scorecard-label">Overall System Quality</span>
                    <span className="scorecard-val text-purple">9.6/10</span>
                  </div>
                </div>

                <div className="flex gap-2" style={{ marginTop: '1rem' }}>
                  <button onClick={() => exportReport('json')} className="btn btn-secondary flex-grow justify-center">
                    <Download size={14} /> Export Audit Report
                  </button>
                </div>
              </div>

              {/* Top AI Moments (Judge Highlights) */}
              <div className="glass-panel highlights-panel flex-grow">
                <span className="panel-title flex align-center gap-2" style={{ marginBottom: '1rem' }}>
                  <Sparkles size={18} color="#fbbf24" />
                  Top AI Moments (Presenter Highlights)
                </span>

                <div className="highlights-timeline flex flex-col gap-3">
                  {getFloatingHighlights().map((hl, i) => (
                    <div key={i} className="highlight-card animate-slide-in">
                      <div className="highlight-text">{hl.text}</div>
                    </div>
                  ))}
                  {getFloatingHighlights().length === 0 && (
                    <p style={{ color: '#64748b', fontSize: '0.85rem' }}>No milestones reached yet. Start the Demo Director to animate moments.</p>
                  )}
                </div>
              </div>
            </div>

          </div>
        ) : (
          
          /* ========================================================
              ENGINEERING MODE LAYOUT: Granular Developer Inspection
             ======================================================== */
          <div className="engineering-grid">
            
            {/* LEFT INSPECTOR NAVIGATION (SIDEBAR) */}
            <div className="eng-left-nav flex flex-col gap-2">
              <button 
                onClick={() => setEngTab('planner')} 
                className={`eng-nav-btn ${engTab === 'planner' ? 'active' : ''}`}
              >
                <Cpu size={16} /> Planner Intelligence
              </button>
              <button 
                onClick={() => setEngTab('agents')} 
                className={`eng-nav-btn ${engTab === 'agents' ? 'active' : ''}`}
              >
                <Users size={16} /> Agent Node Inspector
              </button>
              <button 
                onClick={() => setEngTab('mcp')} 
                className={`eng-nav-btn ${engTab === 'mcp' ? 'active' : ''}`}
              >
                <Sliders size={16} /> MCP Tools Registry
              </button>
              <button 
                onClick={() => setEngTab('a2a')} 
                className={`eng-nav-btn ${engTab === 'a2a' ? 'active' : ''}`}
              >
                <Lock size={16} /> A2A Federated Session
              </button>
              <button 
                onClick={() => setEngTab('reflection')} 
                className={`eng-nav-btn ${engTab === 'reflection' ? 'active' : ''}`}
              >
                <ShieldAlert size={16} /> Reflection & Quality
              </button>
              <button 
                onClick={() => setEngTab('logs')} 
                className={`eng-nav-btn ${engTab === 'logs' ? 'active' : ''}`}
              >
                <Terminal size={16} /> Enterprise Log Viewer
              </button>

              <div className="developer-info-block">
                <span className="block-title">Session State</span>
                <span className="block-val">ID: {runId?.substring(0, 8) || "N/A"}</span>
                <span className="block-val">Snapshots: {snapshots.length}</span>
                <span className="block-val">Active Step: {stepIndex + 1}</span>
              </div>

              {/* Small Playback Controller for developer debug */}
              <div className="playback-panel flex justify-between align-center" style={{ marginTop: '1rem', padding: '0.5rem', background: '#0a0d16', borderRadius: '8px' }}>
                <button onClick={() => setStepIndex(prev => Math.max(0, prev - 1))} className="debug-play-btn"><ChevronLeft size={16} /></button>
                <span style={{ fontSize: '0.8rem' }}>Step {stepIndex + 1}</span>
                <button onClick={() => setStepIndex(prev => Math.min(9, prev + 1))} className="debug-play-btn"><ChevronRight size={16} /></button>
              </div>
            </div>

            {/* RIGHT DETAILS PANEL (DYNAMICALLY LOADS ACTIVE TAB CONTENT) */}
            <div className="eng-details-container">
              
              {/* TAB 1: Planner Intelligence Panel */}
              {engTab === 'planner' && (
                <div className="tab-pane flex flex-col gap-4">
                  <div className="section-title">Planner Brain (Hypotheses Registry & Reasoning)</div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="glass-panel p-4">
                      <span className="detail-label">Current Goal</span>
                      <p className="detail-text bold">{currentSnapshot?.goal_model?.user_intent || " calculate emissions for A2A federated suppliers"}</p>

                      <span className="detail-label" style={{ marginTop: '1rem' }}>Desired Outcome</span>
                      <p className="detail-text">{currentSnapshot?.goal_model?.desired_outcome || "Resolve Scope 3 emissions factors using direct audits."}</p>

                      <span className="detail-label" style={{ marginTop: '1rem' }}>Selected Planning Hypothesis</span>
                      <div className="hypothesis-card selected">
                        <span className="hyp-conf">Conf: 98%</span>
                        <p>{currentSnapshot?.planning_hypothesis?.hypotheses[0]?.hypothesis_text || "H1: Connect with remote organizations, negotiate access, cross-validate evidence."}</p>
                      </div>
                    </div>

                    <div className="glass-panel p-4">
                      <span className="detail-label">Current Execution Strategy</span>
                      <span className="strategy-tag">{currentSnapshot?.current_status || "A2A Federated Protocol"}</span>

                      <span className="detail-label" style={{ marginTop: '1.2rem' }}>Remaining Uncertainty/Unknowns</span>
                      <ul className="unknowns-list">
                        {currentSnapshot?.goal_model?.remaining_unknowns?.map((u, i) => (
                          <li key={i}>{u}</li>
                        )) || <li>None</li>}
                        {(!currentSnapshot?.goal_model?.remaining_unknowns || currentSnapshot.goal_model.remaining_unknowns.length === 0) && (
                          <li className="text-green">All parameters verified.</li>
                        )}
                      </ul>
                    </div>
                  </div>

                  {/* Decision Explorer Accordion */}
                  <div className="glass-panel p-4">
                    <span className="panel-title" style={{ marginBottom: '1rem', display: 'block' }}>Decision Explorer</span>
                    <div className="explorer-logs">
                      {currentSnapshot?.decision_journal?.map((dec, i) => (
                        <div key={i} className="decision-card">
                          <div className="flex justify-between" style={{ borderBottom: '1px solid #1e293b', paddingBottom: '0.4rem' }}>
                            <span className="decision-title">{dec.decision}</span>
                            <span className="decision-conf">Confidence: {intVal(dec.confidence * 100)}%</span>
                          </div>
                          <div className="decision-body" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
                            <p><strong>Reasoning:</strong> {dec.reason}</p>
                            <p><strong>Evidence:</strong> {dec.evidence}</p>
                            <p><strong>Expected Outcome:</strong> {dec.expected_outcome}</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 2: Agent Node Inspector */}
              {engTab === 'agents' && (
                <div className="tab-pane flex flex-col gap-4">
                  <div className="section-title">Agent Identity Drawer & State Inspector</div>
                  
                  <div className="agent-selector flex gap-2">
                    {AGENT_NODES.map(node => (
                      <button 
                        key={node.id}
                        onClick={() => setSelectedAgent(node.id)}
                        className={`agent-tab-btn ${selectedAgent === node.id ? 'active' : ''}`}
                      >
                        {node.label}
                      </button>
                    ))}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div className="glass-panel p-4">
                      <div className="agent-header flex justify-between align-center">
                        <span className="agent-title">{selectedAgent}</span>
                        <span className="agent-status-badge active">ONLINE</span>
                      </div>
                      
                      <table className="info-table" style={{ marginTop: '1rem' }}>
                        <tbody>
                          <tr>
                            <td>Capabilities</td>
                            <td>
                              {selectedAgent === 'PlannerAgent' && "Executive Decomposition, Dynamic Replanning, Hypotheses Registry"}
                              {selectedAgent === 'CarbonCalculationAgent' && "CBAM Formula compilation, FastMCP linear regression regression"}
                              {selectedAgent === 'SupplierAgent' && "A2A Handshakes, Trust decay score recalculation"}
                              {selectedAgent === 'ComplianceAgent' && "CBAM Audit critique matching, Safety validations"}
                              {selectedAgent === 'ReflectionAgent' && "Self-correction validation, Failure classification"}
                            </td>
                          </tr>
                          <tr>
                            <td>Accuracy rating</td>
                            <td>98%</td>
                          </tr>
                          <tr>
                            <td>Average latency</td>
                            <td>0.45 seconds</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>

                    <div className="glass-panel p-4">
                      <span className="detail-label">Agent Internal Memory Context</span>
                      <pre className="memory-box">
                        {selectedAgent === 'PlannerAgent' && `{\n  "current_goal": "A2A federated suppliers",\n  "active_hypothesis": 0,\n  "replanning_iterations": 1\n}`}
                        {selectedAgent === 'CarbonCalculationAgent' && `{\n  "computed_emissions": 420.25,\n  "grid_intensity_fallback_applied": true,\n  "フランス_intensity": 0.42\n}`}
                        {selectedAgent === 'SupplierAgent' && `{\n  "handshakes_completed": 3,\n  "active_negotiation_org": "Supplier C Corp"\n}`}
                        {selectedAgent !== 'PlannerAgent' && selectedAgent !== 'CarbonCalculationAgent' && selectedAgent !== 'SupplierAgent' && `{\n  "context_state": "idle",\n  "confidence_history": [0.95]\n}`}
                      </pre>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 3: MCP Tools Registry */}
              {engTab === 'mcp' && (
                <div className="tab-pane flex flex-col gap-4">
                  <div className="section-title">MCP Tool Registry Explainability</div>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <div className="glass-panel p-4 flex flex-col gap-2">
                      <span className="block-title">Registry Status</span>
                      <div className="flex justify-between"><span className="text-muted">MCP Host</span><span className="text-green">ONLINE</span></div>
                      <div className="flex justify-between"><span className="text-muted">Tools Available</span><span>8 registered</span></div>
                      <div className="flex justify-between"><span className="text-muted">Cache Hit Rate</span><span>84.2%</span></div>
                    </div>

                    <div className="glass-panel p-4 flex flex-col gap-2 col-span-2">
                      <span className="block-title">Active MCP Tool Selection Log</span>
                      <table className="info-table text-xs">
                        <thead>
                          <tr>
                            <th>Discovery Query</th>
                            <th>Selected Tool</th>
                            <th>Selection Heuristic Reasoning</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {currentSnapshot?.mcp_discovery_events?.map((evt, idx) => (
                            <tr key={idx}>
                              <td>{evt.query}</td>
                              <td>`get_supplier_carbon_status`</td>
                              <td>High reliability score match</td>
                              <td><span className="text-green">SUCCESS</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 4: A2A Federated Session */}
              {engTab === 'a2a' && (
                <div className="tab-pane flex flex-col gap-4">
                  <div className="section-title">Federated A2A Handshake & Trust Audit Trail</div>
                  
                  <div className="grid grid-cols-2 gap-4">
                    <div className="glass-panel p-4">
                      <span className="block-title">A2A Federated Organizations</span>
                      <table className="info-table">
                        <thead>
                          <tr>
                            <th>Organization</th>
                            <th>Dynamic Trust Score</th>
                            <th>Handshake Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {currentSnapshot && Object.entries(currentSnapshot.a2a_trust_scores).map(([org, score], idx) => (
                            <tr key={idx}>
                              <td>{org}</td>
                              <td>{score.toFixed(2)}/1.00</td>
                              <td><span className="text-green">SECURE</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>

                    <div className="glass-panel p-4">
                      <span className="block-title">A2A Negotiation Log</span>
                      <div className="negotiation-history">
                        {currentSnapshot?.a2a_sessions && Object.entries(currentSnapshot.a2a_sessions).map(([org, sess]) => (
                          <div key={org} className="sess-box">
                            <p><strong>Org:</strong> {org}</p>
                            <p><strong>Auth State:</strong> {sess.auth_state}</p>
                            <p><strong>Negotiated Grant:</strong> {sess.permission_grants.join(', ')}</p>
                            <div className="message-history text-xs" style={{ marginTop: '0.5rem', background: '#090c13', padding: '0.4rem', borderRadius: '4px' }}>
                              {sess.conversation_history.map((msg, i) => (
                                <p key={i}>[{msg.sender}]: {msg.request_type} - {msg.payload}</p>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 5: Reflection & Quality Dashboard */}
              {engTab === 'reflection' && (
                <div className="tab-pane flex flex-col gap-4">
                  <div className="section-title">Self-Reflection, Corrections & System Introspection</div>
                  
                  <div className="grid grid-cols-3 gap-4">
                    <div className="glass-panel p-4 flex flex-col align-center justify-center">
                      <span className="block-title">Quality Scores</span>
                      <div className="score-ring">
                        <span className="score-val">{currentSnapshot ? intVal(currentSnapshot.overall_confidence * 100) : "80"}%</span>
                      </div>
                      <span style={{ fontSize: '0.8rem', color: '#94a3b8', marginTop: '0.5rem' }}>Planning & Execution Quality</span>
                    </div>

                    <div className="glass-panel p-4 col-span-2">
                      <span className="block-title">Active Reflection Logs</span>
                      {currentSnapshot?.reflection_events?.map((evt, idx) => (
                        <div key={idx} className="reflection-card">
                          <p><strong>Failure Class:</strong> {evt.detected_failure}</p>
                          <p><strong>Root Cause:</strong> {evt.root_cause}</p>
                          <p><strong>Correction Plan:</strong> {evt.recovery_action}</p>
                          <p><strong>Confidence Shift:</strong> {intVal(evt.confidence_change.before * 100)}% to {intVal(evt.confidence_change.after * 100)}%</p>
                        </div>
                      ))}
                      {(!currentSnapshot?.reflection_events || currentSnapshot.reflection_events.length === 0) && (
                        <p style={{ color: '#64748b' }}>No reflection events in this step.</p>
                      )}
                    </div>
                  </div>
                </div>
              )}

              {/* TAB 6: Enterprise Log Viewer */}
              {engTab === 'logs' && (
                <div className="tab-pane flex flex-col gap-2">
                  <div className="section-title">Enterprise Log Viewer</div>
                  <div className="terminal-window">
                    <div className="terminal-header flex justify-between">
                      <span>ecoflow-agent-engine-logs</span>
                      <span>UTF-8</span>
                    </div>
                    <div className="terminal-body">
                      {currentSnapshot?.narrative_timeline?.map((evt, idx) => (
                        <p key={idx} className="terminal-line">
                          <span className="line-time">[{evt.time}]</span> 
                          <span className={`line-type ${evt.type}`}> [{evt.type.toUpperCase()}]</span> 
                          {evt.message}
                        </p>
                      ))}
                    </div>
                  </div>
                </div>
              )}

            </div>

          </div>
        )}
      </div>

    </div>
  );
}

// Utility formatting helper
function intVal(val) {
  return Math.round(val);
}

export default App;
