import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

export const TENNANT_LOGO_URL =
  "https://customer-assets.emergentagent.com/job_clean-logistics-dash/artifacts/0nr2wkta_Screenshot%202026-05-11%20021002.png";
