import { clearSession, getToken, getUser, requireSession } from "./api.js";
import { $, icon, initTheme, loadingState, toggleTheme } from "./ui.js";
import * as monitoring from "./views/monitoring.js";
import * as orders from "./views/orders.js";
import * as routesView from "./views/routes.js";
import * as stores from "./views/stores.js";
import * as trucks from "./views/trucks.js";
import * as drivers from "./views/drivers.js";
import * as mapView from "./views/map.js";
import * as settings from "./views/settings.js";

const routeTable = {
  monitoring: { title: "Monitoreo", eyebrow: "Operaciones", icon: "monitoring", view: monitoring },
  orders: { title: "Pedidos", eyebrow: "Operaciones", icon: "orders", view: orders },
  routes: { title: "Rutas", eyebrow: "Operaciones", icon: "routes", view: routesView },
  map: { title: "Mapa en vivo", eyebrow: "Operaciones", icon: "map", view: mapView },
  stores: { title: "Tiendas", eyebrow: "Red", icon: "stores", view: stores },
  trucks: { title: "Camiones", eyebrow: "Red", icon: "trucks", view: trucks },
  drivers: { title: "Conductores", eyebrow: "Equipo", icon: "drivers", view: drivers },
  settings: { title: "Configuración", eyebrow: "Sistema", icon: "settings", view: settings },
};

const groups = [
  ["Operaciones", ["monitoring", "orders", "routes", "map"]],
  ["Red", ["stores", "trucks"]],
  ["Equipo", ["drivers"]],
  ["Sistema", ["settings"]],
];

if (!requireSession()) throw new Error("Autenticación requerida");

initTheme();

let cleanup = null;
let currentRoute = "monitoring";

function renderNav() {
  const user = getUser();
  const nav = $("#main-nav");
  nav.innerHTML = groups
    .map(([label, keys]) => {
      const visible = keys.filter((key) => key !== "settings" || user?.isAdmin);
      if (!visible.length) return "";
      return (
        `<span class="nav-label">${label}</span>` +
        visible
          .map(
            (key) =>
              `<a class="nav-item" href="#/${key}" data-route="${key}"><span class="nav-icon">${icon(routeTable[key].icon)}</span><span>${routeTable[key].title}</span></a>`,
          )
          .join("")
      );
    })
    .join("");
}

function renderUser() {
  const user = getUser();
  if (!user) return;
  const firstName = user.name?.firstName || user.name?.fullName || "Frostbase";
  const lastName = user.name?.lastName || "";
  const initials = `${firstName[0] || ""}${lastName[0] || ""}`.toUpperCase() || "FB";
  $("#user-avatar").textContent = initials;
  $("#user-name").textContent = user.name?.fullName || `${firstName} ${lastName}`.trim();
  $("#user-role").textContent = user.isAdmin ? "Administrador" : "Conductor";
}

function setActiveNav(key) {
  document.querySelectorAll(".nav-item").forEach((item) => {
    item.classList.toggle("active", item.dataset.route === key);
  });
  $("#sidebar").classList.remove("open");
}

async function loadRoute() {
  if (!getToken()) {
    window.location.replace("index.html");
    return;
  }
  const key = (window.location.hash.replace(/^#\/?/, "") || "monitoring").split("?")[0];
  if (key === "settings" && !getUser()?.isAdmin) {
    window.location.hash = "#/monitoring";
    return;
  }
  const route = routeTable[key] || routeTable.monitoring;
  currentRoute = key in routeTable ? key : "monitoring";
  if (cleanup) {
    try {
      cleanup();
    } catch {
      /* no-op */
    }
    cleanup = null;
  }
  $("#page-title").textContent = route.title;
  $("#page-eyebrow").textContent = route.eyebrow;
  document.title = `${route.title} | Frostbase`;
  setActiveNav(currentRoute);
  const view = $("#view");
  view.innerHTML = loadingState();
  try {
    const result = await route.view.render(view, { navigate: (target) => (window.location.hash = `#/${target}`) });
    if (typeof result === "function") cleanup = result;
    view.focus({ preventScroll: true });
  } catch (error) {
    view.innerHTML = `<div class="card"><div class="empty"><strong>No se pudo cargar esta vista</strong><span>${error.message || "Error inesperado"}</span><button class="btn" onclick="location.reload()">Recargar</button></div></div>`;
  }
}

$("#theme-toggle").innerHTML = icon(document.documentElement.dataset.theme === "dark" ? "sun" : "moon");
$("#theme-toggle").addEventListener("click", toggleTheme);
$("#menu-toggle").innerHTML = icon("menu");
$("#menu-toggle").addEventListener("click", () => $("#sidebar").classList.toggle("open"));
$("#logout-btn").innerHTML = icon("logout");
$("#logout-btn").addEventListener("click", () => {
  clearSession();
  window.location.replace("index.html");
});

document.addEventListener("click", (event) => {
  const sidebar = $("#sidebar");
  if (
    window.innerWidth <= 960 &&
    sidebar.classList.contains("open") &&
    !sidebar.contains(event.target) &&
    !$("#menu-toggle").contains(event.target)
  ) {
    sidebar.classList.remove("open");
  }
});

window.addEventListener("hashchange", loadRoute);
window.addEventListener("storage", (event) => {
  if (event.key === "frostbase.token" && !event.newValue) window.location.replace("index.html");
});

renderNav();
renderUser();
loadRoute();

window.addEventListener("resize", () => {
  if (window.innerWidth > 960) $("#sidebar").classList.remove("open");
});

void currentRoute;
