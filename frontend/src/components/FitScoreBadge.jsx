import React from 'react';
import { ChevronDown } from 'lucide-react';

const FitScoreBadge = ({ score, onClick, expanded }) => {
  const color = score >= 85 ? 'text-emerald-400 bg-emerald-500/20 border-emerald-500/30' : 
                score >= 70 ? 'text-teal-400 bg-teal-500/20 border-teal-500/30' :
                score >= 55 ? 'text-amber-400 bg-amber-500/20 border-amber-500/30' : 
                'text-red-400 bg-red-500/20 border-red-500/30';
  return (
    <button 
      onClick={onClick}
      className={`group flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold border ${color} hover:scale-105 transition-all cursor-pointer`}
      title="Click to see breakdown"
    >
      <span>{score}%</span>
      <ChevronDown className={`w-3 h-3 opacity-60 group-hover:opacity-100 transition-all ${expanded ? 'rotate-180' : ''}`} />
    </button>
  );
};

export default FitScoreBadge;


