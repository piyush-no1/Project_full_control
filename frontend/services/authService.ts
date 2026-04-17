import { signInWithPopup, signOut, onAuthStateChanged } from "firebase/auth";
import { auth, googleProvider } from "./firebase";

export const loginWithGoogle = async () => {
  if (!auth || !googleProvider) {
    throw new Error("Google auth is not configured.");
  }
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
};

export const logoutUser = async () => {
  if (!auth) {
    return;
  }
  await signOut(auth);
};

export const listenToAuthChanges = (callback: any) => {
  if (!auth) {
    return () => undefined;
  }
  return onAuthStateChanged(auth, callback);
};
