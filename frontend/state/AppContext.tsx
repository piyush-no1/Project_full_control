
import React, { createContext, useContext, useState, useEffect } from 'react';
import { Screen, User, Gesture, AppState } from '../types';
import { apiService } from '../services/apiService';
import { signInWithPopup, signOut } from "firebase/auth";
import { auth, googleProvider } from "../services/firebase";

interface AppContextType extends AppState {
  setScreen: (screen: Screen) => void;
  login: (method: 'google' | 'guest') => Promise<void>;
  logout: () => Promise<void>;
  exitSession: () => void;
  startAirStylus: () => Promise<boolean>;
  startGestureControl: () => Promise<boolean>;
  stopActiveControl: () => Promise<void>;
  refreshGestures: () => Promise<void>;
  removeGesture: (id: string) => Promise<void>;
  retrainModel: () => Promise<void>;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentScreen, setCurrentScreen] = useState<Screen>(Screen.INTRO);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [gestures, setGestures] = useState<Gesture[]>([]);
  const [needsRetraining, setNeedsRetraining] = useState(false);

  const setScreen = (screen: Screen) => setCurrentScreen(screen);

  const login = async (method: 'google' | 'guest') => {
    setIsLoading(true);
    try {
      if (method === 'google') {
        const result = await signInWithPopup(auth, googleProvider);
      
        const userData = {
          id: result.user.uid,
          name: result.user.displayName || "",
          email: result.user.email || "",
          avatar: result.user.photoURL || ""
        };
      
        setUser(userData);
        setCurrentScreen(Screen.GESTURE_DASHBOARD);
      }
    
      if (method === 'guest') {
        setUser({
          id: "guest",
          name: "Guest",
          email: "",
          avatar: ""
        });
        setCurrentScreen(Screen.GESTURE_DASHBOARD);
      }
    
    } catch (error) {
      console.error("Login failed:", error);
    } finally {
      setIsLoading(false);
    }
  };


  const logout = async () => {
    setIsLoading(true);
    try {
      await signOut(auth);
      setUser(null);
      setCurrentScreen(Screen.INTRO);
    } catch (error) {
      console.error("Logout failed:", error);
    } finally {
      setIsLoading(false);
    }
  };


  const exitSession = () => {
    setCurrentScreen(Screen.GESTURE_DASHBOARD);
  };

  const refreshGestures = async () => {
    setIsLoading(true);
    try {
      const data = await apiService.fetchGestures();
      setGestures(data);
    } finally {
      setIsLoading(false);
    }
  };

  const startAirStylus = async (): Promise<boolean> => {
    setIsLoading(true);
    try {
      const success = await apiService.startAirStylus();
      if (success) setScreen(Screen.CONTROL_DASHBOARD);
      return success;
    } catch {
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const startGestureControl = async (): Promise<boolean> => {
    setIsLoading(true);
    try {
      const success = await apiService.startGestureControl();
      if (success) setScreen(Screen.CONTROL_DASHBOARD);
      return success;
    } catch {
      return false;
    } finally {
      setIsLoading(false);
    }
  };

  const stopActiveControl = async () => {
    setIsLoading(true);
    try {
      await apiService.stopControl();
      setScreen(Screen.GESTURE_DASHBOARD);
    } finally {
      setIsLoading(false);
    }
  };

  const removeGesture = async (id: string) => {
    setIsLoading(true);
    try {
      await apiService.deleteGesture(id);
      setNeedsRetraining(true);
      await refreshGestures();
    } finally {
      setIsLoading(false);
    }
  };

  const retrainModel = async () => {
    setIsLoading(true);
    try {
      await apiService.retrainModel();
      setNeedsRetraining(false);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <AppContext.Provider value={{
      currentScreen,
      user,
      isLoading,
      gestures,
      needsRetraining,
      setScreen,
      login,
      logout,
      exitSession,
      startAirStylus,
      startGestureControl,
      stopActiveControl,
      refreshGestures,
      removeGesture,
      retrainModel
    }}>
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) throw new Error('useApp must be used within an AppProvider');
  return context;
};
