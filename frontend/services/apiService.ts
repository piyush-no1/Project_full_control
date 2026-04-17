import { Gesture } from '../types';
import { auth } from './firebase';

const backendHost = typeof window !== 'undefined' ? window.location.hostname : '127.0.0.1';
const backendPort = import.meta.env.VITE_BACKEND_PORT || '8000';
const BASE_URL = `http://${backendHost}:${backendPort}`;

type GestureApiItem = {
  name: string;
  isPredefined: boolean;
  hasScript: boolean;
};

export type JobCreatedResponse = {
  status: 'queued' | 'rejected';
  job_id?: string;
  stage?: string;
  message: string;
  reason?: string;
  active_job_id?: string;
};

export type JobStatusResponse = {
  job_id: string;
  job_type: string;
  user_id: string;
  status: string;
  stage: string;
  message: string;
  error?: unknown;
  result?: unknown;
  created_at: string;
  updated_at: string;
  completed_at?: string | null;
};

export type UploadGestureSamplesResponse = {
  status: string;
  gesture_name: string;
  total_frames: number;
  added_samples: number;
  csv_path: string;
};

export const transformGesture = (apiGesture: GestureApiItem): Gesture => {
  const gestureMap: Record<string, { icon: string; description: string }> = {
    scroll_up: { icon: 'UP', description: 'Pan content upwards' },
    scroll_down: { icon: 'DN', description: 'Pan content downwards' },
    swipe_right: { icon: '>>', description: 'Next page or forward' },
    swipe_left: { icon: '<<', description: 'Previous page or back' },
    zoom_in: { icon: '+', description: 'Enlarge current view' },
    zoom_out: { icon: '-', description: 'Shrink current view' },
    volume_up: { icon: 'V+', description: 'Increase system audio' },
    volume_down: { icon: 'V-', description: 'Decrease system audio' },
    play_pause: { icon: 'PP', description: 'Toggle media playback' },
    'play/pause': { icon: 'PP', description: 'Toggle media playback' },
    ok: { icon: 'OK', description: 'OK gesture' },
  };

  const mapped = gestureMap[apiGesture.name.toLowerCase()] || {
    icon: '*',
    description: 'Custom gesture',
  };

  return {
    id: apiGesture.name,
    name: apiGesture.name.replace(/_/g, ' ').replace(/\//g, ' / '),
    description: mapped.description,
    icon: mapped.icon,
    isCustom: !apiGesture.isPredefined,
    category: apiGesture.isPredefined ? 'system' : 'user',
    hasScript: apiGesture.hasScript,
  };
};

export const createGestureFromName = (
  name: string,
  overrides?: Partial<GestureApiItem>
): Gesture =>
  transformGesture({
    name,
    isPredefined: overrides?.isPredefined ?? false,
    hasScript: overrides?.hasScript ?? true,
  });

const buildHeaders = async (userId?: string, includeJson = false): Promise<HeadersInit> => {
  const headers: Record<string, string> = {};

  if (includeJson) {
    headers['Content-Type'] = 'application/json';
  }

  if (userId) {
    headers['X-User-Id'] = userId;
  }

  if (auth && auth.currentUser) {
    try {
      const token = await auth.currentUser.getIdToken();
      if (token) {
        headers.Authorization = `Bearer ${token}`;
      }
    } catch (err) {
      console.warn('Failed to attach Firebase token to request:', err);
    }
  }

  return headers;
};

export const apiService = {
  getBaseUrl: () => BASE_URL,

  getVideoWebSocketUrl: () => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    return `${wsProtocol}://${backendHost}:${backendPort}/ws/video`;
  },

  getEventsWebSocketUrl: (userId: string) => {
    const wsProtocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const encodedUser = encodeURIComponent(userId || 'guest');
    return `${wsProtocol}://${backendHost}:${backendPort}/ws/events?user_id=${encodedUser}`;
  },

  fetchGestures: async (userId?: string): Promise<Gesture[]> => {
    try {
      const response = await fetch(`${BASE_URL}/api/gestures`, {
        headers: await buildHeaders(userId),
      });
      if (!response.ok) {
        console.error('Failed to fetch gestures:', response.status, response.statusText);
        return [];
      }
      const apiGestures: GestureApiItem[] = await response.json();
      return apiGestures.map(transformGesture);
    } catch (error) {
      console.error('Error fetching gestures:', error);
      return [];
    }
  },

  startAirStylus: async (userId?: string): Promise<boolean> => {
    try {
      const response = await fetch(`${BASE_URL}/air-stylus/start`, {
        method: 'POST',
        headers: await buildHeaders(userId),
      });
      return response.ok;
    } catch (error) {
      console.error('Error starting Air Stylus:', error);
      return false;
    }
  },

  startGestureControl: async (userId?: string): Promise<boolean> => {
    try {
      const response = await fetch(`${BASE_URL}/gesture/start`, {
        method: 'POST',
        headers: await buildHeaders(userId),
      });
      return response.ok;
    } catch (error) {
      console.error('Error starting Gesture Control:', error);
      return false;
    }
  },

  stopControl: async (userId?: string): Promise<boolean> => {
    try {
      const headers = await buildHeaders(userId);
      await fetch(`${BASE_URL}/gesture/stop`, { method: 'POST', headers });
      await fetch(`${BASE_URL}/air-stylus/stop`, { method: 'POST', headers });
      return true;
    } catch (error) {
      console.error('Error stopping controls:', error);
      return false;
    }
  },

  addGestureJob: async (
    payload: {
      name: string;
      description: string;
      cooldown?: number;
      collectionMode?: 'camera' | 'browser';
    },
    userId?: string
  ): Promise<JobCreatedResponse> => {
    const response = await fetch(`${BASE_URL}/api/gestures`, {
      method: 'POST',
      headers: await buildHeaders(userId, true),
      body: JSON.stringify({
        gesture_name: payload.name.trim().replace(/\s+/g, '_'),
        action_description: payload.description.trim(),
        cooldown: payload.cooldown ?? 2.0,
        collection_mode: payload.collectionMode || 'camera',
      }),
    });

    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to queue add-gesture job');
    }
    return body as JobCreatedResponse;
  },

  uploadGestureSamples: async (
    payload: { gestureName: string; frames: string[] },
    userId?: string
  ): Promise<UploadGestureSamplesResponse> => {
    const response = await fetch(`${BASE_URL}/api/gestures/upload-samples`, {
      method: 'POST',
      headers: await buildHeaders(userId, true),
      body: JSON.stringify({
        gesture_name: payload.gestureName.trim().replace(/\s+/g, '_'),
        frames: payload.frames,
      }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to upload gesture samples');
    }
    return body as UploadGestureSamplesResponse;
  },

  deleteGestureJob: async (gestureId: string, userId?: string): Promise<JobCreatedResponse> => {
    const response = await fetch(`${BASE_URL}/api/gestures/${encodeURIComponent(gestureId)}`, {
      method: 'DELETE',
      headers: await buildHeaders(userId),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to queue delete-gesture job');
    }
    return body as JobCreatedResponse;
  },

  retrainModel: async (userId?: string): Promise<JobCreatedResponse> => {
    const response = await fetch(`${BASE_URL}/api/gestures/retrain`, {
      method: 'POST',
      headers: await buildHeaders(userId),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to queue retrain job');
    }
    return body as JobCreatedResponse;
  },

  getJobStatus: async (jobId: string, userId?: string): Promise<JobStatusResponse> => {
    const response = await fetch(`${BASE_URL}/api/jobs/${encodeURIComponent(jobId)}`, {
      headers: await buildHeaders(userId),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to read job status');
    }
    return body as JobStatusResponse;
  },

  syncUserProfile: async (userId?: string): Promise<boolean> => {
    try {
      const response = await fetch(`${BASE_URL}/api/user/profile`, {
        method: 'PUT',
        headers: await buildHeaders(userId),
      });
      return response.ok;
    } catch (error) {
      console.error('Failed to sync user profile:', error);
      return false;
    }
  },

  getUserSettings: async (userId?: string): Promise<Record<string, unknown>> => {
    const response = await fetch(`${BASE_URL}/api/user/settings`, {
      headers: await buildHeaders(userId),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to load user settings');
    }
    return (body?.settings || {}) as Record<string, unknown>;
  },

  updateUserSettings: async (
    settings: Record<string, unknown>,
    userId?: string
  ): Promise<Record<string, unknown>> => {
    const response = await fetch(`${BASE_URL}/api/user/settings`, {
      method: 'PUT',
      headers: await buildHeaders(userId, true),
      body: JSON.stringify({ settings }),
    });
    const body = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(body?.detail || body?.message || 'Failed to update user settings');
    }
    return (body?.settings || {}) as Record<string, unknown>;
  },
};
