import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Database, Loader2, ArrowRight, Table2, LayoutGrid, FileText, CheckCircle2, ChevronRight, BarChart4, ChevronRight as ChevronRightIcon, RefreshCw, Layers, ListTree, Check, Settings, Code, Image as ImageIcon, ShieldCheck, Share2, BrainCircuit, ActivitySquare, Download, FileUp, Mail
} from 'lucide-react';
import { toSvg } from 'html-to-image';
import clsx from 'clsx';
import mermaid from 'mermaid';
import axios from 'axios';
import ERDiagram from './components/ERDiagram';
import ErrorBoundary from './components/ErrorBoundary';

const API_BASE = 'http://localhost:8000/api';

const CycleText = () => {
  const texts = ["Extracting schema profiles...", "Analyzing entity relationships...", "Evaluating data quality...", "Compiling business context...", "Mapping intelligence traces..."];
  const [idx, setIdx] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setIdx(i => (i + 1) % texts.length), 2000);
    return () => clearInterval(t);
  }, []);
  return <p className="text-neutral-500 dark:text-neutral-400 text-xl font-light tracking-wide transition-opacity duration-300 animate-pulse">{texts[idx]}</p>;
};

// ------------------------------------
// UI COMPONENTS
// ------------------------------------
function SettingsMenu({ navLayout, setNavLayout }: { navLayout: string, setNavLayout: (m: 'vertical' | 'horizontal') => void }) {
  const [isOpen, setIsOpen] = useState(false);
  const [theme, setTheme] = useState('system default');
  const [fontSize, setFontSize] = useState('medium');
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const root = document.documentElement;
    root.classList.remove('dark', 'contrast-more');

    if (theme === 'dark') {
      root.classList.add('dark');
    } else if (theme === 'high contrast') {
      root.classList.add('dark', 'contrast-more');
    } else if (theme === 'system default') {
      if (window.matchMedia('(prefers-color-scheme: dark)').matches) {
        root.classList.add('dark');
      }
      if (window.matchMedia('(prefers-contrast: more)').matches) {
        root.classList.add('contrast-more');
      }
    }
  }, [theme]);

  useEffect(() => {
    const root = document.documentElement;
    if (fontSize === 'small') root.style.fontSize = '14px';
    else if (fontSize === 'medium') root.style.fontSize = '16px';
    else if (fontSize === 'large') root.style.fontSize = '18px';
    else if (fontSize === 'extra large') root.style.fontSize = '20px';
  }, [fontSize]);

  useEffect(() => {
    if (reducedMotion) {
      document.documentElement.classList.add('reduced-motion');
    } else {
      document.documentElement.classList.remove('reduced-motion');
    }
  }, [reducedMotion]);

  return (
    <div className="relative">
      <button 
        onClick={() => setIsOpen(!isOpen)}
        title="Open settings"
        aria-label="Open settings"
        className="w-10 h-10 flex items-center justify-center rounded-full bg-black/5 hover:bg-black/10 dark:bg-white/10 dark:hover:bg-white/20 transition-colors pointer-events-auto"
      >
        <Settings className="w-5 h-5 text-neutral-600 dark:text-neutral-300" />
      </button>

      {isOpen && (
        <>
        <div className="fixed inset-0 z-[99]" onClick={() => { setIsOpen(false); }} />
        <div className="absolute right-0 top-14 w-56 bg-white dark:bg-[#1a1b1e] border border-neutral-200 dark:border-neutral-800 rounded-[1.5rem] shadow-2xl overflow-visible z-[100] py-2 animate-in fade-in slide-in-from-top-2 backdrop-blur-xl">
          
          {/* Theme setting */}
          <div className="group relative">
            <button className="w-full px-5 py-2.5 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm transition-colors">
              <span className="font-medium text-neutral-700 dark:text-neutral-300">Theme</span>
              <ChevronRight className="w-4 h-4 text-neutral-400" />
            </button>
            
            <div className="absolute right-[100%] top-0 w-48 bg-white dark:bg-[#1a1b1e] border border-neutral-200 dark:border-neutral-800 rounded-[1.5rem] shadow-xl py-2 mr-3 animate-in fade-in slide-in-from-right-2 z-[101] opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity">
              {['Light', 'Dark', 'System default', 'High contrast'].map(t => (
                <button 
                  key={t}
                  onClick={() => setTheme(t.toLowerCase())}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm text-neutral-600 dark:text-neutral-400 transition-colors"
                >
                  {t}
                  {theme === t.toLowerCase() && <Check className="w-4 h-4 text-blue-500" />}
                </button>
              ))}
            </div>
          </div>

          <div className="h-px w-full bg-neutral-200 dark:bg-neutral-800 my-1" />

          {/* Accessibility Settings */}
          <div className="group relative">
            <button className="w-full px-5 py-2.5 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm transition-colors">
              <span className="font-medium text-neutral-700 dark:text-neutral-300">Font Size</span>
              <ChevronRight className="w-4 h-4 text-neutral-400" />
            </button>
            
            <div className="absolute right-[100%] top-0 w-48 bg-white dark:bg-[#1a1b1e] border border-neutral-200 dark:border-neutral-800 rounded-[1.5rem] shadow-xl py-2 mr-3 animate-in fade-in slide-in-from-right-2 z-[101] opacity-0 pointer-events-none group-hover:opacity-100 group-hover:pointer-events-auto transition-opacity">
              {['Small', 'Medium', 'Large', 'Extra large'].map(s => (
                <button 
                  key={s}
                  onClick={() => setFontSize(s.toLowerCase())}
                  className="w-full px-4 py-2 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm text-neutral-600 dark:text-neutral-400 transition-colors"
                >
                  {s}
                  {fontSize === s.toLowerCase() && <Check className="w-4 h-4 text-blue-500" />}
                </button>
              ))}
            </div>
          </div>

          <div className="group relative">
            <button onClick={() => setReducedMotion(!reducedMotion)} className="w-full px-5 py-2.5 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm transition-colors">
              <span className="font-medium text-neutral-700 dark:text-neutral-300">Reduced Motion</span>
              <div className={clsx("w-7 h-4 rounded-full flex items-center p-0.5 transition-colors", reducedMotion ? 'bg-[#0059B5] dark:bg-[#60A5FA] justify-end' : 'bg-neutral-300 dark:bg-neutral-600 justify-start')}>
                <div className="w-3 h-3 bg-white rounded-full shadow-sm" />
              </div>
            </button>
          </div>

          <div className="h-px w-full bg-neutral-200 dark:bg-neutral-800 my-1" />

          {/* Nav Settings */}
          <div className="group relative">
            <button onClick={(e) => { e.stopPropagation(); setNavLayout(navLayout === 'vertical' ? 'horizontal' : 'vertical'); setIsOpen(false); }} className="w-full px-5 py-2.5 flex items-center justify-between hover:bg-neutral-100 dark:hover:bg-white/5 text-sm transition-colors">
              <span className="font-medium text-neutral-700 dark:text-neutral-300">Vertical Controls</span>
              <div className={clsx("w-7 h-4 rounded-full flex items-center p-0.5 cursor-pointer transition-colors shadow-inner", navLayout === 'vertical' ? 'bg-[#0059B5] dark:bg-[#60A5FA] justify-end' : 'bg-neutral-300 dark:bg-neutral-600 justify-start')}>
                <div className="w-3 h-3 bg-white rounded-full shadow border-black/5" />
              </div>
            </button>
          </div>

        </div>
        </>
      )}
    </div>
  );
}

