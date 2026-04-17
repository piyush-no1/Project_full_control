import { initializeApp } from 'firebase/app';
import { getAnalytics, isSupported } from 'firebase/analytics';
import { getAuth, GoogleAuthProvider, type Auth } from 'firebase/auth';

const firebaseConfig = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY || '',
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN || '',
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID || '',
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET || '',
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || '',
  appId: import.meta.env.VITE_FIREBASE_APP_ID || '',
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || '',
};

const requiredConfigKeys: Array<keyof typeof firebaseConfig> = [
  'apiKey',
  'authDomain',
  'projectId',
  'appId',
];
const hasRequiredFirebaseConfig = requiredConfigKeys.every((key) => Boolean(firebaseConfig[key]));
const app = hasRequiredFirebaseConfig ? initializeApp(firebaseConfig) : null;

export const firebaseAuthEnabled = hasRequiredFirebaseConfig;
export const auth: Auth | null = app ? getAuth(app) : null;
export const googleProvider = auth ? new GoogleAuthProvider() : null;
export const firebaseMissingConfigReason = hasRequiredFirebaseConfig
  ? null
  : `Missing Firebase config values: ${requiredConfigKeys.join(', ')}`;

if (app && typeof window !== 'undefined') {
  isSupported()
    .then((supported) => {
      if (supported && firebaseConfig.measurementId) {
        getAnalytics(app);
      }
    })
    .catch(() => {
      // Ignore analytics initialization failure in local/dev environments.
    });
}
