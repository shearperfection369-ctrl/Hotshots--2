import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// Cross-origin Bearer fallback: when the frontend is served from a different
// parent domain than the backend (e.g. *.preview.static.* vs *.preview.*),
// browsers refuse to send third-party cookies. We persist the session_token
// in localStorage after sign-in and inject it as Authorization: Bearer here
// so the same session works regardless of origin.
const TOKEN_KEY = "tms_session_token";

export function setStoredToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getStoredToken() {
  try { return localStorage.getItem(TOKEN_KEY) || ""; } catch (_) { return ""; }
}

api.interceptors.request.use((config) => {
  const t = getStoredToken();
  if (t && !config.headers?.Authorization) {
    config.headers = config.headers || {};
    config.headers.Authorization = `Bearer ${t}`;
  }
  return config;
});

export const TENNANT_LOGO_URL =
  "https://customer-assets.emergentagent.com/job_clean-logistics-dash/artifacts/0nr2wkta_Screenshot%202026-05-11%20021002.png";
