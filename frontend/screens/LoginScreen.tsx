
import React from 'react';
import { useApp } from '../state/AppContext';
import { Screen } from '../types';
import { Button, BackButton } from '../components/UI';
import { loginWithGoogle } from "../services/authService";

const handleGoogleLogin = async () => {
  try {
    const user = await loginWithGoogle();
    console.log("Logged in user:", user);
  } catch (error) {
    console.error("Login failed:", error);
  }
};
const LoginScreen: React.FC = () => {
  const { login, setScreen } = useApp();

  return (
    <div className="min-h-screen bg-bg-dark flex flex-col items-center justify-center p-6 dot-pattern relative">
      <div className="fixed top-10 left-10">
        <BackButton onClick={() => setScreen(Screen.GESTURE_DASHBOARD)} label="BACK TO LIBRARY" />
      </div>

      <div className="absolute top-0 left-0 w-full h-full pointer-events-none opacity-20 overflow-hidden">
        <div className="absolute top-1/4 -left-20 w-96 h-96 bg-primary rounded-full blur-[120px]"></div>
        <div className="absolute bottom-1/4 -right-20 w-96 h-96 bg-primary rounded-full blur-[120px]"></div>
      </div>

      <div className="w-full max-w-4xl flex flex-col items-center z-10 animate-in fade-in zoom-in duration-700">
        <div className="mb-16 flex flex-col items-center">
          <div className="mb-4 bg-primary/10 p-4 rounded-xl border border-primary/30 shadow-[0_0_20px_rgba(13,89,242,0.2)]">
            <span className="material-icons text-5xl text-primary neon-glow">back_hand</span>
          </div>
          <h1 className="text-5xl font-bold tracking-tighter neon-glow uppercase">
            FULL <span className="text-primary">CONTROL</span>
          </h1>
          <p className="mt-4 text-primary/60 font-medium tracking-widest uppercase text-xs">Gesture-Based PC Interface</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 w-full">
          <button 
            onClick={() => login('google')}
            className="group relative flex flex-col items-center p-10 bg-bg-panel/40 backdrop-blur-xl border border-white/10 rounded-xl transition-all duration-300 hover:border-primary hover:shadow-[0_0_40px_rgba(13,89,242,0.2)] hover:-translate-y-1"
          >
            <div className="mb-6 h-20 w-20 flex items-center justify-center bg-white rounded-full transition-colors overflow-hidden shadow-lg group-hover:scale-110">
              <svg className="w-10 h-10" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"></path>
                <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"></path>
                <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l3.66-2.84z" fill="#FBBC05"></path>
                <path d="M12 5.38c1.62 0 3.06.56 4.21 1.66l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335"></path>
              </svg>
            </div>
            <h2 className="text-2xl font-semibold mb-2 group-hover:text-primary transition-colors">Login with Google</h2>
            <p className="text-white/40 text-center text-sm leading-relaxed max-w-[200px]">
              Access your personalized gesture library and sync devices.
            </p>
            <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="material-icons text-primary">arrow_forward</span>
            </div>
          </button>

          <button 
            onClick={() => login('guest')}
            className="group relative flex flex-col items-center p-10 bg-bg-panel/40 backdrop-blur-xl border border-white/10 rounded-xl transition-all duration-300 hover:border-primary hover:shadow-[0_0_40px_rgba(13,89,242,0.2)] hover:-translate-y-1"
          >
            <div className="mb-6 h-20 w-20 flex items-center justify-center bg-white/5 rounded-full transition-colors group-hover:bg-primary/10 group-hover:scale-110">
              <span className="material-icons text-4xl text-white/60 group-hover:text-primary">person_outline</span>
            </div>
            <h2 className="text-2xl font-semibold mb-2 group-hover:text-primary transition-colors">Continue as Guest</h2>
            <p className="text-white/40 text-center text-sm leading-relaxed max-w-[200px]">
              Explore basic features without saving your preferences.
            </p>
            <div className="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity">
              <span className="material-icons text-primary">arrow_forward</span>
            </div>
          </button>
        </div>

        <div className="mt-16">
          <div className="flex gap-4">
            <div className="h-1 w-1 rounded-full bg-primary/40"></div>
            <div className="h-1 w-1 rounded-full bg-primary/40"></div>
            <div className="h-1 w-1 rounded-full bg-primary/40"></div>
          </div>
        </div>
      </div>

      <footer className="fixed bottom-8 left-8 hidden lg:block">
        <div className="flex items-center gap-4 text-xs font-mono text-white/20 tracking-tighter">
          <span className="material-icons text-xs">sensors</span>
          <span>SYSTEM STATUS: <span className="text-emerald-500/50 uppercase">Operational</span></span>
        </div>
      </footer>
    </div>
  );
};

export default LoginScreen;
