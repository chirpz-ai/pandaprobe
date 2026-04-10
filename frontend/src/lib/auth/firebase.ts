import { initializeApp, type FirebaseApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

const envFlag = process.env.NEXT_PUBLIC_AUTH_ENABLED !== "false";

export const AUTH_ENABLED =
  process.env.NODE_ENV !== "development" ? true : envFlag;

if (!envFlag && AUTH_ENABLED) {
  console.warn(
    "[auth] NEXT_PUBLIC_AUTH_ENABLED=false is ignored outside development. Forcing auth ON."
  );
}

let app: FirebaseApp | null = null;
let auth: Auth | null = null;

if (AUTH_ENABLED && typeof window !== "undefined") {
  const apiKey = process.env.NEXT_PUBLIC_FIREBASE_API_KEY;
  if (apiKey) {
    try {
      app = initializeApp({
        apiKey,
        authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
        projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
        storageBucket: process.env.NEXT_PUBLIC_FIREBASE_STORAGE_BUCKET,
        messagingSenderId:
          process.env.NEXT_PUBLIC_FIREBASE_MESSAGING_SENDER_ID,
        appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
        measurementId: process.env.NEXT_PUBLIC_FIREBASE_MEASUREMENT_ID,
      });
      auth = getAuth(app);
    } catch (err) {
      console.error("[auth] Firebase initialization failed:", err);
    }
  } else {
    console.warn(
      "[auth] AUTH_ENABLED=true but NEXT_PUBLIC_FIREBASE_API_KEY is not set. Auth will not work."
    );
  }
}

export { app, auth };