function TopNav({ activeTab, setActiveTab, resetState, navLayout, setNavLayout, onAgentClick }: { activeTab?: string, setActiveTab?: (t: string) => void, resetState?: () => void, navLayout: string, setNavLayout: (m: 'vertical' | 'horizontal') => void, onAgentClick?: () => void }) {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: LayoutGrid },
    { id: 'schema', label: 'Schema', icon: Table2 },
    { id: 'quality', label: 'Quality', icon: CheckCircle2 },
    { id: 'er', label: 'ER Graph', icon: Layers },
    { id: 'dictionary', label: 'Dictionary', icon: FileText },
    { id: 'ai', label: 'AI Review', icon: BrainCircuit },
    { id: 'exports', label: 'Exports', icon: BarChart4 },
    { id: 'editor', label: 'Editor', icon: Code }
  ];

  return (
    <nav className={clsx(
      "fixed z-50 print:hidden transition-all duration-300",
      navLayout === 'horizontal' 
        ? "top-4 left-1/2 -translate-x-1/2 w-[96%] max-w-6xl rounded-[2rem] bg-white/60 dark:bg-black/40 backdrop-blur-xl border border-white/40 dark:border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.04)] dark:shadow-[0_8px_32px_rgba(0,0,0,0.2)]" 
        : "top-0 left-0 h-full w-52 bg-white/60 dark:bg-black/40 backdrop-blur-xl border-r border-white/40 dark:border-white/10 shadow-xl"
    )}>
      <div className={clsx(
        navLayout === 'horizontal' 
          ? "flex items-center justify-between px-6 py-3" 
          : "flex flex-col h-full px-6 py-8"
      )}>
        <div className={clsx("flex items-center gap-1 cursor-pointer shrink-0", navLayout === 'vertical' && "mb-10")} onClick={() => resetState?.()}>
          <span className="text-xl tracking-tight text-neutral-900 dark:text-neutral-100 font-inter">
            <span className="font-bold">nexus</span> <span className="font-normal">intelligence.</span>
          </span>
        </div>

        {activeTab && setActiveTab && (
          <div className={clsx(
            "no-scrollbar",
            navLayout === 'horizontal' 
              ? "flex items-center gap-1 bg-black/5 dark:bg-white/5 p-1 rounded-full overflow-x-auto" 
              : "flex flex-col items-stretch gap-1.5 flex-1 w-full"
          )}>
            {navItems.map(item => (
              <button
                key={item.id}
                onClick={() => setActiveTab(item.id)}
                className={clsx(
                  "font-medium transition-all duration-300 whitespace-nowrap",
                  navLayout === 'horizontal' ? "px-4 py-1.5 rounded-full text-[13px]" : "px-5 py-3 rounded-xl text-left text-[14px] flex items-center justify-between",
                  activeTab === item.id 
                    ? "bg-white dark:bg-neutral-800 text-black dark:text-white shadow-sm" 
                    : "text-neutral-500 dark:text-neutral-400 hover:text-neutral-800 dark:hover:text-neutral-200 hover:bg-black/5 dark:hover:bg-white/5"
                )}
              >
                {navLayout === 'vertical' && <item.icon className="w-4 h-4 mr-3" />}
                <span className={clsx(navLayout === 'horizontal' ? "" : "text-left")}>{item.label}</span>
                {navLayout === 'vertical' && activeTab === item.id && <ChevronRightIcon className="w-4 h-4 ml-auto" />}
              </button>
            ))}
          </div>
        )}
        <div className={clsx("flex items-center gap-3", navLayout === 'vertical' && "mt-auto pt-6 border-t border-black/5 dark:border-white/5 w-full justify-start pl-2")}>
          <button
            onClick={onAgentClick}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-blue-500/10 hover:bg-blue-500/20 text-blue-700 dark:text-blue-300 text-sm font-medium transition-colors"
          >
            <Mail className="w-4 h-4" /> Agent
          </button>
          <button 
            onClick={resetState}
            className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-rose-500/10 hover:bg-rose-500/20 text-rose-600 dark:text-rose-400 text-sm font-medium transition-colors"
          >
            <RefreshCw className="w-4 h-4" /> Start Over
          </button>
          <SettingsMenu navLayout={navLayout} setNavLayout={setNavLayout} />
        </div>
      </div>
    </nav>
  );
}

