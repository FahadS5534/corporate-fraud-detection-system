import { useState, useEffect, useRef } from 'react';
import cytoscape from 'cytoscape';
import {
  ShieldAlert,
  Activity,
  Users,
  MapPin,
  FolderGit2,
  Search,
  Eye,
  CheckCircle2,
  RefreshCw,
  Network,
  Maximize2,
  TrendingUp,
  BookOpen,
  Scale
  ,ArrowLeft
  ,LogOut
} from 'lucide-react';
import {
  AreaChart,
  Area,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  BarChart,
  Bar,
  XAxis,
  YAxis
} from 'recharts';

const API_BASE = 'http://127.0.0.1:8000';

interface SummaryData {
  total_companies: number;
  total_directors: number;
  total_addresses: number;
  total_lenders: number;
  total_clusters: number;
  high_risk_clusters_count: number;
}

interface ClusterSummary {
  rank: number;
  cluster_id: number;
  cluster_name: string;
  company_names: string[];
  companies_count: number;
  directors_count: number;
  addresses_count: number;
  lenders_count: number;
  defaulters_count: number;
  average_company_risk: number;
  date_spread_days: number;
  network_density: number;
  cluster_risk_score: number;
  risk_category: string;
}

interface CompanyDetail {
  cin: string;
  name: string;
  incorporation_date: string;
  filing_status: string;
  paidup_capital: number;
  loans: any[];
  defaults: any[];
  scores: {
    address_risk: number;
    director_risk: number;
    temporal_risk: number;
    lender_risk: number;
    defaulter_risk: number;
    capital_filing_risk: number;
    composite_score: number;
  };
}

interface ClusterDetail {
  cluster_id: number;
  cluster_name?: string;
  companies_count: number;
  directors_count: number;
  addresses_count: number;
  lenders_count: number;
  defaulters_count: number;
  average_company_risk: number;
  date_spread_days: number;
  network_density: number;
  cluster_risk_score: number;
  risk_category: string;
  companies_detailed: CompanyDetail[];
  directors: string[];
  addresses: string[];
  lenders: string[];
}

interface EvidenceData {
  cin: string;
  name: string;
  composite_score: number;
  individual_scores: {
    address_risk: number;
    director_risk: number;
    temporal_risk: number;
    lender_risk: number;
    defaulter_risk: number;
    capital_filing_risk: number;
    composite_score: number;
  };
  raw_signals: any;
  evidence_trail: string[];
}



