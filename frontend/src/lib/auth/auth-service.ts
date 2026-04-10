import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  signOut as firebaseSignOut,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  onIdTokenChanged as firebaseOnIdTokenChanged,
  type User,
  type Unsubscribe,
} from "firebase/auth";
import { auth, AUTH_ENABLED } from "./firebase";

export async function signInWithGoogle(): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const provider = new GoogleAuthProvider();
  const result = await signInWithPopup(auth, provider);
  return result.user;
}

export async function signInWithEmail(
  email: string,
  password: string
): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function signUpWithEmail(
  email: string,
  password: string
): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const result = await createUserWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function signOut(): Promise<void> {
  if (!auth) return;
  await firebaseSignOut(auth);
}

export async function getCurrentToken(
  forceRefresh = false
): Promise<string | null> {
  if (!AUTH_ENABLED) return null;
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken(forceRefresh);
}

export function onAuthStateChanged(
  callback: (user: User | null) => void
): Unsubscribe {
  if (!auth) {
    callback(null);
    return () => {};
  }
  return firebaseOnAuthStateChanged(auth, callback);
}

export function onIdTokenChanged(
  callback: (user: User | null) => void
): Unsubscribe {
  if (!auth) {
    callback(null);
    return () => {};
  }
  return firebaseOnIdTokenChanged(auth, callback);
}
