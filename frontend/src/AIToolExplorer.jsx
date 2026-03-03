import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Search, X, Plus, Minus, Layers, DollarSign, Shield, ArrowRight, Sparkles, ChevronDown, Target, GitCompare, BarChart3 } from 'lucide-react';

// Data imports
import { taskDefinitions, industryData, categoryIcons } from './data/toolData';
import { capabilityProfiles, defaultProfile, toolData, availableSoftware, userRoles } from './data/capabilityProfiles';

// Utility imports
import { calculateTaskFitScore, getTaskFitLabel } from './utils/scoring';

// Component imports
import CapabilityBar from './components/CapabilityBar';
import FitScoreBadge from './components/FitScoreBadge';
import ComparisonView from './components/ComparisonView';
import CategoryCompareView from './components/CategoryCompareView';

// Max total points for priorities
const MAX_PRIORITY_POINTS = 100;

export default function AIToolExplorer() {
  const [activeTask, setActiveTask] = useState(null);
  const [activeIndustry, setActiveIndustry] = useState(null);
  const [selectedTool, setSelectedTool] = useState(null);
  const [currentStack, setCurrentStack] = useState([]);
  const [hoveredTool, setHoveredTool] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [zoomLevel, setZoomLevel] = useState(1);
  const [compareTarget, setCompareTarget] = useState(null);
  const [showCompareMenu, setShowCompareMenu] = useState(false);
  const [showCategoryCompare, setShowCategoryCompare] = useState(false);
  const [isExploringMode, setIsExploringMode] = useState(false);
  const [userSoftware, setUserSoftware] = useState([]);
  const [showSoftwareSelector, setShowSoftwareSelector] = useState(false);
  const [isDragging, setIsDragging] = useState(false);
  
  // Role preferences
  const [userRole, setUserRole] = useState(null);
  const [showRoleSelector, setShowRoleSelector] = useState(false);
  
  // Pricing preferences - with priority allocation (total must be <= 100)
  const [pricingPrefs, setPricingPrefs] = useState({
    monthlyBudget: '',
    priorities: {
      cost: 20,
      quality: 20,
      speed: 20,
      easeOfUse: 20,
      support: 20,
    },
    requireFreeTier: false,
    preferOpenSource: false,
    requireSelfHost: false,
    requireSOC2: false,
    requireHIPAA: false,
  });
  const [showPricingSelector, setShowPricingSelector] = useState(false);
  
  // State for fit score detail modal
  const [showFitDetails, setShowFitDetails] = useState(false);

  const canvasRef = useRef(null);
  const rotation = useRef({ x: 0, y: 0 });
  const targetRotation = useRef(null);
  const dragging = useRef(false);
  const lastMouse = useRef({ x: 0, y: 0 });
  const velocity = useRef({ x: 0.0005, y: 0 });
  const points = useRef([]);
  const rendered = useRef([]);

  // Determine if we're in "exploring" mode
  const isExploring = activeIndustry !== null || isExploringMode;

  const inStack = useCallback((id) => currentStack.some(t => t.id === id), [currentStack]);
  const taskDef = activeTask ? taskDefinitions[activeTask] : null;
  
  // Build filters object from preferences
  const filters = useMemo(() => ({
    ...pricingPrefs,
    role: userRole,
  }), [pricingPrefs, userRole]);

  const rankedTools = useMemo(() => {
    if (!activeTask) return toolData.map(t => ({ ...t, fitScore: 50, fitBreakdown: null }));
    return toolData.map(t => {
      const result = calculateTaskFitScore(t, activeTask, filters, userSoftware);
      return { ...t, fitScore: result.score, fitBreakdown: result.breakdown };
    }).sort((a, b) => b.fitScore - a.fitScore);
  }, [activeTask, filters, userSoftware]);

  // Search filtered tools
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const query = searchQuery.toLowerCase().trim();
    return rankedTools.filter(tool => 
      tool.name.toLowerCase().includes(query) ||
      tool.category.toLowerCase().includes(query) ||
      tool.provider?.toLowerCase().includes(query) ||
      tool.guidance?.toLowerCase().includes(query) ||
      tool.software?.some(s => s.toLowerCase().includes(query))
    ).slice(0, 8);
  }, [searchQuery, rankedTools]);

  const topTools = useMemo(() => {
    if (!activeTask) return [];
    const taskDefinition = taskDefinitions[activeTask];
    if (!taskDefinition) return [];
    return rankedTools.filter(t => taskDefinition.categories.includes(t.category)).slice(0, 4);
  }, [activeTask, rankedTools]);

  // Select task but stay in preview mode
  const handleTaskSelect = useCallback((taskKey) => {
    if (activeTask === taskKey) {
      setActiveTask(null);
    } else {
      setActiveTask(taskKey);
    }
    setSelectedTool(null);
    setCompareTarget(null);
    setShowCompareMenu(false);
    setShowCategoryCompare(false);
    setShowFitDetails(false);
  }, [activeTask]);

  // Clear everything and go back
  const clearAll = useCallback(() => {
    setActiveIndustry(null);
    setActiveTask(null);
    setSelectedTool(null);
    setIsExploringMode(false);
    setShowFitDetails(false);
  }, []);

  const toggleStack = useCallback((tool) => {
    setCurrentStack(prev => {
      if (prev.some(t => t.id === tool.id)) return prev.filter(t => t.id !== tool.id);
      if (prev.length >= 8) return prev;
      return [...prev, tool];
    });
  }, []);

  // Normalize angle to be between -PI and PI
  const normalizeAngle = (angle) => {
    while (angle > Math.PI) angle -= Math.PI * 2;
    while (angle < -Math.PI) angle += Math.PI * 2;
    return angle;
  };

  const centerOnTool = useCallback((tool) => {
    const point = points.current.find(p => p.id === tool.id);
    if (point) {
      // Calculate target rotation
      const targetX = -point.lon;
      const targetY = -point.lat * 0.5;
      
      // Normalize the target relative to current position to take shortest path
      const currentX = rotation.current.x;
      let dx = targetX - currentX;
      
      // Adjust dx to take the shortest path around the globe
      dx = normalizeAngle(dx);
      
      targetRotation.current = { 
        x: currentX + dx, 
        y: targetY 
      };
    }
  }, []);

  useEffect(() => {
    const phi = Math.PI * (3 - Math.sqrt(5));
    points.current = toolData.map((tool, i) => ({ lat: Math.asin(1 - (i / (toolData.length - 1)) * 2), lon: phi * i, ...tool }));
  }, []);

  useEffect(() => { if (selectedTool) centerOnTool(selectedTool); }, [selectedTool, centerOnTool]);
  
  // Close fit details when selecting a different tool
  useEffect(() => {
    setShowFitDetails(false);
  }, [selectedTool]);

  // Globe rendering effect
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !points.current.length) return;
    const ctx = canvas.getContext('2d');
    let frame;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      if (canvas.width !== canvas.offsetWidth * dpr) {
        canvas.width = canvas.offsetWidth * dpr;
        canvas.height = canvas.offsetHeight * dpr;
        ctx.scale(dpr, dpr);
      }
      const w = canvas.offsetWidth, h = canvas.offsetHeight;
      
      const grad = ctx.createRadialGradient(w/2, h/2, 0, w/2, h/2, Math.max(w,h)/1.5);
      grad.addColorStop(0, '#0a0a0a');
      grad.addColorStop(1, '#030303');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, w, h);

      if (!dragging.current) {
        if (targetRotation.current) {
          let dx = targetRotation.current.x - rotation.current.x;
          let dy = targetRotation.current.y - rotation.current.y;
          
          // Normalize dx to shortest path (in case rotation drifted)
          while (dx > Math.PI) dx -= Math.PI * 2;
          while (dx < -Math.PI) dx += Math.PI * 2;
          
          if (Math.abs(dx) < 0.01 && Math.abs(dy) < 0.01) {
            targetRotation.current = null;
            // Normalize rotation to prevent accumulation
            rotation.current.x = rotation.current.x % (Math.PI * 2);
          } else { 
            rotation.current.x += dx * 0.1; // Slightly faster interpolation
            rotation.current.y += dy * 0.1; 
          }
        } else {
          rotation.current.x += velocity.current.x;
          rotation.current.y += velocity.current.y;
          rotation.current.y = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, rotation.current.y));
          velocity.current.x *= 0.98;
          velocity.current.y *= 0.98;
          if (Math.abs(velocity.current.x) < 0.0002 && Math.abs(velocity.current.y) < 0.0001) {
            velocity.current.x = 0.0003;
          }
        }
      }

      const cx = w / 2, cy = h / 2;
      const baseR = Math.min(cx, cy) * 0.95;
      const rx = baseR * zoomLevel, ry = baseR * zoomLevel * 0.95;

      // Subtle glow
      const glowGrad = ctx.createRadialGradient(cx, cy, rx * 0.5, cx, cy, rx * 1.3);
      glowGrad.addColorStop(0, 'rgba(255,255,255,0.02)');
      glowGrad.addColorStop(1, 'transparent');
      ctx.fillStyle = glowGrad;
      ctx.fillRect(0, 0, w, h);

      const time = Date.now() * 0.001;
      
      // Outer ellipse
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.08)';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      
      // Outer glow ring
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx + 2, ry + 1.5, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.03)';
      ctx.lineWidth = 4;
      ctx.stroke();

      // Latitude lines
      const latitudes = [-0.6, -0.3, 0, 0.3, 0.6];
      latitudes.forEach(lat => {
        const latRadius = Math.cos(Math.asin(lat));
        const yOffset = lat * ry;
        const xRadius = latRadius * rx;
        ctx.beginPath();
        ctx.ellipse(cx, cy - yOffset, xRadius, xRadius * 0.15, 0, 0, Math.PI * 2);
        ctx.strokeStyle = `rgba(255, 255, 255, ${0.04 + Math.abs(lat) * 0.02})`;
        ctx.lineWidth = 0.5;
        ctx.stroke();
      });

      // Longitude lines
      const numMeridians = 8;
      for (let i = 0; i < numMeridians; i++) {
        const lon = (i / numMeridians) * Math.PI * 2 + rotation.current.x;
        const cosLon = Math.cos(lon);
        const sinLon = Math.sin(lon);
        
        if (sinLon > -0.2) {
          ctx.beginPath();
          for (let j = 0; j <= 32; j++) {
            const lat = (j / 32) * Math.PI - Math.PI / 2;
            const cLat = Math.cos(lat);
            const sLat = Math.sin(lat);
            const cTilt = Math.cos(rotation.current.y);
            const sTilt = Math.sin(rotation.current.y);
            const x3d = cLat * sinLon;
            const y3d = sLat * cTilt - cLat * cosLon * sTilt;
            const z3d = sLat * sTilt + cLat * cosLon * cTilt;
            if (z3d > -0.1) {
              const px = cx + x3d * rx;
              const py = cy - y3d * ry;
              if (j === 0 || z3d <= -0.1) {
                ctx.moveTo(px, py);
              } else {
                ctx.lineTo(px, py);
              }
            }
          }
          const alpha = 0.03 + sinLon * 0.03;
          ctx.strokeStyle = `rgba(255, 255, 255, ${Math.max(0.02, alpha)})`;
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }

      // Center meridian
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx * 0.02, ry, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      // Equator
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx, ry * 0.02, 0, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.06)';
      ctx.lineWidth = 0.5;
      ctx.stroke();

      const taskCategories = taskDef ? taskDef.categories : [];
      const industryCategories = activeIndustry ? industryData[activeIndustry]?.relevantCategories || [] : [];

      // Calculate 3D positions
      const sorted = points.current.map(p => {
        const cLat = Math.cos(p.lat), sLat = Math.sin(p.lat);
        const cLon = Math.cos(p.lon + rotation.current.x), sLon = Math.sin(p.lon + rotation.current.x);
        const cTilt = Math.cos(rotation.current.y), sTilt = Math.sin(rotation.current.y);
        return { ...p, x: cLat * sLon, y: sLat * cTilt - cLat * cLon * sTilt, z: sLat * sTilt + cLat * cLon * cTilt };
      }).sort((a, b) => a.z - b.z);

      // Position map for connections
      const positionMap = {};
      sorted.forEach(p => {
        if (p.z > -0.3) {
          const px = cx + p.x * rx;
          const py = cy - p.y * ry;
          positionMap[p.id] = { px, py, z: p.z, visible: p.z > -0.1 };
        }
      });

      // Draw connections
      const connectionsDrawn = new Set();
      sorted.forEach(p => {
        if (p.z > -0.1 && p.compatible) {
          p.compatible.forEach(compatId => {
            const connId = [p.id, compatId].sort().join('-');
            if (connectionsDrawn.has(connId)) return;
            connectionsDrawn.add(connId);
            
            const targetPos = positionMap[compatId];
            if (!targetPos || !targetPos.visible) return;
            const sourcePos = positionMap[p.id];
            if (!sourcePos) return;
            
            const isSelectedConnection = selectedTool && (p.id === selectedTool.id || compatId === selectedTool.id);
            const avgZ = (p.z + targetPos.z) / 2;
            let baseAlpha = Math.max(0, (avgZ + 0.5) * 0.4);
            if (isSelectedConnection) baseAlpha = Math.max(0.5, (avgZ + 0.5) * 0.9);
            
            const phase = (p.id + compatId) * 0.5;
            const pulseSpeed = isSelectedConnection ? 2.5 : 1.8;
            const pulse = 0.5 + 0.5 * Math.sin(time * pulseSpeed + phase);
            
            const dx = targetPos.px - sourcePos.px;
            const dy = targetPos.py - sourcePos.py;
            const dist = Math.sqrt(dx * dx + dy * dy);
            const distAlpha = Math.max(0.4, 1 - dist / (rx * 2.5));
            
            let finalAlpha = baseAlpha * (0.4 + pulse * 0.6) * distAlpha;
            if (!selectedTool && !activeTask) finalAlpha *= 0.7;
            if (finalAlpha < 0.02) return;
            
            const midX = (sourcePos.px + targetPos.px) / 2;
            const midY = (sourcePos.py + targetPos.py) / 2;
            const toCenterX = cx - midX;
            const toCenterY = cy - midY;
            const toCenterDist = Math.sqrt(toCenterX * toCenterX + toCenterY * toCenterY);
            const curveAmount = dist * 0.2;
            const ctrlX = midX - (toCenterX / toCenterDist) * curveAmount;
            const ctrlY = midY - (toCenterY / toCenterDist) * curveAmount;
            
            ctx.beginPath();
            ctx.moveTo(sourcePos.px, sourcePos.py);
            ctx.quadraticCurveTo(ctrlX, ctrlY, targetPos.px, targetPos.py);
            
            let lineColor = isSelectedConnection 
              ? `rgba(52, 211, 153, ${finalAlpha})`
              : `rgba(255, 255, 255, ${finalAlpha})`;
            
            if (!isSelectedConnection) {
              const gradient = ctx.createLinearGradient(sourcePos.px, sourcePos.py, targetPos.px, targetPos.py);
              gradient.addColorStop(0, `rgba(255, 255, 255, ${finalAlpha * 0.3})`);
              gradient.addColorStop(0.5, `rgba(255, 255, 255, ${finalAlpha})`);
              gradient.addColorStop(1, `rgba(255, 255, 255, ${finalAlpha * 0.3})`);
              lineColor = gradient;
            }
            
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = isSelectedConnection ? (1.5 + pulse * 1.5) : (1 + pulse * 0.8);
            ctx.stroke();
            
            if (isSelectedConnection) {
              ctx.strokeStyle = `rgba(52, 211, 153, ${finalAlpha * 0.3})`;
              ctx.lineWidth = 6 + pulse * 4;
              ctx.stroke();
              ctx.strokeStyle = `rgba(52, 211, 153, ${finalAlpha * 0.1})`;
              ctx.lineWidth = 12 + pulse * 6;
              ctx.stroke();
            } else if (finalAlpha > 0.08) {
              ctx.strokeStyle = `rgba(255, 255, 255, ${finalAlpha * 0.25})`;
              ctx.lineWidth = 3 + pulse * 1.5;
              ctx.stroke();
            }
          });
        }
      });

      // Draw tool nodes
      const rnd = [];
      sorted.forEach(p => {
        if (p.z > -0.1) {
          const scale = (p.z + 1) / 2;
          const px = cx + p.x * rx, py = cy - p.y * ry;
          
          const isSel = selectedTool?.id === p.id;
          const isHov = hoveredTool?.id === p.id;
          const isStk = inStack(p.id);
          const isComp = selectedTool?.compatible?.includes(p.id);
          
          const toolRanked = rankedTools.find(t => t.id === p.id);
          const isHighFit = activeTask && toolRanked && toolRanked.fitScore >= 70;
          const isMedFit = activeTask && toolRanked && toolRanked.fitScore >= 50;
          const isTaskRelevant = taskCategories.includes(p.category);
          const isIndustryRelevant = industryCategories.includes(p.category);

          let alpha = scale * 0.6;
          let size = Math.max(14, Math.floor((16 + scale * 16) * Math.sqrt(zoomLevel)));

          if (!activeTask && !activeIndustry) {
            alpha = scale * 0.4;
          } else if (activeTask) {
            if (isHighFit) { alpha = 1; size *= 1.15; }
            else if (isMedFit) alpha = 0.7;
            else if (isTaskRelevant) alpha = 0.35;
            else alpha = 0.1;
          } else if (activeIndustry) {
            if (isIndustryRelevant) alpha = scale * 0.8;
            else alpha = 0.12;
          }

          if (isStk) alpha = Math.max(0.95, alpha);
          if (isSel) alpha = 1;

          ctx.globalAlpha = alpha;
          
          if (isHighFit && activeTask) {
            ctx.shadowColor = p.bg;
            ctx.shadowBlur = 25;
          }
          
          ctx.beginPath();
          ctx.arc(px, py, size / 2, 0, Math.PI * 2);
          ctx.fillStyle = p.bg;
          ctx.fill();
          ctx.shadowBlur = 0;

          if (isSel) {
            ctx.strokeStyle = 'rgba(255,255,255,0.9)';
            ctx.lineWidth = 2.5;
            ctx.stroke();
          } else if (isHov) {
            ctx.strokeStyle = 'rgba(255,255,255,0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          } else if (isStk) {
            ctx.strokeStyle = 'rgba(167,139,250,0.7)';
            ctx.lineWidth = 2;
            ctx.stroke();
          } else if (isHighFit && activeTask) {
            ctx.strokeStyle = 'rgba(52,211,153,0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
          } else if (isComp && selectedTool) {
            ctx.strokeStyle = 'rgba(52,211,153,0.4)';
            ctx.lineWidth = 1;
            ctx.stroke();
          }

          ctx.fillStyle = '#fff';
          ctx.font = `${Math.floor(size * 0.42)}px system-ui`;
          ctx.textAlign = 'center';
          ctx.textBaseline = 'middle';
          ctx.fillText(categoryIcons[p.category] || '•', px, py);
          ctx.globalAlpha = 1;
          rnd.push({ ...p, px, py, size });
        }
      });
      rendered.current = rnd;
      frame = requestAnimationFrame(draw);
    };
    
    frame = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frame);
  }, [selectedTool, hoveredTool, activeTask, activeIndustry, zoomLevel, inStack, rankedTools, taskDef]);

  const findToolAtPosition = (x, y) => {
    const canvas = canvasRef.current;
    if (!canvas) return null;
    const rect = canvas.getBoundingClientRect();
    const px = x - rect.left, py = y - rect.top;
    for (let i = rendered.current.length - 1; i >= 0; i--) {
      const p = rendered.current[i];
      if ((px - p.px) ** 2 + (py - p.py) ** 2 < (p.size / 2 + 6) ** 2) return toolData.find(t => t.id === p.id);
    }
    return null;
  };

  const onMouseDown = (e) => { 
    dragging.current = true; 
    setIsDragging(true);
    lastMouse.current = { x: e.clientX, y: e.clientY }; 
  };
  
  const onMouseMove = (e) => {
    if (!isDragging) {
      setHoveredTool(findToolAtPosition(e.clientX, e.clientY));
    }
    if (dragging.current) {
      const dx = e.clientX - lastMouse.current.x;
      const dy = e.clientY - lastMouse.current.y;
      rotation.current.x += dx * 0.005;
      rotation.current.y += dy * 0.005;
      rotation.current.y = Math.max(-Math.PI / 2.2, Math.min(Math.PI / 2.2, rotation.current.y));
      velocity.current.x = dx * 0.002;
      velocity.current.y = dy * 0.002;
      lastMouse.current = { x: e.clientX, y: e.clientY };
    }
  };
  
  const onMouseUp = (e) => {
    if (dragging.current && Math.abs(e.clientX - lastMouse.current.x) < 5) {
      const tool = findToolAtPosition(e.clientX, e.clientY);
      if (tool) {
        if (selectedTool?.id === tool.id) {
          setSelectedTool(null);
        } else {
          setSelectedTool(tool);
          setIsExploringMode(true);
          setCompareTarget(null);
          setShowCompareMenu(false);
          setShowCategoryCompare(false);
        }
      }
    }
    dragging.current = false;
    setIsDragging(false);
  };

  useEffect(() => {
    const up = () => { 
      dragging.current = false; 
      setIsDragging(false);
    };
    window.addEventListener('mouseup', up);
    return () => window.removeEventListener('mouseup', up);
  }, []);

  const selectedFitResult = selectedTool && activeTask ? calculateTaskFitScore(selectedTool, activeTask, filters, userSoftware) : null;
  const selectedFitScore = selectedFitResult?.score || null;
  const selectedFitBreakdown = selectedFitResult?.breakdown || null;
  const selectedFitLabel = selectedFitScore ? getTaskFitLabel(selectedFitScore) : null;
  const profile = selectedTool ? (capabilityProfiles[selectedTool.id] || defaultProfile) : null;

  return (
    <div className="h-screen w-screen overflow-hidden bg-[#030303] text-white font-sans antialiased select-none">
      
      {/* Globe Canvas */}
      <canvas
        ref={canvasRef}
        onMouseDown={onMouseDown}
        onMouseMove={onMouseMove}
        onMouseUp={onMouseUp}
        onMouseLeave={() => setHoveredTool(null)}
        style={{ cursor: hoveredTool ? 'pointer' : 'grab' }}
        className="absolute inset-0 w-full h-full"
      />

      {/* Logo */}
      <button onClick={clearAll} className={`absolute top-6 left-6 z-50 flex items-center gap-2.5 hover:opacity-80 transition-opacity ${isDragging ? 'pointer-events-none' : ''}`}>
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center">
          <Sparkles className="w-4 h-4 text-white" />
        </div>
        <span className="text-white/80 font-medium text-sm tracking-tight">Touchstone</span>
      </button>

      {/* Top Right Filters */}
      <div className={`absolute top-6 right-6 z-50 flex items-center gap-2 ${isDragging ? 'pointer-events-none' : ''}`}>
        {currentStack.length > 0 && (
          <button className="flex items-center gap-2 px-3 py-2 bg-white/5 hover:bg-white/10 border border-white/10 rounded-full transition-all">
            <Layers className="w-4 h-4 text-white/50" />
            <span className="text-sm text-white/70">{currentStack.length}</span>
          </button>
        )}
        
        <button 
          onClick={() => setShowRoleSelector(true)}
          className={`flex items-center gap-2 px-3 py-2 border rounded-full transition-all ${
            userRole 
              ? 'bg-violet-500/20 border-violet-500/30 text-violet-300' 
              : 'bg-white/5 hover:bg-white/10 border-white/10 text-white/70'
          }`}
        >
          <span className="text-sm">{userRole ? userRoles.find(r => r.id === userRole)?.icon : '👤'}</span>
          <span className="text-sm">{userRole ? userRoles.find(r => r.id === userRole)?.name : 'Role'}</span>
        </button>
        
        <button 
          onClick={() => setShowPricingSelector(true)}
          className={`flex items-center gap-2 px-3 py-2 border rounded-full transition-all ${
            pricingPrefs.monthlyBudget !== '' || 
            Object.values(pricingPrefs.priorities).some(v => v !== 20) || 
            pricingPrefs.requireFreeTier || pricingPrefs.preferOpenSource || pricingPrefs.requireSOC2 || pricingPrefs.requireHIPAA || pricingPrefs.requireSelfHost
              ? 'bg-emerald-500/20 border-emerald-500/30 text-emerald-300' 
              : 'bg-white/5 hover:bg-white/10 border-white/10 text-white/70'
          }`}
        >
          <DollarSign className="w-3.5 h-3.5" />
          <span className="text-sm">Priorities</span>
        </button>
        
        <button 
          onClick={() => setShowSoftwareSelector(true)}
          className={`flex items-center gap-2 px-3 py-2 border rounded-full transition-all ${
            userSoftware.length > 0 
              ? 'bg-teal-500/20 border-teal-500/30 text-teal-300' 
              : 'bg-white/5 hover:bg-white/10 border-white/10 text-white/70'
          }`}
        >
          <span className="text-sm">Software</span>
          {userSoftware.length > 0 && (
            <span className="px-1.5 py-0.5 bg-teal-500/30 text-teal-300 text-xs rounded-full">{userSoftware.length}</span>
          )}
        </button>
      </div>

      {/* Role Selector Modal */}
      {showRoleSelector && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-8">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowRoleSelector(false)} />
          <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-md overflow-hidden">
            <button onClick={() => setShowRoleSelector(false)} className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors z-10">
              <X className="w-5 h-5" />
            </button>
            
            <div className="p-6">
              <div className="text-lg text-white font-medium mb-1">Your Role</div>
              <div className="text-sm text-zinc-500 mb-5">Select your role to prioritize relevant capabilities</div>
              
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {userRoles.map(role => (
                  <button
                    key={role.id}
                    onClick={() => setUserRole(userRole === role.id ? null : role.id)}
                    className={`w-full flex items-center gap-3 p-3 rounded-xl transition-all text-left ${
                      userRole === role.id 
                        ? 'bg-violet-500/20 border border-violet-500/40' 
                        : 'bg-zinc-800/50 border border-zinc-700/50 hover:bg-zinc-800'
                    }`}
                  >
                    <span className="text-2xl">{role.icon}</span>
                    <div className="flex-1">
                      <div className={`text-sm font-medium ${userRole === role.id ? 'text-violet-300' : 'text-zinc-200'}`}>
                        {role.name}
                      </div>
                      <div className="text-xs text-zinc-500">{role.description}</div>
                    </div>
                    {userRole === role.id && <span className="text-violet-400">✓</span>}
                  </button>
                ))}
              </div>
              
              <div className="mt-5 pt-4 border-t border-zinc-800 flex justify-end">
                <button onClick={() => setShowRoleSelector(false)} className="px-4 py-2 bg-violet-500 hover:bg-violet-600 text-white text-sm font-medium rounded-lg transition-colors">
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Pricing Selector Modal */}
      {showPricingSelector && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-6">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowPricingSelector(false)} />
          <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-xl">
            <button onClick={() => setShowPricingSelector(false)} className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors z-10">
              <X className="w-5 h-5" />
            </button>
            
            <div className="p-6">
              <div className="mb-6">
                <div className="text-lg text-white font-medium">Priorities & Budget</div>
                <div className="text-sm text-zinc-500">Customize recommendations to match your needs</div>
              </div>
              
              <div className="mb-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Suggested Monthly Budget</div>
                <div className="flex items-center gap-3">
                  <div className="relative w-44">
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
                    <input
                      type="text"
                      placeholder="No limit"
                      value={pricingPrefs.monthlyBudget}
                      onChange={(e) => {
                        const val = e.target.value;
                        if (val === '' || val === '-' || !isNaN(parseFloat(val))) {
                          setPricingPrefs(p => ({ ...p, monthlyBudget: val }));
                        }
                      }}
                      className="w-full bg-zinc-800 border border-zinc-700 rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-zinc-600 focus:outline-none focus:border-emerald-500/50"
                    />
                  </div>
                  <span className="text-sm text-zinc-500">per month total</span>
                </div>
              </div>
              
              <div className="mb-6">
                <div className="flex items-center justify-between mb-3">
                  <div className="text-xs text-zinc-500 uppercase tracking-wider">Priority Allocation</div>
                  <div className={`text-sm px-2.5 py-1 rounded-lg ${
                    Object.values(pricingPrefs.priorities).reduce((a, b) => a + b, 0) > MAX_PRIORITY_POINTS
                      ? 'bg-red-500/20 text-red-400'
                      : 'bg-zinc-800 text-zinc-400'
                  }`}>
                    {Object.values(pricingPrefs.priorities).reduce((a, b) => a + b, 0)} / {MAX_PRIORITY_POINTS} points
                  </div>
                </div>
                
                <div className="space-y-3">
                  {[
                    { key: 'cost', label: 'Cost Savings', icon: '💰', color: '#10b981' },
                    { key: 'quality', label: 'Output Quality', icon: '✨', color: '#8b5cf6' },
                    { key: 'speed', label: 'Speed', icon: '⚡', color: '#f59e0b' },
                    { key: 'easeOfUse', label: 'Ease of Use', icon: '🎯', color: '#14b8a6' },
                    { key: 'support', label: 'Support & Security', icon: '🛡️', color: '#3b82f6' },
                  ].map(priority => {
                    const value = pricingPrefs.priorities[priority.key];
                    const totalOthers = Object.entries(pricingPrefs.priorities)
                      .filter(([k]) => k !== priority.key)
                      .reduce((sum, [, v]) => sum + v, 0);
                    const maxAllowed = Math.min(100, MAX_PRIORITY_POINTS - totalOthers);
                    
                    return (
                      <div key={priority.key} className="flex items-center gap-4">
                        <div className="flex items-center gap-2 w-40">
                          <span className="text-lg">{priority.icon}</span>
                          <span className="text-sm text-zinc-300">{priority.label}</span>
                        </div>
                        <input
                          type="range"
                          min="0"
                          max={maxAllowed}
                          value={Math.min(value, maxAllowed)}
                          onChange={(e) => setPricingPrefs(p => ({
                            ...p,
                            priorities: { ...p.priorities, [priority.key]: parseInt(e.target.value) }
                          }))}
                          className="flex-1 h-2 bg-zinc-700 rounded-full appearance-none cursor-pointer"
                          style={{ accentColor: priority.color }}
                        />
                        <span className={`text-sm font-medium w-8 text-right ${value > 25 ? 'text-white' : 'text-zinc-600'}`}>{value}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
              
              <div className="mb-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Quick Presets</div>
                <div className="flex flex-wrap gap-2">
                  {[
                    { name: 'Balanced', p: { cost: 20, quality: 20, speed: 20, easeOfUse: 20, support: 20 } },
                    { name: 'Budget Focused', p: { cost: 50, quality: 15, speed: 15, easeOfUse: 15, support: 5 } },
                    { name: 'Quality First', p: { cost: 5, quality: 50, speed: 15, easeOfUse: 15, support: 15 } },
                    { name: 'Fast & Easy', p: { cost: 10, quality: 15, speed: 40, easeOfUse: 30, support: 5 } },
                    { name: 'Enterprise', p: { cost: 5, quality: 25, speed: 15, easeOfUse: 15, support: 40 } },
                  ].map(preset => (
                    <button
                      key={preset.name}
                      onClick={() => setPricingPrefs(p => ({ ...p, priorities: preset.p }))}
                      className="px-3 py-1.5 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-400 hover:bg-zinc-700 hover:text-zinc-200 transition-all"
                    >
                      {preset.name}
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="mb-6">
                <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">Requirements</div>
                <div className="flex flex-wrap gap-2">
                  {[
                    { key: 'requireFreeTier', label: 'Free Tier', icon: '🆓' },
                    { key: 'preferOpenSource', label: 'Open Source', icon: '📖' },
                    { key: 'requireSelfHost', label: 'Self-Hostable', icon: '🏠' },
                    { key: 'requireSOC2', label: 'SOC2', icon: '🔒' },
                    { key: 'requireHIPAA', label: 'HIPAA', icon: '🏥' },
                  ].map(opt => (
                    <button
                      key={opt.key}
                      onClick={() => setPricingPrefs(p => ({ ...p, [opt.key]: !p[opt.key] }))}
                      className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm transition-all ${
                        pricingPrefs[opt.key] 
                          ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-300' 
                          : 'bg-zinc-800 border border-zinc-700 text-zinc-400 hover:bg-zinc-700'
                      }`}
                    >
                      <span>{opt.icon}</span>
                      <span>{opt.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              
              <div className="flex items-center justify-between pt-4 border-t border-zinc-800">
                <button 
                  onClick={() => setPricingPrefs({
                    monthlyBudget: '',
                    priorities: { cost: 20, quality: 20, speed: 20, easeOfUse: 20, support: 20 },
                    requireFreeTier: false,
                    preferOpenSource: false,
                    requireSelfHost: false,
                    requireSOC2: false,
                    requireHIPAA: false,
                  })}
                  className="text-sm text-zinc-500 hover:text-zinc-300"
                >
                  Reset all
                </button>
                <button onClick={() => setShowPricingSelector(false)} className="px-5 py-2.5 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors">
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Software Selector Modal */}
      {showSoftwareSelector && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-8">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setShowSoftwareSelector(false)} />
          <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-lg max-h-[80vh] overflow-hidden">
            <button onClick={() => setShowSoftwareSelector(false)} className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors z-10">
              <X className="w-5 h-5" />
            </button>
            
            <div className="p-6">
              <div className="text-lg text-white font-medium mb-1">Your Software Stack</div>
              <div className="text-sm text-zinc-500 mb-5">Select the tools you already use</div>
              
              <div className="space-y-4 max-h-96 overflow-y-auto pr-2">
                {['Communication', 'Productivity', 'CRM', 'Design', 'Development', 'Cloud', 'Project Management', 'Automation', 'Observability'].map(category => {
                  const softwareInCategory = availableSoftware.filter(s => s.category === category);
                  if (softwareInCategory.length === 0) return null;
                  
                  return (
                    <div key={category}>
                      <div className="text-xs text-zinc-500 uppercase tracking-wider mb-2">{category}</div>
                      <div className="flex flex-wrap gap-2">
                        {softwareInCategory.map(sw => {
                          const isSelected = userSoftware.includes(sw.id);
                          return (
                            <button
                              key={sw.id}
                              onClick={() => {
                                if (isSelected) {
                                  setUserSoftware(prev => prev.filter(id => id !== sw.id));
                                } else {
                                  setUserSoftware(prev => [...prev, sw.id]);
                                }
                              }}
                              className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                                isSelected 
                                  ? 'bg-emerald-500/20 border border-emerald-500/40 text-emerald-400' 
                                  : 'bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-300'
                              }`}
                            >
                              {sw.name}
                              {isSelected && <span className="ml-1.5">✓</span>}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  );
                })}
              </div>
              
              <div className="mt-5 pt-4 border-t border-zinc-800 flex items-center justify-between">
                <div className="text-sm text-zinc-500">{userSoftware.length} software selected</div>
                <button onClick={() => setShowSoftwareSelector(false)} className="px-4 py-2 bg-emerald-500 hover:bg-emerald-600 text-white text-sm font-medium rounded-lg transition-colors">
                  Done
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Search + Navigation */}
      <div className={`absolute left-1/2 -translate-x-1/2 z-40 transition-all duration-500 ease-out ${
        isExploring ? 'top-20 w-full max-w-3xl px-6' : 'top-1/2 -translate-y-1/2 w-full max-w-4xl px-8'
      } ${isDragging ? 'pointer-events-none' : ''}`}>
        <div className="flex flex-col items-center">
          
          {!isExploring && (
            <div className="mb-10 text-center">
              <h1 className="text-4xl font-extralight text-white tracking-tight mb-3">Explore AI Tools</h1>
              <p className="text-base text-white/40 font-light">Find the right tools for your workflow</p>
            </div>
          )}

          <div className={`relative w-full transition-all duration-500 ${isExploring ? 'max-w-xl' : 'max-w-2xl'}`}>
            <Search className="absolute left-5 top-1/2 -translate-y-1/2 w-5 h-5 text-white/40" />
            <input
              type="text"
              value={searchQuery}
              onFocus={() => { if (!isExploringMode) setIsExploringMode(true); }}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                if (e.target.value.trim() && !isExploringMode) setIsExploringMode(true);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && searchResults.length > 0) {
                  setSelectedTool(searchResults[0]);
                  setSearchQuery('');
                  setIsExploringMode(true);
                }
                if (e.key === 'Escape') { setSearchQuery(''); e.target.blur(); }
              }}
              placeholder="Search tools by name, category, or feature..."
              className={`w-full bg-zinc-900/80 backdrop-blur-2xl border border-white/[0.12] rounded-2xl placeholder-white/40 transition-all ring-0 ${
                isExploring ? 'h-12 pl-12 pr-14 text-sm' : 'h-14 pl-14 pr-16 text-base'
              } focus:outline-none focus:border-emerald-500/50 focus:bg-zinc-900/90 focus:ring-2 focus:ring-emerald-500/20`}
              style={{ caretColor: '#10b981', color: '#ffffff' }}
            />
            <button 
              onClick={() => {
                if (searchResults.length > 0) {
                  setSelectedTool(searchResults[0]);
                  setSearchQuery('');
                  setIsExploringMode(true);
                }
              }}
              className={`absolute top-1/2 -translate-y-1/2 bg-gradient-to-r from-emerald-500 to-teal-500 rounded-xl cursor-pointer hover:opacity-80 transition-opacity ${
                isExploring ? 'right-2 p-2' : 'right-2.5 p-2.5'
              }`}
            >
              <ArrowRight className="w-4 h-4 text-white" />
            </button>
            
            {searchQuery.trim() && (
              <div className="absolute top-full left-0 right-0 mt-2 bg-zinc-900/95 backdrop-blur-xl border border-zinc-700/50 rounded-xl shadow-2xl overflow-hidden z-50">
                {searchResults.length > 0 ? (
                  <div className="max-h-80 overflow-y-auto">
                    {searchResults.map((tool, idx) => (
                      <button
                        key={tool.id}
                        onClick={() => { setSelectedTool(tool); setSearchQuery(''); setIsExploringMode(true); }}
                        className={`w-full flex items-center gap-3 px-4 py-3 hover:bg-white/5 transition-colors text-left ${idx === 0 ? 'bg-white/[0.03]' : ''}`}
                      >
                        <div className="w-9 h-9 rounded-lg flex items-center justify-center text-sm flex-shrink-0" style={{ backgroundColor: tool.bg }}>
                          {categoryIcons[tool.category]}
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-white font-medium">{tool.name}</span>
                            {activeTask && (
                              <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                                tool.fitScore >= 85 ? 'bg-emerald-500/20 text-emerald-400' :
                                tool.fitScore >= 70 ? 'bg-teal-500/20 text-teal-400' :
                                tool.fitScore >= 55 ? 'bg-amber-500/20 text-amber-400' :
                                'bg-red-500/20 text-red-400'
                              }`}>{tool.fitScore}%</span>
                            )}
                          </div>
                          <div className="text-xs text-zinc-500 truncate">{tool.category} • {tool.provider}</div>
                        </div>
                        {idx === 0 && <span className="text-[10px] text-zinc-600 flex-shrink-0">↵ Enter</span>}
                      </button>
                    ))}
                  </div>
                ) : (
                  <div className="px-4 py-6 text-center">
                    <div className="text-sm text-zinc-400">No tools found for "{searchQuery}"</div>
                    <div className="text-xs text-zinc-600 mt-1">Try searching by name, category, or feature</div>
                  </div>
                )}
              </div>
            )}
          </div>

          <div className={`flex flex-col items-center w-full transition-all duration-500 ${isExploring ? 'mt-4' : 'mt-10'}`}>
            <div className="flex items-center justify-center">
              {Object.entries(industryData).map(([key, ind], idx) => {
                const isSelected = activeIndustry === key;
                const hasSelection = activeIndustry !== null;
                return (
                  <div key={key} className="flex items-center">
                    <button
                      onClick={() => {
                        if (isSelected) { setActiveIndustry(null); setActiveTask(null); }
                        else { setActiveIndustry(key); setActiveTask(null); }
                      }}
                      className={`px-5 py-3 text-sm font-medium transition-all duration-200 ${
                        isSelected ? 'text-white' : hasSelection ? 'text-white/30 hover:text-white/60' : 'text-white/60 hover:text-white'
                      }`}
                    >
                      {ind.label}
                    </button>
                    {idx < Object.keys(industryData).length - 1 && (
                      <div className={`w-px h-4 transition-colors duration-200 ${hasSelection ? 'bg-white/10' : 'bg-white/20'}`} />
                    )}
                  </div>
                );
              })}
            </div>

            {activeIndustry && (
              <div className="mt-5 flex flex-col items-center animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="w-16 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent mb-5" />
                <div className="flex flex-wrap justify-center gap-2 max-w-2xl">
                  {industryData[activeIndustry].tasks.map(taskKey => {
                    const task = taskDefinitions[taskKey];
                    if (!task) return null;
                    const isSelected = activeTask === taskKey;
                    return (
                      <button
                        key={taskKey}
                        onClick={() => handleTaskSelect(taskKey)}
                        className={`px-4 py-2 rounded-xl text-sm transition-all duration-200 ${
                          isSelected
                            ? 'bg-white/10 text-white border border-white/20'
                            : 'bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] hover:border-white/[0.12] text-white/60 hover:text-white'
                        }`}
                      >
                        {task.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}

            {activeTask && topTools.length > 0 && (
              <div className="mt-5 flex flex-col items-center animate-in fade-in slide-in-from-top-2 duration-300">
                <div className="w-16 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent mb-4" />
                <div className="text-xs text-white/40 mb-3">Recommended tools</div>
                <div className="flex gap-3">
                  {topTools.map(tool => {
                    const fit = getTaskFitLabel(tool.fitScore);
                    return (
                      <button
                        key={tool.id}
                        onClick={() => setSelectedTool(tool)}
                        className="group flex flex-col items-center gap-2 p-3 bg-white/[0.03] hover:bg-white/[0.08] border border-white/[0.06] hover:border-white/[0.12] rounded-2xl transition-all duration-200 min-w-[90px]"
                      >
                        <div className="w-10 h-10 rounded-xl flex items-center justify-center text-base group-hover:scale-110 transition-transform" style={{ backgroundColor: tool.bg }}>
                          {categoryIcons[tool.category]}
                        </div>
                        <div className="text-center">
                          <div className="text-xs text-white/80 font-medium">{tool.name}</div>
                          <div className={`text-[10px] ${fit.color}`}>{fit.label} · {tool.fitScore}%</div>
                        </div>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Zoom Controls */}
      <div className={`absolute bottom-6 left-6 flex flex-col gap-1 z-40 ${isDragging ? 'pointer-events-none' : ''}`}>
        <button onClick={() => setZoomLevel(z => Math.min(z + 0.15, 1.8))} className="w-9 h-9 bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.05] rounded-xl flex items-center justify-center text-white/30 hover:text-white/60 transition-all">
          <Plus className="w-4 h-4" />
        </button>
        <button onClick={() => setZoomLevel(z => Math.max(z - 0.15, 0.5))} className="w-9 h-9 bg-white/[0.02] hover:bg-white/[0.06] border border-white/[0.05] rounded-xl flex items-center justify-center text-white/30 hover:text-white/60 transition-all">
          <Minus className="w-4 h-4" />
        </button>
      </div>

      {/* Stack */}
      {currentStack.length > 0 && (
        <div className={`absolute bottom-6 left-1/2 -translate-x-1/2 z-40 ${isDragging ? 'pointer-events-none' : ''}`}>
          <div className="flex items-center gap-2 px-3 py-2 bg-black/50 backdrop-blur-xl border border-white/10 rounded-2xl">
            {currentStack.map(tool => (
              <div key={tool.id} className="relative group">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center text-sm cursor-pointer hover:scale-110 transition-transform" style={{ backgroundColor: tool.bg }} onClick={() => setSelectedTool(tool)}>
                  {categoryIcons[tool.category]}
                </div>
                <button onClick={() => toggleStack(tool)} className="absolute -top-1 -right-1 w-4 h-4 bg-zinc-900 border border-zinc-700 rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                  <X className="w-2.5 h-2.5 text-white/60" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Detail Panel */}
      <div className={`absolute left-0 right-0 bottom-0 z-50 transition-transform duration-300 ease-out ${selectedTool ? 'translate-y-0' : 'translate-y-full'} ${isDragging ? 'pointer-events-none' : ''}`}>
        {selectedTool && (
          <div className="bg-zinc-900/98 backdrop-blur-xl border-t border-zinc-700/50 shadow-2xl">
            <div className="flex justify-center pt-2 pb-1">
              <div className="w-10 h-1 bg-zinc-700 rounded-full" />
            </div>
            
            <button onClick={() => setSelectedTool(null)} className="absolute top-3 right-4 text-zinc-500 hover:text-zinc-300 p-1 hover:bg-zinc-800 rounded-lg transition-colors">
              <X className="w-5 h-5" />
            </button>

            <div className="px-6 pb-4 pt-2">
              <div className="flex gap-6">
                {/* Left Column */}
                <div className="flex-shrink-0 w-56">
                  <div className="flex items-center gap-3 mb-3">
                    <div className="w-12 h-12 rounded-xl flex items-center justify-center text-xl shadow-lg" style={{ backgroundColor: selectedTool.bg }}>
                      {categoryIcons[selectedTool.category]}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <h2 className="text-lg font-medium text-white">{selectedTool.name}</h2>
                        {selectedFitScore && (
                          <FitScoreBadge score={selectedFitScore} onClick={() => setShowFitDetails(!showFitDetails)} expanded={showFitDetails} />
                        )}
                      </div>
                      <p className="text-xs text-zinc-500">{selectedTool.category} • {selectedTool.provider}</p>
                    </div>
                  </div>
                  
                  {activeTask && selectedFitLabel && (
                    <div className={`mb-3 px-3 py-2 rounded-lg ${selectedFitLabel.bg} border border-zinc-800/40`}>
                      <div className="flex items-center gap-2">
                        <Target className="w-3.5 h-3.5 text-zinc-400" />
                        <span className={`text-sm font-medium ${selectedFitLabel.color}`}>{selectedFitLabel.label}</span>
                        <span className="text-xs text-zinc-600">for {taskDef?.label}</span>
                      </div>
                    </div>
                  )}
                  
                  <p className="text-xs text-zinc-400 mb-3 line-clamp-2">{selectedTool.guidance}</p>
                  
                  <button 
                    onClick={() => toggleStack(selectedTool)}
                    className={`w-full py-1.5 rounded-lg text-xs font-medium transition-all ${
                      inStack(selectedTool.id) ? 'bg-indigo-500 text-white' : 'bg-emerald-500 text-white hover:bg-emerald-600'
                    }`}
                  >
                    {inStack(selectedTool.id) ? 'Remove from Stack' : 'Add to Stack'}
                  </button>
                </div>

                {/* Middle Column - Capabilities */}
                <div className="flex-1 min-w-0 border-l border-zinc-800 pl-5">
                  {(() => {
                    const taskCategories = taskDef?.categories || [];
                    const toolMatchesTask = !activeTask || taskCategories.includes(selectedTool.category);
                    
                    if (activeTask && !toolMatchesTask) {
                      return (
                        <div className="flex-1">
                          <div className="text-xs text-zinc-500 mb-3 font-medium uppercase tracking-wider">
                            Why {selectedFitScore}% fit for {taskDef?.label}
                          </div>
                          <div className="p-3 bg-red-500/10 border border-red-500/20 rounded-lg mb-3">
                            <div className="flex items-center gap-2 text-red-400 text-sm font-medium mb-1">
                              <span>⚠</span>
                              <span>Category Mismatch</span>
                            </div>
                            <p className="text-xs text-zinc-400">
                              {selectedTool.name} is a <span className="text-white">{selectedTool.category}</span> tool.
                              This task requires: <span className="text-white">{taskCategories.join(', ')}</span>.
                            </p>
                          </div>
                          <div className="text-xs text-zinc-600 mb-2">Tool's actual strengths:</div>
                          <div className="space-y-1 opacity-60">
                            {['Output Quality', 'Accuracy', 'Speed', 'Cost Efficiency'].map(dim => {
                              const level = profile?.[dim] || 'limited';
                              return <CapabilityBar key={dim} label={dim} level={level} emphasized={false} />;
                            })}
                          </div>
                        </div>
                      );
                    } else if (activeTask && taskDef?.requirements) {
                      return (
                        <div className="flex-1">
                          <div className="text-xs text-zinc-500 mb-3 font-medium uppercase tracking-wider">
                            Requirements for {taskDef?.label}
                          </div>
                          <div className="space-y-0.5">
                            {Object.entries(taskDef.requirements).map(([dim, req]) => {
                              const level = profile?.[dim] || 'limited';
                              return <CapabilityBar key={dim} label={dim} level={level} emphasized={true} requirement={req.min} />;
                            })}
                          </div>
                        </div>
                      );
                    } else {
                      return (
                        <div>
                          <div className="text-xs text-zinc-500 mb-2 font-medium uppercase tracking-wider">Key Capabilities</div>
                          <div className="space-y-0.5">
                            {['Output Quality', 'Accuracy', 'Speed', 'Cost Efficiency', 'Integration Ease', 'API Robustness'].map(dim => {
                              const level = profile?.[dim] || 'limited';
                              return <CapabilityBar key={dim} label={dim} level={level} emphasized={false} />;
                            })}
                          </div>
                        </div>
                      );
                    }
                  })()}
                </div>

                {/* Integrations Column */}
                <div className="flex-shrink-0 w-36 border-l border-zinc-800 pl-4">
                  {selectedTool.compatible?.length > 0 && (
                    <div className="mb-3">
                      <div className="text-[10px] text-zinc-500 mb-1.5 uppercase tracking-wider">AI Tools</div>
                      <div className="flex flex-wrap gap-1">
                        {selectedTool.compatible.slice(0, 8).map(id => {
                          const t = toolData.find(x => x.id === id);
                          return t ? (
                            <button key={id} onClick={() => setSelectedTool(t)} className="w-5 h-5 rounded flex items-center justify-center text-[9px] hover:scale-110 transition-transform" style={{ backgroundColor: t.bg }} title={t.name}>
                              {categoryIcons[t.category]}
                            </button>
                          ) : null;
                        })}
                      </div>
                    </div>
                  )}
                  
                  {selectedTool.software?.length > 0 && (
                    <div>
                      <div className="text-[10px] text-zinc-500 mb-1.5 uppercase tracking-wider">Software</div>
                      <div className="flex flex-wrap gap-1">
                        {selectedTool.software.slice(0, 5).map(sw => (
                          <span key={sw} className="px-1.5 py-0.5 bg-zinc-800/50 text-zinc-500 text-[9px] rounded">{sw}</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                {/* Right Column */}
                <div className="flex-shrink-0 w-40 border-l border-zinc-800 pl-4">
                  <div className="space-y-2">
                    {selectedTool.pricing && (
                      <div>
                        <div className="flex items-center gap-1 mb-1">
                          <DollarSign className="w-3 h-3 text-emerald-500" />
                          <span className="text-xs text-zinc-500 font-medium">Pricing</span>
                        </div>
                        <div className="text-sm text-white">{selectedTool.pricing.cost}</div>
                        {selectedTool.pricing.free && (
                          <span className="inline-block mt-1 px-1.5 py-0.5 bg-emerald-500/15 text-emerald-400 text-[10px] rounded">Free tier</span>
                        )}
                      </div>
                    )}
                    
                    {selectedTool.constraints && (
                      <div>
                        <div className="flex items-center gap-1 mb-1">
                          <Shield className="w-3 h-3 text-zinc-500" />
                          <span className="text-xs text-zinc-500 font-medium">Compliance</span>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {selectedTool.constraints.soc2 && <span className="px-1.5 py-0.5 bg-emerald-500/15 text-emerald-400 text-[10px] rounded">SOC2</span>}
                          {selectedTool.constraints.hipaa && <span className="px-1.5 py-0.5 bg-emerald-500/15 text-emerald-400 text-[10px] rounded">HIPAA</span>}
                          {selectedTool.constraints.onprem && <span className="px-1.5 py-0.5 bg-teal-500/15 text-teal-400 text-[10px] rounded">Self-host</span>}
                        </div>
                      </div>
                    )}
                  </div>
                  
                  <div className="space-y-1.5 mt-3 pt-2 border-t border-zinc-800">
                    <button 
                      onClick={() => {
                        if (showCategoryCompare) setShowCategoryCompare(false);
                        else { setShowCategoryCompare(true); setShowCompareMenu(false); setCompareTarget(null); }
                      }}
                      className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[10px] transition-colors ${
                        showCategoryCompare ? 'bg-teal-500/20 border border-teal-500/30 text-teal-300' : 'bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                      }`}
                    >
                      <BarChart3 className="w-3 h-3" />
                      <span>Compare category</span>
                    </button>
                    
                    <button 
                      onClick={() => {
                        if (showCompareMenu || compareTarget) { setShowCompareMenu(false); setCompareTarget(null); }
                        else { setShowCompareMenu(true); setShowCategoryCompare(false); }
                      }}
                      className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-lg text-[10px] transition-colors ${
                        showCompareMenu || compareTarget ? 'bg-teal-500/20 border border-teal-500/30 text-teal-300' : 'bg-zinc-800/50 border border-zinc-700/50 text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800'
                      }`}
                    >
                      <GitCompare className="w-3 h-3" />
                      <span>Compare 1-on-1</span>
                    </button>
                  </div>
                </div>
              </div>
              
              {/* Fit Score Breakdown */}
              {showFitDetails && selectedFitBreakdown && (
                <div className="mt-3 pt-3 border-t border-zinc-800/50">
                  <div className="flex gap-5">
                    <div className="flex-shrink-0 flex items-center gap-3">
                      <div className="relative w-11 h-11">
                        <svg className="w-11 h-11 -rotate-90">
                          <circle cx="22" cy="22" r="18" fill="none" stroke="#27272a" strokeWidth="3" />
                          <circle 
                            cx="22" cy="22" r="18" fill="none" 
                            stroke={selectedFitScore >= 85 ? '#10b981' : selectedFitScore >= 70 ? '#14b8a6' : selectedFitScore >= 55 ? '#f59e0b' : '#ef4444'}
                            strokeWidth="3" 
                            strokeLinecap="round"
                            strokeDasharray={`${(selectedFitScore / 100) * 113} 113`}
                          />
                        </svg>
                        <div className="absolute inset-0 flex items-center justify-center">
                          <span className="text-sm font-bold text-white">{selectedFitScore}</span>
                        </div>
                      </div>
                      <div className={`text-xs font-medium ${
                        selectedFitScore >= 85 ? 'text-emerald-400' : selectedFitScore >= 70 ? 'text-teal-400' : selectedFitScore >= 55 ? 'text-amber-400' : 'text-red-400'
                      }`}>
                        {selectedFitScore >= 85 ? 'Excellent' : selectedFitScore >= 70 ? 'Good' : selectedFitScore >= 55 ? 'Viable' : 'Poor'}
                      </div>
                    </div>
                    
                    <div className="flex-1 min-w-0">
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Task Requirements</div>
                      {selectedFitBreakdown.categoryMatch ? (
                        <div className="grid grid-cols-3 gap-x-4 gap-y-1">
                          {selectedFitBreakdown.capabilityScores?.map(cap => (
                            <div key={cap.dimension} className="flex items-center gap-2">
                              <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                cap.status === 'exceeds' ? 'bg-emerald-400' : cap.status === 'meets' ? 'bg-teal-400' : 'bg-red-400'
                              }`} />
                              <span className="text-[11px] text-zinc-300 truncate flex-1">{cap.dimension}</span>
                              <span className={`text-[10px] font-medium flex-shrink-0 ${
                                cap.status === 'exceeds' ? 'text-emerald-400' : cap.status === 'meets' ? 'text-teal-400' : 'text-red-400'
                              }`}>
                                {cap.status === 'exceeds' ? 'Exceeds' : cap.status === 'meets' ? 'Meets' : 'Below'}
                              </span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 text-red-400">
                          <span className="text-xs">⚠</span>
                          <span className="text-xs">Category mismatch — needs {selectedFitBreakdown.requiredCategories?.join(', ')}</span>
                        </div>
                      )}
                    </div>
                    
                    <div className="flex-shrink-0 w-44">
                      <div className="text-[10px] text-zinc-500 uppercase tracking-wider mb-1.5">Modifiers</div>
                      <div className="flex flex-wrap gap-1">
                        {userRole && selectedFitBreakdown.roleBonus !== 0 && (
                          <span className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                            selectedFitBreakdown.roleBonus > 0 ? 'bg-violet-500/20 text-violet-300' : 'bg-red-500/20 text-red-300'
                          }`}>
                            {userRoles.find(r => r.id === userRole)?.icon} {selectedFitBreakdown.roleBonus > 0 ? '+' : ''}{selectedFitBreakdown.roleBonus}%
                          </span>
                        )}
                        {selectedFitBreakdown.priorityBreakdown?.map((p, i) => (
                          <span key={i} className={`inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] ${
                            p.bonus > 0 ? 'bg-emerald-500/20 text-emerald-300' : 'bg-orange-500/20 text-orange-300'
                          }`}>
                            {p.name === 'Cost' ? '💰' : p.name === 'Quality' ? '✨' : p.name === 'Speed' ? '⚡' : p.name === 'Ease of Use' ? '🎯' : '🛡️'}{p.bonus > 0 ? '+' : ''}{p.bonus.toFixed(0)}%
                          </span>
                        ))}
                        {selectedFitBreakdown.softwareBonus > 0 && (
                          <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded text-[10px] bg-teal-500/20 text-teal-300">
                            🔗+{selectedFitBreakdown.softwareBonus}%
                          </span>
                        )}
                        {selectedFitBreakdown.pricingNotes?.map((note, i) => (
                          <span key={i} className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] bg-orange-500/20 text-orange-300">
                            ⚠{note}
                          </span>
                        ))}
                        {!userRole && !selectedFitBreakdown.priorityBreakdown?.length && !selectedFitBreakdown.softwareBonus && (
                          <span className="text-[10px] text-zinc-600">Base score</span>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex-shrink-0 flex items-center gap-2">
                      <div className="flex gap-1.5">
                        <div className="text-center px-2 py-1 bg-zinc-800/50 rounded">
                          <div className={`text-sm font-bold ${selectedFitBreakdown.bonusCount > 0 ? 'text-emerald-400' : 'text-zinc-600'}`}>
                            {selectedFitBreakdown.bonusCount || 0}
                          </div>
                          <div className="text-[8px] text-zinc-500">GREAT</div>
                        </div>
                        <div className="text-center px-2 py-1 bg-zinc-800/50 rounded">
                          <div className={`text-sm font-bold ${selectedFitBreakdown.penaltyCount > 0 ? 'text-red-400' : 'text-zinc-600'}`}>
                            {selectedFitBreakdown.penaltyCount || 0}
                          </div>
                          <div className="text-[8px] text-zinc-500">BELOW</div>
                        </div>
                      </div>
                      <button onClick={() => setShowFitDetails(false)} className="p-1.5 hover:bg-zinc-800 rounded text-zinc-500 hover:text-zinc-300">
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Compare Modal */}
      {selectedTool && (showCompareMenu || compareTarget || showCategoryCompare) && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-8">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => { setShowCompareMenu(false); setShowCategoryCompare(false); setCompareTarget(null); }} />
          
          <div className="relative bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <button onClick={() => { setShowCompareMenu(false); setShowCategoryCompare(false); setCompareTarget(null); }} className="absolute top-4 right-4 text-zinc-500 hover:text-zinc-300 p-1.5 hover:bg-zinc-800 rounded-lg transition-colors z-10">
              <X className="w-5 h-5" />
            </button>

            {showCompareMenu && !compareTarget && (
              <div className="p-6">
                <div className="text-lg text-white font-medium mb-1">Compare 1-on-1</div>
                <div className="text-sm text-zinc-500 mb-5">Select a tool to compare with {selectedTool.name}</div>
                <div className="grid grid-cols-3 gap-3 max-h-96 overflow-y-auto">
                  {toolData
                    .filter(t => t.id !== selectedTool.id)
                    .map(t => {
                      const result = activeTask ? calculateTaskFitScore(t, activeTask, filters, userSoftware) : { score: 50 };
                      return { ...t, fitScore: result.score };
                    })
                    .sort((a, b) => b.fitScore - a.fitScore)
                    .map(t => {
                      const fit = getTaskFitLabel(t.fitScore);
                      return (
                        <button key={t.id} onClick={() => { setCompareTarget(t); setShowCompareMenu(false); }} className="flex items-center gap-3 p-3 bg-zinc-800/50 hover:bg-zinc-800 border border-zinc-700/50 hover:border-zinc-600 rounded-xl transition-all text-left">
                          <div className="w-10 h-10 rounded-lg flex items-center justify-center text-base flex-shrink-0" style={{ backgroundColor: t.bg }}>
                            {categoryIcons[t.category]}
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="text-sm text-zinc-200 font-medium truncate">{t.name}</div>
                            <div className="text-xs text-zinc-600">{t.category}</div>
                            <div className={`text-xs ${fit.color}`}>{fit.label} · {t.fitScore}%</div>
                          </div>
                        </button>
                      );
                    })}
                </div>
              </div>
            )}

            {compareTarget && (
              <div className="p-6">
                <ComparisonView toolA={selectedTool} toolB={compareTarget} onClose={() => setCompareTarget(null)} activeTask={activeTask} userSoftware={userSoftware} />
              </div>
            )}

            {showCategoryCompare && (
              <div className="p-6">
                <CategoryCompareView 
                  category={selectedTool.category} 
                  referenceTool={selectedTool} 
                  onClose={() => setShowCategoryCompare(false)}
                  onSelectTool={(tool) => { setSelectedTool(tool); setShowCategoryCompare(false); }}
                  activeTask={activeTask}
                />
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

