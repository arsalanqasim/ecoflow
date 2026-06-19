import React, { useState, useEffect, useRef } from 'react';
import { 
  Leaf, 
  Upload, 
  Send, 
  MessageSquare, 
  ShieldAlert, 
  TrendingUp, 
  Award, 
  Activity, 
  Layers 
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

// Register ChartJS modules
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

function App() {
  const [dashboard, setDashboard] = useState({
    total_emissions_tCO2: 0.0,
    cbam_liabilities_eur: 0.0,
    top_emitting_supplier: 'Loading...',
    compliant_ratio: 1.0
  });

  const [chatMessages, setChatMessages] = useState([
    {
      sender: 'assistant',
      text: "Welcome to EcoFlow's AI Assistant. I can analyze Scope 3 emissions, compute CBAM border tariffs, or run forecasting projections. Ask me anything about your supply chain!"
    }
  ]);
  const [chatInput, setChatInput] = useState('');
  const [uploadStatus, setUploadStatus] = useState('');
  const [uploading, setUploading] = useState(false);
  
  // Chart state (contains merged historical and forecast projections)
  const [chartData, setChartData] = useState({
    labels: ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul (Forecast)', 'Aug (Forecast)', 'Sep (Forecast)', 'Oct (Forecast)'],
    datasets: [
      {
        label: 'Emissions (tCO2)',
        data: [1500, 1850, 1600, 2200, 2100, 2450, 2600, 2800, 3100, 3350],
        borderColor: '#10b981',
        backgroundColor: 'rgba(16, 185, 129, 0.07)',
        fill: true,
        tension: 0.3,
        pointBackgroundColor: '#10b981',
      }
    ]
  });

  const chatEndRef = useRef(null);

  useEffect(() => {
    fetchDashboardSummary();
    fetchEmissionsTrend();
  }, []);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  const fetchDashboardSummary = async () => {
    try {
      const response = await fetch('/api/dashboard/summary');
      if (response.ok) {
        const data = await response.json();
        setDashboard(data);
      }
    } catch (e) {
      console.error("Failed to fetch dashboard summary:", e);
    }
  };

  const fetchEmissionsTrend = async () => {
    // Populate default line chart with database values + forecast
    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 1, question: "forecast emissions", context: {} })
      });
      if (response.ok) {
        const resData = await response.json();
        if (resData.status === 'success' && resData.charts.length > 0) {
          const forecastPoints = resData.charts[0].data;
          
          // Hardcode mock historical to draw a cohesive chart
          const historicalLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
          const historicalValues = [1850.5, 1920.2, 1880.8, 2010.4, 2150.3, 2240.1];
          
          const forecastLabels = forecastPoints.map(p => {
            const dateObj = new Date(p.date);
            return dateObj.toLocaleString('default', { month: 'short' }) + ' (Forecast)';
          });
          const forecastValues = forecastPoints.map(p => p.predicted_emission_tCO2);

          setChartData({
            labels: [...historicalLabels, ...forecastLabels],
            datasets: [
              {
                label: 'Supply Chain Carbon Trend (tCO2)',
                data: [...historicalValues, ...forecastValues],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.05)',
                fill: true,
                tension: 0.35,
                pointBackgroundColor: (context) => {
                  return context.index >= historicalValues.length ? '#f59e0b' : '#10b981';
                },
                segment: {
                  borderDash: (ctx) => ctx.p0.parsed.x >= historicalValues.length - 1 ? [6, 6] : undefined,
                  borderColor: (ctx) => ctx.p0.parsed.x >= historicalValues.length - 1 ? '#f59e0b' : '#10b981'
                }
              }
            ]
          });
        }
      }
    } catch (e) {
      console.error("Failed to fetch emissions trend:", e);
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!chatInput.trim()) return;

    const userText = chatInput;
    setChatMessages(prev => [...prev, { sender: 'user', text: userText }]);
    setChatInput('');

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: 1, question: userText, context: {} })
      });
      
      if (response.ok) {
        const data = await response.json();
        setChatMessages(prev => [...prev, { sender: 'assistant', text: data.answer }]);
        
        // If the reply contains updated chart data, refresh chart view
        if (data.charts && data.charts.length > 0 && data.charts[0].type === 'forecast') {
          const forecastPoints = data.charts[0].data;
          const historicalLabels = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
          const historicalValues = [1850.5, 1920.2, 1880.8, 2010.4, 2150.3, 2240.1];
          const forecastLabels = forecastPoints.map(p => {
            const dateObj = new Date(p.date);
            return dateObj.toLocaleString('default', { month: 'short' }) + ' (Forecast)';
          });
          const forecastValues = forecastPoints.map(p => p.predicted_emission_tCO2);

          setChartData({
            labels: [...historicalLabels, ...forecastLabels],
            datasets: [
              {
                label: 'Supply Chain Carbon Trend (tCO2)',
                data: [...historicalValues, ...forecastValues],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.05)',
                fill: true,
                tension: 0.35,
                pointBackgroundColor: (context) => {
                  return context.index >= historicalValues.length ? '#f59e0b' : '#10b981';
                },
                segment: {
                  borderDash: (ctx) => ctx.p0.parsed.x >= historicalValues.length - 1 ? [6, 6] : undefined,
                  borderColor: (ctx) => ctx.p0.parsed.x >= historicalValues.length - 1 ? '#f59e0b' : '#10b981'
                }
              }
            ]
          });
        }
      } else {
        setChatMessages(prev => [...prev, { sender: 'assistant', text: 'Error calling the assistant agent. Please try again.' }]);
      }
    } catch (err) {
      console.error(err);
      setChatMessages(prev => [...prev, { sender: 'assistant', text: 'Network connection lost.' }]);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    setUploading(true);
    setUploadStatus('Uploading dataset...');
    const formData = new FormData();
    formData.append('file', file);

    try {
      const response = await fetch('/api/data/upload', {
        method: 'POST',
        body: formData
      });
      const res = await response.json();
      if (res.status === 'success') {
        setUploadStatus('Data loaded. Calculations recalculated!');
        fetchDashboardSummary();
        fetchEmissionsTrend();
      } else {
        setUploadStatus(`Upload failed: ${res.message}`);
      }
    } catch (err) {
      console.error(err);
      setUploadStatus('Connection error uploading dataset.');
    } finally {
      setUploading(false);
      setTimeout(() => setUploadStatus(''), 5000);
    }
  };

  return (
    <div className="app-container">
      
      {/* 1. Sidebar Panel */}
      <aside className="sidebar flex flex-col justify-between">
        <div>
          <div className="flex align-center gap-2" style={{ marginBottom: '2.5rem' }}>
            <div style={{ background: '#10b981', padding: '8px', borderRadius: '10px', display: 'flex' }}>
              <Leaf size={24} color="#000" />
            </div>
            <span style={{ fontSize: '1.4rem', fontWeight: 700, letterSpacing: '0.5px' }}>EcoFlow</span>
          </div>
          
          <nav className="flex flex-col gap-2">
            <a href="#" className="flex align-center gap-4" style={{ padding: '0.8rem 1rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '10px', color: '#10b981', textDecoration: 'none', fontWeight: 500 }}>
              <Layers size={18} /> Dashboard
            </a>
            <a href="#" className="flex align-center gap-4" style={{ padding: '0.8rem 1rem', borderRadius: '10px', color: '#94a3b8', textDecoration: 'none', transition: 'all 0.2s' }}>
              <Activity size={18} /> Supplier Metrics
            </a>
            <a href="#" className="flex align-center gap-4" style={{ padding: '0.8rem 1rem', borderRadius: '10px', color: '#94a3b8', textDecoration: 'none', transition: 'all 0.2s' }}>
              <ShieldAlert size={18} /> CBAM Audits
            </a>
          </nav>
        </div>

        <div className="glass-panel" style={{ padding: '1rem', borderRadius: '12px' }}>
          <div className="flex align-center gap-2" style={{ fontSize: '0.85rem', color: '#94a3b8' }}>
            <Award size={16} color="#10b981" />
            <span>Kaggle × Google Capstone</span>
          </div>
        </div>
      </aside>

      {/* 2. Header Panel */}
      <header className="header flex justify-between align-center">
        <div>
          <h1 style={{ fontSize: '1.2rem', margin: 0, fontWeight: 600 }}>Supply Chain Decarbonization Intelligence</h1>
          <p style={{ fontSize: '0.8rem', color: '#94a3b8', margin: 0 }}>Federated Carbon Audits & CBAM Compliance Engine</p>
        </div>

        <div className="flex align-center gap-4">
          {uploadStatus && <span style={{ fontSize: '0.85rem', color: '#94a3b8' }}>{uploadStatus}</span>}
          <label className="flex align-center gap-2" style={{ background: '#10b981', color: '#000', padding: '0.6rem 1.2rem', borderRadius: '8px', cursor: 'pointer', fontWeight: 600, transition: 'all 0.2s' }}>
            <Upload size={18} />
            {uploading ? 'Processing...' : 'Upload Manifest'}
            <input type="file" accept=".csv" onChange={handleFileUpload} style={{ display: 'none' }} disabled={uploading} />
          </label>
        </div>
      </header>

      {/* 3. Main Dashboard Content */}
      <main className="main-content flex flex-col gap-4">
        
        {/* KPI Grid */}
        <div className="grid grid-cols-4 gap-4">
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Total Scope 3 Carbon</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-primary)', marginTop: '0.5rem' }}>
              {dashboard.total_emissions_tCO2.toLocaleString()} <span style={{ fontSize: '1rem' }}>tCO2</span>
            </div>
          </div>
          
          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>CBAM Tariff Liabilities</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-accent)', marginTop: '0.5rem' }}>
              €{dashboard.cbam_liabilities_eur.toLocaleString()}
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Top Supplier Emitter</span>
            <div style={{ fontSize: '1.1rem', fontWeight: 600, color: '#f87171', marginTop: '0.8rem', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
              {dashboard.top_emitting_supplier}
            </div>
          </div>

          <div className="glass-panel" style={{ padding: '1.5rem' }}>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>Compliance Ratio</span>
            <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--color-secondary)', marginTop: '0.5rem' }}>
              {(dashboard.compliant_ratio * 100).toFixed(1)}%
            </div>
          </div>
        </div>

        {/* Analytics Section */}
        <div className="grid grid-cols-2 gap-4" style={{ flexGrow: 1 }}>
          
          {/* Carbon Projections Line Chart */}
          <div className="glass-panel" style={{ padding: '1.5rem', display: 'flex', flexDirection: 'column' }}>
            <div className="flex justify-between align-center" style={{ marginBottom: '1rem' }}>
              <span style={{ fontWeight: 600, fontSize: '1rem' }}>Carbon Projections & Forecasting</span>
              <div className="flex align-center gap-2" style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                <TrendingUp size={14} color="var(--color-primary)" />
                <span>FastMCP Regression Model</span>
              </div>
            </div>
            <div style={{ position: 'relative', flexGrow: 1, minHeight: '260px' }}>
              <Line 
                data={chartData} 
                options={{
                  responsive: true,
                  maintainAspectRatio: false,
                  scales: {
                    y: { grid: { color: 'rgba(255, 255, 255, 0.05)' }, ticks: { color: '#94a3b8' } },
                    x: { grid: { display: false }, ticks: { color: '#94a3b8' } }
                  },
                  plugins: {
                    legend: { display: false }
                  }
                }} 
              />
            </div>
          </div>

          {/* Supplier Grid table */}
          <div className="glass-panel" style={{ padding: '1.5rem', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            <span style={{ fontWeight: 600, fontSize: '1rem', marginBottom: '1rem' }}>Supplier Audit Overview</span>
            <div style={{ overflowY: 'auto', flexGrow: 1 }}>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.9rem' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--bg-card-border)', textAlign: 'left', color: '#94a3b8' }}>
                    <th style={{ padding: '0.6rem 0' }}>Supplier Name</th>
                    <th>Country</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.02)' }}>
                    <td style={{ padding: '0.8rem 0', fontWeight: 500 }}>US Alloys Corp</td>
                    <td>US</td>
                    <td><span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', padding: '2px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>NON_COMPLIANT</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.02)' }}>
                    <td style={{ padding: '0.8rem 0', fontWeight: 500 }}>Acme Steel Co.</td>
                    <td>CN</td>
                    <td><span style={{ background: 'rgba(239, 68, 68, 0.15)', color: '#f87171', padding: '2px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>NON_COMPLIANT</span></td>
                  </tr>
                  <tr style={{ borderBottom: '1px solid rgba(255, 255, 255, 0.02)' }}>
                    <td style={{ padding: '0.8rem 0', fontWeight: 500 }}>Bengal Aluminum Ltd.</td>
                    <td>IN</td>
                    <td><span style={{ background: 'rgba(245, 158, 11, 0.15)', color: '#fbbf24', padding: '2px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>WARNING</span></td>
                  </tr>
                  <tr>
                    <td style={{ padding: '0.8rem 0', fontWeight: 500 }}>Euro Metalworks</td>
                    <td>DE</td>
                    <td><span style={{ background: 'rgba(16, 185, 129, 0.15)', color: '#34d399', padding: '2px 8px', borderRadius: '6px', fontSize: '0.75rem', fontWeight: 600 }}>COMPLIANT</span></td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

      </main>

      {/* 4. AIAssistant Chatbot Panel */}
      <aside className="chat-panel">
        <div className="flex align-center gap-2" style={{ padding: '1.2rem', borderBottom: '1px solid var(--bg-card-border)', background: 'rgba(10, 13, 22, 0.4)' }}>
          <MessageSquare size={18} color="#10b981" />
          <span style={{ fontWeight: 600 }}>EcoFlow Assistant</span>
        </div>

        <div style={{ flexGrow: 1, overflowY: 'auto', padding: '1rem', display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {chatMessages.map((msg, i) => (
            <div 
              key={i} 
              style={{
                alignSelf: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                background: msg.sender === 'user' ? '#10b981' : 'rgba(255, 255, 255, 0.05)',
                color: msg.sender === 'user' ? '#000' : '#e2e8f0',
                padding: '0.75rem 1rem',
                borderRadius: msg.sender === 'user' ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
                maxWidth: '85%',
                fontSize: '0.9rem',
                lineHeight: '1.4',
                whiteSpace: 'pre-line'
              }}
            >
              {msg.text}
            </div>
          ))}
          <div ref={chatEndRef} />
        </div>

        <form onSubmit={handleSendMessage} className="flex gap-2" style={{ padding: '1rem', borderTop: '1px solid var(--bg-card-border)', background: 'rgba(10, 13, 22, 0.4)' }}>
          <input 
            type="text" 
            value={chatInput} 
            onChange={(e) => setChatInput(e.target.value)} 
            placeholder="Ask EcoFlow..." 
            style={{
              flexGrow: 1,
              background: '#0d111d',
              border: '1px solid var(--bg-card-border)',
              borderRadius: '8px',
              padding: '0.6rem 1rem',
              color: '#fff',
              fontSize: '0.9rem',
              outline: 'none'
            }}
          />
          <button type="submit" style={{ display: 'flex', alignCenter: 'center', justifyContent: 'center', background: '#10b981', color: '#000', padding: '0.6rem' }}>
            <Send size={18} />
          </button>
        </form>
      </aside>

    </div>
  );
}

export default App;
