
import React, { useState, useEffect, useRef } from 'react';
import { useApp } from '../state/AppContext';
import { Screen } from '../types';
import { Button } from '../components/UI';

interface Point {
  x: number;
  y: number;
}

interface Spark {
  x: number;
  y: number;
  vx: number;
  vy: number;
  life: number;
  maxLife: number;
  size: number;
  history: Point[];
}

const IntroScreen: React.FC = () => {
  const { setScreen } = useApp();
  const [permissionsGranted, setPermissionsGranted] = useState(false);
  const [phase, setPhase] = useState<'initial' | 'buildup' | 'strike' | 'revealed'>('initial');
  const [isShaking, setIsShaking] = useState(false);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const sparksRef = useRef<Spark[]>([]);
  const textSparksRef = useRef<Spark[]>([]);

  useEffect(() => {
    // Sequence Timing
    const timer1 = setTimeout(() => setPhase('buildup'), 800);
    const timer2 = setTimeout(() => setPhase('strike'), 1000);

    return () => {
      clearTimeout(timer1);
      clearTimeout(timer2);
    };
  }, []);

  const requestPermissions = async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ audio: true, video: true });
      setPermissionsGranted(true);
    } catch (err) {
      alert("Please grant camera and microphone permissions to use Full Control.");
    }
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animationFrameId: number;
    let lightningSegments: Point[] = [];
    let branches: Point[][] = [];
    let strikeOpacity = 0;
    let strikeFrameCount = 0;

    const createLightningPath = (x1: number, y1: number, x2: number, y2: number, segments: number, deviation: number): Point[] => {
      const path: Point[] = [{ x: x1, y: y1 }];
      for (let i = 1; i < segments; i++) {
        const t = i / segments;
        const x = x1 + (x2 - x1) * t + (Math.random() - 0.5) * deviation;
        const y = y1 + (y2 - y1) * t + (Math.random() - 0.5) * deviation;
        path.push({ x, y });
      }
      path.push({ x: x2, y: y2 });
      return path;
    };

    const drawBolt = (path: Point[], width: number, opacity: number, color: string, blur: number) => {
      ctx.save();
      ctx.shadowBlur = blur;
      ctx.shadowColor = color;
      ctx.strokeStyle = color;
      ctx.lineWidth = width;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.globalAlpha = opacity;
      ctx.beginPath();
      ctx.moveTo(path[0].x, path[0].y);
      for (let i = 1; i < path.length; i++) {
        ctx.lineTo(path[i].x, path[i].y);
      }
      ctx.stroke();
      ctx.restore();
    };

    const spawnSparks = (x: number, y: number, count: number, isTextSpark: boolean = false) => {
      for (let i = 0; i < count; i++) {
        const angle = Math.random() * Math.PI * 2;
        const force = isTextSpark ? Math.random() * 2 + 1 : Math.random() * 10 + 2;
        const spark: Spark = {
          x,
          y,
          vx: Math.cos(angle) * force,
          vy: Math.sin(angle) * force - (isTextSpark ? 0.5 : 2),
          life: 1,
          maxLife: Math.random() * 0.8 + 0.4,
          size: Math.random() * 2 + 1,
          history: [{ x, y }]
        };
        if (isTextSpark) textSparksRef.current.push(spark);
        else sparksRef.current.push(spark);
      }
    };

    const updateSparks = (list: Spark[], dt: number) => {
      for (let i = list.length - 1; i >= 0; i--) {
        const s = list[i];
        s.history.push({ x: s.x, y: s.y });
        if (s.history.length > 5) s.history.shift();
        
        s.x += s.vx;
        s.y += s.vy;
        s.vy += 0.15; // Gravity
        s.vx *= 0.98; // Friction
        s.life -= dt / s.maxLife;

        if (s.life <= 0) list.splice(i, 1);
      }
    };

    const drawSparks = (list: Spark[]) => {
      list.forEach(s => {
        ctx.beginPath();
        ctx.moveTo(s.history[0].x, s.history[0].y);
        for (let j = 1; j < s.history.length; j++) {
          ctx.lineTo(s.history[j].x, s.history[j].y);
        }
        ctx.strokeStyle = `rgba(255, 204, 102, ${s.life})`;
        ctx.lineWidth = s.size;
        ctx.stroke();

        ctx.beginPath();
        ctx.arc(s.x, s.y, s.size * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = `rgba(255, 255, 255, ${s.life})`;
        ctx.fill();
      });
    };

    const init = () => {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
      lightningSegments = createLightningPath(
        canvas.width / 2 + (Math.random() - 0.5) * 50,
        -50,
        canvas.width / 2,
        canvas.height / 2,
        25,
        60
      );
      
      // Random branches
      branches = [];
      for (let i = 0; i < 4; i++) {
        const idx = Math.floor(Math.random() * (lightningSegments.length - 5)) + 2;
        const start = lightningSegments[idx];
        branches.push(createLightningPath(
          start.x, 
          start.y, 
          start.x + (Math.random() - 0.5) * 300, 
          start.y + Math.random() * 200, 
          8, 
          40
        ));
      }
    };

    const animate = () => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      const dt = 0.016;

      if (phase === 'buildup') {
        // Pre-strike energy glow
        const gradient = ctx.createRadialGradient(
          canvas.width / 2, canvas.height / 2, 0,
          canvas.width / 2, canvas.height / 2, 100
        );
        gradient.addColorStop(0, 'rgba(102, 204, 255, 0.2)');
        gradient.addColorStop(1, 'rgba(0, 0, 0, 0)');
        ctx.fillStyle = gradient;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }

      if (phase === 'strike' || (phase === 'revealed' && strikeFrameCount < 30)) {
        strikeFrameCount++;
        // Multiple flicker pulses
        if (strikeFrameCount < 20) {
          strikeOpacity = Math.sin(strikeFrameCount * 1.5) > 0 ? 1 : 0.1;
          
          if (strikeFrameCount === 5) {
            setIsShaking(true);
            spawnSparks(canvas.width / 2, canvas.height / 2, 80);
            setTimeout(() => setIsShaking(false), 300);
          }

          // Draw layers
          [branches, [lightningSegments]].flat().forEach((path: any) => {
            drawBolt(path, 12, strikeOpacity * 0.3, '#0088ff', 30); // Aura
            drawBolt(path, 6, strikeOpacity * 0.8, '#00ccff', 10);  // Mid
            drawBolt(path, 2, strikeOpacity, '#ffffff', 2);        // Core
          });

          // Impact shockwave
          if (strikeFrameCount > 5 && strikeFrameCount < 15) {
            ctx.beginPath();
            ctx.arc(canvas.width / 2, canvas.height / 2, (strikeFrameCount - 5) * 40, 0, Math.PI * 2);
            ctx.strokeStyle = `rgba(102, 204, 255, ${1 - (strikeFrameCount - 5) / 10})`;
            ctx.lineWidth = 2;
            ctx.stroke();
          }
        } else if (phase === 'strike') {
          setPhase('revealed');
        }
      }

      if (phase === 'revealed') {
        // Random sparks on letters
        if (Math.random() > 0.92) {
          const rx = canvas.width / 2 + (Math.random() - 0.5) * 600;
          const ry = canvas.height / 2 + (Math.random() - 0.5) * 200;
          spawnSparks(rx, ry, 3, true);
        }
      }

      updateSparks(sparksRef.current, dt);
      updateSparks(textSparksRef.current, dt);
      drawSparks(sparksRef.current);
      drawSparks(textSparksRef.current);

      animationFrameId = requestAnimationFrame(animate);
    };

    init();
    animate();

    window.addEventListener('resize', init);
    return () => {
      cancelAnimationFrame(animationFrameId);
      window.removeEventListener('resize', init);
    };
  }, [phase]);

  return (
    <div className={`relative min-h-screen bg-black flex flex-col items-center justify-center overflow-hidden transition-transform duration-75 ${isShaking ? 'translate-x-1 -translate-y-1' : ''}`}>
      {/* Screen Flash Layer */}
      <div className={`fixed inset-0 bg-white pointer-events-none z-[100] transition-opacity duration-100 ${phase === 'strike' && isShaking ? 'opacity-30' : 'opacity-0'}`} />
      
      {/* Main Canvas */}
      <canvas ref={canvasRef} className="absolute inset-0 pointer-events-none z-[50]" />

      {/* Cinematic Reveal Content */}
      <div className={`relative z-10 text-center flex flex-col items-center transition-all duration-1000 ${phase === 'revealed' ? 'opacity-100 scale-100 translate-y-0' : 'opacity-0 scale-[0.8] translate-y-10'}`}>
        
        {/* Top Permission Panel */}
        <div className="absolute top-[-35vh] w-full flex justify-center z-20">
          <div className="glass-panel rounded-2xl px-10 py-5 flex items-center space-x-10 shadow-[0_0_50px_rgba(13,89,242,0.15)] border-white/5">
            <div className="flex items-center space-x-6 border-r border-white/10 pr-10">
              <div className="flex space-x-4">
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-500 ${permissionsGranted ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'bg-primary/20 text-primary border border-primary/30 shadow-[0_0_15px_rgba(13,89,242,0.3)]'}`}>
                  <span className="material-icons text-2xl">{permissionsGranted ? 'check_circle' : 'videocam'}</span>
                </div>
                <div className={`w-11 h-11 rounded-xl flex items-center justify-center transition-all duration-500 ${permissionsGranted ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.3)]' : 'bg-primary/20 text-primary border border-primary/30 shadow-[0_0_15px_rgba(13,89,242,0.3)]'}`}>
                  <span className="material-icons text-2xl">{permissionsGranted ? 'check_circle' : 'mic'}</span>
                </div>
              </div>
              <div className="text-left">
                <p className="text-[10px] font-black uppercase tracking-[0.4em] text-primary/80 mb-1">Neural Access</p>
                <h4 className="text-sm font-bold tracking-tight text-white/90">{permissionsGranted ? 'LINK VERIFIED' : 'AWAITING UPLINK'}</h4>
              </div>
            </div>
            <Button onClick={requestPermissions} disabled={permissionsGranted} variant={permissionsGranted ? 'ghost' : 'primary'} className="py-3 px-6 text-xs font-black tracking-[0.2em]" glow={!permissionsGranted}>
              {permissionsGranted ? 'AUTHORIZED' : 'GRANT ACCESS'}
            </Button>
          </div>
        </div>

        <div className="relative group">
          <div className="absolute -inset-16 border border-primary/10 rounded-[3rem] pointer-events-none group-hover:border-primary/20 transition-colors duration-1000"></div>
          
          {/* Main Title with Cinematic Glow */}
          <h1 className="text-8xl md:text-[11rem] font-black tracking-[0.2em] text-white leading-none selection:bg-primary/50 text-glow-electric">
            FULL<br/>CONTROL
          </h1>
          
          <div className="mt-12 flex flex-col items-center space-y-4">
             <div className="flex items-center justify-center space-x-6">
                <div className="h-[1px] w-20 bg-gradient-to-r from-transparent via-primary/50 to-primary"></div>
                <p className="text-[12px] text-primary font-black uppercase tracking-[0.6em] animate-pulse drop-shadow-[0_0_8px_rgba(13,89,242,0.8)]">
                  Neural Link v4.0.2
                </p>
                <div className="h-[1px] w-20 bg-gradient-to-l from-transparent via-primary/50 to-primary"></div>
             </div>
             <p className="text-white/20 font-mono text-[9px] tracking-[0.8em] uppercase">Forged in High Voltage</p>
          </div>
        </div>

        {/* Enter System Action */}
        <div className="mt-24">
          <button 
            onClick={() => setScreen(Screen.GESTURE_DASHBOARD)}
            className="group relative flex items-center space-x-12 bg-white/[0.03] hover:bg-primary/10 border border-white/5 hover:border-primary/40 px-12 py-6 rounded-3xl transition-all duration-700 hover:scale-110 active:scale-95 shadow-[0_20px_60px_-15px_rgba(0,0,0,0.5)]"
          >
            <div className="absolute inset-0 bg-gradient-to-r from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity rounded-3xl"></div>
            <div className="text-left relative z-10">
              <p className="text-[11px] font-black tracking-[0.5em] text-primary mb-1 uppercase opacity-70 group-hover:opacity-100 transition-opacity">Direct Access</p>
              <span className="text-2xl font-black tracking-[0.2em] text-white group-hover:text-primary transition-colors">ENTER SYSTEM</span>
            </div>
            <div className="w-16 h-16 rounded-2xl bg-primary flex items-center justify-center shadow-[0_0_30px_rgba(13,89,242,0.4)] group-hover:rotate-[360deg] transition-all duration-700 relative z-10">
              <span className="material-icons text-4xl text-white group-hover:scale-110 transition-transform">bolt</span>
            </div>
          </button>
        </div>
      </div>

      <style>{`
        .text-glow-electric {
          text-shadow: 0 0 10px rgba(255, 255, 255, 0.4), 
                       0 0 30px rgba(102, 204, 255, 0.2), 
                       0 0 60px rgba(13, 89, 242, 0.1);
        }
        @keyframes electric-flicker {
          0%, 100% { opacity: 1; }
          45% { opacity: 0.95; }
          50% { opacity: 0.85; }
          55% { opacity: 0.98; }
        }
        .animate-electric {
          animation: electric-flicker 2s infinite;
        }
      `}</style>
    </div>
  );
};

export default IntroScreen;
