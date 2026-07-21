const DEFAULT_BACKEND_URL = "http://localhost:8000";

export const env = {
  backendUrl:
    import.meta.env.VITE_BACKEND_URL?.replace(/\/$/, "") ?? DEFAULT_BACKEND_URL,
};
