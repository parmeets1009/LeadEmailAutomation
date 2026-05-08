import axios from "axios";

const BASE = (import.meta.env.REACT_APP_BACKEND_URL || "").replace(/\/$/, "");
export const API_URL = `${BASE}/api`;

export const api = axios.create({
  baseURL: API_URL,
  headers: { "Content-Type": "application/json" },
});

export function extractError(err) {
  const detail = err?.response?.data?.detail;
  if (detail) return typeof detail === "string" ? detail : JSON.stringify(detail);
  return err?.message || "Unknown error";
}
