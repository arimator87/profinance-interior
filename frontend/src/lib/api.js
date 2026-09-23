import axios from "axios";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("pf_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error) => {
    const detail = error?.response?.data?.detail;
    if (error?.response?.status === 403 && typeof detail === "string" && detail.startsWith("Mode Demo")) {
      toast.info(detail);
    }
    return Promise.reject(error);
  }
);

export function fileUrl(path) {
  if (!path) return null;
  if (/^(https?:|data:)/i.test(path)) return path;
  const token = localStorage.getItem("pf_token");
  return `${API}/files/${path}?auth=${encodeURIComponent(token || "")}`;
}

export function pdfUrl(projectId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/projects/${projectId}/report/pdf?auth=${encodeURIComponent(token || "")}`;
}

export function rabPdfUrl(projectId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/projects/${projectId}/rab/pdf?auth=${encodeURIComponent(token || "")}`;
}

export function invoicePdfUrl(invoiceId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/invoices/${invoiceId}/pdf?auth=${encodeURIComponent(token || "")}`;
}

export function recapXlsxUrl(projectId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/projects/${projectId}/recap/xlsx?auth=${encodeURIComponent(token || "")}`;
}

export function workersPdfUrl(projectId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/projects/${projectId}/workers/report/pdf?auth=${encodeURIComponent(token || "")}`;
}

export function workerPdfUrl(workerId) {
  const token = localStorage.getItem("pf_token");
  return `${API}/workers/${workerId}/report/pdf?auth=${encodeURIComponent(token || "")}`;
}
