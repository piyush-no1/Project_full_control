import { signInWithPopup, signOut, onAuthStateChanged } from "firebase/auth";
import { auth, googleProvider } from "./firebase";

export const loginWithGoogle = async () => {
  const result = await signInWithPopup(auth, googleProvider);
  return result.user;
};

export const logoutUser = async () => {
  await signOut(auth);
};

export const listenToAuthChanges = (callback: any) => {
  return onAuthStateChanged(auth, callback);
};
