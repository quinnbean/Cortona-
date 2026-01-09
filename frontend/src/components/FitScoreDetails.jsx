import React from 'react';
import { X } from 'lucide-react';
import { categoryIcons } from '../data/toolData';

// Fit Score Details Modal
const FitScoreDetails = ({ tool, breakdown, taskDef, onClose }) => {
  if (!breakdown) return null;
  
  const statusColors = {
    exceeds: 'text-emerald-400',
    meets: 'text-teal-400', 
    below: 'text-red-400'
  };
  
  const statusLabels = {
    exceeds: 'Exceeds',
    meets: 'Meets',
    below: 'Below'
  };
  
  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center p-8">
      <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
      <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-md max-h-[80vh] overflow-y-auto z-10">
        <button 
          onClick={onClose}
          className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors z-10"
        >
          <X className="w-5 h-5" />
        </button>
        
        <div className="p-6">
          {/* Header */}
          <div className="flex items-center gap-3 mb-4">
            <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg" style={{ backgroundColor: tool.bg }}>
              {categoryIcons[tool.category]}
            </div>
            <div>
              <div className="text-base font-medium text-white">{tool.name}</div>
              <div className="text-xs text-zinc-500">Fit Score Breakdown</div>
            </div>
          </div>
          
          {!breakdown.categoryMatch ? (
            // Category mismatch
            <div className="p-4 bg-red-500/10 border border-red-500/20 rounded-lg">
              <div className="text-red-400 font-medium mb-2">Category Mismatch</div>
              <p className="text-sm text-zinc-400">
                {tool.name} is a <span className="text-white">{breakdown.toolCategory}</span> tool.
              </p>
              <p className="text-sm text-zinc-400">
                This task requires: <span className="text-white">{breakdown.requiredCategories.join(', ')}</span>
              </p>
            </div>
          ) : (
            <>
              {/* Capability breakdown */}
              <div className="text-xs text-zinc-500 uppercase tracking-wider mb-3">Capability Requirements</div>
              <div className="space-y-2 mb-4">
                {breakdown.capabilityScores.map(cap => (
                  <div key={cap.dimension} className="flex items-center justify-between py-1.5 border-b border-zinc-800">
                    <span className="text-sm text-zinc-300">{cap.dimension}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-500">
                        {cap.toolLevel} vs {cap.required}
                      </span>
                      <span className={`text-xs font-medium ${statusColors[cap.status]}`}>
                        {statusLabels[cap.status]}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
              
              {/* Role bonus */}
              {breakdown.roleBonus !== 0 && breakdown.roleBonus !== undefined && (
                <div className={`p-3 ${breakdown.roleBonus > 0 ? 'bg-violet-500/10 border-violet-500/20' : 'bg-red-500/10 border-red-500/20'} border rounded-lg mb-3`}>
                  <div className={`${breakdown.roleBonus > 0 ? 'text-violet-400' : 'text-red-400'} text-sm font-medium mb-1`}>
                    {breakdown.roleBonus > 0 ? '+' : ''}{breakdown.roleBonus}% Role Fit
                  </div>
                  {breakdown.roleAdjustments?.length > 0 && (
                    <div className="text-xs text-zinc-400">
                      {breakdown.roleAdjustments.map((adj, i) => (
                        <span key={adj.dimension}>
                          {adj.dimension}: {adj.level} ({adj.bonus > 0 ? '+' : ''}{adj.bonus.toFixed(1)})
                          {i < breakdown.roleAdjustments.length - 1 && ' · '}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              )}
              
              {/* Priority breakdown */}
              {breakdown.priorityBreakdown?.length > 0 && (
                <div className="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg mb-3">
                  <div className="text-amber-400 text-sm font-medium mb-1">Priority Adjustments</div>
                  <div className="space-y-1">
                    {breakdown.priorityBreakdown.map((p, i) => (
                      <div key={i} className="flex items-center justify-between text-xs">
                        <span className="text-zinc-400">{p.name}: {p.reason}</span>
                        <span className={p.bonus > 0 ? 'text-emerald-400' : 'text-red-400'}>
                          {p.bonus > 0 ? '+' : ''}{p.bonus.toFixed(1)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
              
              {/* Other pricing notes */}
              {breakdown.pricingNotes?.length > 0 && (
                <div className={`p-3 ${breakdown.pricingAdjustment > 0 ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-orange-500/10 border-orange-500/20'} border rounded-lg mb-3`}>
                  <div className={`${breakdown.pricingAdjustment > 0 ? 'text-emerald-400' : 'text-orange-400'} text-sm font-medium mb-1`}>
                    Budget & Requirements
                  </div>
                  <div className="text-xs text-zinc-400">
                    {breakdown.pricingNotes.join(' · ')}
                  </div>
                </div>
              )}
              
              {/* Software bonus */}
              {breakdown.softwareBonus > 0 && (
                <div className="p-3 bg-teal-500/10 border border-teal-500/20 rounded-lg mb-3">
                  <div className="text-teal-400 text-sm font-medium mb-1">
                    +{breakdown.softwareBonus}% Software Compatibility
                  </div>
                  <div className="text-xs text-zinc-400">
                    Integrates with: {breakdown.matchingSoftware.join(', ')}
                  </div>
                </div>
              )}
              
              {/* Summary */}
              <div className="flex items-center justify-between pt-3 border-t border-zinc-700">
                <div className="text-sm text-zinc-400">
                  {breakdown.penaltyCount > 0 && (
                    <span className="text-red-400">{breakdown.penaltyCount} below minimum</span>
                  )}
                  {breakdown.penaltyCount > 0 && breakdown.bonusCount > 0 && ' · '}
                  {breakdown.bonusCount > 0 && (
                    <span className="text-emerald-400">{breakdown.bonusCount} exceptional</span>
                  )}
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default FitScoreDetails;


