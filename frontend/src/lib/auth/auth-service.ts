import {
  GoogleAuthProvider,
  signInWithPopup,
  signInWithEmailAndPassword,
  createUserWithEmailAndPassword,
  sendPasswordResetEmail,
  signOut as firebaseSignOut,
  onAuthStateChanged as firebaseOnAuthStateChanged,
  onIdTokenChanged as firebaseOnIdTokenChanged,
  type User,
  type Unsubscribe,
} from "firebase/auth";
import { auth, AUTH_ENABLED } from "./firebase";
import { SESSION_COOKIE_NAME } from "./config";

export async function signInWithGoogle(): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const provider = new GoogleAuthProvider();
  const result = await signInWithPopup(auth, provider);
  return result.user;
}

export async function signInWithEmail(
  email: string,
  password: string,
): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const result = await signInWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function signUpWithEmail(
  email: string,
  password: string,
): Promise<User> {
  if (!auth) throw new Error("Auth is not enabled");
  const result = await createUserWithEmailAndPassword(auth, email, password);
  return result.user;
}

export async function resetPassword(email: string): Promise<void> {
  if (!auth) throw new Error("Auth is not enabled");
  await sendPasswordResetEmail(auth, email);
}

export async function signOut(): Promise<void> {
  if (!auth) return;
  await firebaseSignOut(auth);
  clearSessionCookie();
}

export function setSessionCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_COOKIE_NAME}=1; path=/; max-age=86400; SameSite=Lax`;
}

export function clearSessionCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${SESSION_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}

export async function getCurrentToken(
  forceRefresh = false,
): Promise<string | null> {
  if (!AUTH_ENABLED) return null;
  if (!auth?.currentUser) return null;
  return auth.currentUser.getIdToken(forceRefresh);
}

export function onAuthStateChanged(
  callback: (user: User | null) => void,
): Unsubscribe {
  if (!auth) {
    callback(null);
    return () => {};
  }
  return firebaseOnAuthStateChanged(auth, callback);
}

export function onIdTokenChanged(
  callback: (user: User | null) => void,
): Unsubscribe {
  if (!auth) {
    callback(null);
    return () => {};
  }
  return firebaseOnIdTokenChanged(auth, callback);
}
