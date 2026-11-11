import React from 'react';
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  PlusCircle,
  FileText,
  ShieldCheck,
  Lightbulb,
  BarChart3,
  Cpu,
  Radio,
  ExternalLink,
} from 'lucide-react';
import { useResearch } from '../../context/ResearchContext';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: LayoutDashboard },
  { path: '/new-research', label: 'New Research', icon: PlusCircle, highlight: true },
  { path: '/results', label: 'Research Results', icon: FileText },
  { path: '/verification', label: 'Verification', icon: ShieldCheck },
  { path: '/insights', label: 'AI Insights', icon: Lightbulb },
  { path: '/dashboard', label: 'Analytics Dashboard', icon: BarChart3 },
  { path: '/activity', label: 'Agent Activity', icon: Cpu },
];

export default function Sidebar({ isOpen, onClose }) {
  const { currentPipeline, backendHealth } = useResearch();

  return (
    <>
      {/* Mobile backdrop */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/60 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-navy-900 border-r border-slate-800/80 flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand header */}
        <div className="p-5 border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500 to-indigo-700 flex items-center justify-center text-white shadow-glow-indigo font-bold text-lg">
              I
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-white text-base tracking-tight">IntelliScope AI</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-brand-950 text-brand-300 border border-brand-800/50">
                  v1.0
                </span>
              </div>
              <p className="text-[11px] text-slate-400 truncate">Multi-Agent Intelligence</p>
            </div>
          </div>
        </div>

        {/* Current topic indicator if research is active */}
        {currentPipeline?.query && (
          <div className="mx-3 mt-3 p-2.5 rounded-lg bg-brand-950/40 border border-brand-800/30">
            <div className="text-[10px] uppercase tracking-wider text-brand-400 font-semibold mb-0.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" />
              Active Research
            </div>
            <p className="text-xs font-medium text-slate-200 truncate" title={currentPipeline.query}>
              "{currentPipeline.query}"
            </p>
          </div>
        )}

        {/* Navigation links */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                onClick={() => onClose?.()}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium transition-all ${
                    isActive
                      ? 'bg-brand-600 text-white shadow-sm shadow-brand-500/30'
                      : item.highlight
                      ? 'text-brand-300 hover:bg-brand-950/60 hover:text-white border border-brand-800/40'
                      : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/60'
                  }`
                }
              >
                <Icon className="w-4 h-4 flex-shrink-0" />
                <span>{item.label}</span>
              </NavLink>
            );
          })}
        </nav>

        {/* Backend health status in sidebar footer */}
        <div className="p-3.5 border-t border-slate-800/80 bg-navy-950/40">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-slate-400 flex items-center gap-1.5">
              <Radio className="w-3.5 h-3.5 text-slate-400" />
              <span>FastAPI Backend</span>
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendHealth.healthy ? 'bg-emerald-400 shadow-sm shadow-emerald-400' : 'bg-rose-400 animate-pulse'
                }`}
              />
              <span className={backendHealth.healthy ? 'text-emerald-400 font-medium' : 'text-rose-400 font-medium'}>
                {backendHealth.healthy ? ':8010 Online' : ':8010 Offline'}
              </span>
            </span>
          </div>

          <div className="text-[11px] text-slate-400 text-center flex items-center justify-center gap-2 pt-1 border-t border-slate-800/40">
            <span>Official BAND SDK 6.0.1</span>
            <span>•</span>
            <a
              href="http://127.0.0.1:8010/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="text-brand-400 hover:text-brand-300 flex items-center gap-0.5"
            >
              Docs <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}

