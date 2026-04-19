import { io } from 'socket.io-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'http://localhost:8000';

// Singleton Socket.IO client with reconnection settings.
// auth.token is read lazily at connect-time so it always reflects
// the current localStorage value (e.g. after a token refresh).
const socket = io(WS_URL, {
  autoConnect: false,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 16000,
  reconnectionAttempts: 10,
  transports: ['websocket', 'polling'],
  auth: (cb) => {
    cb({ token: localStorage.getItem('pravaah_access_token') || '' });
  },
});

export default socket;
