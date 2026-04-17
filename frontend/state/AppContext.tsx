import React, { createContext, useCallback, useContext, useMemo, useState } from 'react';
import { signInWithPopup, signOut } from 'firebase/auth';

import { AppState, Gesture, Screen, User } from '../types';
import { apiService, createGestureFromName } from '../services/apiService';
import { auth, firebaseAuthEnabled, googleProvider } from '../services/firebase';

interface AppContextType extends AppState {
  setScreen: (screen: Screen) => void;
  login: (method: 'google' | 'guest') => Promise<void>;
  logout: () => Promise<void>;
  exitSession: () => void;
  startAirStylus: () => Promise<boolean>;
  startGestureControl: () => Promise<boolean>;
  stopActiveControl: () => Promise<void>;
  refreshGestures: () => Promise<void>;
  queueDeleteGesture: (gestureId: string) => Promise<string | null>;
  queueRetrainModel: () => Promise<string | null>;
  removeGestureLocally: (gestureId: string) => void;
  upsertGestureLocally: (gestureName: string) => void;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const normalizeGuestUser = (): User => ({
  id: 'guest',
  name: 'Guest',
  isGuest: true,
  email: '',
  avatar: '',
});

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [currentScreen, setCurrentScreen] = useState<Screen>(Screen.INTRO);
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [gestures, setGestures] = useState<Gesture[]>([]);
  const [needsRetraining, setNeedsRetraining] = useState(false);

  const setScreen = (screen: Screen) => setCurrentScreen(screen);

  const activeUserId = useMemo(() => user?.id || 'guest', [user?.id]);

  const login = async (method: 'google' | 'guest') => {
    setIsLoading(true);
    try {
      let nextUser: User;
      if (method === 'google') {
        if (!firebaseAuthEnabled || !auth || !googleProvider) {
          throw new Error(
            'Google login is not configured. Set VITE_FIREBASE_* variables or continue as Guest.'
          );
        }
        const result = await signInWithPopup(auth, googleProvider);
        nextUser = {
          id: result.user.uid,
          name: result.user.displayName || 'User',
          email: result.user.email || '',
          avatar: result.user.photoURL || '',
          isGuest: false,
        };
      } else {
        nextUser = normalizeGuestUser();
      }
      setUser(nextUser);
      await apiService.syncUserProfile(nextUser.id);
      setCurrentScreen(Screen.GESTURE_DASHBOARD);
    } catch (error) {
      console.error('Login failed:', error);
      alert(error instanceof Error ? error.message : 'Login failed');
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    setIsLoading(true);
    try {
      if (auth && auth.currentUser) {
        await signOut(auth);
      }
      setUser(null);
      setGestures([]);
      setCurrentScreen(Screen.INTRO);
      setNeedsRetraining(false);
    } catch (error) {
      console.error('Logout failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const exitSession = () => {
    setCurrentScreen(Screen.GESTURE_DASHBOARD);
  };

  const refreshGestures = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await apiService.fetchGestures(activeUserId);
      setGestures(data);
    } finally {
      setIsLoading(false);
    }
  }, [activeUserId]);

  const startAirStylus = async (): Promise<boolean> => {
    setIsLoading(true);
    try {
      const success = await apiService.startAirStylus(activeUserId);
      if (success) {
        try {
          await apiService.updateUserSettings({ last_control_mode: 'air_stylus' }, activeUserId);
        } catch (error) {
          console.warn('Failed to persist user settings:', error);
        }
        setScreen(Screen.CONTROL_DASHBOARD);
      }
      return success;
    } finally {
      setIsLoading(false);
    }
  };

  const startGestureControl = async (): Promise<boolean> => {
    setIsLoading(true);
    try {
      const success = await apiService.startGestureControl(activeUserId);
      if (success) {
        try {
          await apiService.updateUserSettings({ last_control_mode: 'gesture' }, activeUserId);
        } catch (error) {
          console.warn('Failed to persist user settings:', error);
        }
        setScreen(Screen.CONTROL_DASHBOARD);
      }
      return success;
    } finally {
      setIsLoading(false);
    }
  };

  const stopActiveControl = async () => {
    setIsLoading(true);
    try {
      await apiService.stopControl(activeUserId);
      setScreen(Screen.GESTURE_DASHBOARD);
    } finally {
      setIsLoading(false);
    }
  };

  const queueDeleteGesture = async (gestureId: string): Promise<string | null> => {
    setIsLoading(true);
    try {
      const response = await apiService.deleteGestureJob(gestureId, activeUserId);
      if (response.status === 'queued' && response.job_id) {
        setNeedsRetraining(false);
        return response.job_id;
      }
      return null;
    } catch (error) {
      console.error('Delete gesture job queue failed:', error);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const queueRetrainModel = async (): Promise<string | null> => {
    setIsLoading(true);
    try {
      const response = await apiService.retrainModel(activeUserId);
      if (response.status === 'queued' && response.job_id) {
        setNeedsRetraining(false);
        return response.job_id;
      }
      return null;
    } catch (error) {
      console.error('Retrain job queue failed:', error);
      return null;
    } finally {
      setIsLoading(false);
    }
  };

  const removeGestureLocally = (gestureId: string) => {
    setGestures((current) => current.filter((gesture) => gesture.id !== gestureId));
  };

  const upsertGestureLocally = (gestureName: string) => {
    const nextGesture = createGestureFromName(gestureName, { hasScript: true });
    setGestures((current) => {
      const existingIndex = current.findIndex((gesture) => gesture.id === gestureName);
      if (existingIndex === -1) {
        return [...current, nextGesture].sort((a, b) => a.name.localeCompare(b.name));
      }

      const updated = [...current];
      updated[existingIndex] = {
        ...updated[existingIndex],
        ...nextGesture,
      };
      return updated;
    });
  };

  return (
    <AppContext.Provider
      value={{
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
        queueDeleteGesture,
        queueRetrainModel,
        removeGestureLocally,
        upsertGestureLocally,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useApp = () => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useApp must be used within an AppProvider');
  }
  return context;
};
