import React, { useState, useRef, useEffect } from 'react';
import { useApp } from '../state/AppContext';
import { Screen } from '../types';
import { Button, Modal, BackButton } from '../components/UI';
import { connectSocket } from "../services/socket";


const ControlDashboard: React.FC = () => {
  const { user, logout, startAirStylus, startGestureControl, stopActiveControl, exitSession } = useApp();
  const [activeMode, setActiveMode] = useState<'gesture' | 'stylus' | 'none'>('none');
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  
  const videoRef = useRef<HTMLImageElement>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [gestureInfo, setGestureInfo] = useState({ gesture: '', confidence: 0, status: 'no_hand' });

  // Connect to WebSocket for video streaming
  const connectVideoStream = () => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsHost = window.location.hostname;
    const ws = new WebSocket(`${wsProtocol}://${wsHost}:8000/ws/video`);
    
    ws.onopen = () => {
      console.log('[WebSocket] Connected to video stream');
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        
        if (data.type === 'frame' && data.frame) {
          // Update the image source
          if (videoRef.current) {
            videoRef.current.src = data.frame;
          }
          // Update gesture info
          setGestureInfo({
            gesture: data.gesture || '',
            confidence: data.confidence || 0,
            status: data.status || 'no_hand'
          });
        }
      } catch (err) {
        console.error('Error parsing WebSocket message:', err);
      }
    };
    
    ws.onclose = () => {
      console.log('[WebSocket] Disconnected from video stream');
    };
    
    ws.onerror = (err) => {
      console.error('[WebSocket] Error:', err);
    };
    
    wsRef.current = ws;
  };

  const disconnectVideoStream = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setGestureInfo({ gesture: '', confidence: 0, status: 'no_hand' });
  };

  const stopStream = () => {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      setStream(null);
    }
  };

  useEffect(() => {
    connectSocket();
    
    return () => {
      disconnectVideoStream();
    };
  }, []);

  const handleStartStylus = async () => {
    const success = await startAirStylus();
    if (!success) {
      alert('Failed to start Air Stylus. Check backend is running on port 8000.');
      return;
    }
    setActiveMode('stylus');
    connectVideoStream();
  };

  const handleStartGesture = async () => {
    const success = await startGestureControl();
    if (!success) {
      alert('Failed to start Gesture Engine. Check backend is running on port 8000.');
      return;
    }
    setActiveMode('gesture');
    connectVideoStream();
  };

  const handleStop = async () => {
    setActiveMode('none');
    disconnectVideoStream();
    await stopActiveControl();
  };

  const handleTerminate = async () => {
    disconnectVideoStream();
    stopStream();
    await logout();
  };

  const handleBackToLibrary = () => {
    handleStop();
    exitSession();
  };

  return (
    <div className="min-h-screen bg-bg-dark font-sans flex overflow-hidden">
      <header className="fixed top-0 left-0 right-0 h-20 glass-panel border-b border-white/5 z-40 px-10 flex items-center justify-between shadow-xl">
        <div className="flex items-center gap-6">
          <BackButton onClick={handleBackToLibrary} label="STOP & RETURN" />
          <div className="h-8 w-[1px] bg-white/10 mx-2"></div>
          <h1 className="text-xl font-black tracking-tighter uppercase neon-glow">
            Full Control <span className="text-primary italic">Center</span>
          </h1>
        </div>
        
        <div className="flex items-center gap-8">
          <div className="flex items-center gap-3 px-5 py-2 rounded-full bg-emerald-500/10 border border-emerald-500/20">
            <span className={`w-2 h-2 rounded-full ${activeMode !== 'none' ? 'bg-emerald-500 animate-pulse' : 'bg-white/20'}`}></span>
            <span className="text-[10px] font-black uppercase tracking-[0.2em] text-emerald-500">
              {activeMode !== 'none' ? 'Neural Link Active' : 'System Idle'}
            </span>
          </div>

          {user && (
            <div 
              className="flex items-center gap-4 group cursor-pointer border-l border-white/10 pl-8 transition-all hover:opacity-80" 
              onClick={() => setIsProfileOpen(true)}
            >
              <div className="text-right">
                <p className="text-sm font-black tracking-tight">{user.name}</p>
                <p className="text-[9px] text-primary uppercase font-black tracking-[0.2em] opacity-60 group-hover:opacity-100">User Profile</p>
              </div>
              <div className="w-12 h-12 rounded-xl overflow-hidden border border-primary/40 group-hover:border-primary transition-all shadow-lg ring-4 ring-primary/5">
                <img src={user.avatar || 'https://picsum.photos/seed/guest/100'} alt="Profile" className="w-full h-full object-cover" />
              </div>
            </div>
          )}
        </div>
      </header>

      <main className="flex-1 pt-20 flex flex-col items-center justify-center relative">
        <div className="absolute inset-0 dot-pattern pointer-events-none opacity-40" />
        
        <div className="relative z-10 w-full max-w-6xl px-10 flex flex-col items-center animate-in fade-in zoom-in duration-700">
          
          <div className="w-full relative group mb-12">
            <div className={`relative aspect-video rounded-[3rem] overflow-hidden border-2 transition-all duration-700 ${activeMode !== 'none' ? 'border-primary shadow-[0_0_80px_rgba(13,89,242,0.3)]' : 'border-white/10 bg-white/5 shadow-2xl'}`}>
              
              {/* Video from WebSocket - for gesture mode */}
              <img 
                ref={videoRef}
                alt="Video Feed"
                className={`w-full h-full object-cover transition-opacity duration-700 scale-x-[-1] ${activeMode !== 'none' ? 'opacity-100' : 'opacity-0'}`}
              />

              {activeMode !== 'none' && (
                <div className="absolute inset-0 pointer-events-none">
                  <div className="absolute inset-0 border-[40px] border-transparent border-t-primary/5 border-b-primary/5"></div>
                  <div className="absolute inset-0 grid grid-cols-12 grid-rows-8 gap-4 p-8 opacity-20">
                    {Array.from({ length: 96 }).map((_, i) => (
                      <div key={i} className="w-1 h-1 bg-primary rounded-full"></div>
                    ))}
                  </div>
                </div>
              )}

              {activeMode === 'none' && (
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <div className="w-32 h-32 rounded-full bg-white/5 flex items-center justify-center mb-8 border border-white/10 animate-pulse">
                    <span className="material-icons text-7xl text-white/10">sensors</span>
                  </div>
                  <p className="text-white/20 font-black uppercase tracking-[0.6em] text-sm">Awaiting Neural Link Initialization</p>
                </div>
              )}

              {activeMode !== 'none' && (
                <div className="absolute top-8 left-8 flex flex-col gap-4">
                  <div className="bg-black/60 backdrop-blur-md px-6 py-4 rounded-2xl border border-white/10 flex items-center gap-5">
                    <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                      <span className="material-icons text-primary">
                        {activeMode === 'stylus' ? 'draw' : 'back_hand'}
                      </span>
                    </div>
                    <div className="text-left">
                      <p className="text-[10px] font-black text-primary uppercase tracking-widest leading-none mb-1">Active Interface</p>
                      <h4 className="text-sm font-black uppercase tracking-tight">{activeMode === 'stylus' ? 'Air Stylus Mode' : 'Gesture Engine'}</h4>
                    </div>
                  </div>
                  
                  {/* Gesture Info Overlay */}
                  {activeMode === 'gesture' && gestureInfo.status !== 'no_hand' && (
                    <div className="bg-black/60 backdrop-blur-md px-4 py-3 rounded-xl border border-white/10">
                      <p className="text-[10px] text-white/60 uppercase tracking-wider">Detected</p>
                      <p className="text-lg font-black text-emerald-400 uppercase">{gestureInfo.gesture || '—'}</p>
                      <p className="text-xs text-white/40">{Math.round(gestureInfo.confidence * 100)}% confidence</p>
                    </div>
                  )}
                </div>
              )}

              {activeMode !== 'none' && (
                <div className="absolute bottom-8 right-8">
                  <div className="bg-black/60 backdrop-blur-md px-5 py-3 rounded-xl border border-white/10 text-[10px] font-mono font-bold text-emerald-400 flex items-center gap-3">
                    <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full animate-ping"></span>
                    SYNC: 30FPS | LATENCY: 33MS
                  </div>
                </div>
              )}
            </div>

            <div className="text-center mt-12">
              <h2 className="text-6xl font-black mb-4 tracking-tighter uppercase leading-none">
                {activeMode === 'none' ? 'Initialize Bridge' : activeMode === 'stylus' ? 'Air Stylus Live' : 'Gesture Engine Live'}
              </h2>
              <p className="text-primary/60 max-w-xl mx-auto leading-relaxed font-bold uppercase tracking-[0.2em] text-[10px] opacity-80">
                Direct neural uplink verified. Tracking hand coordinates v3.1 for <span className="text-white">{user?.name}</span>. 
                Keep your hand within the focal frame.
              </p>
            </div>
          </div>
        </div>

        {/* Terminate Session - Bottom Right */}
        <div className="fixed bottom-12 right-12 z-[60]">
          <button 
            onClick={handleTerminate}
            className="flex items-center gap-4 px-8 py-5 rounded-2xl bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white transition-all duration-500 group border border-rose-500/20 hover:border-rose-500 shadow-2xl hover:shadow-[0_0_40px_rgba(244,63,94,0.3)] active:scale-95"
          >
            <span className="material-icons group-hover:rotate-180 transition-transform duration-500">logout</span>
            <span className="font-black uppercase tracking-[0.3em] text-xs">Terminate Session</span>
          </button>
        </div>

        {/* Control Bar - Resized buttons to be equal size */}
        <nav className="fixed bottom-12 left-1/2 -translate-x-1/2 z-30 w-full max-w-4xl px-6">
          <div className="flex flex-col md:flex-row gap-6 bg-bg-panel/60 p-5 rounded-[3rem] border border-white/10 backdrop-blur-2xl shadow-[0_30px_100px_-20px_rgba(0,0,0,0.8)]">
            <button 
              onClick={handleStartStylus}
              className={`flex-1 relative group flex items-center justify-center gap-5 py-6 px-10 rounded-[2rem] border transition-all duration-500 overflow-hidden ${activeMode === 'stylus' ? 'bg-primary border-primary shadow-[0_0_30px_rgba(13,89,242,0.4)] scale-105' : 'bg-white/5 border-white/5 hover:border-white/20'}`}
            >
              <span className={`material-symbols-outlined text-4xl transition-all duration-500 ${activeMode === 'stylus' ? 'text-white' : 'text-white/20 group-hover:text-white/60'}`}>draw</span>
              <span className={`text-[11px] font-black uppercase tracking-[0.4em] ${activeMode === 'stylus' ? 'text-white' : 'text-white/40'}`}>Air Stylus</span>
              {activeMode === 'stylus' && <div className="absolute inset-x-0 bottom-0 h-1.5 bg-white/20 animate-pulse"></div>}
            </button>

            <button 
              onClick={handleStartGesture}
              className={`flex-1 relative group flex items-center justify-center gap-5 py-6 px-10 rounded-[2rem] border transition-all duration-500 overflow-hidden ${activeMode === 'gesture' ? 'bg-primary border-primary shadow-[0_0_30px_rgba(13,89,242,0.4)] scale-105' : 'bg-white/5 border-white/5 hover:border-white/20'}`}
            >
              <span className={`material-symbols-outlined text-4xl transition-all duration-500 ${activeMode === 'gesture' ? 'text-white' : 'text-white/20 group-hover:text-white/60'}`}>back_hand</span>
              <span className={`text-[11px] font-black uppercase tracking-[0.4em] ${activeMode === 'gesture' ? 'text-white' : 'text-white/40'}`}>Gesture Engine</span>
              {activeMode === 'gesture' && <div className="absolute inset-x-0 bottom-0 h-1.5 bg-white/20 animate-pulse"></div>}
            </button>

            <button 
              onClick={handleStop}
              className={`flex-1 relative group flex items-center justify-center gap-5 py-6 px-10 rounded-[2rem] border transition-all duration-500 overflow-hidden ${activeMode === 'none' ? 'bg-rose-500 border-rose-500 shadow-[0_0_30px_rgba(244,63,94,0.4)]' : 'bg-rose-500/10 border-rose-500/20 hover:bg-rose-500/20'}`}
            >
              <span className={`material-symbols-outlined text-4xl transition-all duration-500 ${activeMode === 'none' ? 'text-white' : 'text-rose-500'}`}>stop_circle</span>
              <span className={`text-[11px] font-black uppercase tracking-[0.4em] ${activeMode === 'none' ? 'text-white' : 'text-rose-500'}`}>Stop System</span>
            </button>
          </div>
        </nav>
      </main>

      {/* Neural Profile Panel */}
      <Modal isOpen={isProfileOpen} onClose={() => setIsProfileOpen(false)} title="NEURAL PROFILE">
        {user && (
          <div className="flex flex-col items-center gap-10 py-4">
            <div className="relative">
              <div className="w-28 h-28 rounded-3xl overflow-hidden border-2 border-primary shadow-[0_0_30px_rgba(13,89,242,0.4)]">
                <img src={user.avatar || 'https://picsum.photos/seed/guest/200'} alt="Avatar" className="w-full h-full object-cover" />
              </div>
              <div className="absolute -bottom-2 -right-2 w-8 h-8 bg-emerald-500 rounded-full border-4 border-bg-panel flex items-center justify-center">
                <span className="material-icons text-white text-[16px]">check</span>
              </div>
            </div>
            
            <div className="text-center">
              <h3 className="text-3xl font-black uppercase tracking-tight mb-2">{user.name}</h3>
              <p className="text-[10px] text-primary font-black tracking-[0.5em] uppercase opacity-70">Uplink Verified: {user.id}</p>
            </div>

            <div className="w-full grid grid-cols-2 gap-5">
              <div className="glass-panel p-5 rounded-2xl text-center border-white/5">
                <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-2">Neural Link</p>
                <p className="text-sm font-black text-emerald-400 uppercase">Connected</p>
              </div>
              <div className="glass-panel p-5 rounded-2xl text-center border-white/5">
                <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-2">Response</p>
                <p className="text-sm font-black text-primary uppercase">Ultra Low</p>
              </div>
            </div>

            <div className="w-full space-y-4 pt-4">
              <Button onClick={() => setIsProfileOpen(false)} className="w-full py-5 uppercase tracking-[0.3em] text-xs" glow>
                Return to Command
              </Button>
              <button 
                onClick={handleTerminate} 
                className="w-full py-4 text-[10px] font-black uppercase tracking-[0.4em] text-rose-500/60 hover:text-rose-500 transition-colors"
              >
                End Current Session
              </button>
            </div>
          </div>
        )}
      </Modal>
    </div>
  );
};

export default ControlDashboard;
