// ============================================
// DATA
// ============================================

// Comprehensive capability dimensions
export const allDimensions = [
  'Output Quality',      // How good is the final output
  'Accuracy',            // Factual correctness, precision
  'Speed',               // Latency, throughput
  'Cost Efficiency',     // Price per unit of work
  'API Robustness',      // Uptime, rate limits, documentation
  'Integration Ease',    // SDK quality, ecosystem support
  'Customization',       // Fine-tuning, parameters, control
  'Context Window',      // How much input it can handle
  'Multimodal',          // Support for multiple input/output types
  'Enterprise Ready',    // SOC2, SLAs, support
  'Open Source',         // Can self-host, modify
  'Streaming',           // Real-time output support
  'Batch Processing',    // Bulk operations
  'Version Control',     // Model versioning, reproducibility
];

// Task definitions with specific capability requirements and weights
export const taskDefinitions = {
  'write-content': { 
    label: 'Write content & copy', 
    categories: ['Language Model'], 
    requirements: {
      'Output Quality': { weight: 2.0, min: 'strong' },
      'Accuracy': { weight: 1.5, min: 'moderate' },
      'Customization': { weight: 1.3, min: 'moderate' },
      'Speed': { weight: 0.8, min: 'limited' },
      'Cost Efficiency': { weight: 1.0, min: 'limited' },
      'Context Window': { weight: 1.2, min: 'moderate' },
    },
    industry: 'Marketing' 
  },
  'generate-images': { 
    label: 'Generate images', 
    categories: ['Image Generation'], 
    requirements: {
      'Output Quality': { weight: 2.5, min: 'strong' },
      'Customization': { weight: 1.8, min: 'moderate' },
      'Speed': { weight: 1.0, min: 'moderate' },
      'Cost Efficiency': { weight: 1.2, min: 'limited' },
      'API Robustness': { weight: 1.0, min: 'moderate' },
      'Batch Processing': { weight: 0.8, min: 'limited' },
    },
    industry: 'Marketing' 
  },
  'create-videos': { 
    label: 'Create videos', 
    categories: ['Video Generation'], 
    requirements: {
      'Output Quality': { weight: 2.2, min: 'moderate' },
      'Customization': { weight: 1.5, min: 'moderate' },
      'Speed': { weight: 0.6, min: 'limited' },
      'Cost Efficiency': { weight: 0.8, min: 'limited' },
      'API Robustness': { weight: 1.2, min: 'moderate' },
      'Multimodal': { weight: 1.5, min: 'moderate' },
    },
    industry: 'Marketing' 
  },
  'generate-voice': { 
    label: 'Generate voiceovers', 
    categories: ['Voice'], 
    requirements: {
      'Output Quality': { weight: 2.3, min: 'strong' },
      'Customization': { weight: 1.6, min: 'moderate' },
      'Speed': { weight: 1.2, min: 'moderate' },
      'Streaming': { weight: 1.4, min: 'moderate' },
      'API Robustness': { weight: 1.0, min: 'moderate' },
      'Cost Efficiency': { weight: 0.9, min: 'limited' },
    },
    industry: 'Marketing' 
  },
  'write-code': { 
    label: 'Write & debug code', 
    categories: ['Code', 'Language Model'], 
    requirements: {
      'Accuracy': { weight: 2.5, min: 'strong' },
      'Output Quality': { weight: 1.8, min: 'strong' },
      'Context Window': { weight: 2.0, min: 'strong' },
      'Speed': { weight: 1.3, min: 'moderate' },
      'Integration Ease': { weight: 1.5, min: 'moderate' },
      'Customization': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Engineering' 
  },
  'build-agent': { 
    label: 'Build AI agents', 
    categories: ['Orchestration', 'Language Model'], 
    requirements: {
      'Integration Ease': { weight: 2.2, min: 'strong' },
      'API Robustness': { weight: 2.0, min: 'strong' },
      'Accuracy': { weight: 1.8, min: 'moderate' },
      'Streaming': { weight: 1.5, min: 'moderate' },
      'Version Control': { weight: 1.3, min: 'moderate' },
      'Open Source': { weight: 1.0, min: 'limited' },
    },
    industry: 'Engineering' 
  },
  'build-rag': { 
    label: 'Build RAG systems', 
    categories: ['Vector DB', 'Language Model', 'Orchestration'], 
    requirements: {
      'Accuracy': { weight: 2.3, min: 'strong' },
      'Integration Ease': { weight: 2.0, min: 'strong' },
      'Speed': { weight: 1.5, min: 'moderate' },
      'Context Window': { weight: 1.8, min: 'strong' },
      'Batch Processing': { weight: 1.2, min: 'moderate' },
      'Enterprise Ready': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Engineering' 
  },
  'test-prompts': { 
    label: 'Test prompts', 
    categories: ['Evaluation'], 
    requirements: {
      'Accuracy': { weight: 2.5, min: 'strong' },
      'Integration Ease': { weight: 1.8, min: 'moderate' },
      'Batch Processing': { weight: 2.0, min: 'strong' },
      'Version Control': { weight: 1.5, min: 'moderate' },
      'Open Source': { weight: 1.2, min: 'moderate' },
      'Cost Efficiency': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Engineering' 
  },
  'monitor-llm': { 
    label: 'Monitor LLMs', 
    categories: ['Observability'], 
    requirements: {
      'Integration Ease': { weight: 2.2, min: 'strong' },
      'Enterprise Ready': { weight: 2.0, min: 'strong' },
      'Speed': { weight: 1.5, min: 'strong' },
      'Batch Processing': { weight: 1.3, min: 'moderate' },
      'Version Control': { weight: 1.2, min: 'moderate' },
      'Cost Efficiency': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Engineering' 
  },
  'analyze-calls': { 
    label: 'Analyze calls', 
    categories: ['Speech', 'Language Model'], 
    requirements: {
      'Accuracy': { weight: 2.5, min: 'strong' },
      'Speed': { weight: 1.8, min: 'strong' },
      'Context Window': { weight: 1.5, min: 'moderate' },
      'Batch Processing': { weight: 1.3, min: 'moderate' },
      'Enterprise Ready': { weight: 1.2, min: 'moderate' },
      'Cost Efficiency': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Sales' 
  },
  'research-leads': { 
    label: 'Research prospects', 
    categories: ['Search', 'Language Model'], 
    requirements: {
      'Accuracy': { weight: 2.3, min: 'strong' },
      'Speed': { weight: 1.5, min: 'moderate' },
      'Integration Ease': { weight: 1.3, min: 'moderate' },
      'Cost Efficiency': { weight: 1.2, min: 'moderate' },
      'API Robustness': { weight: 1.0, min: 'moderate' },
      'Batch Processing': { weight: 0.8, min: 'limited' },
    },
    industry: 'Sales' 
  },
  'write-outreach': { 
    label: 'Write outreach', 
    categories: ['Language Model'], 
    requirements: {
      'Output Quality': { weight: 2.0, min: 'strong' },
      'Customization': { weight: 1.8, min: 'strong' },
      'Speed': { weight: 1.5, min: 'moderate' },
      'Cost Efficiency': { weight: 1.3, min: 'moderate' },
      'Batch Processing': { weight: 1.2, min: 'moderate' },
      'API Robustness': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Sales' 
  },
  'edit-photos': { 
    label: 'Edit photos', 
    categories: ['Image Generation'], 
    requirements: {
      'Output Quality': { weight: 2.3, min: 'strong' },
      'Customization': { weight: 2.0, min: 'strong' },
      'Speed': { weight: 1.2, min: 'moderate' },
      'Multimodal': { weight: 1.5, min: 'strong' },
      'Batch Processing': { weight: 1.0, min: 'moderate' },
      'Cost Efficiency': { weight: 0.8, min: 'limited' },
    },
    industry: 'Creative' 
  },
  'create-music': { 
    label: 'Create music', 
    categories: ['Voice'], 
    requirements: {
      'Output Quality': { weight: 2.5, min: 'strong' },
      'Customization': { weight: 2.0, min: 'strong' },
      'Speed': { weight: 0.8, min: 'limited' },
      'API Robustness': { weight: 1.0, min: 'moderate' },
      'Cost Efficiency': { weight: 0.7, min: 'limited' },
      'Streaming': { weight: 1.2, min: 'moderate' },
    },
    industry: 'Creative' 
  },
  'design-assets': { 
    label: 'Design assets', 
    categories: ['Image Generation'], 
    requirements: {
      'Output Quality': { weight: 2.2, min: 'strong' },
      'Customization': { weight: 2.0, min: 'strong' },
      'Batch Processing': { weight: 1.5, min: 'moderate' },
      'Speed': { weight: 1.3, min: 'moderate' },
      'API Robustness': { weight: 1.2, min: 'moderate' },
      'Cost Efficiency': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Creative' 
  },
  'add-safety': { 
    label: 'Add guardrails', 
    categories: ['Guardrails'], 
    requirements: {
      'Accuracy': { weight: 2.8, min: 'strong' },
      'Speed': { weight: 2.0, min: 'strong' },
      'Integration Ease': { weight: 1.8, min: 'strong' },
      'Enterprise Ready': { weight: 1.5, min: 'moderate' },
      'Customization': { weight: 1.3, min: 'moderate' },
      'Open Source': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Enterprise' 
  },
  'manage-models': { 
    label: 'Manage models', 
    categories: ['Governance', 'Observability'], 
    requirements: {
      'Enterprise Ready': { weight: 2.5, min: 'strong' },
      'Integration Ease': { weight: 2.0, min: 'strong' },
      'Version Control': { weight: 1.8, min: 'strong' },
      'Speed': { weight: 1.3, min: 'moderate' },
      'Cost Efficiency': { weight: 1.2, min: 'moderate' },
      'API Robustness': { weight: 1.5, min: 'strong' },
    },
    industry: 'Enterprise' 
  },
  'ensure-compliance': { 
    label: 'Ensure compliance', 
    categories: ['Guardrails'], 
    requirements: {
      'Accuracy': { weight: 2.8, min: 'strong' },
      'Enterprise Ready': { weight: 2.5, min: 'strong' },
      'Version Control': { weight: 1.8, min: 'strong' },
      'Integration Ease': { weight: 1.5, min: 'moderate' },
      'Customization': { weight: 1.3, min: 'moderate' },
      'Speed': { weight: 1.0, min: 'moderate' },
    },
    industry: 'Enterprise' 
  },
};

export const industryData = {
  'Marketing': { label: 'Marketing', tasks: ['write-content', 'generate-images', 'create-videos', 'generate-voice'], relevantCategories: ['Language Model', 'Image Generation', 'Voice', 'Video Generation'] },
  'Engineering': { label: 'Engineering', tasks: ['write-code', 'build-agent', 'build-rag', 'test-prompts', 'monitor-llm'], relevantCategories: ['Code', 'Language Model', 'Orchestration', 'Evaluation', 'Vector DB', 'Observability'] },
  'Sales': { label: 'Sales', tasks: ['analyze-calls', 'research-leads', 'write-outreach'], relevantCategories: ['Language Model', 'Voice', 'Speech', 'Search'] },
  'Creative': { label: 'Creative', tasks: ['generate-images', 'create-videos', 'edit-photos', 'create-music', 'design-assets'], relevantCategories: ['Image Generation', 'Video Generation', 'Voice', 'Language Model'] },
  'Enterprise': { label: 'Enterprise', tasks: ['add-safety', 'manage-models', 'ensure-compliance', 'build-rag'], relevantCategories: ['Language Model', 'Guardrails', 'Governance', 'Vector DB', 'Observability'] },
};

export const categoryIcons = { 
  'Language Model': '🧠', 
  'Image Generation': '🎨', 
  'Video Generation': '🎬', 
  'Orchestration': '🔗', 
  'Search': '🔍', 
  'Code': '💻', 
  'Voice': '🎙️', 
  'Speech': '👂', 
  'Evaluation': '📊', 
  'Observability': '👁️', 
  'Vector DB': '📦', 
  'Guardrails': '🛡️', 
  'Governance': '⚙️' 
};

// Level values for scoring - exceptional is rare and valuable
export const levelVal = { exceptional: 5, strong: 4, moderate: 3, limited: 2, weak: 1 };
export const levelMin = { exceptional: 5, strong: 4, moderate: 3, limited: 2, weak: 1 };