export default function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(() => sessionStorage.getItem('investigator_session') === 'active');
  const [investigatorName, setInvestigatorName] = useState(() => sessionStorage.getItem('investigator_name') || '');
  const [loginUsername, setLoginUsername] = useState('demo.investigator');
  const [loginPassword, setLoginPassword] = useState('SFIO_DEMO_2026');
  const [loginError, setLoginError] = useState('');
  const [loginLoading, setLoginLoading] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'rankings' | 'explorer'>('overview');
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [clusters, setClusters] = useState<ClusterSummary[]>([]);
  const [selectedClusterId, setSelectedClusterId] = useState<number | null>(null);
  const [clusterDetail, setClusterDetail] = useState<ClusterDetail | null>(null);
  const [selectedEntity, setSelectedEntity] = useState<any | null>(null);
  const [evidence, setEvidence] = useState<EvidenceData | null>(null);
  const [graphElements, setGraphElements] = useState<any>(null);

  const [searchQuery, setSearchQuery] = useState('');
  const [layoutType, setLayoutType] = useState('cose');
  const [loading, setLoading] = useState(false);

  const [viewMode, setViewMode] = useState<'graph' | 'map' | 'pyvis'>('pyvis');
  const cyRef = useRef<HTMLDivElement>(null);
  const cyInstance = useRef<any>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstance = useRef<any>(null);

  // Fetch summary and cluster list on startup
  useEffect(() => {
    if (!isAuthenticated) return;
    fetchSummary();
    fetchClusters();
  }, [isAuthenticated]);

  // Fetch detail when selectedClusterId changes
  useEffect(() => {
    if (isAuthenticated && selectedClusterId !== null) {
      fetchClusterDetail(selectedClusterId);
    }
  }, [isAuthenticated, selectedClusterId]);

  // Trigger graph rendering when switching tabs or when graph elements load
  useEffect(() => {
    if (activeTab === 'explorer' && viewMode === 'graph' && graphElements) {
      const timer = setTimeout(() => {
        initCytoscape(graphElements);
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [activeTab, viewMode, graphElements]);

  // Initialize/Update Leaflet Map
  useEffect(() => {
    if (activeTab === 'explorer' && viewMode === 'map' && graphElements) {
      const addressNodes = graphElements.filter((el: any) => el.data.type === 'address' && el.data.latitude && el.data.longitude);

      if (addressNodes.length === 0) return;

      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }

      if (!mapRef.current) return;

      const lats = addressNodes.map((n: any) => parseFloat(n.data.latitude));
      const lngs = addressNodes.map((n: any) => parseFloat(n.data.longitude));
      const avgLat = lats.reduce((a: number, b: number) => a + b, 0) / lats.length;
      const avgLng = lngs.reduce((a: number, b: number) => a + b, 0) / lngs.length;

      const L = (window as any).L;
      if (!L) return;

      const map = L.map(mapRef.current).setView([avgLat, avgLng], 12);
      mapInstance.current = map;

      L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
      }).addTo(map);

      addressNodes.forEach((node: any) => {
        const { latitude, longitude, id, raw_address } = node.data;

        const connectedCompanies = graphElements.filter((el: any) =>
          el.data.source === id || el.data.target === id
        ).map((el: any) => {
          const otherId = el.data.source === id ? el.data.target : el.data.source;
          const companyNode = graphElements.find((nodeEl: any) => nodeEl.data.id === otherId && nodeEl.data.type === 'company');
          return companyNode ? companyNode.data.label : null;
        }).filter(Boolean);

        const count = connectedCompanies.length;
        const color = count >= 3 ? '#DC2626' : count >= 2 ? '#D97706' : '#1E3B8A';

        const customIcon = L.divIcon({
          html: `<div style="background-color: ${color}; border: 2px solid white; border-radius: 50%; width: 24px; height: 24px; display: flex; align-items: center; justify-content: center; color: white; font-weight: bold; font-size: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.3);">${count}</div>`,
          className: 'custom-map-marker',
          iconSize: [24, 24],
          iconAnchor: [12, 12]
        });

        const popupContent = `
          <div style="font-family: Inter, sans-serif; font-size: 11px; padding: 4px; max-width: 220px;">
            <div style="font-weight: 800; color: #1E293B; margin-bottom: 4px; text-transform: uppercase; font-size: 9px; letter-spacing: 0.5px;">Address Coordinate</div>
            <div style="font-weight: 500; color: #475569; margin-bottom: 8px; line-height: 1.4;">${raw_address}</div>
            <div style="font-weight: 800; color: #0F172A; border-top: 1px solid #E2E8F0; padding-top: 6px; margin-bottom: 4px;">Registered Entities (${count}):</div>
            <ul style="margin: 0; padding: 0 0 0 12px; color: #1E3A8A; font-weight: 600; line-height: 1.5;">
              ${connectedCompanies.map((c: string) => `<li>${c}</li>`).join('')}
            </ul>
          </div>
        `;

        L.marker([parseFloat(latitude), parseFloat(longitude)], { icon: customIcon })
          .addTo(map)
          .bindPopup(popupContent);
      });
    }

    return () => {
      if (mapInstance.current) {
        mapInstance.current.remove();
        mapInstance.current = null;
      }
    };
  }, [activeTab, viewMode, graphElements]);

  const fetchSummary = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/dashboard/summary`);
      const data = await res.json();
      setSummary(data);
    } catch (e) {
      console.error("Failed to fetch dashboard summary", e);
    }
  };

  const fetchClusters = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/clusters`);
      const data = await res.json();
      setClusters(data);
      if (data.length > 0 && selectedClusterId === null) {
        setSelectedClusterId(data[0].cluster_id);
      }
    } catch (e) {
      console.error("Failed to fetch clusters list", e);
    }
  };

  const fetchClusterDetail = async (id: number) => {
    setLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/clusters/${id}`);
      const data = await res.json();
      setClusterDetail(data);
      setSelectedEntity(null);
      setEvidence(null);

      const graphRes = await fetch(`${API_BASE}/api/clusters/${id}/graph`);
      const graphData = await graphRes.json();
      setGraphElements(graphData);
    } catch (e) {
      console.error("Failed to load cluster details", e);
    } finally {
      setLoading(false);
    }
  };

  const fetchEvidence = async (cin: string) => {
    try {
      const res = await fetch(`${API_BASE}/api/companies/${cin}/evidence`);
      const data = await res.json();
      setEvidence(data);
    } catch (e) {
      console.error("Failed to fetch evidence details", e);
    }
  };

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoginLoading(true);
    setLoginError('');
    try {
      const response = await fetch(`${API_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: loginUsername, password: loginPassword })
      });
      if (!response.ok) {
        throw new Error('Invalid investigator credentials');
      }
      const data = await response.json();
      sessionStorage.setItem('investigator_session', 'active');
      sessionStorage.setItem('investigator_name', data.investigator.display_name);
      sessionStorage.setItem('investigator_token', data.token);
      setInvestigatorName(data.investigator.display_name);
      setIsAuthenticated(true);
    } catch (error) {
      setLoginError(error instanceof Error ? error.message : 'Unable to sign in');
    } finally {
      setLoginLoading(false);
    }
  };

  const handleLogout = () => {
    sessionStorage.removeItem('investigator_session');
    sessionStorage.removeItem('investigator_name');
    sessionStorage.removeItem('investigator_token');
    setIsAuthenticated(false);
    setActiveTab('overview');
  };

  const goBackToDashboard = () => {
    setActiveTab('overview');
    setSelectedEntity(null);
    setEvidence(null);
  };



  // Render Cytoscape.js Relationship Graph
  const initCytoscape = (elements: any) => {
    if (!cyRef.current) return;

    if (cyInstance.current) {
      cyInstance.current.destroy();
    }

    cyInstance.current = cytoscape({
      container: cyRef.current,
      elements: elements,
      style: [
        {
          selector: 'node',
          style: {
            'content': 'data(label)',
            'color': '#0F172A',
            'font-size': '9px',
            'font-family': 'Inter, sans-serif',
            'font-weight': '500',
            'text-valign': 'bottom',
            'text-margin-y': 4,
            'background-color': '#94A3B8',
            'width': '22px',
            'height': '22px',
            'transition-property': 'background-color, border-color, border-width, width, height',
            'transition-duration': '0.2s' as any,
            'text-wrap': 'wrap',
            'text-max-width': '75px'
          } as any
        },
        {
          selector: 'node[type="company"]',
          style: {
            'shape': 'hexagon',
            'background-color': '#1E3A8A',
            'border-width': '1.5px',
            'border-color': '#3B82F6',
            'width': '26px',
            'height': '26px',
            'color': '#1E3A8A',
            'font-weight': '600'
          } as any
        },
        {
          selector: 'node[type="director"]',
          style: {
            'shape': 'ellipse',
            'background-color': '#065F46',
            'border-width': '1.5px',
            'border-color': '#10B981',
            'width': '20px',
            'height': '20px',
            'color': '#065F46'
          } as any
        },
        {
          selector: 'node[type="address"]',
          style: {
            'shape': 'rectangle',
            'background-color': '#92400E',
            'border-width': '1.5px',
            'border-color': '#F59E0B',
            'width': '20px',
            'height': '20px',
            'color': '#92400E'
          } as any
        },
        {
          selector: 'node[type="lender"]',
          style: {
            'shape': 'triangle',
            'background-color': '#5B21B6',
            'border-width': '1.5px',
            'border-color': '#8B5CF6',
            'width': '22px',
            'height': '22px',
            'color': '#5B21B6'
          } as any
        },
        {
          selector: 'edge',
          style: {
            'width': 1.5,
            'line-color': '#94A3B8',
            'curve-style': 'bezier',
            'transition-property': 'line-color, width',
            'transition-duration': '0.2s' as any
          } as any
        },
        {
          selector: 'edge[relation="REGISTERED_AT"]',
          style: {
            'line-style': 'dashed',
            'line-color': '#CBD5E1'
          } as any
        },
        {
          selector: 'edge[relation="DIRECTOR_OF"]',
          style: {
            'line-style': 'solid',
            'line-color': '#64748B'
          } as any
        },
        {
          selector: 'edge[relation="LENDER_OF"]',
          style: {
            'line-style': 'solid',
            'line-color': '#C084FC'
          } as any
        },
        {
          selector: '.highlighted',
          style: {
            'background-color': '#BE123C',
            'border-color': '#FDA4AF',
            'line-color': '#BE123C',
            'width': '28px',
            'height': '28px',
            'font-weight': 'bold',
            'font-size': '10px',
            'color': '#9F1239'
          } as any
        },
        {
          selector: 'edge.highlighted',
          style: {
            'line-color': '#BE123C',
            'width': 3
          } as any
        },
        {
          selector: '.dimmed',
          style: {
            'opacity': 0.1
          } as any
        }
      ] as any,
      layout: {
        name: layoutType as any,
        animate: true,
        fit: true,
        padding: 25
      }
    });

    cyInstance.current.on('tap', 'node', (evt: any) => {
      const node = evt.target;
      const data = node.data();

      setSelectedEntity(data);

      if (data.type === 'company') {
        fetchEvidence(data.id);
      } else {
        setEvidence(null);
      }

      const cy = cyInstance.current;
      cy.elements().removeClass('highlighted').removeClass('dimmed');

      const neighbors = node.neighborhood();
      cy.elements().difference(node.union(neighbors)).addClass('dimmed');
      node.addClass('highlighted');
      neighbors.addClass('highlighted');
    });

    cyInstance.current.on('tap', (evt: any) => {
      if (evt.target === cyInstance.current) {
        cyInstance.current.elements().removeClass('highlighted').removeClass('dimmed');
        setSelectedEntity(null);
        setEvidence(null);
      }
    });
  };

  const changeLayout = (type: string) => {
    setLayoutType(type);
    if (cyInstance.current) {
      cyInstance.current.layout({
        name: type,
        animate: true,
        fit: true,
        padding: 25
      }).run();
    }
  };

  const recenterGraph = () => {
    if (cyInstance.current) {
      cyInstance.current.fit();
      cyInstance.current.center();
    }
  };

  const filteredClusters = clusters.filter(c => {
    const q = searchQuery.toLowerCase().trim();
    if (!q) return true;

    const matchesId = c.cluster_id.toString().includes(q);
    const matchesName = c.cluster_name?.toLowerCase().includes(q);
    const matchesCompany = c.company_names?.some(name => name.toLowerCase().includes(q));
    const matchesRisk = Math.round(c.cluster_risk_score).toString().includes(q);
    const matchesCount = c.companies_count.toString().includes(q);

    return matchesId || matchesName || matchesCompany || matchesRisk || matchesCount;
  });

  const riskDistributionData = clusters.reduce((acc: any[], curr) => {
    const score = curr.cluster_risk_score;
    let range = 'Low (<40)';
    if (score >= 75) range = 'High (>=75)';
    else if (score >= 40) range = 'Medium (40-74)';

    const existing = acc.find(item => item.name === range);
    if (existing) {
      existing.value += 1;
    } else {
      acc.push({ name: range, value: 1 });
    }
    return acc;
  }, []);

  const PIE_COLORS = ['#059669', '#D97706', '#DC2626', '#7C3AED'];

  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-slate-50 flex items-center justify-center p-6">
        <div className="w-full max-w-md glass-panel p-8 animate-fade-in">
          <div className="border-l-4 border-[#FF9933] pl-4 mb-8">
            <p className="text-[10px] font-bold text-slate-400 uppercase tracking-[0.2em]">Restricted Investigator Workspace</p>
            <h1 className="text-2xl font-extrabold text-[#183a6b] mt-2">Investigator Sign In</h1>
            <p className="text-xs text-slate-500 mt-2">MCA21 Risk Intelligence Portal</p>
          </div>
          <form onSubmit={handleLogin} className="space-y-4">
            <label className="block text-xs font-bold text-slate-600">
              Investigator ID
              <input value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} className="mt-1.5 w-full border border-slate-300 rounded-md px-3 py-2.5 text-sm font-normal text-slate-800 focus:outline-none focus:border-[#183a6b]" autoComplete="username" />
            </label>
            <label className="block text-xs font-bold text-slate-600">
              Access key
              <input type="password" value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} className="mt-1.5 w-full border border-slate-300 rounded-md px-3 py-2.5 text-sm font-normal text-slate-800 focus:outline-none focus:border-[#183a6b]" autoComplete="current-password" />
            </label>
            {loginError && <p className="text-xs font-semibold text-red-600" role="alert">{loginError}</p>}
            <button type="submit" disabled={loginLoading} className="w-full bg-[#183a6b] text-white rounded-md py-2.5 text-xs font-bold hover:bg-[#102d56] disabled:opacity-60">
              {loginLoading ? 'Authenticating...' : 'Sign in'}
            </button>
          </form>
          <div className="mt-6 pt-4 border-t border-slate-200 text-[10px] text-slate-500">
            Demo investigator: <span className="font-mono text-slate-700">demo.investigator</span> / <span className="font-mono text-slate-700">SFIO_DEMO_2026</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col min-h-screen bg-slate-50 text-slate-800">

      {/* Official Government Bilingual Banner */}
      <div className="h-1 w-full flex">
        <div className="h-full bg-[#FF9933] flex-1"></div>
        <div className="h-full bg-white flex-1"></div>
        <div className="h-full bg-[#138808] flex-1"></div>
      </div>
      <div className="bg-[#183a6b] text-slate-100 py-1.5 px-6 text-[10px] font-medium flex items-center justify-between border-b border-slate-900 tracking-wide">
        <div className="flex items-center space-x-4">
          <span>भारत सरकार • GOVERNMENT OF INDIA</span>
          <span className="text-slate-400">|</span>
          <span>कॉर्पोरेट कार्य मंत्रालय • MINISTRY OF CORPORATE AFFAIRS</span>
        </div>
        <div className="flex items-center space-x-3">
          <span className="opacity-90">SFIO Restricted Workspace</span>
          <span className="bg-red-900/80 text-red-100 border border-red-700/80 px-2 py-0.5 rounded-[4px] font-bold text-[9px] shadow-sm tracking-wider">SECURE SESSION</span>
          <span className="text-[10px] font-semibold text-slate-200">{investigatorName}</span>
          <button onClick={handleLogout} title="Sign out" className="text-slate-300 hover:text-white" aria-label="Sign out">
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Official Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between shadow-sm">
        <div className="flex items-center space-x-4">
          <div className="flex items-center justify-center">
            <img src="/mca-logo-screenshot.png" alt="MCA Logo" className="h-20 sm:h-24 md:h-28 w-auto min-w-[200px] object-contain" onError={(e) => {
              (e.target as HTMLImageElement).src = "https://upload.wikimedia.org/wikipedia/en/thumb/f/fa/Ministry_of_Corporate_Affairs.svg/120px-Ministry_of_Corporate_Affairs.svg.png";
            }} />
          </div>
          <div className="pl-2 border-l-2 border-slate-100">
            <div className="flex items-center space-x-2">
              <h1 className="text-xl font-extrabold text-[#183a6b] tracking-tight font-serif uppercase">
                MCA21 Risk Intelligence Portal
              </h1>
              <span className="text-slate-300 font-light hidden sm:inline">|</span>
              <span className="text-xs font-bold text-slate-600 uppercase tracking-widest bg-slate-50 border border-slate-200 px-2 py-0.5 rounded shadow-sm">MODULAR CLUSTERING</span>
            </div>
            <p className="text-[11.5px] text-slate-500 font-medium mt-1">Shell Syndicate Screening & Modularity Cluster Analytics Dashboard</p>
          </div>
        </div>

        {/* Tab Navigation (Flat Government Style) */}
        <nav className="flex space-x-1 bg-slate-100/80 p-1.5 rounded-lg border border-slate-200">
          {activeTab !== 'overview' && (
            <button onClick={goBackToDashboard} title="Back to dashboard" aria-label="Back to dashboard" className="px-2.5 py-2 text-xs font-semibold rounded-md text-slate-600 hover:bg-slate-200 flex items-center gap-1.5">
              <ArrowLeft className="w-3.5 h-3.5" /> Back
            </button>
          )}
          <button
            onClick={() => setActiveTab('overview')}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all flex items-center gap-1.5 ${activeTab === 'overview' ? 'bg-[#183a6b] text-white shadow-md' : 'text-slate-600 hover:bg-slate-200'}`}
          >
            <Activity className="w-3.5 h-3.5" /> Dashboard
          </button>
          <button
            onClick={() => setActiveTab('rankings')}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all flex items-center gap-1.5 ${activeTab === 'rankings' ? 'bg-[#183a6b] text-white shadow-md' : 'text-slate-600 hover:bg-slate-200'}`}
          >
            <TrendingUp className="w-3.5 h-3.5" /> Risk Rankings
          </button>
          <button
            onClick={() => setActiveTab('explorer')}
            className={`px-4 py-2 text-xs font-semibold rounded-md transition-all flex items-center gap-1.5 ${activeTab === 'explorer' ? 'bg-[#183a6b] text-white shadow-md' : 'text-slate-600 hover:bg-slate-200'}`}
          >
            <Network className="w-3.5 h-3.5" /> Network Workspace
          </button>

        </nav>
      </header>

      {/* Main Body */}
      <main className="flex-1 p-6 max-w-7xl mx-auto w-full flex flex-col gap-6">

        {/* TAB 1: OVERVIEW */}
        {activeTab === 'overview' && (
          <div className="flex flex-col gap-6 animate-fade-in">
            {/* KPI Cards Banner */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="glass-panel p-4 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Total Companies Ingested</p>
                  <h3 className="text-2xl font-bold text-slate-800 mt-1">{summary?.total_companies || 0}</h3>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-slate-600">
                  <FolderGit2 className="w-5 h-5" />
                </div>
              </div>

              <div className="glass-panel p-4 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Unique Directors Affiliated</p>
                  <h3 className="text-2xl font-bold text-slate-800 mt-1">{summary?.total_directors || 0}</h3>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-slate-600">
                  <Users className="w-5 h-5" />
                </div>
              </div>

              <div className="glass-panel p-4 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Registered Locations</p>
                  <h3 className="text-2xl font-bold text-slate-800 mt-1">{summary?.total_addresses || 0}</h3>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-slate-600">
                  <MapPin className="w-5 h-5" />
                </div>
              </div>

              <div className="glass-panel p-4 flex items-center justify-between">
                <div>
                  <p className="text-[10px] font-bold text-slate-400 uppercase tracking-wider">Active Lenders (CERSAI)</p>
                  <h3 className="text-2xl font-bold text-slate-800 mt-1">{summary?.total_lenders || 0}</h3>
                </div>
                <div className="bg-slate-50 p-2.5 rounded-lg border border-slate-200 text-slate-600">
                  <Scale className="w-5 h-5" />
                </div>
              </div>

              <div className="glass-panel p-4 flex items-center justify-between border-red-200 bg-red-50/50">
                <div>
                  <p className="text-[10px] font-bold text-red-600 uppercase tracking-wider">Critical Flagged Cases</p>
                  <h3 className="text-2xl font-bold text-red-700 mt-1">{summary?.high_risk_clusters_count || 0}</h3>
                </div>
                <div className="bg-red-100 p-2.5 rounded-lg border border-red-200 text-red-700">
                  <ShieldAlert className="w-5 h-5" />
                </div>
              </div>
            </div>

            {/* Charts Section */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <div className="glass-panel p-5 md:col-span-2 flex flex-col h-[320px]">
                <h4 className="text-xs font-bold text-slate-700 mb-4 uppercase tracking-wider">Risk Profile Distribution</h4>
                <div className="flex-1 w-full">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={clusters.slice(0, 15)}
                      margin={{ top: 10, right: 10, left: -20, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="colorRisk" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#1E3A8A" stopOpacity={0.2} />
                          <stop offset="95%" stopColor="#1E3A8A" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis dataKey="cluster_id" stroke="#64748B" style={{ fontSize: 9 }} />
                      <YAxis stroke="#64748B" style={{ fontSize: 9 }} />
                      <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: 8, fontSize: 11 }} />
                      <Area type="monotone" dataKey="cluster_risk_score" stroke="#1E3A8A" fillOpacity={1} fill="url(#colorRisk)" name="Modularity Risk Index" />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>

              <div className="glass-panel p-5 flex flex-col h-[320px]">
                <h4 className="text-xs font-bold text-slate-700 mb-4 uppercase tracking-wider">Cluster Risk Modularity</h4>
                <div className="flex-1 flex items-center justify-center relative">
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie
                        data={riskDistributionData}
                        cx="50%"
                        cy="50%"
                        innerRadius={60}
                        outerRadius={80}
                        paddingAngle={5}
                        dataKey="value"
                      >
                        {riskDistributionData.map((_, index) => (
                          <Cell key={`cell-${index}`} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                        ))}
                      </Pie>
                      <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#E2E8F0', borderRadius: 8, fontSize: 11 }} />
                    </PieChart>
                  </ResponsiveContainer>
                  <div className="absolute flex flex-col items-center justify-center">
                    <span className="text-2xl font-bold text-slate-800">{clusters.length}</span>
                    <span className="text-[9px] font-bold text-slate-400 uppercase">Communities</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-4 text-[9px] font-semibold">
                  {riskDistributionData.map((entry, index) => (
                    <div key={entry.name} className="flex items-center space-x-2">
                      <span className="w-2 h-2 rounded-full" style={{ backgroundColor: PIE_COLORS[index % PIE_COLORS.length] }}></span>
                      <span className="text-slate-500">{entry.name}: <b className="text-slate-800">{entry.value}</b></span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Official Directives Summary */}
            <div className="glass-panel p-5">
              <h4 className="text-xs font-bold text-slate-800 mb-3 flex items-center gap-2 uppercase tracking-wider">
                <BookOpen className="w-4 h-4 text-slate-600" /> MCA21 Shell Syndicate Detection Mandate
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4 text-[11px] text-slate-600 mt-2">
                <div className="bg-slate-50 p-3 rounded border border-slate-200 leading-relaxed">
                  <h5 className="font-bold text-slate-900 mb-1 flex items-center gap-1"><MapPin className="w-3.5 h-3.5 text-blue-600" /> Address Centrality</h5>
                  Cross-checks identical street coordinates. Correctly filters out shared CA office address coordinates by testing director board overlaps and registration timeline spacing.
                </div>
                <div className="bg-slate-50 p-3 rounded border border-slate-200 leading-relaxed">
                  <h5 className="font-bold text-slate-900 mb-1 flex items-center gap-1"><Users className="w-3.5 h-3.5 text-emerald-600" /> Dummy Boards</h5>
                  Tracks boarding counts per DIN. Dummy directors registered across multiple coordinate shell companies are immediately captured.
                </div>
                <div className="bg-slate-50 p-3 rounded border border-slate-200 leading-relaxed">
                  <h5 className="font-bold text-slate-900 mb-1 flex items-center gap-1"><Activity className="w-3.5 h-3.5 text-amber-600" /> Incorporation Bursts</h5>
                  Identifies windowed batch floatations. Shell company groups incorporated in batches within a 30-day window are flagged by network statistics.
                </div>
                <div className="bg-slate-50 p-3 rounded border border-slate-200 leading-relaxed">
                  <h5 className="font-bold text-slate-900 mb-1 flex items-center gap-1"><Scale className="w-3.5 h-3.5 text-purple-600" /> CERSAI & RBI Integration</h5>
                  Cross-checks credit registry security charges and RBI wilful defaulter lists to uncover financial round-tripping networks.
                </div>
              </div>
            </div>
          </div>
        )}

        {/* TAB 2: RANKINGS */}
        {activeTab === 'rankings' && (
          <div className="glass-panel p-6 flex flex-col gap-4 animate-fade-in">
            <div className="flex items-center justify-between border-b border-slate-100 pb-4">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Ranked Communities Modularity Listing</h3>
                <p className="text-[11px] text-slate-500">Louvain-partitioned corporate networks ranked by composite risk scores.</p>
              </div>
              <div className="relative">
                <Search className="w-3.5 h-3.5 text-slate-400 absolute left-3 top-1/2 -translate-y-1/2" />
                <input
                  type="text"
                  placeholder="Search by Company or Cluster Name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="bg-slate-50 border border-slate-300 rounded-md pl-8 pr-4 py-1.5 text-xs text-slate-700 focus:outline-none focus:border-slate-500 w-[240px]"
                />
              </div>
            </div>

            <div className="overflow-x-auto border border-slate-200 rounded-lg">
              <table>
                <thead>
                  <tr>
                    <th>Rank</th>
                    <th>Target Entity Group / Syndicate</th>
                    <th>Companies</th>
                    <th>Directors</th>
                    <th>Addresses</th>
                    <th>Lenders</th>
                    <th>Defaulters</th>
                    <th>Density</th>
                    <th>Avg Co. Risk</th>
                    <th>Modularity Risk score</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredClusters.map((c) => (
                    <tr key={c.cluster_id} className={c.cluster_risk_score >= 70 ? 'bg-red-50/30' : ''}>
                      <td className="font-bold text-slate-400">#{c.rank}</td>
                      <td>
                        <div className="font-bold text-slate-900 leading-tight">{c.cluster_name}</div>
                        <div className="text-[10px] text-slate-400 font-mono mt-0.5">Cluster ID: #{c.cluster_id}</div>
                      </td>
                      <td>{c.companies_count}</td>
                      <td>{c.directors_count}</td>
                      <td>{c.addresses_count}</td>
                      <td>{c.lenders_count}</td>
                      <td>{c.defaulters_count}</td>
                      <td>{(c.network_density * 100).toFixed(1)}%</td>
                      <td>{c.average_company_risk.toFixed(1)}</td>
                      <td>
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${c.cluster_risk_score >= 70 ? 'bg-red-50 text-red-700 border-red-200' :
                          c.cluster_risk_score >= 50 ? 'bg-amber-50 text-amber-700 border-amber-200' :
                            'bg-emerald-50 text-emerald-700 border-emerald-200'
                          }`}>
                          {c.cluster_risk_score.toFixed(1)}
                        </span>
                        <div className="text-[9px] text-slate-500 font-semibold mt-1">{c.risk_category}</div>
                      </td>
                      <td>
                        <button
                          onClick={() => {
                            setSelectedClusterId(c.cluster_id);
                            setActiveTab('explorer');
                          }}
                          className="bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 px-2.5 py-1 rounded text-[10px] font-bold transition-all flex items-center gap-1 shadow-xs"
                        >
                          <Eye className="w-3.5 h-3.5 text-slate-500" /> Investigate
                        </button>
                      </td>
                    </tr>
                  ))}
                  {filteredClusters.length === 0 && (
                    <tr>
                      <td colSpan={11} className="text-center text-slate-400 py-8 font-medium">No clusters matched search criteria.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* TAB 3: NETWORK WORKSPACE */}
        {activeTab === 'explorer' && (
          <div className="flex-1 grid grid-cols-1 lg:grid-cols-4 gap-6 min-h-[580px] animate-fade-in">
            {/* Left Column: Cluster directory */}
            <div className="glass-panel p-4 flex flex-col gap-4 max-h-[580px] overflow-y-auto">
              <div className="border-b border-slate-100 pb-3">
                <span className="text-[9px] font-bold text-slate-400 uppercase tracking-widest">Active Investigation Target</span>
                <div className="mt-1.5">
                  <select
                    value={selectedClusterId || ''}
                    onChange={(e) => setSelectedClusterId(Number(e.target.value))}
                    className="w-full bg-slate-50 border border-slate-300 rounded px-2 py-1.5 text-xs text-slate-800 font-bold focus:outline-none focus:border-slate-500"
                  >
                    {clusters.map((c) => (
                      <option key={c.cluster_id} value={c.cluster_id}>
                        Rank #{c.rank}: {c.cluster_name} (Risk: {c.cluster_risk_score.toFixed(0)})
                      </option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-2 mt-3 text-[10px] text-slate-500 bg-slate-50 p-2.5 rounded border border-slate-200 font-semibold">
                  <div>Companies: <span className="text-slate-800">{clusterDetail?.companies_count}</span></div>
                  <div>Directors: <span className="text-slate-800">{clusterDetail?.directors_count}</span></div>
                  <div>Locations: <span className="text-slate-800">{clusterDetail?.addresses_count}</span></div>
                  <div>Lenders: <span className="text-slate-800">{clusterDetail?.lenders_count}</span></div>
                  <div className="col-span-2 border-t border-slate-200 pt-1.5 mt-1">
                    Risk Score: <span className="text-red-600 font-bold">{clusterDetail?.cluster_risk_score.toFixed(1)}</span>
                  </div>
                </div>
              </div>

              <div className="flex-1 flex flex-col gap-2 min-h-0">
                <h4 className="text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1.5">Registered Entities</h4>
                <div className="flex-1 overflow-y-auto space-y-1.5 pr-1 text-[11px]">
                  {clusterDetail?.companies_detailed.map((c) => (
                    <div
                      key={c.cin}
                      onClick={() => {
                        setSelectedEntity({ id: c.cin, type: 'company', label: c.name });
                        fetchEvidence(c.cin);
                        if (viewMode === 'graph' && cyInstance.current) {
                          const node = cyInstance.current.getElementById(c.cin);
                          if (node.length > 0) {
                            cyInstance.current.elements().removeClass('highlighted').removeClass('dimmed');
                            const neighbors = node.neighborhood();
                            cyInstance.current.elements().difference(node.union(neighbors)).addClass('dimmed');
                            node.addClass('highlighted');
                            neighbors.addClass('highlighted');
                          }
                        }
                      }}
                      className={`p-2.5 rounded border cursor-pointer transition-all ${selectedEntity?.id === c.cin
                        ? 'bg-slate-100 border-slate-400 shadow-xs'
                        : 'bg-white border-slate-200 hover:border-slate-300'
                        }`}
                    >
                      <div className="font-bold text-slate-950 truncate">{c.name}</div>
                      <div className="text-[9px] text-slate-500 font-mono mt-0.5">{c.cin}</div>
                      <div className="flex items-center justify-between mt-2.5 text-[9px] font-semibold border-t border-slate-100 pt-1.5">
                        <span className="text-slate-400">Paid-up: ₹{(c.paidup_capital / 100000).toFixed(1)}L</span>
                        <span className={`px-1.5 py-0.5 rounded font-bold border ${c.scores.composite_score >= 75 ? 'bg-red-50 text-red-700 border-red-100' :
                          c.scores.composite_score >= 40 ? 'bg-amber-50 text-amber-700 border-amber-100' :
                            'bg-emerald-50 text-emerald-700 border-emerald-100'
                          }`}>
                          Score: {c.scores.composite_score.toFixed(0)}
                        </span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Center Column: Graph Canvas / Map / Pyvis iframe */}
            <div className="lg:col-span-2 glass-panel p-4 flex flex-col gap-3 min-h-[480px]">
              <div className="flex items-center justify-between border-b border-slate-100 pb-2">
                <div className="flex items-center space-x-2">
                  <div className="flex items-center bg-slate-100 rounded border border-slate-200 p-0.5">
                    <button
                      onClick={() => setViewMode('pyvis')}
                      className={`px-2.5 py-1 text-[10px] font-bold rounded transition-all flex items-center gap-1 ${viewMode === 'pyvis' ? 'bg-white text-slate-900 shadow-xs border border-slate-200' : 'text-slate-500 hover:text-slate-800'}`}
                    >
                      <Eye className="w-3.5 h-3.5 text-slate-500" /> Interactive Graph
                    </button>
                    <button
                      onClick={() => setViewMode('graph')}
                      className={`px-2.5 py-1 text-[10px] font-bold rounded transition-all flex items-center gap-1 ${viewMode === 'graph' ? 'bg-white text-slate-900 shadow-xs border border-slate-200' : 'text-slate-500 hover:text-slate-800'}`}
                    >
                      <Network className="w-3.5 h-3.5" /> Subgraph Canvas
                    </button>
                    <button
                      onClick={() => setViewMode('map')}
                      className={`px-2.5 py-1 text-[10px] font-bold rounded transition-all flex items-center gap-1 ${viewMode === 'map' ? 'bg-white text-slate-900 shadow-xs border border-slate-200' : 'text-slate-500 hover:text-slate-800'}`}
                    >
                      <MapPin className="w-3.5 h-3.5" /> Map View
                    </button>
                  </div>
                </div>

                {viewMode === 'graph' && (
                  <div className="flex space-x-1.5">
                    <button
                      onClick={recenterGraph}
                      title="Fit view"
                      className="p-1.5 rounded bg-white border border-slate-200 text-slate-600 hover:text-slate-900 transition-all hover:bg-slate-50 shadow-xs"
                    >
                      <Maximize2 className="w-3.5 h-3.5" />
                    </button>
                    <div className="flex items-center bg-slate-100 rounded border border-slate-200 p-0.5">
                      <button
                        onClick={() => changeLayout('cose')}
                        className={`px-2 py-0.5 text-[9px] font-bold rounded transition-all ${layoutType === 'cose' ? 'bg-white text-slate-900 shadow-xs border border-slate-200' : 'text-slate-500 hover:text-slate-800'}`}
                      >
                        COSE
                      </button>
                      <button
                        onClick={() => changeLayout('circle')}
                        className={`px-2 py-0.5 text-[9px] font-bold rounded transition-all ${layoutType === 'circle' ? 'bg-white text-slate-900 shadow-xs border border-slate-200' : 'text-slate-500 hover:text-slate-800'}`}
                      >
                        Circle
                      </button>
                    </div>
                  </div>
                )}

                {viewMode === 'pyvis' && (
                  <div className="flex items-center space-x-1.5">
                    <span className="text-[9px] font-extrabold text-slate-500 uppercase tracking-wide bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">VisJS Force Simulation</span>
                    <button
                      onClick={() => {
                        const iframe = document.querySelector('iframe[title="Interactive Corporate Network Graph"]');
                        if (iframe) {
                          if (iframe.requestFullscreen) {
                            iframe.requestFullscreen();
                          } else if ((iframe as any).webkitRequestFullscreen) {
                            (iframe as any).webkitRequestFullscreen();
                          }
                        }
                      }}
                      className="p-1 rounded bg-white border border-slate-200 text-slate-600 hover:text-slate-900 transition-all hover:bg-slate-50 shadow-xs flex items-center justify-center"
                      title="Make Graph Fullscreen"
                    >
                      <Maximize2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}
                {viewMode === 'map' && (
                  <span className="text-[9px] font-extrabold text-slate-500 uppercase tracking-wide bg-slate-50 border border-slate-200 px-2 py-0.5 rounded">Geographic Mapping</span>
                )}
              </div>

              {/* Display Canvas */}
              <div className="flex-1 bg-white rounded-lg relative border border-slate-200 overflow-hidden min-h-[420px]">
                {viewMode === 'pyvis' && (
                  <iframe
                    src={`${API_BASE}/static/pyvis_graph.html`}
                    className="w-full h-full min-h-[420px] border-0"
                    title="Interactive Corporate Network Graph"
                  />
                )}

                {viewMode === 'graph' && (
                  <>
                    {loading && (
                      <div className="absolute inset-0 bg-white/80 backdrop-blur-xs z-10 flex items-center justify-center space-x-2">
                        <RefreshCw className="w-5 h-5 text-slate-700 animate-spin" />
                        <span className="text-xs font-bold text-slate-500">Recalculating network coordinates...</span>
                      </div>
                    )}
                    <div ref={cyRef} className="w-full h-full min-h-[420px]" />

                    <div className="absolute bottom-3 left-3 bg-white/95 border border-slate-200 px-3 py-2 rounded-lg flex flex-col gap-1.5 text-[9px] font-semibold text-slate-500 pointer-events-none shadow-xs z-10 animate-fade-in">
                      <div className="flex items-center space-x-2">
                        <span className="w-3.5 h-3 bg-blue-900 border border-blue-700" style={{ clipPath: 'polygon(25% 0%, 75% 0%, 100% 50%, 75% 100%, 25% 100%, 0% 50%)' }}></span>
                        <span>Company (Hexagon)</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="w-3 h-3 rounded-full bg-emerald-800 border border-emerald-600"></span>
                        <span>Director (Circle)</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="w-3.5 h-3 bg-amber-900 border border-amber-700"></span>
                        <span>Address (Square)</span>
                      </div>
                      <div className="flex items-center space-x-2">
                        <span className="w-3.5 h-3 bg-purple-900 border border-purple-700" style={{ clipPath: 'polygon(50% 0%, 0% 100%, 100% 100%)' }}></span>
                        <span>Lender Bank (Triangle)</span>
                      </div>
                    </div>
                  </>
                )}

                {viewMode === 'map' && (
                  <>
                    <div className="absolute top-3 left-1/2 transform -translate-x-1/2 bg-amber-50/95 border border-amber-200 px-4 py-2 rounded-lg text-[10px] font-bold text-amber-800 flex items-center gap-1.5 shadow-md z-10 select-none pointer-events-none">
                      <ShieldAlert className="w-3.5 h-3.5 text-amber-600 animate-pulse" />
                      <span>Note: Geographical coordinates are hash-derived rough estimates for proximity intelligence.</span>
                    </div>
                    <div ref={mapRef} className="w-full h-full min-h-[420px]" style={{ zIndex: 1 }} />
                  </>
                )}
              </div>
            </div>

            {/* Right Column: Node details & compliance evidence logs */}
            <div className="glass-panel p-4 flex flex-col gap-4 max-h-[580px] overflow-y-auto">
              {!selectedEntity ? (
                <div className="flex-1 flex flex-col items-center justify-center text-center text-slate-400 px-4">
                  <Network className="w-8 h-8 text-slate-300 mb-3" />
                  <h5 className="font-bold text-xs text-slate-500">Inspector Panel</h5>
                  <p className="text-[10px] text-slate-400 mt-1.5 leading-relaxed">Select a company, director, or address node in the modularity graph to inspect compliance trails.</p>
                </div>
              ) : (
                <div className="flex-1 flex flex-col gap-4 animate-fade-in">
                  <div>
                    <span className={`px-2 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider border ${selectedEntity.type === 'company' ? 'bg-blue-50 text-blue-800 border-blue-200' :
                      selectedEntity.type === 'director' ? 'bg-emerald-50 text-emerald-800 border-emerald-200' :
                        selectedEntity.type === 'lender' ? 'bg-purple-50 text-purple-800 border-purple-200' :
                          'bg-amber-50 text-amber-800 border-amber-200'
                      }`}>
                      {selectedEntity.type}
                    </span>
                    <h3 className="text-sm font-bold text-slate-900 mt-2 break-words leading-tight">{selectedEntity.label}</h3>
                    <p className="text-[9px] text-slate-500 font-mono mt-0.5">{selectedEntity.id}</p>
                  </div>

                  {selectedEntity.type === 'company' && evidence && (
                    <div className="flex-1 flex flex-col gap-4">
                      {/* Gauge of risk */}
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg flex items-center justify-between font-semibold">
                        <div>
                          <p className="text-[10px] text-slate-500 uppercase">Composite Risk Score</p>
                          <h4 className="text-xl font-bold text-slate-900 mt-0.5">{evidence.composite_score.toFixed(1)} <span className="text-xs text-slate-400 font-normal">/ 100</span></h4>
                        </div>
                        <div className={`px-2 py-0.5 rounded text-[10px] font-bold border ${evidence.composite_score >= 75 ? 'bg-red-100 text-red-800 border-red-200' :
                          evidence.composite_score >= 40 ? 'bg-amber-100 text-amber-800 border-amber-200' :
                            'bg-emerald-100 text-emerald-800 border-emerald-200'
                          }`}>
                          {evidence.composite_score >= 75 ? 'HIGH RISK' : evidence.composite_score >= 40 ? 'MEDIUM RISK' : 'COMPLIANT'}
                        </div>
                      </div>

                      {/* Dynamic CERSAI & RBI details */}
                      {(() => {
                        const detailedComp = clusterDetail?.companies_detailed.find(c => c.cin === evidence.cin);
                        return (
                          <div className="flex flex-col gap-2">
                            {detailedComp?.defaults && detailedComp.defaults.length > 0 && (
                              <div className="bg-red-50 border border-red-200 p-3 rounded-lg text-[10.5px]">
                                <span className="text-[9.5px] text-red-700 uppercase font-extrabold block mb-1">RBI Wilful Defaulter Alert</span>
                                {detailedComp.defaults.map((d: any, idx: number) => (
                                  <div key={idx} className="border-b border-red-100 last:border-b-0 py-1 leading-relaxed">
                                    <div><b>Lender:</b> {d.lender_name}</div>
                                    <div><b>Default Amount:</b> ₹{(d.default_amount / 10000000).toFixed(2)} Cr</div>
                                    <div><b>Reason:</b> {d.wilful_default_reason}</div>
                                    {d.classification_date && <div><b>Date:</b> {d.classification_date}</div>}
                                  </div>
                                ))}
                              </div>
                            )}

                            {detailedComp?.loans && detailedComp.loans.length > 0 && (
                              <div className="bg-purple-50 border border-purple-200 p-3 rounded-lg text-[10.5px]">
                                <span className="text-[9.5px] text-purple-700 uppercase font-extrabold block mb-1">CERSAI Registered Loans</span>
                                {detailedComp.loans.map((l: any, idx: number) => (
                                  <div key={idx} className="border-b border-purple-100 last:border-b-0 py-1 leading-relaxed">
                                    <div><b>Lender:</b> {l.lender_name}</div>
                                    <div><b>Security Type:</b> {l.security_type}</div>
                                    <div><b>Asset:</b> {l.asset_description}</div>
                                    <div><b>Amount:</b> ₹{(l.charge_amount / 10000000).toFixed(2)} Cr</div>
                                    {l.charge_registration_date && <div><b>Date:</b> {l.charge_registration_date}</div>}
                                  </div>
                                ))}
                              </div>
                            )}
                          </div>
                        );
                      })()}

                      {/* Signals chart */}
                      <div className="h-[120px] w-full">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart
                            data={[
                              { name: 'Addr', score: evidence.individual_scores.address_risk },
                              { name: 'Dir', score: evidence.individual_scores.director_risk },
                              { name: 'Burst', score: evidence.individual_scores.temporal_risk },
                              { name: 'Lend', score: evidence.individual_scores.lender_risk },
                              { name: 'Def', score: evidence.individual_scores.defaulter_risk }
                            ]}
                            margin={{ top: 5, right: 5, left: -35, bottom: 0 }}
                          >
                            <CartesianGrid strokeDasharray="3 3" stroke="#F1F5F9" />
                            <XAxis dataKey="name" stroke="#64748B" style={{ fontSize: 9 }} />
                            <YAxis domain={[0, 100]} stroke="#64748B" style={{ fontSize: 9 }} />
                            <Tooltip contentStyle={{ backgroundColor: '#FFFFFF', borderColor: '#CBD5E1', fontSize: 10 }} />
                            <Bar dataKey="score" fill="#1E3A8A" radius={[2, 2, 0, 0]} />
                          </BarChart>
                        </ResponsiveContainer>
                      </div>

                      {/* Evidence Logs */}
                      <div className="flex-1 flex flex-col gap-2 min-h-0">
                        <h4 className="text-[10px] font-bold text-slate-700 uppercase tracking-wider border-b border-slate-100 pb-1.5 flex items-center gap-1">
                          <CheckCircle2 className="w-3.5 h-3.5 text-slate-600" /> Evidence Audit Trail
                        </h4>
                        <div className="flex-1 overflow-y-auto space-y-2 pr-1 text-[10.5px]">
                          {evidence.evidence_trail.map((log, index) => (
                            <div
                              key={index}
                              className={`p-2.5 rounded border leading-relaxed ${log.includes('Risk Score') && !log.includes('Risk Score: 0')
                                ? 'bg-red-50/50 border-red-200 text-red-950 font-medium'
                                : 'bg-slate-50 border-slate-200 text-slate-600'
                                }`}
                            >
                              {log}
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'director' && (
                    <div className="space-y-3 text-[11px] text-slate-600 leading-relaxed">
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                        <span className="text-[9px] text-slate-400 uppercase font-bold block">Board Directorships Count</span>
                        <span className="text-lg font-bold text-slate-900 mt-1 block">Concurrently Active</span>
                      </div>
                      <div>
                        Tracks multi-company registration overlaps. Multiple coordinates indicate potential dummy director affiliations holding board seats across coordinate tax mills.
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'address' && (
                    <div className="space-y-3 text-[11px] text-slate-600 leading-relaxed">
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                        <span className="text-[9px] text-slate-400 uppercase font-bold block">Registered Coordinate Load</span>
                        <span className="text-lg font-bold text-slate-900 mt-1 block">Shared Office Hub</span>
                      </div>
                      <div>
                        Registered address coordinate clusters highlight potential shell-company locations operating from duplicate desk space.
                      </div>
                    </div>
                  )}

                  {selectedEntity.type === 'lender' && (
                    <div className="space-y-3 text-[11px] text-slate-600 leading-relaxed">
                      <div className="bg-slate-50 border border-slate-200 p-3 rounded-lg">
                        <span className="text-[9px] text-slate-400 uppercase font-bold block">Lender Credit Institution</span>
                        <span className="text-lg font-bold text-slate-950 mt-1 block">CERSAI Securitised Bank</span>
                      </div>
                      <div>
                        Shared lender registries help identify cooperative or multi-state bank siphoning rings, where all connected shell corporations borrow from the same branch coordinates.
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}


      </main>

      {/* Footer */}
      <footer className="mt-auto flex flex-col w-full z-10 relative">
        {/* Ministries Logos Strip */}
        <div className="bg-white py-1 md:py-2 w-full flex justify-center border-t border-slate-200 shadow-sm">
          <div className="w-full flex justify-center items-center">
            <img src="/ministries-logos.png" alt="Ministries Logos" className="w-[100%] max-w-full h-auto object-contain" />
          </div>
        </div>

        {/* Nav Links Band */}
        <div className="bg-[#005e8d] py-3 text-white text-[13px] font-semibold flex flex-wrap justify-center items-center gap-x-6 gap-y-2 px-4 tracking-wide shadow-inner border-t-[1px] border-[#074769]">
          <a href="#" className="hover:underline">About</a>
          <span className="text-blue-300 hidden sm:inline">|</span>
          <a href="#" className="hover:underline">Policies</a>
          <span className="text-blue-300 hidden sm:inline">|</span>
          <a href="#" className="hover:underline">Links</a>
          <span className="text-blue-300 hidden sm:inline">|</span>
          <a href="#" className="hover:underline">Trademark's Portal</a>
        </div>

        {/* Dark Footer Bottom */}
        <div className="bg-[#051e3e] py-8 text-white px-8 flex justify-center w-full relative">
          <div className="max-w-6xl w-full flex flex-col md:flex-row justify-between items-center md:items-start md:pr-8">
            <div className="flex-1 flex flex-col items-center text-center space-y-3.5 pr-0 md:pr-12 md:border-r border-[#193d62]">
              <p className="text-[12px] tracking-wide text-slate-100">© Copyright <span className="font-extrabold text-white">Ministry of Corporate Affairs</span>, Government of India. All Rights Reserved.</p>
              <p className="text-[12px] tracking-wide text-slate-100">This site is best viewed at a screen resolution of 1366x768 using the latest versions of Chrome, Firefox, Safari, or Microsoft Edge.</p>
              <a href="#" className="text-[12px] hover:underline underline-offset-4 tracking-wide text-white">Disclaimer</a>
              <p className="text-[12px] mt-2 text-slate-100 tracking-wide pt-1">Last Updated: 14 August, 2026</p>
            </div>

            <div className="flex flex-col items-center md:items-start justify-start md:pl-12 mt-8 md:mt-1 min-w-[200px]">
              <span className="text-[12px] font-bold mb-4 tracking-wider">Follow us:</span>
              <div className="flex space-x-3">
                <div className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-[#051e3e] cursor-pointer hover:bg-slate-200 transition">
                  <span className="font-bold text-[13px] translate-y-[-1px]">𝕏</span>
                </div>
                <div className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-[#051e3e] cursor-pointer hover:bg-slate-200 transition font-serif font-bold text-md">f</div>
                <div className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-[#051e3e] cursor-pointer hover:bg-slate-200 transition text-[9px] font-black">▶</div>
                <div className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-[#051e3e] cursor-pointer hover:bg-slate-200 transition text-[10px] font-black">ig</div>
                <div className="w-7 h-7 bg-white rounded-full flex items-center justify-center text-[#051e3e] cursor-pointer hover:bg-slate-200 transition font-bold text-[10px]">in</div>
              </div>
            </div>
          </div>

          <button
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="absolute right-4 md:right-8 -top-5 bg-[#e86c00] rounded-full w-[42px] h-[42px] flex items-center justify-center shadow-lg hover:bg-[#c95d00] transition group border border-white/20"
          >
            <span className="text-white text-xl -translate-y-[-1px] font-mono group-hover:-translate-y-[2px] transition-transform">↑</span>
          </button>
        </div>
      </footer>
    </div>
  );
}
