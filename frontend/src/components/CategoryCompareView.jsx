import React, { useMemo } from 'react';
import { categoryIcons, taskDefinitions } from '../data/toolData';
import { toolData, capabilityProfiles, defaultProfile } from '../data/capabilityProfiles';
import { calculateTaskFitScore, getTaskFitLabel } from '../utils/scoring';

// Category Compare View - Clean modal version
const CategoryCompareView = ({ category, onClose, onSelectTool, referenceTool, activeTask }) => {
  const toolsInCategory = toolData.filter(t => t.category === category);
  const taskDef = activeTask ? taskDefinitions[activeTask] : null;
  
  const sortedTools = useMemo(() => {
    return [...toolsInCategory].map(t => ({
      ...t,
      fitScore: activeTask ? calculateTaskFitScore(t, activeTask, {}).score : 50
    })).sort((a, b) => b.fitScore - a.fitScore);
  }, [toolsInCategory, activeTask]);
  
  const levelLabels = { exceptional: 'Exc', strong: 'Strong', moderate: 'Med', limited: 'Low', weak: 'Weak' };
  const levelColors = { exceptional: 'text-emerald-400', strong: 'text-emerald-400', moderate: 'text-zinc-400', limited: 'text-zinc-600', weak: 'text-red-400' };
  
  // If only one tool in category, show a message
  if (sortedTools.length <= 1) {
    return (
      <div>
        <div className="text-lg text-white font-medium mb-1">All {category} Tools</div>
        <div className="text-center py-8 text-zinc-500">
          <div className="text-sm mb-2">Only one {category.toLowerCase()} tool available</div>
          <div className="text-xs">Try "Compare 1-on-1" to compare with tools from other categories</div>
        </div>
      </div>
    );
  }
  
  return (
    <div>
      <div className="text-lg text-white font-medium mb-1">All {category} Tools</div>
      <div className="text-sm text-zinc-500 mb-5">{sortedTools.length} tools to compare</div>
      
      {/* Table */}
      <div className="bg-zinc-800/30 rounded-xl overflow-hidden">
        <table className="w-full">
          <thead>
            <tr className="border-b border-zinc-700">
              <th className="text-left py-3 px-4 text-xs text-zinc-500 font-medium">Tool</th>
              <th className="text-center py-3 px-4 text-xs text-zinc-500 font-medium">Quality</th>
              <th className="text-center py-3 px-4 text-xs text-zinc-500 font-medium">Speed</th>
              <th className="text-center py-3 px-4 text-xs text-zinc-500 font-medium">Cost</th>
              <th className="text-center py-3 px-4 text-xs text-zinc-500 font-medium">Pricing</th>
              <th className="text-right py-3 px-4 text-xs text-zinc-500 font-medium">Fit Score</th>
            </tr>
          </thead>
          <tbody>
            {sortedTools.map((tool, idx) => {
              const profile = capabilityProfiles[tool.id] || defaultProfile;
              const isReference = referenceTool?.id === tool.id;
              const isBest = idx === 0;
              const fit = getTaskFitLabel(tool.fitScore);
              return (
                <tr 
                  key={tool.id}
                  onClick={() => onSelectTool(tool)}
                  className={`cursor-pointer transition-colors ${
                    isReference 
                      ? 'bg-teal-500/10' 
                      : 'hover:bg-zinc-800/50'
                  } ${idx < sortedTools.length - 1 ? 'border-b border-zinc-800' : ''}`}
                >
                  <td className="py-3 px-4">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-lg flex items-center justify-center text-sm" style={{ backgroundColor: tool.bg }}>
                        {categoryIcons[tool.category]}
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm text-zinc-200 font-medium">{tool.name}</span>
                          {isBest && <span className="text-emerald-400 text-xs">★ Best</span>}
                          {isReference && <span className="text-teal-400 text-xs">(current)</span>}
                        </div>
                        <div className="text-xs text-zinc-600">{tool.provider}</div>
                      </div>
                    </div>
                  </td>
                  <td className={`text-center py-3 px-4 text-sm ${levelColors[profile['Output Quality']]}`}>
                    {levelLabels[profile['Output Quality']]}
                  </td>
                  <td className={`text-center py-3 px-4 text-sm ${levelColors[profile['Speed']]}`}>
                    {levelLabels[profile['Speed']]}
                  </td>
                  <td className={`text-center py-3 px-4 text-sm ${levelColors[profile['Cost Efficiency']]}`}>
                    {levelLabels[profile['Cost Efficiency']]}
                  </td>
                  <td className="text-center py-3 px-4 text-sm text-zinc-400">
                    {tool.pricing?.cost || '—'}
                  </td>
                  <td className="text-right py-3 px-4">
                    <span className={`text-sm font-semibold ${fit.color}`}>{tool.fitScore}%</span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      
      <div className="mt-4 text-xs text-zinc-600 text-center">
        Click any row to view that tool's details
      </div>
    </div>
  );
};

export default CategoryCompareView;


