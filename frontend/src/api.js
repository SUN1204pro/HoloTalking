// Backend base URL. When the page is opened from another device (e.g. an iPhone
// on the same Wi-Fi at http://<mac-ip>:5173), location.hostname is that IP, so the
// API calls follow to http://<mac-ip>:8000 automatically. Override with
// VITE_API_BASE if the backend runs elsewhere.
export const API_BASE =
  import.meta.env.VITE_API_BASE || `http://${window.location.hostname}:8000`;