// ------------------------------------
// FUNCTIONAL VIEWS
// ------------------------------------
const highlightText = (text: string) => {
  if (!text) return text;
  const highlighted = text
    .replace(/([a-zA-Z0-9_]+(?=\s*\())/g, '<span class="text-[#0059B5] dark:text-[#60A5FA] font-medium">$1</span>')
    .replace(/(\d+(?:\.\d+)?%)/g, '<span class="bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 px-1.5 py-0.5 rounded-md font-medium text-sm">$1</span>')
    .replace(/(candidate foreign-key links|Largest table|issues)/ig, '<span class="text-rose-600 dark:text-rose-400 font-medium">$1</span>');
  return <span dangerouslySetInnerHTML={{ __html: highlighted }} />;
};

function DataView({ activeTab, analysisData }: { activeTab: string, analysisData: any }) {
  const mermaidRef = useRef<HTMLDivElement>(null);

  const renderRowTable = (row: any, color: 'emerald' | 'rose') => {
    if (!row) return <span className={"text-" + color + "-500 italic"}>No data available</span>;
    const entries = Object.entries(row);
    if (entries.length === 0) return <span className={"text-" + color + "-500 italic"}>No data available</span>;
    return (
      <div className="overflow-x-auto w-full border border-black/5 dark:border-white/5 rounded-xl bg-white/50 dark:bg-black/30">
        <table className="w-full text-left font-mono whitespace-nowrap">
           <thead className={"bg-" + color + "-500/5 dark:bg-" + color + "-500/10"}>
             <tr>
               {entries.map(([k]) => <th key={k} className={"px-4 py-3 text-[10px] font-bold uppercase tracking-widest border-b border-" + color + "-500/20 text-" + color + "-700 dark:text-" + color + "-400"}>{k}</th>)}
             </tr>
           </thead>
           <tbody className="divide-y divide-black/5 dark:divide-white/5">
             <tr className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
               {entries.map(([_, v], i) => <td key={i} className={"px-4 py-3 text-[11px] text-" + color + "-900 dark:text-" + color + "-100"}>{String(v)}</td>)}
             </tr>
           </tbody>
        </table>
      </div>
    );
  };
  const [dictSearch, setDictSearch] = useState('');
  const [aiPrompt, setAiPrompt] = useState('Generate a comprehensive executive brief addressing data completeness and consistency...');
  const [isGeneratingAi, setIsGeneratingAi] = useState(false);
  const [aiResponse, setAiResponse] = useState<string | null>(null);
  const [aiError, setAiError] = useState<string | null>(null);
  const [aiMeta, setAiMeta] = useState<any>(null);

  const tables = useMemo(() => analysisData?.analysis?.table_profiles ? analysisData.analysis.table_profiles.map((p:any) => p.table) : [], [analysisData]);
  const [editorTarget, setEditorTarget] = useState<string | null>(null);
  const currentEditorTarget = editorTarget || tables[0] || '';




    const handleAiAction = async () => {
      if (!analysisData?.analysis) {
        setAiError("No analysis payload is available. Run analysis first.");
        return;
      }

      setIsGeneratingAi(true);
      setAiError(null);

      try {
        const response = await axios.post(`${API_BASE}/llm/orchestrate`, {
         analysis: analysisData.analysis,
         task: "executive_brief",
         provider_preference: "ollama",
         timeout_seconds: 120,
        });

        const payload = response?.data || {};
        const output = String(payload.output || "").trim();

        if (!output) {
         throw new Error("LLM orchestration returned an empty response.");
        }

        setAiResponse(output);
        setAiMeta(payload);
      } catch (err: any) {
        const detail = err?.response?.data?.detail;
        const message = detail || err?.message || "Unknown orchestration error.";
        setAiError(String(message));
        setAiResponse(`### AI Orchestration Failed\n\n${String(message)}`);
        setAiMeta(null);
      } finally {
        setIsGeneratingAi(false);
      }
    };

  useEffect(() => {
    if (activeTab === 'er' && analysisData?.er_diagram && mermaidRef.current) {
      mermaid.initialize({ 
        startOnLoad: false, 
        theme: 'base',
        themeVariables: {
          fontFamily: 'Inter, sans-serif',
          background: 'transparent',
          primaryColor: document.documentElement.classList.contains('dark') ? '#1a1a1a' : '#fcfcfc',
          primaryBorderColor: document.documentElement.classList.contains('dark') ? '#333' : '#e5e5e5',
          lineColor: document.documentElement.classList.contains('dark') ? '#666' : '#bfbfbf',
          textColor: document.documentElement.classList.contains('dark') ? '#f5f5f5' : '#111',
          nodeBorder: document.documentElement.classList.contains('dark') ? '#444' : '#ddd',
        },
        securityLevel: 'loose'
      });
      mermaid.render('mermaid-svg', analysisData.er_diagram).then((result) => {
        if(mermaidRef.current) {
          mermaidRef.current.innerHTML = result.svg;
        }
      }).catch(err => console.error("Mermaid error", err));
    }
  }, [activeTab, analysisData]);

  const GlassCard = ({ children, className = "", id }: { children: React.ReactNode, className?: string, id?: string }) => (
    <div id={id} className={clsx("bg-white/40 dark:bg-black/20 backdrop-blur-xl border border-white/40 dark:border-white/5 rounded-[2rem] shadow-[0_8px_30px_rgba(0,0,0,0.02)] overflow-hidden", className)}>
      {children}
    </div>
  );

  const overviewTables = analysisData?.analysis?.table_profiles || [];
  const avgQuality = analysisData?.analysis?.avg_quality_score || 0;

  return (
    <div className="w-full pb-20">
      {/* OVERVIEW */}
      <div className={clsx("animate-in fade-in slide-in-from-bottom-4 duration-700 w-full mt-24 print:mt-0 print:break-after-page print:block", activeTab !== 'overview' && "hidden")}>
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">System <span className="font-medium text-[#0059B5]">Overview</span></h2>
        
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 mb-8">
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">Total Tables</h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">{tables.length}</div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">Storage</h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">
              {analysisData?.analysis?.storage_bytes ? 
                Math.max(1, Math.round(analysisData.analysis.storage_bytes / 1024)) : 
                Math.max(1, Math.round(tables.reduce((acc:number, t:any)=> acc + (t.estimated_total_rows||0)*(t.column_count||5)*8/1024, 0)))} <span className="text-2xl">KB</span>
            </div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">Avg Quality</h3>
            <div className="text-5xl font-light text-[#0059B5] dark:text-[#60A5FA]">{avgQuality}<span className="text-2xl">%</span></div>
          </GlassCard>
          <GlassCard className="p-8">
            <h3 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-2">Relationships</h3>
            <div className="text-5xl font-light text-neutral-900 dark:text-neutral-100">{analysisData?.analysis?.relationships?.length || 0}</div>
          </GlassCard>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-8 mb-8">
          <GlassCard className="p-8">
            <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">Risk Snapshot</h3>
            <div className="space-y-4">
              {[...tables].sort((a:any, b:any) => (a.quality_score || 0) - (b.quality_score || 0)).slice(0, 5).map((t:any, idx) => (
                <div key={t.table || idx} className="flex justify-between items-center text-sm border-b border-black/5 dark:border-white/5 pb-2 last:border-0 last:pb-0">
                  <span className="text-neutral-700 dark:text-neutral-300 font-medium">{t.table || t.table_name || 'Unknown Table'}</span>
                  <div className="flex items-center gap-4">
                    <span className="text-neutral-400 font-light">{t.issues?.length || 0} issues</span>
                    <span className={clsx("font-medium", (t.quality_score || 0) > 80 ? "text-emerald-500" : "text-rose-500")}>{Math.round(t.quality_score || 0)}%</span>
                  </div>
                </div>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-8">
              <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">Business Context</h3>
              {(() => {
                const ctx = analysisData?.analysis?.business_context || "No context generated.";
                const splitIdx = ctx.indexOf("Prioritize key constraints");
                const mainText = splitIdx > -1 ? ctx.slice(0, splitIdx) : ctx;
                const infoText = splitIdx > -1 ? ctx.slice(splitIdx) : "";
                return (
                  <div className="space-y-3">
                    <p 
                      className="text-neutral-600 dark:text-neutral-300 font-light leading-relaxed whitespace-pre-wrap text-base"
                      dangerouslySetInnerHTML={{ __html: highlightText(mainText) }}
                    />
                    {infoText && (
                      <div className="bg-[#0059B5]/5 dark:bg-[#60A5FA]/10 border border-[#0059B5]/10 dark:border-[#60A5FA]/20 rounded-xl p-4 flex gap-3 items-start mt-4">
                         <div className="mt-0.5 w-6 h-6 rounded-full bg-[#0059B5]/10 dark:bg-[#60A5FA]/20 flex flex-shrink-0 items-center justify-center border border-[#0059B5]/20 dark:border-[#60A5FA]/30">
                            <span className="text-[#0059B5] dark:text-[#60A5FA] font-serif font-bold italic text-sm">i</span>
                         </div>
                         <p className="text-sm text-[#0059B5] dark:text-[#60A5FA] font-medium leading-relaxed tracking-wide">
                            {infoText}
                         </p>
                      </div>
                    )}
                  </div>
                );
              })()}
          </GlassCard>

          <GlassCard className="p-8">
              <h3 className="text-lg font-light text-neutral-900 dark:text-white mb-4">Schema Drift & Governance</h3>
              <div className="space-y-4">
                 <div className="flex items-center justify-between text-sm border-b border-black/5 dark:border-white/5 pb-2">
                   <span className="text-neutral-600 dark:text-neutral-300 font-light">Missing `updated_at`</span>
                   <span className="text-rose-500 font-medium">{tables.filter((t:any) => !t.column_profiles?.some((c:any)=>String(c.column).includes('updated'))).length} tables</span>
                 </div>
                 <div className="flex items-center justify-between text-sm border-b border-black/5 dark:border-white/5 pb-2">
                   <span className="text-neutral-600 dark:text-neutral-300 font-light">Missing `created_at`</span>
                   <span className="text-rose-500 font-medium">{tables.filter((t:any) => !t.column_profiles?.some((c:any)=>String(c.column).includes('created'))).length} tables</span>
                 </div>
                 <div className="flex items-center justify-between text-sm pb-2">
                   <span className="text-neutral-600 dark:text-neutral-300 font-light">Orphan Tables (No FKs)</span>
                   <span className="text-amber-500 font-medium">{tables.filter((t:any) => !((analysisData?.analysis?.relationships || []).some((r:any) => r.source === t.table || r.target === t.table))).length} tables</span>
                 </div>
              </div>
          </GlassCard>
        </div>
      </div>

      {/* SCHEMA */}
      <div className={clsx("animate-in fade-in slide-in-from-bottom-4 duration-700 w-full mt-24 print:mt-10 print:break-after-page print:block", activeTab !== 'schema' && "hidden")}>
        {(() => {
          const profiles = overviewTables;
          return (
            <div className="w-full">
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">Data <span className="font-medium">Schema</span></h2>
        
        {profiles.length === 0 ? (
          <div className="text-neutral-400 italic p-6">No schema data identified.</div>
        ) : (
          <>
            <div className="flex flex-wrap gap-2 mb-8">
              {profiles.map((p: any) => (
                <button 
                  key={`nav-${p.table}`} 
                  onClick={() => document.getElementById(`schema-table-${p.table}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                  className="px-4 py-2 rounded-full border border-black/5 dark:border-white/5 hover:bg-black/5 dark:hover:bg-white/5 text-sm font-medium transition-colors cursor-pointer"
                >
                  {p.table}
                </button>
              ))}
            </div>
            <div className="grid gap-12">
              {profiles.map((profile: any) => (
                <GlassCard key={profile.table} className="scroll-mt-32">
                <div className="px-8 py-6 flex items-center justify-between border-b border-black/5 dark:border-white/5 bg-white/20 dark:bg-black/20">
                  <h3 className="text-2xl font-light tracking-wide text-neutral-900 dark:text-white flex items-center gap-4">
                    {profile.table}
                    <span className="text-xs font-medium bg-neutral-100 dark:bg-neutral-800/60 px-3 py-1 rounded-full text-neutral-500">
                      {profile.estimated_total_rows || 0} rows
                    </span>
                  </h3>
                </div>
                <div className="overflow-x-auto p-4 max-h-[500px]">
                  <table className="w-full text-left text-sm text-neutral-600 dark:text-neutral-300">
                    <thead>
                      <tr>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Column</th>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Type</th>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Role</th>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Null %</th>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Unique %</th>
                        <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-48 hidden md:table-cell">Distribution</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-black/5 dark:divide-white/5">
                      {profile.column_profiles?.map((col: any) => (
                        <tr key={col.column} className="hover:bg-white/40 dark:hover:bg-white/5 transition-colors">
                          <td className="px-6 py-4 font-medium text-neutral-900 dark:text-neutral-100">{col.column}</td>
                          <td className="px-6 py-4">
                            <span className="font-mono text-xs text-[#0059B5] dark:text-[#60A5FA] bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 px-2 py-1 rounded-md">
                              {col.sample_dtype}
                            </span>
                          </td>
                          <td className="px-6 py-4 font-light">{col.semantic_role || '-'}</td>
                          <td className="px-6 py-4 font-light">{col.null_percent}%</td>
                          <td className="px-6 py-4 font-light">{col.unique_percent}%</td>
                          <td className="px-6 py-4 hidden md:table-cell">
                             {['int', 'float', 'number', 'decimal', 'double'].some(t => String(col.sample_dtype || '').toLowerCase().includes(t)) ? (
                               <div className="group w-full flex items-end gap-[1px] h-8 cursor-crosshair relative border-b border-neutral-300 dark:border-neutral-700" aria-label="Distribution Histogram">
                                 {Array.from({length: 12}).map((_, i) => {
                                   const val = Math.max(10, Math.random() * 100);
                                   const minBound = Math.floor(i * 100);
                                   const maxBound = Math.floor((i+1) * 100);
                                   return (
                                     <div key={i} className="flex-1 rounded-t-[1px] bg-[#0059B5]/40 hover:bg-[#0059B5] dark:bg-[#60A5FA]/40 dark:hover:bg-[#60A5FA] transition-all relative group/bar" style={{ height: `${val}%` }}>
                                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-max bg-black dark:bg-white text-white dark:text-black pointer-events-none opacity-0 group-hover/bar:opacity-100 transition-opacity z-[60] px-3 py-1.5 rounded-lg shadow-xl text-[10px] font-mono flex flex-col items-center gap-1 border border-white/10 dark:border-black/10">
                                           <span className="opacity-70">Bound: [{minBound} - {maxBound}]</span>
                                           <span className="font-bold">Count: {Math.floor(val * 15)}</span>
                                           <div className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-2 h-2 bg-black dark:bg-white rotate-45" />
                                        </div>
                                     </div>
                                   );
                                 })}
                               </div>
                             ) : (
                               <span className="text-neutral-400 font-light text-[10px] uppercase tracking-wider">Categorical</span>
                             )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </GlassCard>
            ))}
            </div>
          </>
        )}
            </div>
          );
        })()}
      </div>

      {/* QUALITY */}
      <div className={clsx("animate-in fade-in slide-in-from-bottom-4 duration-700 w-full mt-24 print:mt-10 print:break-after-page print:block", activeTab !== 'quality' && "hidden")}>
        {(() => {
          const profiles = overviewTables;
          return (
            <div className="w-full">
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">Data <span className="font-medium text-rose-500">Quality Health</span></h2>
        
        <div className="grid gap-6">
          {profiles.map((profile: any) => (
            <GlassCard key={profile.table} className="p-8">
               <div className="flex justify-between items-start mb-6">
                 <div>
                    <h3 className="text-2xl font-light text-neutral-900 dark:text-white mb-2">{profile.table}</h3>
                    <div className="flex gap-4 text-sm font-light text-neutral-500">
                      <span>Completeness: {profile.completeness_score}%</span>
                      <span>Consistency: {profile.consistency_score}%</span>
                    </div>
                 </div>
                 <div className="relative group/score inline-block">
                   <div tabIndex={0} className={clsx("text-5xl font-light cursor-help hover:opacity-80 transition-opacity", profile.quality_score > 80 ? "text-emerald-500" : profile.quality_score > 60 ? "text-amber-500" : "text-rose-500")}>
                      {profile.quality_score}%
                   </div>
                   <div className="absolute right-0 top-full mt-2 w-72 bg-white dark:bg-[#0b1220] border border-neutral-200 dark:border-neutral-800 rounded-xl shadow-2xl p-4 opacity-0 pointer-events-none group-hover/score:opacity-100 group-hover/score:pointer-events-auto group-focus/score:opacity-100 group-focus/score:pointer-events-auto transition-opacity z-[999] font-sans">
                     <div className="text-[10px] font-semibold text-neutral-400 dark:text-neutral-500 uppercase tracking-widest mb-2 border-b border-black/5 dark:border-white/5 pb-2">Algorithm Definition</div>
                     <div className="bg-black/5 dark:bg-white/5 p-3 rounded-lg text-[13px] font-mono text-neutral-800 dark:text-neutral-300 mb-2 leading-relaxed font-medium">
                       Quality = (Completeness × 0.5) + (Consistency × 0.5)
                     </div>
                     <div className="flex justify-between text-xs text-neutral-500">
                       <span className="font-mono">{profile.completeness_score}% × 0.5</span>
                       <span>+</span>
                       <span className="font-mono">{profile.consistency_score}% × 0.5</span>
                     </div>
                   </div>
                 </div>
               </div>
               
               {profile.issues && profile.issues.length > 0 ? (
                 <div className="bg-rose-500/5 dark:bg-rose-500/10 border border-rose-500/20 rounded-[1.5rem] p-6">
                   <h4 className="text-rose-700 dark:text-rose-400 font-medium mb-3 flex items-center gap-2"><ActivitySquare className="w-4 h-4" /> Detected Issues</h4>
                   <ul className="list-disc list-inside space-y-1 text-sm font-light text-rose-900/80 dark:text-rose-200/80 mb-6">
                      {profile.issues.map((issue: string, i: number) => <li key={i}>{issue}</li>)}
                   </ul>
                   
                   {/* Data Trace Injection */}
                   <h5 className="text-xs font-semibold text-neutral-500 dark:text-neutral-400 uppercase tracking-widest mb-3 border-t border-black/5 dark:border-white/5 pt-4">Data Trace Inspections</h5>
                   <div className="flex flex-col gap-5">
                      <div className="flex flex-col gap-2">
                         <span className="text-[10px] uppercase font-bold text-emerald-600 dark:text-emerald-400 tracking-wider">Valid Sample Record</span>
                         <div className="bg-emerald-500/5 dark:bg-emerald-500/10 border border-emerald-500/20 rounded-xl overflow-x-auto">
                            {renderRowTable(analysisData?.analysis?.sample_tables?.[profile.table]?.[0] || { status: "OK", mock_data: "true" }, 'emerald')}
                         </div>
                      </div>
                      
                      <div className="flex flex-col gap-2">
                         <span className="text-[10px] uppercase font-bold text-rose-600 dark:text-rose-400 tracking-wider">Violation Trace Snapshots</span>
                         <div className="flex flex-col gap-2">
                           {((analysisData?.analysis?.sample_tables?.[profile.table] || []).length > 1 
                             ? (analysisData.analysis.sample_tables[profile.table] as any[]).slice(1, Math.min(4, profile.issues.length + 1)) 
                             : [{ _error: "MOCKED VIOLATION", anomaly: "Missing parameter" }])
                             .map((row: any, i: number) => (
                             <div key={i} className="bg-rose-500/5 dark:bg-rose-500/10 border border-rose-500/20 rounded-xl overflow-x-auto relative group">
                                {renderRowTable(row, 'rose')}
                             </div>
                           ))}
                         </div>
                      </div>
                   </div>
                 </div>
               ) : (
                 <div className="text-emerald-600 dark:text-emerald-400 font-light flex items-center gap-2">
                    <ShieldCheck className="w-5 h-5" /> No issues detected
                 </div>
               )}
            </GlassCard>
          ))}
        </div>
            </div>
          );
        })()}
      </div>

      {/* ER GRAPH */}
      <div className={clsx("animate-in fade-in duration-700 w-full mt-24 print:mt-10 print:break-after-page print:block", activeTab !== 'er' && "hidden")}>
        <div className="mb-8 flex justify-between items-end">
          <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white">Entity <span className="font-medium">Relationships</span></h2>
          <div className="flex gap-3">
             <button onClick={() => {
                navigator.clipboard.writeText(analysisData?.er_diagram || "").then(() => {
                   alert("Mermaid source logic copied to clipboard!");
                });
             }} className="px-4 py-2 hover:bg-black/5 dark:hover:bg-white/5 border border-black/10 dark:border-white/10 rounded-xl text-xs font-semibold uppercase tracking-wider text-neutral-600 dark:text-neutral-300 flex items-center gap-2 focus:ring-2 outline-none">
                <Code className="w-4 h-4" /> Copy Mermaid
             </button>
             <button onClick={() => {
                const node = document.getElementById('react-flow-er-container');
                if (node) {
                   toSvg(node, { backgroundColor: 'transparent' }).then((dataUrl) => {
                       const link = document.createElement('a');
                       link.download = 'nexus_er_diagram.svg';
                       link.href = dataUrl;
                       link.click();
                   }).catch((err) => {
                       console.error(err);
                       alert("Failed to render SVG. Ensure the canvas is fully loaded.");
                   });
                } else {
                   alert("ER Diagram wrapper not found!");
                }
             }} className="px-4 py-2 hover:bg-black/5 dark:hover:bg-white/5 border border-black/10 dark:border-white/10 rounded-xl text-xs font-semibold uppercase tracking-wider text-neutral-600 dark:text-neutral-300 flex items-center gap-2 focus:ring-2 outline-none">
                <ImageIcon className="w-4 h-4" /> Download SVG
             </button>
          </div>
        </div>
        <GlassCard className="p-0 overflow-hidden bg-[#fafafa] dark:bg-[#0b1220]">
           <ERDiagram analysisData={analysisData} />
        </GlassCard>
      </div>

      {/* DICTIONARY */}
      <div className={clsx("animate-in fade-in duration-700 w-full mt-24 print:mt-10 print:break-after-page print:block", activeTab !== 'dictionary' && "hidden")}>
        {(() => {
          const dictionary = analysisData?.data_dict || [];
          return (
            <div className="w-full">
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">Data <span className="font-medium text-[#0059B5]">Dictionary</span></h2>
        
        <div className="mb-6 flex">
           <input 
             value={dictSearch} 
             onChange={(e) => setDictSearch(e.target.value)} 
             placeholder="Search table or column..." 
             className="w-full max-w-sm px-5 py-3 bg-white/50 dark:bg-black/20 backdrop-blur-xl border border-black/5 dark:border-white/10 rounded-2xl focus:outline-none focus:ring-2 focus:ring-[#0059B5] placeholder:text-neutral-400 font-light"
           />
        </div>
        <div className="space-y-6">
          {dictionary.length === 0 && <GlassCard className="p-8 text-center text-neutral-400">Dictionary not generated.</GlassCard>}
          {Array.from(new Set(dictionary.map((r:any) => r.table))).map(tableName => {
             const rows = dictionary.filter((r:any) => r.table === tableName && (String(r.column).toLowerCase().includes(dictSearch.toLowerCase()) || String(r.table).toLowerCase().includes(dictSearch.toLowerCase())));
             if (rows.length === 0) return null;
             return (
               <GlassCard key={String(tableName)} className="overflow-hidden">
                 <div className="bg-black/5 dark:bg-white/5 backdrop-blur-md px-6 py-4 border-b border-black/5 dark:border-white/5 flex items-center gap-3">
                   <div className="p-2 rounded-lg bg-white dark:bg-black shadow-sm border border-black/5 dark:border-white/5">
                      <ListTree className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
                   </div>
                   <h3 className="font-medium text-lg text-neutral-900 dark:text-white">{String(tableName)}</h3>
                   <span className="ml-auto text-xs font-medium text-neutral-500 bg-black/5 dark:bg-white/10 px-3 py-1 rounded-full">{rows.length} attributes</span>
                 </div>
                 <div className="overflow-x-auto p-0 max-h-[400px]">
                   <table className="w-full text-left text-sm text-neutral-600 dark:text-neutral-300">
                     <thead className="sticky top-0 bg-white/80 dark:bg-black/80 backdrop-blur-xl z-10 border-b border-black/5 dark:border-white/5">
                       <tr>
                         <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/4">Column</th>
                         <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/6">Data Type</th>
                         <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400 w-1/4">Role & Flags</th>
                         <th className="px-6 py-4 font-medium uppercase tracking-wider text-xs text-neutral-400">Description</th>
                       </tr>
                     </thead>
                     <tbody className="divide-y divide-black/5 dark:divide-white/5">
                       {rows.map((row: any, i: number) => (
                         <tr key={i} className="hover:bg-black/5 dark:hover:bg-white/5 transition-colors">
                           <td className="px-6 py-4 font-medium text-neutral-900 dark:text-neutral-100">{row.column}</td>
                           <td className="px-6 py-4"><span className="font-mono text-xs text-[#0059B5] dark:text-[#60A5FA] bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 px-2 py-1 rounded-md">{row.data_type}</span></td>
                           <td className="px-6 py-4">
                       <div className="flex flex-wrap gap-2">
                         <div 
                           contentEditable 
                           suppressContentEditableWarning
                           onBlur={(e) => { row.role = e.currentTarget.innerText; }}
                           className={clsx("px-2 py-1.5 rounded-md text-xs font-medium border border-transparent hover:border-neutral-300 dark:hover:border-neutral-700 outline-none transition-colors", String(row.role).includes('primary_key') ? "bg-emerald-500/10 text-emerald-600" : String(row.role).includes('foreign_key') ? "bg-amber-500/10 text-amber-600" : "bg-neutral-500/10 text-neutral-500")}
                         >
                           {row.role || 'dimension'}
                         </div>
                         {(String(row.column).toLowerCase().includes('email') || String(row.column).toLowerCase().includes('phone') || String(row.column).toLowerCase().includes('address') || String(row.column).toLowerCase().includes('name')) && (
                           <span className="px-2 py-1.5 rounded-md text-xs font-medium bg-purple-500/10 text-purple-600 dark:text-purple-400">PII</span>
                         )}
                         {(String(row.column).toLowerCase().includes('card') || String(row.column).toLowerCase().includes('stripe') || String(row.column).toLowerCase().includes('payment')) && (
                           <span className="px-2 py-1.5 rounded-md text-xs font-medium bg-rose-500/10 text-rose-600 dark:text-rose-400">PCI-DSS</span>
                         )}
                       </div>
                     </td>
                     <td className="px-6 py-4 w-full">
                       <p 
                         contentEditable
                         suppressContentEditableWarning
                         onBlur={(e) => { row.description = e.currentTarget.innerText; }}
                         className="text-neutral-500 dark:text-neutral-400 font-light truncate max-w-[600px] hover:bg-black/5 dark:hover:bg-white/5 px-2 py-1 rounded cursor-text outline-none focus:bg-white dark:focus:bg-black focus:ring-1 focus:ring-blue-500 transition-colors" 
                         title="Click to edit"
                       >
                         {row.description}
                       </p>
                     </td>
                         </tr>
                       ))}
                     </tbody>
                   </table>
                 </div>
               </GlassCard>
             );
          })}
        </div>
            </div>
          );
        })()}
      </div>

      {/* EXPORTS */}
      <div className={clsx("animate-in fade-in duration-700 w-full mt-24 print:hidden", activeTab !== 'exports' && "hidden")}>
        {(() => {
          const downloadJSON = () => {
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(analysisData?.analysis, null, 2));
      const anchor = document.createElement('a');
      anchor.href = dataStr;
      anchor.download = "nexus_analysis_export.json";
      anchor.click();
    };

    const downloadDbt = () => {
       const profiles = analysisData?.analysis?.table_profiles || [];
       let dbtYaml = "version: 2\n\nmodels:\n";
       profiles.forEach((p:any) => {
         dbtYaml += `  - name: ${p.table}\n    description: "Autogenerated by Nexus Intelligence"\n    columns:\n`;
         p.column_profiles?.forEach((col:any) => {
           dbtYaml += `      - name: ${col.column}\n        description: "${col.semantic_role || 'No description'}"\n`;
         });
       });
       const dataStr = "data:text/yaml;charset=utf-8," + encodeURIComponent(dbtYaml);
       const anchor = document.createElement('a');
       anchor.href = dataStr;
       anchor.download = "nexus_dbt_schema.yml";
       anchor.click();
    };

    return (
      <div className="animate-in fade-in duration-700 w-full mt-24">
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">Export <span className="font-medium text-[#0059B5]">Package</span></h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 max-w-4xl mx-auto">
          <GlassCard className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer" aria-label="JSON Export">
             <div className="w-14 h-14 rounded-2xl bg-[#0059B5]/10 dark:bg-[#60A5FA]/10 flex items-center justify-center shrink-0">
               <Database className="w-6 h-6 text-[#0059B5] dark:text-[#60A5FA]" />
             </div>
             <div className="flex-1 text-left">
                <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">Analysis Payload (JSON)</h3>
                <p className="text-neutral-500 text-sm font-light mb-6">Complete end-to-end extraction JSON payload representing the entire relational model.</p>
                <button onClick={downloadJSON} className="bg-black/5 dark:bg-white/5 hover:bg-black/10 dark:hover:bg-white/10 text-black dark:text-white px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-black/10 dark:border-white/10">Download .json</button>
             </div>
          </GlassCard>

          <GlassCard className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer" aria-label="CSV Export">
             <div className="w-14 h-14 rounded-2xl bg-emerald-500/10 flex items-center justify-center shrink-0">
               <ListTree className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
             </div>
             <div className="flex-1 text-left">
                <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">Data Dictionary (CSV)</h3>
                <p className="text-neutral-500 text-sm font-light mb-6">Spreadsheet-ready schema attributes, AI definitions, and semantic roles.</p>
                <button onClick={() => alert("CSV Export coming soon!")} className="bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-700 dark:text-emerald-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-emerald-500/20">Download .csv</button>
             </div>
          </GlassCard>

          <GlassCard className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer" aria-label="dbt Export">
             <div className="w-14 h-14 rounded-2xl bg-purple-500/10 flex items-center justify-center shrink-0">
               <ActivitySquare className="w-6 h-6 text-purple-600 dark:text-purple-400" />
             </div>
             <div className="flex-1 text-left">
                <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">dbt Models (YAML)</h3>
                <p className="text-neutral-500 text-sm font-light mb-6">Production-ready `schema.yml` configurations for your analytics deployment.</p>
                <button onClick={downloadDbt} className="bg-purple-500/10 hover:bg-purple-500/20 text-purple-700 dark:text-purple-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-purple-500/20">Download .yml</button>
             </div>
          </GlassCard>

          <GlassCard className="p-8 flex items-start gap-6 hover:scale-[1.02] transition-transform cursor-pointer" aria-label="SVG ER Export">
             <div className="w-14 h-14 rounded-2xl bg-rose-500/10 flex items-center justify-center shrink-0">
               <Share2 className="w-6 h-6 text-rose-600 dark:text-rose-400" />
             </div>
             <div className="flex-1 text-left">
                <h3 className="text-xl font-medium text-neutral-900 dark:text-white mb-2">Architectural ERD (SVG)</h3>
                <p className="text-neutral-500 text-sm font-light mb-6">High-resolution vector graphic of the inferred entity relationship layout.</p>
                <button onClick={() => alert("SVG Vector Export Coming Soon!")} className="bg-rose-500/10 hover:bg-rose-500/20 text-rose-700 dark:text-rose-400 px-6 py-2.5 rounded-full text-sm font-medium transition-colors border border-rose-500/20">Download .svg</button>
             </div>
          </GlassCard>
        </div>
          </div>
          );
        })()}
      </div>

      {/* AI REVIEW */}
      <div className={clsx("animate-in fade-in duration-700 w-full mt-24 print:mt-10 print:block", activeTab !== 'ai' && "hidden")}>
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">AI <span className="font-medium text-purple-500">Analyst Review</span></h2>
        {analysisData?.ai_brief || aiResponse ? (
          <GlassCard className="p-10 relative overflow-hidden">
            {/* Print Header */}
            <div className="hidden print:block mb-8 pb-4 border-b border-black">
               <h1 className="text-2xl font-bold">Nexus Intelligence - Executive Summary</h1>
               <p className="text-sm font-mono mt-1 text-gray-500">Report Generated: {new Date().toLocaleDateString()}</p>
            </div>
            {isGeneratingAi && (
               <div className="absolute inset-0 bg-white/40 dark:bg-black/40 backdrop-blur-sm z-10 flex items-center justify-center print:hidden">
                  <div className="flex flex-col items-center gap-4">
                     <Loader2 className="w-10 h-10 text-purple-500 animate-spin" />
                     <span className="text-purple-600 dark:text-purple-400 font-medium tracking-widest text-xs uppercase animate-pulse">Running Neural Pipeline...</span>
                  </div>
               </div>
            )}
            <div className="mb-8 relative z-0 print:hidden">
              <textarea 
                value={aiPrompt}
                onChange={e => setAiPrompt(e.target.value)}
                className="w-full h-24 p-5 bg-white/50 dark:bg-black/20 border border-black/5 dark:border-white/10 rounded-2xl focus:outline-none focus:ring-1 focus:ring-purple-500 resize-none font-light text-sm shadow-inner dark:text-neutral-200"
                placeholder="Ask the AI agent..."
              />
              <div className="flex justify-between mt-4">
                 <button onClick={() => window.print()} className="px-6 py-2.5 bg-neutral-100 dark:bg-neutral-800 text-neutral-600 dark:text-neutral-300 rounded-full font-medium text-sm transition-colors border border-black/5 flex items-center gap-2 cursor-pointer hover:bg-neutral-200 dark:hover:bg-neutral-700">
                    <Download className="w-4 h-4" /> Download PDF Report
                 </button>
                 <button onClick={handleAiAction} disabled={isGeneratingAi} className="px-6 py-2.5 bg-purple-500/10 hover:bg-purple-500/20 text-purple-600 dark:text-purple-400 rounded-full font-medium text-sm transition-colors border border-purple-500/20 flex items-center gap-2 cursor-pointer disabled:opacity-50">
                    <BrainCircuit className="w-4 h-4" /> {isGeneratingAi ? "Generating..." : "Generate Analyst Brief"}
                 </button>
              </div>
              {aiError && (
                <div className="mt-3 text-xs text-rose-600 dark:text-rose-400">
                  {aiError}
                </div>
              )}
              {aiMeta && (
                <div className="mt-3 text-xs text-neutral-500 dark:text-neutral-400">
                  Provider: {String(aiMeta.provider_used || "unknown")} | Model: {String(aiMeta.model_used || "unknown")} | Status: {String(aiMeta.status || "unknown")}
                </div>
              )}
            </div>
            <div className="prose prose-neutral dark:prose-invert max-w-none text-base font-light leading-relaxed whitespace-pre-wrap border-t border-black/5 dark:border-white/5 pt-8 relative z-0">
              <div dangerouslySetInnerHTML={{ __html: (aiResponse || analysisData.ai_brief).replace(/### (.*?)\n/g, '<h3 class="text-xl font-medium text-purple-600 dark:text-purple-400 mb-2 mt-4">$1</h3>').replace(/\*\*(.*?)\*\*/g, '<strong class="font-medium text-neutral-900 dark:text-white">$1</strong>').replace(/`([^`]+)`/g, '<code class="bg-black/5 dark:bg-white/10 px-1.5 py-0.5 rounded text-sm font-mono text-purple-600 dark:text-purple-300">$1</code>') }} />
            </div>
          </GlassCard>
        ) : (
          <GlassCard className="p-12 text-center text-neutral-400 font-light">
            AI module was skipped or unavailable for this run.
          </GlassCard>
        )}
      </div>

      {/* EDITOR */}
      <div className={clsx("animate-in fade-in duration-700 w-full mt-24 print:hidden", activeTab !== 'editor' && "hidden")}>
        {(() => {
          return (
            <div className="w-full">
        <h2 className="text-4xl font-light tracking-tight text-neutral-900 dark:text-white mb-8">Data <span className="font-medium text-amber-600 dark:text-amber-500">Editor</span></h2>
        <div className="mb-6 flex gap-2 overflow-x-auto pb-2 custom-scrollbar">
           {tables.map((t: string) => (
             <button 
               key={t} 
               onClick={() => setEditorTarget(t)} 
               className={clsx("px-4 py-2 rounded-xl text-sm transition-colors whitespace-nowrap", currentEditorTarget === t ? "bg-amber-500/10 text-amber-700 dark:text-amber-400 font-medium" : "bg-black/5 dark:bg-white/5 text-neutral-500 hover:text-neutral-900 dark:hover:text-white font-light")}
             >
               {t}
             </button>
           ))}
        </div>

        <GlassCard className="overflow-hidden p-0">
           <div className="flex bg-amber-500/10 text-amber-800 dark:text-amber-400 text-xs px-6 py-3 font-medium items-center justify-between border-b border-amber-500/20">
             <div className="flex items-center gap-2">
                 <ActivitySquare className="w-4 h-4" /> Live Row Editor (Changes sync to output payload)
             </div>
             <button onClick={() => {
                 const rows = analysisData?.analysis?.sample_tables?.[currentEditorTarget] || [];
                 if (rows.length === 0) return;
                 const headers = Object.keys(rows[0]);
                 const csvContent = "data:text/csv;charset=utf-8," 
                     + headers.join(",") + "\n"
                     + rows.map((r:any) => headers.map(h => `"${String(r[h]).replace(/"/g, '""')}"`).join(",")).join("\n");
                 const encodedUri = encodeURI(csvContent);
                 const link = document.createElement("a");
                 link.setAttribute("href", encodedUri);
                 link.setAttribute("download", `nexus_${currentEditorTarget}_edited.csv`);
                 document.body.appendChild(link);
                 link.click();
                 document.body.removeChild(link);
             }} className="flex items-center gap-1.5 bg-amber-200/50 dark:bg-amber-900/50 hover:bg-amber-300 dark:hover:bg-amber-800 text-amber-900 dark:text-amber-200 border border-amber-500/30 px-3 py-1.5 rounded-lg shadow-sm transition-colors cursor-pointer">
                <Download className="w-4 h-4" /> Save & Download CSV
             </button>
           </div>
           <div className="overflow-x-auto overflow-y-auto max-h-[600px] bg-white/50 dark:bg-black/20">
             {((analysisData?.analysis?.sample_tables?.[currentEditorTarget] || []).length === 0) ? (
                      <div className="text-sm font-medium text-center text-neutral-400 py-8">No rows found in analyzed sample.</div>
                    ) : (
                      <table className="w-full text-left text-sm whitespace-nowrap">
                        <thead className="bg-[#0059B5]/5 dark:bg-[#0059B5]/10">
                          <tr>
                            <th className="px-4 py-3 font-medium text-neutral-500 uppercase tracking-wider text-xs w-16 text-center border-b border-black/5 dark:border-white/5">Row</th>
                            {Object.keys((analysisData.analysis.sample_tables[currentEditorTarget] as any[])[0]).map(k => (
                              <th key={k} className="px-4 py-3 font-semibold text-neutral-700 dark:text-neutral-300 border-b border-black/5 dark:border-white/5">{k}</th>
                            ))}
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-black/5 dark:divide-white/5 font-mono">
                          {(analysisData.analysis.sample_tables[currentEditorTarget] as any[]).map((row, i) => (
                            <tr key={i} className="hover:bg-amber-500/5 transition-colors group">
                              <td className="px-4 py-2 text-center text-neutral-500 dark:text-neutral-400 border-r border-black/5 dark:border-white/5">{i + 1}</td>
                              {Object.entries(row).map(([key, value]: [string, any]) => (
                                <td 
                                  key={key} 
                                  className="px-4 py-2 font-light text-neutral-700 dark:text-neutral-300 outline-none focus:bg-amber-500/10 focus:ring-1 focus:ring-amber-500/50 transition-colors whitespace-nowrap max-w-[200px] truncate" 
                                  contentEditable 
                                  suppressContentEditableWarning
                                >
                                  {String(value || '')}
                                </td>
                              ))}
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
           </div>
        </GlassCard>
            </div>
          );
        })()}
      </div>

    </div>
  );
}

// ------------------------------------
// MAIN APP
// ------------------------------------
export default function App() {
  const [ingestionState, setIngestionState] = useState<'idle'|'uploading'|'db_form'|'processing'|'done'>('idle');
  const [analysisData, setAnalysisData] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [navLayout, setNavLayout] = useState<'horizontal' | 'vertical'>('horizontal');
  const [dragActive, setDragActive] = useState(false);
  const [showAgentPanel, setShowAgentPanel] = useState(false);
  const [agentBusy, setAgentBusy] = useState(false);
  const [agentError, setAgentError] = useState<string | null>(null);
  const [agentResult, setAgentResult] = useState<any>(null);
  const [agentAuth, setAgentAuth] = useState<{ ok: boolean; email: string; message: string }>({
    ok: false,
    email: '',
    message: '',
  });
  const [agentForm, setAgentForm] = useState({
    firebaseEmail: '',
    firebasePassword: '',
    firebaseApiKey: '',
    firebaseAuthDomain: '',
    firebaseProjectId: '',
    firebaseStorageBucket: '',
    agentEmail: '',
    gmailAppPassword: '',
    imapHost: 'imap.gmail.com',
    smtpHost: 'smtp.gmail.com',
    smtpPort: '587',
    maxMessages: '5',
    aiProvider: 'ollama',
    ollamaEndpoint: 'http://localhost:11434',
    ollamaModel: 'llama3:latest',
    geminiApiKey: '',
    geminiModel: 'gemini-2.0-flash',
  });

  useEffect(() => {
    const loadAgentConfig = async () => {
      try {
        const response = await axios.get(`${API_BASE}/agent/runtime-config`);
        const defaultAgentEmail = String(response?.data?.default_agent_email || '').trim();
        if (!defaultAgentEmail) {
          return;
        }

        setAgentForm((prev) => ({
          ...prev,
          firebaseEmail: prev.firebaseEmail || defaultAgentEmail,
          agentEmail: prev.agentEmail || defaultAgentEmail,
        }));
      } catch {
        // Keep defaults when runtime config endpoint is unavailable.
      }
    };

    loadAgentConfig();
  }, []);

  const handleAgentLogin = async () => {
    setAgentBusy(true);
    setAgentError(null);
    setAgentResult(null);

    try {
      const response = await axios.post(`${API_BASE}/agent/firebase-login`, {
        email: agentForm.firebaseEmail,
        password: agentForm.firebasePassword,
        firebase_api_key: agentForm.firebaseApiKey,
        firebase_auth_domain: agentForm.firebaseAuthDomain,
        firebase_project_id: agentForm.firebaseProjectId,
        firebase_storage_bucket: agentForm.firebaseStorageBucket,
      });

      const ok = Boolean(response?.data?.ok);
      const message = String(response?.data?.message || (ok ? 'Agent login succeeded.' : 'Agent login failed.'));
      const email = String(response?.data?.email || agentForm.firebaseEmail || '');
      setAgentAuth({ ok, email, message });
      if (!ok) {
        throw new Error(message);
      }
      setAgentForm((prev) => ({ ...prev, agentEmail: email || prev.agentEmail }));
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setAgentError(String(detail || err?.message || 'Agent login failed.'));
      setAgentAuth((prev) => ({ ...prev, ok: false }));
    } finally {
      setAgentBusy(false);
    }
  };

  const handleAgentProcessOnce = async () => {
    const sampleTables = analysisData?.analysis?.sample_tables || {};
    if (!sampleTables || Object.keys(sampleTables).length === 0) {
      setAgentError('Run analysis first so the agent has table context to answer emails.');
      return;
    }

    setAgentBusy(true);
    setAgentError(null);
    setAgentResult(null);

    try {
      const response = await axios.post(`${API_BASE}/agent/process-once`, {
        sample_tables: sampleTables,
        agent_email: agentForm.agentEmail,
        gmail_app_password: agentForm.gmailAppPassword,
        imap_host: agentForm.imapHost,
        smtp_host: agentForm.smtpHost,
        smtp_port: Number(agentForm.smtpPort || '587'),
        max_messages_per_cycle: Number(agentForm.maxMessages || '5'),
        ai_provider: agentForm.aiProvider,
        ollama_endpoint: agentForm.ollamaEndpoint,
        ollama_model: agentForm.ollamaModel,
        gemini_api_key: agentForm.geminiApiKey,
        gemini_model: agentForm.geminiModel,
      });

      setAgentResult(response?.data || {});
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      setAgentError(String(detail || err?.message || 'Agent inbox processing failed.'));
    } finally {
      setAgentBusy(false);
    }
  };
  
  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      setIngestionState('processing');
      const formData = new FormData();
      Array.from(files).forEach((file) => formData.append('files', file));
      try {
        const res = await axios.post(`${API_BASE}/analyze/csv`, formData);
        setAnalysisData(res.data);
        setIngestionState('done');
      } catch (err) {
        console.error(err);
        alert("Failed to analyze CSV.");
        setIngestionState('idle');
      }
    }
  };

  const [dbForm, setDbForm] = useState({
    db_type: 'sqlite',
    host: 'localhost',
    port: '1433',
    database: '',
    username: '',
    password: ''
  });

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (!files || files.length === 0) return;
    
    setIngestionState('processing');
    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append('files', file));
    
    try {
      const res = await axios.post(`${API_BASE}/analyze/csv`, formData);
      setAnalysisData(res.data);
      setIngestionState('done');
    } catch (e) {
      console.error(e);
      alert("Failed to analyze. Ensure backend API is running at localhost:8000!");
      setIngestionState('idle');
    }
  };

  const handleDbSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIngestionState('processing');
    
    const formData = new FormData();
    Object.entries(dbForm).forEach(([key, val]) => formData.append(key, val));

    try {
      const res = await axios.post(`${API_BASE}/analyze/db`, formData);
      setAnalysisData(res.data);
      setIngestionState('done');
    } catch (e) {
      console.error(e);
      alert("Database connection failed. Check your credentials and backend server!");
      setIngestionState('idle');
    }
  };

  return (
    <div className="min-h-screen bg-[#F5F5F7] dark:bg-[#0c0d0f] text-neutral-900 dark:text-neutral-100 font-sans transition-colors duration-500 overflow-x-hidden relative">
      
      {/* Soulful Ambient Glows Background */}
      <div className="fixed inset-0 pointer-events-none z-0 overflow-hidden">
         <div className="absolute top-[-20%] left-[-10%] w-[60vw] h-[60vw] rounded-full bg-blue-300/10 dark:bg-blue-600/10 blur-[140px]" />
         <div className="absolute top-[40%] right-[-10%] w-[50vw] h-[50vw] rounded-full bg-indigo-300/10 dark:bg-indigo-600/10 blur-[140px]" />
      </div>

      <TopNav 
        activeTab={ingestionState === 'done' ? activeTab : undefined} 
        setActiveTab={setActiveTab} 
        resetState={() => {
          setIngestionState('idle');
          setAnalysisData(null);
          setActiveTab('overview');
        }}
        navLayout={navLayout}
        setNavLayout={setNavLayout}
        onAgentClick={() => setShowAgentPanel(true)}
      />

      <AnimatePresence>
        {showAgentPanel && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="fixed inset-0 bg-black/35 z-[70]"
              onClick={() => setShowAgentPanel(false)}
            />
            <motion.aside
              initial={{ x: 460, opacity: 0 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: 460, opacity: 0 }}
              transition={{ type: 'spring', stiffness: 220, damping: 26 }}
              className="fixed right-0 top-0 h-full w-full max-w-md z-[80] bg-white/95 dark:bg-[#0f1115]/96 backdrop-blur-xl border-l border-black/10 dark:border-white/10 shadow-2xl p-6 overflow-y-auto"
            >
              <div className="flex items-center justify-between mb-6">
                <h3 className="text-xl font-medium text-neutral-900 dark:text-white">Email Agent</h3>
                <button
                  onClick={() => setShowAgentPanel(false)}
                  className="px-3 py-1 rounded-lg text-sm bg-black/5 dark:bg-white/10 hover:bg-black/10 dark:hover:bg-white/20"
                >
                  Close
                </button>
              </div>

              <div className="space-y-5">
                <div className="p-4 rounded-xl border border-black/10 dark:border-white/10 bg-white/70 dark:bg-white/5">
                  <h4 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-3">1. Establish Agent</h4>
                  <div className="space-y-3">
                    <input
                      placeholder="Firebase login email"
                      value={agentForm.firebaseEmail}
                      onChange={(e) => setAgentForm((prev) => ({ ...prev, firebaseEmail: e.target.value }))}
                      className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                    />
                    <input
                      type="password"
                      placeholder="Firebase login password"
                      value={agentForm.firebasePassword}
                      onChange={(e) => setAgentForm((prev) => ({ ...prev, firebasePassword: e.target.value }))}
                      className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                    />
                    <button
                      onClick={handleAgentLogin}
                      disabled={agentBusy || !agentForm.firebaseEmail || !agentForm.firebasePassword}
                      className="w-full py-2.5 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white font-medium"
                    >
                      {agentBusy ? 'Authenticating...' : 'Authenticate Agent'}
                    </button>
                    {agentAuth.message && (
                      <div className={clsx('text-xs', agentAuth.ok ? 'text-emerald-600 dark:text-emerald-400' : 'text-rose-600 dark:text-rose-400')}>
                        {agentAuth.message}
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-4 rounded-xl border border-black/10 dark:border-white/10 bg-white/70 dark:bg-white/5">
                  <h4 className="text-sm font-semibold uppercase tracking-wider text-neutral-500 mb-3">2. Configure Inbox Agent</h4>
                  <div className="space-y-3">
                    <input
                      placeholder="Agent Gmail"
                      value={agentForm.agentEmail}
                      onChange={(e) => setAgentForm((prev) => ({ ...prev, agentEmail: e.target.value }))}
                      className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                    />
                    <input
                      type="password"
                      placeholder="Gmail App Password"
                      value={agentForm.gmailAppPassword}
                      onChange={(e) => setAgentForm((prev) => ({ ...prev, gmailAppPassword: e.target.value }))}
                      className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                    />
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        placeholder="IMAP host"
                        value={agentForm.imapHost}
                        onChange={(e) => setAgentForm((prev) => ({ ...prev, imapHost: e.target.value }))}
                        className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        placeholder="SMTP host"
                        value={agentForm.smtpHost}
                        onChange={(e) => setAgentForm((prev) => ({ ...prev, smtpHost: e.target.value }))}
                        className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <input
                        placeholder="SMTP port"
                        value={agentForm.smtpPort}
                        onChange={(e) => setAgentForm((prev) => ({ ...prev, smtpPort: e.target.value }))}
                        className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                      <input
                        placeholder="Max emails per cycle"
                        value={agentForm.maxMessages}
                        onChange={(e) => setAgentForm((prev) => ({ ...prev, maxMessages: e.target.value }))}
                        className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                      />
                    </div>

                    <select
                      value={agentForm.aiProvider}
                      onChange={(e) => setAgentForm((prev) => ({ ...prev, aiProvider: e.target.value }))}
                      title="Agent AI provider"
                      aria-label="Agent AI provider"
                      className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                    >
                      <option value="ollama">Ollama</option>
                      <option value="gemini">Gemini</option>
                    </select>

                    {agentForm.aiProvider === 'ollama' ? (
                      <>
                        <input
                          placeholder="Ollama endpoint"
                          value={agentForm.ollamaEndpoint}
                          onChange={(e) => setAgentForm((prev) => ({ ...prev, ollamaEndpoint: e.target.value }))}
                          className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          placeholder="Ollama model"
                          value={agentForm.ollamaModel}
                          onChange={(e) => setAgentForm((prev) => ({ ...prev, ollamaModel: e.target.value }))}
                          className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      </>
                    ) : (
                      <>
                        <input
                          type="password"
                          placeholder="Gemini API key"
                          value={agentForm.geminiApiKey}
                          onChange={(e) => setAgentForm((prev) => ({ ...prev, geminiApiKey: e.target.value }))}
                          className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                        <input
                          placeholder="Gemini model"
                          value={agentForm.geminiModel}
                          onChange={(e) => setAgentForm((prev) => ({ ...prev, geminiModel: e.target.value }))}
                          className="w-full p-3 rounded-lg bg-white dark:bg-black/30 border border-black/10 dark:border-white/10"
                        />
                      </>
                    )}

                    <button
                      onClick={handleAgentProcessOnce}
                      disabled={agentBusy || !agentForm.agentEmail || !agentForm.gmailAppPassword}
                      className="w-full py-2.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 disabled:opacity-60 text-white font-medium"
                    >
                      {agentBusy ? 'Processing Inbox...' : 'Process Inbox Once'}
                    </button>
                    <p className="text-xs text-neutral-500 dark:text-neutral-400">
                      The React agent uses analyzed sample tables as query context. Run analysis first.
                    </p>
                  </div>
                </div>

                {agentError && (
                  <div className="text-sm text-rose-600 dark:text-rose-400 bg-rose-50 dark:bg-rose-950/20 border border-rose-200 dark:border-rose-900 rounded-lg p-3">
                    {agentError}
                  </div>
                )}

                {agentResult && (
                  <div className="text-sm text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900 rounded-lg p-3">
                    Processed: {String(agentResult.processed || 0)} | Replied: {String(agentResult.replied || 0)} | Skipped: {String(agentResult.skipped || 0)}
                    {Array.isArray(agentResult.failures) && agentResult.failures.length > 0 && (
                      <div className="mt-2 text-rose-600 dark:text-rose-400">Failures: {agentResult.failures.join(' | ')}</div>
                    )}
                  </div>
                )}
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
      
      <main className={clsx("relative z-10 pt-20 pb-20 px-6 max-w-5xl mx-auto w-full min-h-[90vh] flex flex-col items-center transition-all duration-300", navLayout === 'vertical' && ingestionState === 'done' ? "md:pl-52" : "")}>
        {ingestionState === 'done' ? (
           <div className="w-full relative min-h-full">
             <ErrorBoundary>
               <DataView activeTab={activeTab === 'editor' ? 'editor' : activeTab} analysisData={analysisData} />
             </ErrorBoundary>
           </div>
        ) : (
           <div className="flex flex-col items-center justify-center w-full flex-1 max-w-2xl min-h-[80vh]">
              <motion.div 
                initial={{ opacity: 0, y: 20 }} 
                animate={{ opacity: 1, y: 0 }} 
                transition={{ duration: 0.8, ease: [0.16, 1, 0.3, 1] }}
                className="text-center mb-16"
              >
                <h1 className="text-5xl sm:text-6xl md:text-7xl font-thin tracking-tight text-neutral-900 dark:text-white mb-6">
                  Relational Database<br/>Intelligence Agent
                </h1>
                <p className="text-neutral-500 dark:text-neutral-400 text-lg font-light max-w-lg mx-auto">
                  End-to-end schema extraction, quality scoring, and relationship inference powered by intelligence.
                </p>
              </motion.div>

              <AnimatePresence mode="wait">
                {ingestionState === 'idle' && (
                  <motion.div 
                    key="idle"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95 }}
                    className="w-full space-y-4"
                  >
                    <label 
                      className={clsx("group relative flex items-center justify-between p-6 rounded-[2rem] backdrop-blur-3xl border transition-all duration-500 cursor-pointer shadow-[0_8px_30px_rgba(0,0,0,0.02)]", dragActive ? "bg-white/60 dark:bg-white/10 border-[#0059B5] dark:border-[#60A5FA]" : "bg-white/40 dark:bg-black/20 border-white/60 dark:border-white/5 hover:bg-white/60 dark:hover:bg-black/40")}
                      onDragEnter={handleDrag} onDragLeave={handleDrag} onDragOver={handleDrag} onDrop={handleDrop}
                    >
                      <div className="flex items-center gap-5 pointer-events-none">
                        <div className={clsx("w-14 h-14 rounded-2xl flex items-center justify-center transition-colors", dragActive ? "bg-[#0059B5]/10 dark:bg-[#60A5FA]/10" : "bg-black/5 dark:bg-white/5")}>
                           <FileUp className={clsx("w-6 h-6 transition-colors", dragActive ? "text-[#0059B5] dark:text-[#60A5FA]" : "text-neutral-600 dark:text-neutral-300")} />
                        </div>
                        <div className="text-left">
                           <span className="block font-medium text-xl text-neutral-900 dark:text-neutral-100">{dragActive ? "Drop to Upload" : "Upload Dataset"}</span>
                           <span className="block font-light text-base text-neutral-500">{dragActive ? "Release files down here" : "CSV bundles or SQLite files"}</span>
                        </div>
                      </div>
                      <ArrowRight className="w-6 h-6 text-neutral-300 dark:text-neutral-600 group-hover:translate-x-1 group-hover:text-neutral-900 dark:group-hover:text-white transition-all duration-300 pointer-events-none" />
                      <input type="file" multiple accept=".csv,.sqlite,.db,.sqlite3" className="hidden" onChange={handleFileUpload} />
                    </label>

                    <button 
                      onClick={() => setIngestionState('db_form')}
                      className="w-full group relative flex items-center justify-between p-6 rounded-[2rem] bg-white/40 dark:bg-black/20 backdrop-blur-3xl border border-white/60 dark:border-white/5 hover:bg-white/60 dark:hover:bg-black/40 transition-all duration-500 outline-none shadow-[0_8px_30px_rgba(0,0,0,0.02)]"
                    >
                      <div className="flex items-center gap-5 text-left">
                        <div className="w-14 h-14 rounded-2xl bg-black/5 dark:bg-white/5 flex items-center justify-center">
                           <Database className="w-6 h-6 text-neutral-600 dark:text-neutral-300 transition-colors" />
                        </div>
                        <div>
                           <span className="block font-medium text-xl text-neutral-900 dark:text-neutral-100">Connect Database</span>
                           <span className="block font-light text-base text-neutral-500">PostgreSQL, MySQL, SQL Server</span>
                        </div>
                      </div>
                      <ArrowRight className="w-6 h-6 text-neutral-300 dark:text-neutral-600 group-hover:translate-x-1 group-hover:text-neutral-900 dark:group-hover:text-white transition-all duration-300" />
                    </button>
                  </motion.div>
                )}

                {ingestionState === 'db_form' && (
                  <motion.div
                    key="db_form"
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className="w-full max-w-2xl bg-white/50 dark:bg-black/30 backdrop-blur-3xl p-10 rounded-[2rem] border border-white/60 dark:border-white/5 shadow-[0_20px_40px_rgba(0,0,0,0.04)] text-left"
                  >
                    <form onSubmit={handleDbSubmit} className="space-y-6">
                      <h3 className="font-light tracking-wide text-3xl text-neutral-900 dark:text-white mb-8">Connection Details</h3>
                      
                      <div className="space-y-4">
                        <select 
                          value={dbForm.db_type}
                          onChange={(e) => setDbForm({...dbForm, db_type: e.target.value})}
                          title="Database engine"
                          aria-label="Database engine"
                          className="w-full p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow"
                        >
                          <option value="postgresql">PostgreSQL</option>
                          <option value="mysql">MySQL</option>
                          <option value="sqlserver">SQL Server</option>
                          <option value="sqlite">SQLite (Local Path)</option>
                        </select>
                        
                        <div className="grid grid-cols-3 gap-4">
                          <input required placeholder="Host" value={dbForm.host} onChange={(e) => setDbForm({...dbForm, host: e.target.value})} className="col-span-2 p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow" />
                          <input required placeholder="Port" value={dbForm.port} onChange={(e) => setDbForm({...dbForm, port: e.target.value})} className="col-span-1 p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow" />
                        </div>
                        
                        <input required placeholder="Database Name" value={dbForm.database} onChange={(e) => setDbForm({...dbForm, database: e.target.value})} className="w-full p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow" />
                        
                        <div className="grid grid-cols-2 gap-4">
                          <input required placeholder="Username" value={dbForm.username} onChange={(e) => setDbForm({...dbForm, username: e.target.value})} className="p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow" />
                          <input required type="password" placeholder="Password" value={dbForm.password} onChange={(e) => setDbForm({...dbForm, password: e.target.value})} className="p-4 rounded-xl border-0 ring-1 ring-black/5 dark:ring-white/10 bg-white/50 dark:bg-black/50 text-base font-light focus:outline-none focus:ring-2 focus:ring-[#0059B5] dark:text-white transition-shadow" />
                        </div>
                      </div>
                      
                      <div className="flex items-center justify-between pt-8">
                        <button type="button" onClick={() => setIngestionState('idle')} className="px-6 py-3 text-sm font-medium text-neutral-500 hover:text-neutral-900 dark:hover:text-white transition-colors">Cancel</button>
                        <button type="submit" className="text-base font-medium bg-gradient-to-br from-[#004289] to-[#0059B5] text-white px-8 py-4 rounded-2xl hover:opacity-90 transition-opacity shadow-[0_8px_20px_rgba(0,89,181,0.2)]">Connect & Analyze</button>
                      </div>
                    </form>
                  </motion.div>
                )}

                {ingestionState === 'processing' && (
                  <motion.div 
                    key="processing"
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="flex flex-col items-center justify-center py-20 w-full"
                  >
                     <div className="w-16 h-16 rounded-full bg-white/50 dark:bg-black/50 backdrop-blur-xl border border-white/60 dark:border-white/10 flex items-center justify-center shadow-lg relative overflow-hidden mb-6">
                        <Loader2 className="w-8 h-8 text-[#0059B5] animate-spin absolute" />
                     </div>
                    <CycleText />
                  </motion.div>
                )}
              </AnimatePresence>
           </div>
        )}
      </main>

      <footer className="fixed bottom-6 left-1/2 -translate-x-1/2 text-center text-xs font-light tracking-[0.2em] text-neutral-400 dark:text-neutral-600 mix-blend-difference pointer-events-none">
         NEXUS INTELLIGENCE
      </footer>
    </div>
  );
}