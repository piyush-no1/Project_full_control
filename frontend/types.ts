
export enum Screen {
  INTRO = 'INTRO',
  GESTURE_DASHBOARD = 'GESTURE_DASHBOARD',
  LOGIN = 'LOGIN',
  CONTROL_DASHBOARD = 'CONTROL_DASHBOARD'
}

export interface User {
  id: string;
  name: string;
  isGuest: boolean;
  avatar?: string;
}

export interface Gesture {
  id: string;
  name: string;
  description: string;
  icon: string;
  isCustom?: boolean;
  category?: 'system' | 'user';
}

export interface AppState {
  currentScreen: Screen;
  user: User | null;
  isLoading: boolean;
  gestures: Gesture[];
  needsRetraining: boolean;
}
