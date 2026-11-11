import React from 'react';
import { ExternalLink, ShieldAlert } from 'lucide-react';

export default function SafeExternalLink({
  href,
  children,
  className = '',
  showIcon = true,
  maxLength = null,
}) {
  if (!href) return <span className="text-slate-500 italic">No URL provided</span>;

  let isHttps = false;
  try {
    const url = new URL(href);
    isHttps = url.protocol === 'https:';
  } catch {
    isHttps = false;
  }

  const displayText = maxLength && typeof children === 'string' && children.length > maxLength
    ? `${children.slice(0, maxLength)}...`
    : children;

  if (!isHttps) {
    return (
      <span className={`inline-flex items-center gap-1 text-rose-400 font-mono text-xs ${className}`}>
        <ShieldAlert className="w-3.5 h-3.5 flex-shrink-0" />
        <span>Insecure URL ({displayText || href})</span>
      </span>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center gap-1.5 text-brand-400 hover:text-brand-300 underline underline-offset-2 hover:underline transition-colors focus:outline-none focus:ring-1 focus:ring-brand-400 rounded-sm ${className}`}
      title={`Open ${href} in new secure tab`}
    >
      <span className="truncate">{displayText || href}</span>
      {showIcon && <ExternalLink className="w-3.5 h-3.5 flex-shrink-0 opacity-75 group-hover:opacity-100" />}
    </a>
  );
}

