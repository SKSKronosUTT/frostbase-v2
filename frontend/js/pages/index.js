import { getMe } from "../core/auth.js";

getMe()
  .then(() => window.location.replace("dashboard.html"))
  .catch(() => window.location.replace("login.html"));
