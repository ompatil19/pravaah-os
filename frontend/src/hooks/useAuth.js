import { useState, useEffect, useCallback } from 'react';
import api from '../api';

const STORAGE_KEYS = {
  accessToken: 'pravaah_access_token',
  refreshToken: 'pravaah_refresh_token',
  role: 'pravaah_role',
  username: 'pravaah_username',
};

// ─── Axios interceptors (module-level, set up once) ───
let _refreshingToken = false;
let _refreshSubscribers = [];

function onTokenRefreshed(newToken) {
  _refreshSubscribers.forEach((cb) => cb(newToken));
  _refreshSubscribers = [];
}

function addRefreshSubscriber(cb) {
  _refreshSubscribers.push(cb);
}

// Attach token to every request
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(STORAGE_KEYS.accessToken);
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Handle 401: try refresh once, else logout
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    if (
      error.response?.status === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/api/auth/login') &&
      !originalRequest.url?.includes('/api/auth/refresh')
    ) {
      if (_refreshingToken) {
        return new Promise((resolve, reject) => {
          addRefreshSubscriber((newToken) => {
            originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
            resolve(api(originalRequest));
          });
        });
      }

      originalRequest._retry = true;
      _refreshingToken = true;

      const refreshToken = localStorage.getItem(STORAGE_KEYS.refreshToken);
      if (!refreshToken) {
        _refreshingToken = false;
        _doLogout();
        return Promise.reject(error);
      }

      try {
        const { data } = await api.post('/api/auth/refresh', { refresh_token: refreshToken });
        const newAccessToken = data.access_token;
        localStorage.setItem(STORAGE_KEYS.accessToken, newAccessToken);
        onTokenRefreshed(newAccessToken);
        _refreshingToken = false;
        originalRequest.headers['Authorization'] = `Bearer ${newAccessToken}`;
        return api(originalRequest);
      } catch (refreshError) {
        _refreshingToken = false;
        _doLogout();
        return Promise.reject(refreshError);
      }
    }

    const message =
      error.response?.data?.message || error.message || 'An unexpected error occurred';
    return Promise.reject(new Error(message));
  }
);

function _doLogout() {
  localStorage.removeItem(STORAGE_KEYS.accessToken);
  localStorage.removeItem(STORAGE_KEYS.refreshToken);
  localStorage.removeItem(STORAGE_KEYS.role);
  localStorage.removeItem(STORAGE_KEYS.username);
  window.location.href = '/login';
}

export default function useAuth() {
  const [user, setUser] = useState(() => ({
    username: localStorage.getItem(STORAGE_KEYS.username),
    role: localStorage.getItem(STORAGE_KEYS.role),
  }));

  const [isAuthenticated, setIsAuthenticated] = useState(
    () => !!localStorage.getItem(STORAGE_KEYS.accessToken)
  );

  const login = useCallback(async (username, password) => {
    const { data } = await api.post('/api/auth/login', { username, password });
    localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
    localStorage.setItem(STORAGE_KEYS.refreshToken, data.refresh_token);
    localStorage.setItem(STORAGE_KEYS.role, data.role);
    localStorage.setItem(STORAGE_KEYS.username, username);
    setUser({ username, role: data.role });
    setIsAuthenticated(true);
    return data;
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.post('/api/auth/logout');
    } catch {
      // Ignore errors on logout
    }
    _doLogout();
  }, []);

  const refreshToken = useCallback(async () => {
    const token = localStorage.getItem(STORAGE_KEYS.refreshToken);
    if (!token) return null;
    const { data } = await api.post('/api/auth/refresh', { refresh_token: token });
    localStorage.setItem(STORAGE_KEYS.accessToken, data.access_token);
    return data.access_token;
  }, []);

  // Sync auth state with localStorage changes (e.g., other tabs)
  useEffect(() => {
    const handleStorage = () => {
      const token = localStorage.getItem(STORAGE_KEYS.accessToken);
      setIsAuthenticated(!!token);
      setUser({
        username: localStorage.getItem(STORAGE_KEYS.username),
        role: localStorage.getItem(STORAGE_KEYS.role),
      });
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  return {
    user,
    login,
    logout,
    isAuthenticated,
    role: user?.role,
  };
}
