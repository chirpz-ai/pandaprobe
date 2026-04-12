"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import type { User } from "firebase/auth";
import { AUTH_ENABLED } from "@/lib/auth/firebase";
import {
  signInWithGoogle as _signInWithGoogle,
  signInWithEmail as _signInWithEmail,
  signUpWithEmail as _signUpWithEmail,
  signOut as _signOut,
  getCurrentToken,
  onIdTokenChanged,
  setSessionCookie,
  clearSessionCookie,
} from "@/lib/auth/auth-service";
import { clearUserStorage } from "@/lib/utils/constants";

interface AuthContextValue {
  user: User | null;
  loading: boolean;
  authEnabled: boolean;
  signInWithGoogle: () => Promise<void>;
  signInWithEmail: (email: string, password: string) => Promise<void>;
  signUpWithEmail: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(AUTH_ENABLED);

  useEffect(() => {
    if (!AUTH_ENABLED) {
      return;
    }

    const unsubscribe = onIdTokenChanged((firebaseUser) => {
      setUser(firebaseUser);
      setLoading(false);
      if (firebaseUser) {
        setSessionCookie();
      } else {
        clearSessionCookie();
      }
    });

    return unsubscribe;
  }, []);

  const signInWithGoogle = useCallback(async () => {
    await _signInWithGoogle();
  }, []);

  const signInWithEmail = useCallback(
    async (email: string, password: string) => {
      await _signInWithEmail(email, password);
    },
    [],
  );

  const signUpWithEmail = useCallback(
    async (email: string, password: string) => {
      await _signUpWithEmail(email, password);
    },
    [],
  );

  const signOut = useCallback(async () => {
    clearUserStorage();
    await _signOut();
  }, []);

  const getToken = useCallback(async () => {
    return getCurrentToken();
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        loading,
        authEnabled: AUTH_ENABLED,
        signInWithGoogle,
        signInWithEmail,
        signUpWithEmail,
        signOut,
        getToken,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
