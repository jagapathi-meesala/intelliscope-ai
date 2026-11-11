import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorAlert({ error, onRetry, title = 'Execution Error' }) {
  if (!error) return null;

  const errorMessage = typeof error === 'string'
    ? error
    : error?.message || 'An unexpected error occurred during execution.';

  return (
    <div className="p-4 rounded-xl border border-rose-900/60 bg-rose-950/40 text-rose-200 my-4 shadow-sm flex items-start gap-3.5">
      <AlertCircle className="w-5 h-5 text-rose-400 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="text-sm font-semibold text-rose-100 mb-1">{title}</h4>
        <p className="text-sm text-rose-300/90 leading-relaxed font-mono text-xs break-words">
          {errorMessage}
        </p>
        {error?.statusCode && (
          <div className="mt-2 text-xs text-rose-400 font-mono">
            Status Code: <span className="font-semibold">{error.statusCode}</span>
          </div>
        )}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-900/50 hover:bg-rose-900 text-rose-200 text-xs font-medium border border-rose-800/80 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}

