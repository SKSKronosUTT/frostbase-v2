import { api, isCancelledError } from "../core/api.js";
import { logout } from "../core/auth.js";
import { openPasswordChangeModal } from "../core/app.js";
import { setupPolling } from "../core/app.js";
import { notify } from "../core/notifications.js";
import { initTheme, toggleTheme } from "../core/theme.js";
import {
  escapeHtml,
  formatRange,
  formatTemp,
  formatHum,
  qs,
  timeAgo,
} from "../core/helpers.js";

initTheme();

qs("#themeToggle").addEventListener("click", () => toggleTheme(null));
qs("#logoutButton").addEventListener("click", logout);
qs("#changePasswordButton").addEventListener("click", () =>
  openPasswordChangeModal({ mandatory: false })
);

const WEEKDAY_NAMES = ["Dom", "Lun", "Mar", "Mié", "Jue", "Vie", "Sáb"];
const ALERT_LABELS = {
  temperatura: { label: "Temperatura", icon: "fa-temperature-half" },
  humedad: { label: "Humedad", icon: "fa-droplet" },
  desconexion: { label: "Desconexión", icon: "fa-plug-circle-xmark" },
  puerta: { label: "Puerta", icon: "fa-triangle-exclamation" },
};

function renderDashboard(data) {
  // Cabecera
  qs("#driverName").textContent = data.driver.full_name;
  qs("#driverEmail").textContent = data.driver.email;
  qs("#truckPlate").textContent = data.truck?.plate || "Sin camión";

  // Contenedor
  const c = data.container;
  if (c && c.temperature !== null && c.temperature !== undefined) {
    qs("#containerTemp").textContent = formatTemp(c.temperature);
    qs("#containerHum").textContent = formatHum(c.humidity);
    qs("#containerTempRange").textContent = formatRange(
      c.temperature_min,
      c.temperature_max,
      " °C"
    );
    qs("#containerHumRange").textContent = formatRange(
      c.humidity_min,
      c.humidity_max,
      " %"
    );
    qs("#containerLastSeen").textContent = c.received_at ? timeAgo(c.received_at) : "—";

    const badge = qs("#containerStatus");
    if (c.status === "ok") {
      badge.textContent = "Normal";
      badge.className = "badge badge--success";
    } else if (c.status === "out_of_range") {
      badge.textContent = "Fuera de rango";
      badge.className = "badge badge--danger";
    } else {
      badge.textContent = "Sin datos";
      badge.className = "badge badge--muted";
    }
  } else {
    qs("#containerTemp").textContent = "—";
    qs("#containerHum").textContent = "—";
    qs("#containerTempRange").textContent = "Sin lecturas";
    qs("#containerHumRange").textContent = "Sin lecturas";
    qs("#containerStatus").textContent = "Sin datos";
    qs("#containerStatus").className = "badge badge--muted";
    qs("#containerLastSeen").textContent = "—";
  }

  // Ruta de hoy
  const routeBadge = qs("#routeBadge");
  const routeBody = qs("#routeBody");
  if (data.today_route) {
    routeBadge.textContent = data.today_route.name;
    routeBadge.className = "badge badge--success";
    const days = data.today_route.delivery_days
      .map((day) => WEEKDAY_NAMES[day])
      .join(", ");
    routeBody.innerHTML = `
      <div class="driver-route-detail">
        <div class="detail-row">
          <dt>Puntos de entrega</dt>
          <dd>${data.today_route.points_count}</dd>
        </div>
        <div class="detail-row">
          <dt>Días</dt>
          <dd>${escapeHtml(days)}</dd>
        </div>
      </div>
    `;
  } else {
    routeBadge.textContent = "Sin ruta";
    routeBadge.className = "badge badge--muted";
    routeBody.innerHTML = '<p class="muted">No tienes ruta programada para hoy.</p>';
  }

  // Contador de alertas activas
  const countBadge = qs("#activeAlertCount");
  if (data.active_alerts > 0) {
    countBadge.hidden = false;
    countBadge.textContent = data.active_alerts;
  } else {
    countBadge.hidden = true;
  }
}

function renderAlerts(alerts) {
  const list = qs("#alertsList");
  if (!alerts.length) {
    list.innerHTML = '<p class="muted">Sin alertas para mostrar.</p>';
    return;
  }
  list.innerHTML = alerts
    .map((alert) => {
      const meta = ALERT_LABELS[alert.alert_type] || {
        label: alert.alert_type,
        icon: "fa-triangle-exclamation",
      };
      const is_active = alert.status === "activa";
      return `
        <div class="driver-alert-item ${is_active ? "driver-alert-item--active" : ""}">
          <div class="driver-alert-item__icon">
            <i class="fa-solid ${meta.icon}"></i>
          </div>
          <div class="driver-alert-item__body">
            <div class="driver-alert-item__title">
              <strong>${escapeHtml(meta.label)}</strong>
              <span class="badge ${
                is_active ? "badge--danger" : "badge--success"
              }">${is_active ? "Activa" : "Resuelta"}</span>
            </div>
            <span class="muted text-xs">${timeAgo(alert.started_at)}${
              alert.value !== null && alert.value !== undefined
                ? ` · Valor: ${Number(alert.value).toFixed(1)}`
                : ""
            }</span>
            ${alert.message ? `<p class="driver-alert-item__msg">${escapeHtml(alert.message)}</p>` : ""}
          </div>
        </div>
      `;
    })
    .join("");
}

async function loadDashboard() {
  try {
    const data = await api.get("/driver/dashboard");
    renderDashboard(data);
  } catch (error) {
    if (isCancelledError(error)) return;
    console.warn("No se pudo actualizar el dashboard", error);
  }
}

async function loadAlerts() {
  try {
    const data = await api.get("/driver/alerts?page_size=10");
    renderAlerts(data.items);
  } catch (error) {
    if (isCancelledError(error)) return;
  }
}

async function init() {
  // Verificar sesión; si es 401, api.js ya redirige al login.
  const me = await api.get("/driver/me").catch(() => null);
  if (!me) return;

  await loadDashboard();
  await loadAlerts();
  setupPolling(async () => {
    await Promise.allSettled([loadDashboard(), loadAlerts()]);
  }, 5000);
}

init().catch((error) => {
  if (error?.status === 401) return; // api.js ya redirigió
  console.error(error);
  notify.error("No se pudo inicializar el portal del conductor.");
});
