
import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'outline' | 'ghost' | 'danger';
  glow?: boolean;
}

export const Button: React.FC<ButtonProps> = ({ children, variant = 'primary', glow = false, className = '', ...props }) => {
  const base = "px-6 py-2.5 rounded-lg font-bold transition-all active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2";
  const variants = {
    primary: "bg-primary hover:bg-blue-600 text-white shadow-xl shadow-primary/20",
    outline: "border border-primary/40 hover:border-primary text-primary hover:bg-primary/10",
    ghost: "text-white/60 hover:text-white hover:bg-white/5",
    danger: "text-rose-500 hover:bg-rose-500/10",
  };
  
  const glowClass = glow ? "shadow-[0_0_20px_rgba(13,89,242,0.4)]" : "";

  return (
    <button className={`${base} ${variants[variant]} ${glowClass} ${className}`} {...props}>
      {children}
    </button>
  );
};

export const BackButton: React.FC<{ onClick: () => void; label?: string }> = ({ onClick, label = "BACK" }) => {
  return (
    <button 
      onClick={onClick}
      className="flex items-center gap-2 text-white/40 hover:text-white transition-all group px-4 py-2 rounded-xl hover:bg-white/5 border border-transparent hover:border-white/10"
    >
      <span className="material-icons text-xl group-hover:-translate-x-1 transition-transform">arrow_back</span>
      <span className="text-[10px] font-black uppercase tracking-[0.3em]">{label}</span>
    </button>
  );
};

export const Modal: React.FC<{ 
  isOpen: boolean; 
  onClose: () => void; 
  title: string; 
  children: React.ReactNode; 
  maxWidth?: string;
  closable?: boolean;
}> = ({ isOpen, onClose, title, children, maxWidth = "max-w-md", closable = true }) => {
  if (!isOpen) return null;
  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">
      <div 
        className="absolute inset-0 bg-black/80 backdrop-blur-sm" 
        onClick={() => closable && onClose()} 
      />
      <div className={`relative glass-panel rounded-2xl w-full ${maxWidth} overflow-hidden animate-in fade-in zoom-in duration-300`}>
        <div className="p-6 border-b border-white/10 flex justify-between items-center">
          <h3 className="text-xl font-bold uppercase tracking-tight">{title}</h3>
          {closable && (
            <button onClick={onClose} className="material-icons text-white/50 hover:text-white transition-colors">close</button>
          )}
        </div>
        <div className="p-8">
          {children}
        </div>
      </div>
    </div>
  );
};

export const LoadingOverlay: React.FC<{ active: boolean; message?: string }> = ({ active, message = "Processing Request..." }) => {
  if (!active) return null;
  return (
    <div className="fixed inset-0 z-[200] bg-bg-dark/80 backdrop-blur-md flex flex-col items-center justify-center gap-6">
      <div className="w-16 h-16 border-4 border-primary/20 border-t-primary rounded-full animate-spin"></div>
      <p className="text-sm font-bold uppercase tracking-[0.3em] text-primary animate-pulse">{message}</p>
    </div>
  );
};
