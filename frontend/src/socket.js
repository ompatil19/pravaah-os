import { io } from 'socket.io-client';

const WS_URL = import.meta.env.VITE_WS_URL || 'http://localhost:5000';

// Singleton Socket.IO client with reconnection settings
const socket = io(WS_URL, {
  autoConnect: false,
  reconnection: true,
  reconnectionDelay: 1000,
  reconnectionDelayMax: 16000,
  reconnectionAttempts: 10,
  transports: ['websocket', 'polling'],
});

export default socket;
