import { initializeApp } from 'firebase/app';
import { getAuth, RecaptchaVerifier, signInWithPhoneNumber } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "AIzaSyAF4icr8tWg9QYIBqncegivtcohX1y2XAc",
  authDomain: "vrittant-f5ef2.firebaseapp.com",
  projectId: "vrittant-f5ef2",
  storageBucket: "vrittant-f5ef2.firebasestorage.app",
  messagingSenderId: "829303072442",
  appId: "1:829303072442:web:47650a98e93a9fbfc04483",
  measurementId: "G-JZHPF2D9T1",
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

export { auth, RecaptchaVerifier, signInWithPhoneNumber };
