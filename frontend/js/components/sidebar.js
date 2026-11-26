import { logout } from "../core/auth.js";
import { toggleTheme } from "../core/theme.js";

function render(admin) {
  const sidebar = document.getElementById("sidebar");
  if (!sidebar) return;

  // El marcado del sidebar es estático (partials/sidebar.html); aquí solo se
  // completa el usuario y se enlazan las acciones.
  const userName = sidebar.querySelector(".sidebar__user-name");
  if (userName) {
    userName.textContent = admin?.username || "Administrador";
  }

  const brandImg = sidebar.querySelector(".brand-logo__img");
  if (brandImg) {
    brandImg.addEventListener("error", () => {
      brandImg.classList.add("is-hidden");
      brandImg.parentElement?.classList.add("brand-logo--placeholder");
    });
  }

  sidebar.querySelector("#logoutButton")?.addEventListener("click", logout);
  sidebar
    .querySelector("#themeToggle")
    ?.addEventListener("click", () => toggleTheme(admin));

  setupMobileDrawer(sidebar);
}

const DRAWER_FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

/**
 * Menú lateral en móvil: anuncia el estado, atrapa el foco, bloquea el fondo
 * y devuelve el foco al botón al cerrar (FE-002).
 */
function setupMobileDrawer(sidebar) {
  if (document.getElementById("sidebarMobileToggle")) return;

  const toggle = document.createElement("button");
  toggle.id = "sidebarMobileToggle";
  toggle.className = "sidebar-mobile-toggle";
  toggle.type = "button";
  toggle.setAttribute("aria-label", "Abrir menú de navegación");
  toggle.setAttribute("aria-controls", "sidebar");
  toggle.setAttribute("aria-expanded", "false");
  toggle.innerHTML = '<i class="fa-solid fa-bars" aria-hidden="true"></i>';
  // Primer control tabulable después del skip link (si existe).
  const skipLink = document.querySelector(".skip-link");
  if (skipLink) skipLink.insertAdjacentElement("afterend", toggle);
  else document.body.prepend(toggle);

  const overlay = document.createElement("div");
  overlay.className = "sidebar-overlay";
  overlay.id = "sidebarOverlay";
  overlay.setAttribute("aria-hidden", "true");
  document.body.appendChild(overlay);

  const main = document.querySelector(".main");
  const desktop = window.matchMedia("(min-width: 901px)");
  let isOpen = false;

  // `inert` saca el menú cerrado del foco y del árbol accesible aunque la
  // animación de salida lo mantenga visible unos milisegundos.
  const syncSidebarInert = () => {
    sidebar.inert = !isOpen && !desktop.matches;
  };

  const setOpen = (open, { restoreFocus = true } = {}) => {
    if (isOpen === open) return;
    isOpen = open;

    document.body.classList.toggle("sidebar-open", open);
    toggle.setAttribute("aria-expanded", String(open));
    toggle.setAttribute(
      "aria-label",
      open ? "Cerrar menú de navegación" : "Abrir menú de navegación"
    );

    const icon = toggle.querySelector("i");
    if (icon) {
      icon.className = open ? "fa-solid fa-xmark" : "fa-solid fa-bars";
    }

    syncSidebarInert();

    if (main) {
      if (open) main.setAttribute("inert", "");
      else main.removeAttribute("inert");
    }

    if (open) {
      const target =
        sidebar.querySelector(".nav-link.is-active") ||
        sidebar.querySelector(".nav-link");
      window.setTimeout(() => target?.focus(), 30);
    } else if (restoreFocus) {
      toggle.focus();
    }
  };

  toggle.addEventListener("click", () => setOpen(!isOpen));
  overlay.addEventListener("click", () => setOpen(false));

  sidebar.querySelectorAll("a.nav-link").forEach((link) => {
    link.addEventListener("click", () => setOpen(false, { restoreFocus: false }));
  });

  document.addEventListener("keydown", (event) => {
    if (!isOpen) return;

    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      return;
    }

    if (event.key !== "Tab") return;

    const items = [toggle, ...sidebar.querySelectorAll(DRAWER_FOCUSABLE)];
    const first = items[0];
    const last = items[items.length - 1];

    if (!items.includes(document.activeElement)) {
      event.preventDefault();
      first.focus();
    } else if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  });

  // Si la ventana cambia de tamaño, se ajusta el estado sin dejar el fondo inerte.
  desktop.addEventListener("change", () => {
    if (isOpen && desktop.matches) setOpen(false, { restoreFocus: false });
    else syncSidebarInert();
  });

  syncSidebarInert();
}

export function renderSidebar(admin) {
  render(admin);
}
