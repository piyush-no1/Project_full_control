import React, { useEffect, useState, useRef } from 'react';
import { useApp } from '../state/AppContext';
import { Screen, Gesture } from '../types';
import { Button, Modal, BackButton } from '../components/UI';
import { apiService, JobStatusResponse } from '../services/apiService';
import { connectEventSocket } from '../services/eventSocket';

type RecordingStep = 'PERMISSION' | 'TRAINING';

const GestureDashboard: React.FC = () => {
  const {
    gestures,
    user,
    refreshGestures,
    setScreen,
    logout,
    queueDeleteGesture,
    queueRetrainModel,
    removeGestureLocally,
    upsertGestureLocally,
  } = useApp();
  const [showLoginModal, setShowLoginModal] = useState(false);
  const [showProfileModal, setShowProfileModal] = useState(false);
  const [showInitiatePermissionModal, setShowInitiatePermissionModal] = useState(false);
  const [gestureToDelete, setGestureToDelete] = useState<Gesture | null>(null);

  const [recordingStep, setRecordingStep] = useState<RecordingStep | null>(null);
  const [isTraining, setIsTraining] = useState(false);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [jobState, setJobState] = useState<JobStatusResponse | null>(null);

  const [gestureName, setGestureName] = useState('');
  const [gestureDesc, setGestureDesc] = useState('');

  const activeJobRef = useRef<string | null>(null);

  useEffect(() => {
    refreshGestures();
  }, [refreshGestures]);

  useEffect(() => {
    activeJobRef.current = activeJobId;
  }, [activeJobId]);

  const handleJobUpdate = async (job: JobStatusResponse) => {
    if (activeJobRef.current && job.job_id !== activeJobRef.current) {
      return;
    }

    setJobState(job);
    const jobResult = (job.result || {}) as Record<string, unknown>;
    const gestureName =
      (typeof jobResult.gesture === 'string' && jobResult.gesture) ||
      ((job as unknown as { gesture_name?: string }).gesture_name ?? '');

    if (job.status === 'completed') {
      if (job.job_type === 'delete_gesture' && gestureName) {
        removeGestureLocally(gestureName);
      }
      if ((job.job_type === 'add_gesture' || job.job_type === 'finalize_gesture') && gestureName) {
        upsertGestureLocally(gestureName);
      }
      setIsTraining(false);
      await refreshGestures();
      setActiveJobId(null);
      setRecordingStep(null);
      setGestureName('');
      setGestureDesc('');
    } else if (job.status === 'failed') {
      setIsTraining(false);
      setActiveJobId(null);
      setRecordingStep(null);
      alert(job.message || 'Training failed');
    }
  };

  useEffect(() => {
    if (!user) {
      return;
    }
    const disconnect = connectEventSocket(
      user.id,
      (event) => {
        if (event.type === 'job_update' && event.job) {
          handleJobUpdate(event.job as JobStatusResponse);
        }
      },
      () => {
        // Keep the dashboard usable if the backend reconnects in the background.
      }
    );
    return disconnect;
  }, [user, refreshGestures]);

  useEffect(() => {
    if (!activeJobId) {
      return;
    }
    let cancelled = false;

    const poll = async () => {
      try {
        const job = await apiService.getJobStatus(activeJobId, user?.id || 'guest');
        if (!cancelled) {
          await handleJobUpdate(job);
        }
      } catch (error) {
        if (!cancelled) {
          console.error('Failed to poll job status:', error);
        }
      }
    };

    poll();
    const timer = window.setInterval(poll, 2000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activeJobId, user, refreshGestures]);

  const handleActionWithAuth = (action: () => void) => {
    if (!user) {
      setShowLoginModal(true);
    } else {
      action();
    }
  };

  const handleInitiateControl = () => {
    handleActionWithAuth(() => setShowInitiatePermissionModal(true));
  };

  const handleInitiatePermissionContinue = async () => {
    try {
      await navigator.mediaDevices.getUserMedia({ video: true, audio: true });
      setShowInitiatePermissionModal(false);
      setScreen(Screen.CONTROL_DASHBOARD);
    } catch (err) {
      alert('This feature requires access to your camera and microphone to enable gesture control.');
      setShowInitiatePermissionModal(false);
    }
  };

  const startRecordingFlow = () => {
    handleActionWithAuth(() => {
      setGestureName('');
      setGestureDesc('');
      setRecordingStep('PERMISSION');
    });
  };

  const handlePermissionContinue = async () => {
    const normalizedName = gestureName.trim().replace(/\s+/g, '_');
    const description = gestureDesc.trim();

    if (!normalizedName || !description) {
      alert('Please provide gesture name and description.');
      return;
    }

    setRecordingStep('TRAINING');
    setIsTraining(true);

    try {
      const response = await apiService.addGestureJob(
        {
          name: normalizedName,
          description,
          cooldown: 2.0,
          collectionMode: 'camera',
        },
        user?.id || 'guest'
      );

      if (response.status !== 'queued' || !response.job_id) {
        throw new Error(response.message || 'Failed to queue training job');
      }

      setActiveJobId(response.job_id);
      setJobState({
        job_id: response.job_id,
        job_type: 'add_gesture',
        user_id: user?.id || 'guest',
        status: 'queued',
        stage: response.stage || 'queued',
        message: `${response.message} Use the OpenCV capture window (S to start, Q to stop).`,
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      });
    } catch (error) {
      console.error('Error adding gesture:', error);
      setIsTraining(false);
      setRecordingStep('PERMISSION');
      alert((error as Error).message || 'Failed to start training');
    }
  };

  const closeCustomFlow = () => {
    if (activeJobId) {
      return;
    }
    setRecordingStep(null);
    setGestureName('');
    setGestureDesc('');
  };

  const confirmDelete = async () => {
    if (gestureToDelete) {
      const jobId = await queueDeleteGesture(gestureToDelete.id);
      if (jobId) {
        removeGestureLocally(gestureToDelete.id);
        setActiveJobId(jobId);
        setJobState({
          job_id: jobId,
          job_type: 'delete_gesture',
          user_id: user?.id || 'guest',
          status: 'queued',
          stage: 'queued',
          message: `Queued deletion for ${gestureToDelete.name}`,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        });
      }
      setGestureToDelete(null);
    }
  };

  const handleRetrain = async () => {
    const jobId = await queueRetrainModel();
    if (!jobId) {
      return;
    }
    setActiveJobId(jobId);
    setJobState({
      job_id: jobId,
      job_type: 'retrain_model',
      user_id: user?.id || 'guest',
      status: 'queued',
      stage: 'queued',
      message: 'Retraining queued',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    });
  };

  return (
    <div className="h-screen flex flex-col bg-bg-dark dot-pattern overflow-hidden">
      <header className="shrink-0 z-50 flex items-center justify-between px-10 py-6 glass-panel border-b border-white/10 shadow-2xl">
        <div className="flex items-center gap-8">
          <BackButton onClick={() => setScreen(Screen.INTRO)} />
          <div className="flex items-center gap-5">
            <div className="w-12 h-12 bg-primary flex items-center justify-center rounded-2xl shadow-[0_0_20px_rgba(13,89,242,0.4)] border border-white/20">
              <span className="material-icons text-white text-2xl">back_hand</span>
            </div>
            <div>
              <h1 className="text-2xl font-black tracking-tighter uppercase leading-none">Full Control</h1>
              <p className="text-[10px] text-primary font-black tracking-[0.3em] uppercase opacity-90 mt-1.5">Neural Library v5.0</p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-10">
          <button
            onClick={handleRetrain}
            disabled={!!activeJobId}
            className="flex items-center gap-3 px-6 py-2.5 rounded-xl bg-purple-neon/10 border border-purple-neon text-purple-neon hover:bg-purple-neon hover:text-white transition-all duration-300 shadow-[0_0_15px_rgba(188,19,254,0.2)] disabled:opacity-40 disabled:cursor-not-allowed"
          >
            <span className="material-icons text-sm">auto_fix_high</span>
            <span className="text-[10px] font-black uppercase tracking-widest">Retrain Model</span>
          </button>

          <div className="hidden lg:flex flex-col items-end">
            <span className="text-[10px] text-slate-500 uppercase tracking-widest font-black">Environment Tracking</span>
            <span className="text-[10px] text-emerald-400 flex items-center gap-2 font-black">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse shadow-[0_0_8px_#10b981]"></span>
              SYSTEM LIVE
            </span>
          </div>

          {user ? (
            <div className="flex items-center gap-4 group cursor-pointer" onClick={() => setShowProfileModal(true)}>
              <div className="text-right">
                <p className="text-sm font-black tracking-tight">{user.name}</p>
                <p className="text-[9px] text-primary uppercase font-black tracking-[0.2em] opacity-60 group-hover:opacity-100 transition-opacity">Profile</p>
              </div>
              <div className="w-11 h-11 rounded-xl overflow-hidden border border-primary/40 group-hover:border-primary transition-all shadow-lg">
                <img src={user.avatar || 'https://picsum.photos/seed/guest/100'} alt="Profile" className="w-full h-full object-cover" />
              </div>
            </div>
          ) : (
            <Button onClick={() => setScreen(Screen.LOGIN)} className="px-8" glow>
              <span className="material-icons text-lg">login</span>
              LOGIN
            </Button>
          )}
        </div>
      </header>

      <main className="flex-1 overflow-y-auto custom-scrollbar px-10 pt-12 pb-20">
        <div className="max-w-7xl mx-auto w-full">
          <div className="mb-14 animate-in fade-in slide-in-from-bottom duration-700">
            <h2 className="text-5xl font-light tracking-tighter">Neural <span className="text-primary font-black italic">Signatures</span></h2>
            <p className="text-slate-400 mt-3 text-lg max-w-2xl font-medium opacity-70">
              Select or configure hand-tracking patterns. Custom gestures are stored in your encrypted library.
            </p>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 gap-8 mb-20">
            <div
              onClick={startRecordingFlow}
              className="p-10 rounded-3xl border-2 border-dashed border-primary/20 hover:border-primary/60 bg-primary/5 flex flex-col items-center justify-center text-center transition-all duration-500 cursor-pointer group hover:shadow-[0_0_30px_rgba(13,89,242,0.1)] hover:-translate-y-2"
            >
              <div className="w-16 h-16 rounded-2xl border-2 border-primary/20 flex items-center justify-center mb-6 group-hover:bg-primary group-hover:border-primary transition-all duration-500 shadow-lg group-hover:shadow-primary/40">
                <span className="material-icons text-primary group-hover:text-white text-4xl">add</span>
              </div>
              <h3 className="text-xl font-black text-primary/90 uppercase tracking-tight">Record Custom</h3>
              <p className="text-[10px] text-slate-500 font-black mt-2 uppercase tracking-widest opacity-60">Train New Pattern</p>
            </div>

            {gestures.map((gesture, i) => (
              <div
                key={gesture.id}
                style={{ animationDelay: `${(i + 1) * 0.05}s` }}
                className="glass-panel p-10 rounded-3xl flex flex-col items-center text-center group relative cursor-pointer hover:bg-white/10 hover:border-primary/50 hover:-translate-y-3 transition-all duration-500 animate-in fade-in slide-in-from-bottom shadow-xl"
              >
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleActionWithAuth(() => setGestureToDelete(gesture));
                  }}
                  className="absolute top-4 right-4 w-8 h-8 rounded-full bg-rose-500/10 hover:bg-rose-500 text-rose-500 hover:text-white flex items-center justify-center transition-all opacity-0 group-hover:opacity-100 border border-rose-500/20"
                >
                  <span className="material-icons text-sm">delete</span>
                </button>

                <div className="text-6xl mb-8 transition-all duration-500 group-hover:scale-125 group-hover:drop-shadow-[0_0_15px_rgba(13,89,242,0.8)] grayscale group-hover:grayscale-0 opacity-80 group-hover:opacity-100">
                  {gesture.icon}
                </div>
                <h3 className="text-xl font-black mb-2 uppercase tracking-tight group-hover:text-primary transition-colors">{gesture.name}</h3>
                <p className="text-sm text-slate-500 font-bold opacity-60 group-hover:opacity-100">{gesture.description}</p>
              </div>
            ))}
          </div>
        </div>
      </main>

      <footer className="shrink-0 z-50 px-10 pb-10 pt-6 bg-gradient-to-t from-bg-dark via-bg-dark/95 to-transparent border-t border-white/5">
        <div className="max-w-4xl mx-auto flex flex-col items-center">
          <button
            onClick={handleInitiateControl}
            className="group relative overflow-hidden transition-all duration-700 border border-cyan-neon/30 flex flex-col items-center justify-center gap-4 py-8 px-24 rounded-3xl w-full shadow-[0_0_40px_rgba(0,242,255,0.15)] bg-bg-panel/90 hover:-translate-y-2 hover:border-cyan-neon/80 hover:shadow-[0_20px_60px_-15px_rgba(0,242,255,0.5)] active:scale-95"
          >
            <div className="absolute inset-0 bg-gradient-to-t from-cyan-neon/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity"></div>
            <span className="material-icons text-5xl transition-transform duration-700 group-hover:scale-110 group-hover:rotate-12 drop-shadow-[0_0_15px_rgba(0,242,255,0.6)] leading-none">bolt</span>
            <span className="font-black tracking-[0.4em] uppercase text-lg text-cyan-neon">Initiate System Control</span>
            <div className="absolute bottom-0 left-0 w-full h-1.5 bg-cyan-neon shadow-[0_0_20px_rgba(0,242,255,1)]"></div>
          </button>
        </div>
      </footer>

      <Modal isOpen={showLoginModal} onClose={() => setShowLoginModal(false)} title="LOGIN REQUIRED">
        <div className="text-center space-y-8 py-4">
          <span className="material-icons text-8xl text-primary">login</span>
          <p className="text-slate-400 text-lg">Please sign in to perform this action and sync your library.</p>
          <div className="space-y-4">
            <Button onClick={() => setScreen(Screen.LOGIN)} className="w-full py-4 uppercase" glow>Login Now</Button>
            <button onClick={() => setShowLoginModal(false)} className="text-[10px] font-black uppercase text-white/30 tracking-[0.5em]">Cancel</button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={showProfileModal} onClose={() => setShowProfileModal(false)} title="NEURAL PROFILE">
        {user && (
          <div className="flex flex-col items-center gap-8 py-4">
            <div className="w-24 h-24 rounded-3xl overflow-hidden border-2 border-primary shadow-[0_0_20px_rgba(13,89,242,0.3)]">
              <img src={user.avatar || 'https://picsum.photos/seed/guest/200'} alt="Avatar" className="w-full h-full object-cover" />
            </div>
            <div className="text-center">
              <h3 className="text-2xl font-black uppercase tracking-tight">{user.name}</h3>
              <p className="text-[10px] text-primary font-black tracking-[0.4em] uppercase opacity-70 mt-1">Uplink ID: {user.id}</p>
            </div>
            <div className="w-full grid grid-cols-2 gap-4">
              <div className="glass-panel p-4 rounded-xl text-center">
                <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1">Status</p>
                <p className="text-xs font-bold text-emerald-400">ACTIVE</p>
              </div>
              <div className="glass-panel p-4 rounded-xl text-center">
                <p className="text-[10px] text-slate-500 font-black uppercase tracking-widest mb-1">Type</p>
                <p className="text-xs font-bold text-primary">{user.isGuest ? 'GUEST' : 'PREMIUM'}</p>
              </div>
            </div>
            <div className="w-full pt-4">
              <Button onClick={logout} variant="danger" className="w-full py-4 uppercase tracking-[0.2em]" glow>
                Terminate Session
              </Button>
            </div>
          </div>
        )}
      </Modal>

      <Modal isOpen={!!gestureToDelete} onClose={() => setGestureToDelete(null)} title="Confirm Deletion">
        <div className="text-center space-y-6">
          <div className="w-20 h-20 bg-rose-500/10 rounded-full mx-auto flex items-center justify-center text-rose-500">
            <span className="material-icons text-5xl">warning</span>
          </div>
          <p className="text-slate-300 font-medium leading-relaxed">
            Are you sure you want to delete <span className="text-white font-bold">"{gestureToDelete?.name}"</span>?
            This action will remove the signature from your neural library.
          </p>
          <div className="flex flex-col gap-3 pt-4">
            <Button onClick={confirmDelete} variant="danger" className="w-full py-4 uppercase tracking-widest" glow>
              Delete Signature
            </Button>
            <button onClick={() => setGestureToDelete(null)} className="text-[10px] font-black uppercase text-white/30 tracking-[0.4em] hover:text-white transition-colors">
              Keep Gesture
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={showInitiatePermissionModal}
        onClose={() => setShowInitiatePermissionModal(false)}
        title="SYSTEM ACCESS REQUEST"
      >
        <div className="text-center space-y-8">
          <div className="w-24 h-24 bg-primary/10 rounded-3xl mx-auto flex items-center justify-center">
            <span className="material-icons text-5xl text-primary">sensors</span>
          </div>
          <p className="text-slate-300 font-medium">
            This feature requires access to your camera and microphone to enable gesture control. Please allow access to continue.
          </p>
          <div className="flex flex-col gap-4">
            <Button onClick={handleInitiatePermissionContinue} className="w-full py-4 uppercase tracking-widest" glow>Allow / Continue</Button>
            <button onClick={() => setShowInitiatePermissionModal(false)} className="text-[10px] font-black uppercase text-white/30 tracking-[0.4em] hover:text-white transition-colors">Cancel</button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={recordingStep === 'PERMISSION'}
        onClose={closeCustomFlow}
        title="CUSTOM GESTURE SETUP"
      >
        <div className="space-y-6">
          <div className="bg-white/5 border border-white/10 rounded-2xl p-5 text-left space-y-2">
            <p className="text-[10px] font-black uppercase tracking-[0.3em] text-primary flex items-center gap-2">
              <span className="material-icons text-sm">tips_and_updates</span>
              OpenCV Capture Instructions
            </p>
            <p className="text-[11px] leading-relaxed text-slate-400 font-medium">
              After you click continue, the backend OpenCV capture window will open. Press S to start sample collection and Q to finish.
            </p>
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase tracking-[0.3em] text-primary ml-1">Gesture Name</label>
            <input
              type="text"
              placeholder="e.g. Spiral_Wave"
              value={gestureName}
              onChange={(e) => setGestureName(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-4 text-white focus:outline-none focus:border-primary transition-colors"
            />
          </div>

          <div className="space-y-2">
            <label className="text-[10px] font-black uppercase tracking-[0.3em] text-primary ml-1">Description</label>
            <textarea
              placeholder="What should this gesture do?"
              value={gestureDesc}
              onChange={(e) => setGestureDesc(e.target.value)}
              className="w-full bg-white/5 border border-white/10 rounded-xl px-5 py-4 text-white focus:outline-none focus:border-primary transition-colors min-h-[100px]"
            />
          </div>

          <div className="flex flex-col gap-3 pt-2">
            <Button onClick={handlePermissionContinue} className="w-full py-4 uppercase tracking-widest" glow>
              Continue (OpenCV Capture)
            </Button>
            <button onClick={closeCustomFlow} className="text-[10px] font-black uppercase text-white/30 tracking-[0.4em] hover:text-white transition-colors">
              Cancel
            </button>
          </div>
        </div>
      </Modal>

      {(isTraining || !!activeJobId) && (
        <div className="fixed inset-0 z-[200] bg-bg-dark/95 backdrop-blur-xl flex flex-col items-center justify-center gap-10">
          <div className="w-24 h-24 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
          <p className="text-xl font-black uppercase tracking-[0.4em] text-white">
            {jobState?.status === 'completed' ? 'Training Complete' : 'Training in Progress'}
          </p>
          <p className="text-xs uppercase tracking-[0.2em] text-white/70">
            {jobState?.stage || 'queued'}
          </p>
          <p className="text-sm text-white/70 text-center max-w-xl px-6">
            {jobState?.message || 'Preparing gesture training job...'}
          </p>
        </div>
      )}

      <style>{`
        .custom-scrollbar::-webkit-scrollbar { width: 4px; }
        .custom-scrollbar::-webkit-scrollbar-track { background: rgba(255, 255, 255, 0.02); }
        .custom-scrollbar::-webkit-scrollbar-thumb { background: rgba(13, 89, 242, 0.2); border-radius: 10px; }
      `}</style>
    </div>
  );
};

export default GestureDashboard;
