import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";
import { getAnalytics } from "firebase/analytics";

const firebaseConfig = {
  apiKey: "AIzaSyCU-GYDs55QSsH-uTESy6-ZrFMCDgcaOU8",
  authDomain: "final-project-4b8a1.firebaseapp.com",
  projectId: "final-project-4b8a1",
  storageBucket: "final-project-4b8a1.firebasestorage.app",
  messagingSenderId: "709612530443",
  appId: "1:709612530443:web:9f235fd03f300dfa65500e",
  measurementId: "G-SEB8VF8C6S"
};

const app = initializeApp(firebaseConfig);

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
const analytics = getAnalytics(app);