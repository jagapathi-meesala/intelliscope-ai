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
import { API_BASE_URL } from '../../api/client';

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
          className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-64 bg-white border-r border-[#E2E8F0] flex flex-col transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        {/* Brand header */}
        <div className="p-5 border-b border-[#E2E8F0]">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-xl bg-[#4F46E5] flex items-center justify-center text-white shadow-sm font-bold text-lg">
              I
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-[#0F172A] text-base tracking-tight">IntelliScope AI</span>
                <span className="text-[10px] font-mono uppercase px-1.5 py-0.5 rounded bg-[#EEF2FF] text-[#4F46E5] border border-[#C7D2FE] font-medium">
                  v1.0
                </span>
              </div>
              <p className="text-[11px] text-[#64748B] truncate">Multi-Agent Intelligence</p>
            </div>
          </div>
        </div>

        {/* Current topic indicator if research is active */}
        {currentPipeline?.query && (
          <div className="mx-3 mt-3 p-2.5 rounded-lg bg-[#EEF2FF] border border-[#C7D2FE]">
            <div className="text-[10px] uppercase tracking-wider text-[#4F46E5] font-semibold mb-0.5 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#4F46E5] animate-pulse" />
              Active Research
            </div>
            <p className="text-xs font-medium text-[#0F172A] truncate" title={currentPipeline.query}>
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
                      ? 'bg-[#4F46E5] text-white shadow-sm font-semibold'
                      : item.highlight
                      ? 'text-[#4F46E5] bg-[#EEF2FF] hover:bg-indigo-100/80 border border-[#C7D2FE]'
                      : 'text-[#334155] hover:text-[#0F172A] hover:bg-slate-100'
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
        <div className="p-3.5 border-t border-[#E2E8F0] bg-white">
          <div className="flex items-center justify-between text-xs mb-1.5">
            <span className="text-[#334155] flex items-center gap-1.5 font-medium">
              <Radio className="w-3.5 h-3.5 text-[#64748B]" />
              <span>FastAPI Backend</span>
            </span>
            <span className="flex items-center gap-1 text-[11px] font-mono">
              <span
                className={`w-2 h-2 rounded-full ${
                  backendHealth.healthy ? 'bg-emerald-500 shadow-sm shadow-emerald-200' : 'bg-rose-500 animate-pulse'
                }`}
              />
              <span className={backendHealth.healthy ? 'text-emerald-700 font-semibold' : 'text-rose-700 font-semibold'}>
                {backendHealth.checking
                  ? 'Checking...'
                  : backendHealth.healthy
                  ? (API_BASE_URL.includes('8010') ? ':8010 Online' : 'Online')
                  : (API_BASE_URL.includes('8010') ? ':8010 Offline' : 'Offline')}
              </span>
            </span>
          </div>

          <div className="text-[11px] text-[#64748B] text-center flex items-center justify-center gap-2 pt-1 border-t border-[#E2E8F0]">
            <span>Official BAND SDK 6.0.1</span>
            <span>•</span>
            <a
              href={`${API_BASE_URL}/docs`}
              target="_blank"
              rel="noopener noreferrer"
              className="text-[#4F46E5] hover:text-indigo-800 flex items-center gap-0.5 font-medium"
            >
              Docs <ExternalLink className="w-2.5 h-2.5" />
            </a>
          </div>
        </div>
      </aside>
    </>
  );
}

