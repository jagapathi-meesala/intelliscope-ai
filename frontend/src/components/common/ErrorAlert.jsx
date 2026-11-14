import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

export default function ErrorAlert({ error, onRetry, title = 'Execution Error' }) {
  if (!error) return null;

  const errorMessage = typeof error === 'string'
    ? error
    : error?.message || 'An unexpected error occurred during execution.';

  return (
    <div className="p-4 rounded-xl border border-rose-200 bg-rose-50 text-rose-900 my-4 shadow-sm flex items-start gap-3.5">
      <AlertCircle className="w-5 h-5 text-rose-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <h4 className="text-sm font-bold text-rose-900 mb-1">{title}</h4>
        <p className="text-xs font-mono text-rose-700 leading-relaxed break-words">
          {errorMessage}
        </p>
        {error?.statusCode && (
          <div className="mt-2 text-xs text-rose-600 font-mono">
            Status Code: <span className="font-semibold">{error.statusCode}</span>
          </div>
        )}
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          type="button"
          className="flex-shrink-0 inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-100 hover:bg-rose-200 text-rose-800 text-xs font-medium border border-rose-300 transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
}

