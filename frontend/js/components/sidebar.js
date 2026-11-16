import { logout } from "../core/auth.js";
import { toggleTheme } from "../core/theme.js";

const NAV_ITEMS = [
  { page: "dashboard", label: "Inicio", href: "dashboard.html", icon: "fa-house" },
  { page: "trucks", label: "Flota", href: "trucks.html", icon: "fa-truck" },
  { page: "routes", label: "Rutas", href: "routes.html", icon: "fa-route" },
  { page: "alerts", label: "Historial de alertas", href: "alerts.html", icon: "fa-bell" },
  { page: "settings", label: "Configuración", href: "settings.html", icon: "fa-gear" },
];

const PAGE_ALIASES = {
  "truck-detail": "trucks",
  "route-detail": "routes",
};

function activePage() {
  const current = document.body.dataset.page || "dashboard";
  return PAGE_ALIASES[current] || current;
}

function render(admin) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;
  const active = activePage();

  sidebar.innerHTML = `
    <a class="sidebar__brand" href="dashboard.html" aria-label="FrostBase, ir al panel de control">
      <span class="brand-logo">
        <img src="assets/logo.png" alt="Logotipo FrostBase" class="brand-logo__img"
             onerror="this.classList.add('is-hidden'); this.parentElement.classList.add('brand-logo--placeholder');">
      </span>
      <span class="brand-name">FrostBase</span>
    </a>
    <nav class="sidebar__nav" aria-label="Navegación principal">
      ${NAV_ITEMS.map(
        (item) => `
        <a class="nav-link ${active === item.page ? "is-active" : ""}" href="${item.href}"
           ${active === item.page ? 'aria-current="page"' : ""}>
          <i class="fa-solid ${item.icon}"></i>
          <span>${item.label}</span>
        </a>`
      ).join("")}
    </nav>
    <div class="sidebar__footer">
      <div class="sidebar__user">
        <span class="sidebar__user-avatar"><i class="fa-solid fa-user-shield"></i></span>
        <span class="sidebar__user-name">${escapeText(admin?.username || "Administrador")}</span>
      </div>
      <button class="nav-link nav-link--button" id="themeToggle" type="button">
        <i class="fa-solid fa-moon"></i>
        <span>Tema oscuro</span>
      </button>
      <button class="nav-link nav-link--button nav-link--danger" id="logoutButton" type="button">
        <i class="fa-solid fa-right-from-bracket"></i>
        <span>Cerrar sesión</span>
      </button>
    </div>
  `;

  sidebar.querySelector("#logoutButton").addEventListener("click", logout);
  sidebar.querySelector("#themeToggle").addEventListener("click", () => toggleTheme(admin));

  if (!document.getElementById("sidebarMobileToggle")) {
    const toggle = document.createElement("button");
    toggle.id = "sidebarMobileToggle";
    toggle.className = "sidebar-mobile-toggle";
    toggle.type = "button";
    toggle.setAttribute("aria-label", "Abrir menú de navegación");
    toggle.innerHTML = '<i class="fa-solid fa-bars"></i>';
    document.body.appendChild(toggle);

    const overlay = document.createElement("div");
    overlay.className = "sidebar-overlay";
    overlay.id = "sidebarOverlay";
    document.body.appendChild(overlay);

    const close = () => document.body.classList.remove("sidebar-open");
    toggle.addEventListener("click", () => document.body.classList.toggle("sidebar-open"));
    overlay.addEventListener("click", close);
    sidebar.querySelectorAll(".nav-link").forEach((link) => {
      link.addEventListener("click", close);
    });
  }
}

function escapeText(value) {
  const div = document.createElement("div");
  div.textContent = value;
  return div.innerHTML;
}

export function renderSidebar(admin) {
  render(admin);
}
