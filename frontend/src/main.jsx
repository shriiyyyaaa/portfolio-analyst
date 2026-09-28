import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import AdminApp from "./AdminApp.jsx";
import "./index.css";
import "./admin.css";

// Two screens, one small app: no router library needed for just this.
const isAdmin = window.location.pathname.startsWith("/admin");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>{isAdmin ? <AdminApp /> : <App />}</React.StrictMode>
);
