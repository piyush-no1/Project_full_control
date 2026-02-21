
import { User, Gesture } from '../types';

/**
 * API Service connected to Python Flask Backend
 */

const backendHost = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const BASE_URL = `http://${backendHost}:8000`; // FastAPI backend URL
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

export const apiService = {
  login: async (method: 'google' | 'guest'): Promise<User> => {
    // In a real app: fetch(`${BASE_URL}/api/auth/${method}`)
    await delay(1200);
    if (method === 'google') {
      return {
        id: 'user_google_123',
        name: 'Alex Sterling',
        isGuest: false,
        avatar: 'https://picsum.photos/seed/alex/200'
      };
    }
    return {
      id: 'guest_' + Math.random().toString(36).substr(2, 5).toUpperCase(),
      name: 'Guest User',
      isGuest: true
    };
  },

  fetchGestures: async (): Promise<Gesture[]> => {
    // fetch(`${BASE_URL}/api/gestures`)
    await delay(800);
    return [
      { id: '1', name: 'Scroll Up', description: 'Pan content upwards', icon: '👆', category: 'system' },
      { id: '2', name: 'Scroll Down', description: 'Pan content downwards', icon: '👇', category: 'system' },
      { id: '3', name: 'Right Swipe', description: 'Next page or forward', icon: '👉', category: 'system' },
      { id: '4', name: 'Left Swipe', description: 'Previous page or back', icon: '👈', category: 'system' },
      { id: '5', name: 'Zoom In', description: 'Enlarge current view', icon: '🖐️', category: 'system' },
      { id: '6', name: 'Zoom Out', description: 'Shrink current view', icon: '✊', category: 'system' },
      { id: '7', name: 'Volume Up', description: 'Increase system audio', icon: '👍', category: 'system' },
      { id: '8', name: 'Volume Down', description: 'Decrease system audio', icon: '👎', category: 'system' },
      { id: '9', name: 'Play/Pause', description: 'Toggle media playback', icon: '✌️', category: 'system' },
    ];
  },

  startAirStylus: async (): Promise<boolean> => {
    console.log('API: Starting Air Stylus via /air-stylus/start');
    try {
      const response = await fetch(`${BASE_URL}/air-stylus/start`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to start Air Stylus');
      const data = await response.json();
      console.log('Air Stylus response:', data);
      return true;
    } catch (error) {
      console.error('Error starting Air Stylus:', error);
      return false;
    }
  },

  startGestureControl: async (): Promise<boolean> => {
    console.log('API: Starting Gesture Control via /gesture/start');
    try {
      const response = await fetch(`${BASE_URL}/gesture/start`, { method: 'POST' });
      if (!response.ok) throw new Error('Failed to start Gesture Control');
      const data = await response.json();
      console.log('Gesture Control response:', data);
      return true;
    } catch (error) {
      console.error('Error starting Gesture Control:', error);
      return false;
    }
  },

  stopControl: async (): Promise<boolean> => {
    console.log('API: Stopping all controls');
    try {
      // Stop both gesture and air stylus
      await fetch(`${BASE_URL}/gesture/stop`, { method: 'POST' });
      await fetch(`${BASE_URL}/air-stylus/stop`, { method: 'POST' });
      return true;
    } catch (error) {
      console.error('Error stopping controls:', error);
      return false;
    }
  },

  addGesture: async (gesture: Partial<Gesture>): Promise<boolean> => {
    // await fetch(`${BASE_URL}/api/gestures`, { method: 'POST', body: JSON.stringify(gesture) });
    await delay(1000);
    return true;
  },

  deleteGesture: async (id: string): Promise<boolean> => {
    console.log(`API: Deleting gesture ${id} via Flask/Firebase`);
    // await fetch(`${BASE_URL}/api/gestures/${id}`, { method: 'DELETE' });
    await delay(1000);
    return true;
  },

  retrainModel: async (): Promise<boolean> => {
    console.log('API: Retraining model via /retrain-model');
    // await fetch(`${BASE_URL}/retrain-model`, { method: 'POST' });
    await delay(2500);
    return true;
  },

  logout: async (): Promise<void> => {
    await delay(500);
  }
};
