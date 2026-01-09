import { taskDefinitions, levelVal, levelMin } from '../data/toolData';
import { capabilityProfiles, defaultProfile, userRoles } from '../data/capabilityProfiles';

// ============================================
// SCORING - Much more rigorous
// ============================================

export const calculateTaskFitScore = (tool, task, filters = {}, userSoftware = []) => {
  const taskDef = taskDefinitions[task];
  if (!taskDef) return { score: 20, breakdown: null };
  
  // Must be in a relevant category
  if (!taskDef.categories.includes(tool.category)) {
    return { 
      score: 5, 
      breakdown: {
        categoryMatch: false,
        requiredCategories: taskDef.categories,
        toolCategory: tool.category,
        capabilityScores: [],
        softwareBonus: 0,
        matchingSoftware: []
      }
    };
  }
  
  const profile = capabilityProfiles[tool.id] || defaultProfile;
  const requirements = taskDef.requirements;
  
  let totalScore = 0;
  let totalWeight = 0;
  let penaltyCount = 0;
  let bonusCount = 0;
  const capabilityScores = [];
  
  // Evaluate each required dimension
  Object.entries(requirements).forEach(([dim, req]) => {
    const toolLevel = profile[dim] || 'limited';
    const toolValue = levelVal[toolLevel] || 2;
    const minRequired = levelMin[req.min] || 3;
    const weight = req.weight;
    
    totalWeight += weight;
    
    let dimScore = 0;
    let status = 'meets';
    
    // Score based on how well tool meets requirement
    if (toolValue >= 5) {
      // Exceptional - full points plus bonus
      dimScore = weight * 1.0;
      bonusCount++;
      status = 'exceeds';
    } else if (toolValue >= minRequired) {
      // Meets or exceeds minimum
      const excess = (toolValue - minRequired) / (5 - minRequired);
      dimScore = weight * (0.6 + excess * 0.3);
      status = toolValue > minRequired ? 'exceeds' : 'meets';
    } else {
      // Below minimum - penalty
      const deficit = (minRequired - toolValue) / minRequired;
      dimScore = weight * Math.max(0.1, 0.5 - deficit * 0.4);
      penaltyCount++;
      status = 'below';
    }
    
    totalScore += dimScore;
    capabilityScores.push({
      dimension: dim,
      toolLevel,
      required: req.min,
      weight,
      score: dimScore,
      maxScore: weight,
      status
    });
  });
  
  // Base percentage (0-100)
  let baseScore = (totalScore / totalWeight) * 100;
  
  // Apply penalties for missing minimums
  if (penaltyCount > 0) {
    baseScore *= Math.pow(0.85, penaltyCount);
  }
  
  // Small bonus for exceptional ratings (but capped)
  if (bonusCount >= 3) {
    baseScore = Math.min(baseScore * 1.05, 92);
  }
  
  // Filter penalties
  if (filters.budget === 'free' && !tool.pricing?.free) {
    baseScore *= 0.85;
  }
  
  // Role-based scoring adjustments
  let roleBonus = 0;
  let roleAdjustments = [];
  
  if (filters.role) {
    const role = userRoles.find(r => r.id === filters.role);
    if (role && role.priorities) {
      Object.entries(role.priorities).forEach(([dim, multiplier]) => {
        const toolLevel = profile[dim] || 'limited';
        const toolValue = levelVal[toolLevel] || 2;
        
        if (toolValue >= 4) { // Strong or exceptional
          const bonus = (multiplier - 1) * 5 * (toolValue / 5);
          roleBonus += bonus;
          roleAdjustments.push({ dimension: dim, bonus: bonus, level: toolLevel });
        } else if (toolValue <= 2) { // Limited or weak - penalty for important dimensions
          const penalty = (multiplier - 1) * 3;
          roleBonus -= penalty;
          roleAdjustments.push({ dimension: dim, bonus: -penalty, level: toolLevel });
        }
      });
    }
  }
  baseScore += roleBonus;
  
  // Pricing preference adjustments
  let pricingAdjustment = 0;
  let pricingNotes = [];
  let priorityBreakdown = [];
  
  // Parse tool price
  const parsePrice = (cost) => {
    if (!cost || cost === 'Free' || cost === 'Free (self-host)') return 0;
    const match = cost.match(/\$?([\d.]+)/);
    return match ? parseFloat(match[1]) : 100;
  };
  const toolPrice = parsePrice(tool.pricing?.cost);
  
  // Monthly budget filter
  if (filters.monthlyBudget && filters.monthlyBudget !== '') {
    const budget = parseFloat(filters.monthlyBudget);
    if (!isNaN(budget)) {
      if (toolPrice > budget) {
        pricingAdjustment -= 25;
        pricingNotes.push(`Over budget ($${toolPrice} > $${budget}/mo)`);
      } else if (toolPrice === 0) {
        pricingAdjustment += 5;
        pricingNotes.push('Free tool');
      } else if (toolPrice <= budget * 0.5) {
        pricingAdjustment += 3;
        pricingNotes.push('Well under budget');
      }
    }
  }
  
  // Priority-based adjustments (each priority 0-100, affects scoring)
  const priorities = filters.priorities || {};
  
  // Cost priority - higher = prefer cheaper tools
  if (priorities.cost > 20) {
    const costWeight = (priorities.cost - 20) / 80; // 0 to 1
    if (toolPrice === 0) {
      const bonus = costWeight * 10;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Cost', bonus, reason: 'Free tool' });
    } else if (toolPrice <= 30) {
      const bonus = costWeight * 5;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Cost', bonus, reason: 'Low cost' });
    } else if (toolPrice >= 100) {
      const penalty = costWeight * -6;
      pricingAdjustment += penalty;
      priorityBreakdown.push({ name: 'Cost', bonus: penalty, reason: 'High cost' });
    }
  }
  
  // Quality priority - higher = prefer high output quality tools
  if (priorities.quality > 20) {
    const qualityWeight = (priorities.quality - 20) / 80;
    const qualityLevel = profile['Output Quality'] || 'moderate';
    const qualityVal = levelVal[qualityLevel] || 3;
    if (qualityVal >= 4) {
      const bonus = qualityWeight * 8;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Quality', bonus, reason: `${qualityLevel} quality` });
    } else if (qualityVal <= 2) {
      const penalty = qualityWeight * -5;
      pricingAdjustment += penalty;
      priorityBreakdown.push({ name: 'Quality', bonus: penalty, reason: `${qualityLevel} quality` });
    }
  }
  
  // Speed priority - higher = prefer faster tools
  if (priorities.speed > 20) {
    const speedWeight = (priorities.speed - 20) / 80;
    const speedLevel = profile['Speed'] || 'moderate';
    const speedVal = levelVal[speedLevel] || 3;
    if (speedVal >= 4) {
      const bonus = speedWeight * 7;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Speed', bonus, reason: `${speedLevel} speed` });
    } else if (speedVal <= 2) {
      const penalty = speedWeight * -4;
      pricingAdjustment += penalty;
      priorityBreakdown.push({ name: 'Speed', bonus: penalty, reason: `${speedLevel} speed` });
    }
  }
  
  // Ease of use priority
  if (priorities.easeOfUse > 20) {
    const easeWeight = (priorities.easeOfUse - 20) / 80;
    const easeLevel = profile['Integration Ease'] || 'moderate';
    const easeVal = levelVal[easeLevel] || 3;
    if (easeVal >= 4) {
      const bonus = easeWeight * 6;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Ease of Use', bonus, reason: `${easeLevel} integration` });
    } else if (easeVal <= 2) {
      const penalty = easeWeight * -4;
      pricingAdjustment += penalty;
      priorityBreakdown.push({ name: 'Ease of Use', bonus: penalty, reason: `${easeLevel} integration` });
    }
  }
  
  // Support priority
  if (priorities.support > 20) {
    const supportWeight = (priorities.support - 20) / 80;
    const isEnterprise = profile['Enterprise Ready'] === 'strong' || profile['Enterprise Ready'] === 'exceptional';
    const hasGoodSupport = tool.constraints?.soc2 || isEnterprise;
    if (hasGoodSupport) {
      const bonus = supportWeight * 6;
      pricingAdjustment += bonus;
      priorityBreakdown.push({ name: 'Support', bonus, reason: 'Enterprise support' });
    }
  }
  
  // Require free tier
  if (filters.requireFreeTier && !tool.pricing?.free) {
    pricingAdjustment -= 15;
    pricingNotes.push('No free tier');
  }
  
  // Prefer open source
  if (filters.preferOpenSource) {
    const isOpenSource = profile['Open Source'] === 'exceptional' || tool.constraints?.onprem;
    if (isOpenSource) {
      pricingAdjustment += 8;
      pricingNotes.push('Open source bonus');
    }
  }
  
  // Require self-host
  if (filters.requireSelfHost && !tool.constraints?.onprem) {
    pricingAdjustment -= 25;
    pricingNotes.push('Cannot self-host');
  }
  
  // Compliance requirements
  if (filters.requireSOC2 && !tool.constraints?.soc2) {
    pricingAdjustment -= 20;
    pricingNotes.push('No SOC2');
  }
  if (filters.requireHIPAA && !tool.constraints?.hipaa) {
    pricingAdjustment -= 25;
    pricingNotes.push('No HIPAA');
  }
  
  baseScore += pricingAdjustment;
  
  // Software compatibility bonus
  let softwareBonus = 0;
  const matchingSoftware = [];
  
  if (userSoftware.length > 0 && tool.software) {
    // Normalize software names for matching
    const normalizeForMatch = (name) => name.toLowerCase().replace(/[^a-z0-9]/g, '');
    
    const toolSoftwareNormalized = tool.software.map(s => ({
      original: s,
      normalized: normalizeForMatch(s)
    }));
    
    userSoftware.forEach(userSw => {
      const userSwNormalized = normalizeForMatch(userSw);
      const match = toolSoftwareNormalized.find(ts => 
        ts.normalized.includes(userSwNormalized) || 
        userSwNormalized.includes(ts.normalized) ||
        // Special cases
        (userSw === 'google-workspace' && ts.normalized.includes('google')) ||
        (userSw === 'microsoft-365' && ts.normalized.includes('microsoft')) ||
        (userSw === 'adobe' && ts.normalized.includes('adobe')) ||
        (userSw === 'vscode' && ts.normalized.includes('vscode')) ||
        (userSw === 'teams' && ts.normalized.includes('teams'))
      );
      
      if (match) {
        matchingSoftware.push(match.original);
      }
    });
    
    // Bonus: up to 8 points for software matches
    if (matchingSoftware.length > 0) {
      softwareBonus = Math.min(matchingSoftware.length * 3, 8);
      baseScore += softwareBonus;
    }
  }
  
  // Cap at 95 - nothing is perfect
  const finalScore = Math.max(5, Math.min(95, Math.round(baseScore)));
  
  return {
    score: finalScore,
    breakdown: {
      categoryMatch: true,
      requiredCategories: taskDef.categories,
      toolCategory: tool.category,
      capabilityScores,
      penaltyCount,
      bonusCount,
      softwareBonus,
      matchingSoftware,
      roleBonus: Math.round(roleBonus),
      roleAdjustments,
      pricingAdjustment: Math.round(pricingAdjustment),
      pricingNotes,
      priorityBreakdown,
      baseScoreBeforeSoftware: Math.round(baseScore - softwareBonus)
    }
  };
};

// Simple version that just returns the score number (for backward compatibility)
export const getTaskFitScoreSimple = (tool, task, filters = {}, userSoftware = []) => {
  const result = calculateTaskFitScore(tool, task, filters, userSoftware);
  return typeof result === 'object' ? result.score : result;
};

export const getTaskFitLabel = (score) => {
  if (score >= 85) return { label: 'Excellent fit', color: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/20' };
  if (score >= 70) return { label: 'Good fit', color: 'text-teal-400', bg: 'bg-teal-500/10', border: 'border-teal-500/20' };
  if (score >= 55) return { label: 'Viable', color: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/20' };
  if (score >= 40) return { label: 'Tradeoffs', color: 'text-orange-400', bg: 'bg-orange-500/10', border: 'border-orange-500/20' };
  return { label: 'Poor fit', color: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/20' };
};


