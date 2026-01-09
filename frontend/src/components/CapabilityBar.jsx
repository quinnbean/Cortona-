import React from 'react';
import { levelVal, levelMin } from '../data/toolData';

const CapabilityBar = ({ label, level, emphasized, requirement }) => {
  const widths = { exceptional: '95%', strong: '75%', moderate: '55%', limited: '35%', weak: '18%' };
  const colors = { 
    exceptional: 'bg-emerald-400',
    strong: emphasized ? 'bg-emerald-500' : 'bg-emerald-500/70', 
    moderate: emphasized ? 'bg-amber-500' : 'bg-zinc-400', 
    limited: 'bg-zinc-600', 
    weak: 'bg-red-500/60' 
  };
  const levelLabels = { exceptional: 'Exceptional', strong: 'Strong', moderate: 'Moderate', limited: 'Limited', weak: 'Weak' };
  
  // Check if meets requirement (if provided)
  const meetsReq = requirement ? levelVal[level] >= levelMin[requirement] : true;
  
  return (
    <div className={`flex items-center gap-2 py-1 ${emphasized ? 'opacity-100' : 'opacity-60'}`}>
      <span className={`text-xs w-28 truncate ${emphasized ? 'text-zinc-300' : 'text-zinc-500'}`}>{label}</span>
      <div className="flex-1 h-1.5 bg-zinc-800 rounded-full overflow-hidden">
        <div className={`h-full rounded-full ${colors[level] || 'bg-zinc-600'}`} style={{ width: widths[level] || '35%' }} />
      </div>
      <span className={`text-xs w-20 text-right ${
        level === 'exceptional' ? 'text-emerald-400 font-medium' :
        level === 'strong' ? 'text-zinc-300' :
        level === 'moderate' ? 'text-zinc-500' :
        'text-zinc-600'
      }`}>
        {levelLabels[level] || level}
      </span>
      {emphasized && requirement && (
        <span className={`text-xs w-4 ${meetsReq ? 'text-emerald-500' : 'text-red-500'}`}>
          {meetsReq ? '✓' : '✗'}
        </span>
      )}
    </div>
  );
};

export default CapabilityBar;


