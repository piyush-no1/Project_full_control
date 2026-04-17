import { User, Gesture } from '../types';

/**
 * API Service connected to Python Flask Backend
 */

const backendHost = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const BASE_URL = `http://${backendHost}:8000`; // FastAPI backend URL
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// Helper function to get icon for gesture name
function getGestureIcon(gestureName: string): string {
  const iconMap: Record<string, string> = {
    'scroll_up': '👆',
    'scroll_down': '👇',
    'swipe_right': '👉',
    'swipe_left': '👈',
    'zoom_in': '🖐️',
    'zoom_out': '✊',
    'volume_up': '👍',
    'volume_down': '👎',
    'play_pause': '✌️',
    'play/pause': '✌️',
    'play-pause': '✌️',
    'ok': '👌',
    'stop': '✋',
  };
  return iconMap[gestureName.toLowerCase()] || '👋';
}

export const apiService = {
  login: async (method: 'google' | 'guest'): Promise<User> => {
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
    try {
      const response = await fetch(`${BASE_URL}/api/gestures`);
      if (!response.ok) throw new Error('Failed to fetch gestures');
      const data = await response.json();
      return data.map((g: any) => ({
        id: g.name,
        name: g.name,
        description: g.isPredefined ? 'System gesture' : 'Custom gesture',
        icon: getGestureIcon(g.name),
        category: g.isPredefined ? 'system' : 'custom'
      }));
    } catch (error) {
      console.error('Error fetching gestures:', error);
      return [];
    }
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
      await fetch(`${BASE_URL}/gesture/stop`, { method: 'POST' });
      await fetch(`${BASE_URL}/air-stylus/stop`, { method: 'POST' });
      return true;
    } catch (error) {
      console.error('Error stopping controls:', error);
      return false;
    }
  },

  addGesture: async (gesture: Partial<Gesture>): Promise<boolean> => {
    try {
      const response = await fetch(`${BASE_URL}/api/gestures`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          gesture_name: gesture.name,
          action_description: gesture.description || 'Custom gesture',
          cooldown: 2.0
        })
      });
      if (!response.ok) throw new Error('Failed to add gesture');
      return true;
    } catch (error) {
      console.error('Error adding gesture:', error);
      return false;
    }
  },

  deleteGesture: async (id: string): Promise<boolean> => {
    console.log(`API: Deleting gesture ${id} via /api/gestures/${id}`);
    try {
      const response = await fetch(`${BASE_URL}/api/gestures/${id}`, { method: 'DELETE' });
      if (!response.ok) throw new Error('Failed to delete gesture');
      return true;
    } catch (error) {
      console.error('Error deleting gesture:', error);
      return false;
    }
  },

  retrainModel: async (): Promise<boolean> => {
    console.log('API: Retraining model via /retrain-model');
    await delay(2500);
    return true;
  },

  logout: async (): Promise<void> => {
    await delay(500);
  }
};
