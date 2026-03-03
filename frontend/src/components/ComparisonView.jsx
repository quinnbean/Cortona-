import React, { useMemo } from 'react';
import { categoryIcons, levelVal, taskDefinitions } from '../data/toolData';
import { capabilityProfiles, defaultProfile } from '../data/capabilityProfiles';
import { calculateTaskFitScore, getTaskFitLabel } from '../utils/scoring';

// 1-on-1 Comparison View - Compact side-by-side layout
const ComparisonView = ({ toolA, toolB, onClose, activeTask, userSoftware = [] }) => {
  const profileA = capabilityProfiles[toolA.id] || defaultProfile;
  const profileB = capabilityProfiles[toolB.id] || defaultProfile;
  const taskDef = activeTask ? taskDefinitions[activeTask] : null;
  
  const resultA = activeTask ? calculateTaskFitScore(toolA, activeTask, {}, userSoftware) : { score: 50 };
  const resultB = activeTask ? calculateTaskFitScore(toolB, activeTask, {}, userSoftware) : { score: 50 };
  const scoreA = resultA.score;
  const scoreB = resultB.score;
  
  const defaultDims = ['Output Quality', 'Accuracy', 'Speed', 'Cost Efficiency', 'Integration Ease', 'API Robustness'];
  const relevantDimensions = taskDef ? Object.keys(taskDef.requirements) : defaultDims;
  
  // Calculate wins
  let winsA = 0, winsB = 0;
  relevantDimensions.forEach(dim => {
    const vA = levelVal[profileA[dim]] || 2;
    const vB = levelVal[profileB[dim]] || 2;
    if (vA > vB) winsA++;
    else if (vB > vA) winsB++;
  });
  
  // Parse pricing to compare (extract number from string like "$30/1M tokens" or "$19/mo")
  const parsePricing = (cost) => {
    if (!cost || cost === 'Free' || cost === 'Free (self-host)') return 0;
    const match = cost.match(/\$?([\d.]+)/);
    return match ? parseFloat(match[1]) : Infinity;
  };
  
  const priceA = parsePricing(toolA.pricing?.cost);
  const priceB = parsePricing(toolB.pricing?.cost);
  const cheaperA = priceA < priceB;
  const cheaperB = priceB < priceA;
  
  const levelLabels = { exceptional: 'Exceptional', strong: 'Strong', moderate: 'Moderate', limited: 'Limited', weak: 'Weak' };
  const fitA = getTaskFitLabel(scoreA);
  const fitB = getTaskFitLabel(scoreB);
  
  const ToolCard = ({ tool, profile, score, fit, isLeft, wins, isCheaper }) => (
    <div className="flex-1 p-4 bg-zinc-800/50 rounded-xl">
      {/* Header */}
      <div className="flex items-center gap-3 mb-4 pb-3 border-b border-zinc-700">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center text-lg" style={{ backgroundColor: tool.bg }}>
          {categoryIcons[tool.category]}
        </div>
        <div className="flex-1">
          <div className="text-sm font-medium text-white">{tool.name}</div>
          <div className="text-xs text-zinc-500">{tool.provider}</div>
        </div>
        <div className={`text-lg font-bold ${fit.color}`}>{score}%</div>
      </div>
      
      {/* Capabilities */}
      <div className="space-y-2 mb-4">
        {relevantDimensions.map(dim => {
          const level = profile[dim] || 'moderate';
          const otherProfile = isLeft ? profileB : profileA;
          const otherLevel = otherProfile[dim] || 'moderate';
          const isWinner = levelVal[level] > levelVal[otherLevel];
          const isTie = levelVal[level] === levelVal[otherLevel];
          
          return (
            <div key={dim} className="flex items-center justify-between">
              <span className="text-xs text-zinc-400 truncate flex-1">{dim}</span>
              <span className={`text-xs font-medium ml-2 ${
                isWinner ? 'text-emerald-400' : isTie ? 'text-zinc-400' : 'text-zinc-600'
              }`}>
                {levelLabels[level]}
                {isWinner && ' ✓'}
              </span>
            </div>
          );
        })}
      </div>
      
      {/* Pricing */}
      <div className="pt-3 border-t border-zinc-700 space-y-2">
        <div className="flex justify-between items-center">
          <span className="text-xs text-zinc-500">Pricing</span>
          <span className={`text-xs font-medium ${isCheaper ? 'text-emerald-400' : 'text-white'}`}>
            {tool.pricing?.cost || 'N/A'}
            {isCheaper && ' ✓'}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-xs text-zinc-500">Free tier</span>
          <span className={`text-xs ${tool.pricing?.free ? 'text-emerald-400' : 'text-zinc-600'}`}>
            {tool.pricing?.free ? 'Yes' : 'No'}
          </span>
        </div>
        <div className="flex justify-between items-center">
          <span className="text-xs text-zinc-500">Compliance</span>
          <div className="flex gap-1">
            {tool.constraints?.soc2 && <span className="px-1 py-0.5 bg-emerald-500/15 text-emerald-400 text-[9px] rounded">SOC2</span>}
            {tool.constraints?.hipaa && <span className="px-1 py-0.5 bg-emerald-500/15 text-emerald-400 text-[9px] rounded">HIPAA</span>}
            {tool.constraints?.onprem && <span className="px-1 py-0.5 bg-teal-500/15 text-teal-400 text-[9px] rounded">Self-host</span>}
            {!tool.constraints?.soc2 && !tool.constraints?.hipaa && !tool.constraints?.onprem && <span className="text-xs text-zinc-600">—</span>}
          </div>
        </div>
      </div>
    </div>
  );
  
  return (
    <div>
      {/* Title Row with Wins Summary */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <div className="text-lg text-white font-medium">Head-to-Head Comparison</div>
          <div className="text-sm text-zinc-500">{taskDef ? `For: ${taskDef.label}` : 'General comparison'}</div>
        </div>
        
        {/* Wins Summary */}
        <div className="flex items-center gap-3 px-4 py-2 bg-zinc-800 rounded-lg">
          <div className="text-center">
            <div className={`text-lg font-bold ${winsA > winsB ? 'text-emerald-400' : 'text-zinc-400'}`}>{winsA}</div>
            <div className="text-[10px] text-zinc-500 truncate max-w-[60px]">{toolA.name}</div>
          </div>
          <div className="text-zinc-600 text-sm">vs</div>
          <div className="text-center">
            <div className={`text-lg font-bold ${winsB > winsA ? 'text-emerald-400' : 'text-zinc-400'}`}>{winsB}</div>
            <div className="text-[10px] text-zinc-500 truncate max-w-[60px]">{toolB.name}</div>
          </div>
        </div>
      </div>
      
      {/* Side by side cards */}
      <div className="flex gap-4">
        <ToolCard tool={toolA} profile={profileA} score={scoreA} fit={fitA} isLeft={true} wins={winsA} isCheaper={cheaperA} />
        <ToolCard tool={toolB} profile={profileB} score={scoreB} fit={fitB} isLeft={false} wins={winsB} isCheaper={cheaperB} />
      </div>
    </div>
  );
};

export default ComparisonView;


