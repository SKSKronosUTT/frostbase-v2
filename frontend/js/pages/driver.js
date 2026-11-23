import { api, isCancelledError } from "../core/api.js";
import { logout } from "../core/auth.js";
import { openPasswordChangeModal, setupPolling } from "../core/app.js";
import { confirmDialog, notify } from "../core/notifications.js";
import { initTheme, toggleTheme } from "../core/theme.js";
import {
  escapeHtml,
  formatRange,
  formatTemp,
  formatHum,
  qs,
  setButtonLoading,
  timeAgo,
} from "../core/helpers.js";

const BLOCKING_MESSAGES = {
  NO_TRUCK: "No tienes un camión asignado. Contacta a tu administrador.",
  NO_ROUTE_TODAY: "No tienes ruta programada para hoy.",
  TRUCK_UNAVAILABLE: "Tu camión no está disponible.",
  TRIP_IN_PROGRESS: "Ya tienes un viaje en curso.",
};

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
    } else if (c.status === "door_open") {
      badge.textContent = "Puerta abierta";
      badge.className = "badge badge--danger";
    } else if (c.status === "no_signal") {
      badge.textContent = "Sin señal";
      badge.className = "badge badge--warning";
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

  // Estado de la puerta (G7): independiente de las lecturas.
  const doorBadge = qs("#doorState");
  const doorLast = qs("#doorLastEvent");
  if (c && c.door_open !== null && c.door_open !== undefined) {
    doorBadge.textContent = c.door_open ? "Abierta" : "Cerrada";
    doorBadge.className = "badge " + (c.door_open ? "badge--danger" : "badge--success");
    doorLast.textContent = c.door_event_at ? timeAgo(c.door_event_at) : "—";
  } else {
    doorBadge.textContent = "Sin datos";
    doorBadge.className = "badge badge--muted";
    doorLast.textContent = "—";
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
      const can_ack = is_active && !alert.acknowledged_at;
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
              ${
                alert.acknowledged_at
                  ? '<span class="badge badge--muted">Reconocida</span>'
                  : ""
              }
            </div>
            <span class="muted text-xs">${timeAgo(alert.started_at)}${
              alert.value !== null && alert.value !== undefined
                ? ` · Valor: ${Number(alert.value).toFixed(1)}`
                : ""
            }</span>
            ${alert.message ? `<p class="driver-alert-item__msg">${escapeHtml(alert.message)}</p>` : ""}
            ${
              can_ack
                ? `<button class="btn btn--ghost btn--sm driver-alert-ack" type="button" data-ack-id="${alert.id}">
                     <i class="fa-solid fa-check"></i> Reconocer
                   </button>`
                : ""
            }
          </div>
        </div>
      `;
    })
    .join("");

  list.querySelectorAll("[data-ack-id]").forEach((button) => {
    button.addEventListener("click", () => ackAlert(Number(button.dataset.ackId)));
  });
}

async function ackAlert(alertId) {
  try {
    await api.post(`/driver/alerts/${alertId}/ack`);
    notify.success("Alerta reconocida.");
    await loadAlerts();
    await loadDashboard();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo reconocer la alerta" });
  }
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

// ===== Viaje y entregas (G6) =====

function renderTripStatus(data) {
  const idle = qs("#tripIdle");
  const active = qs("#tripActive");
  const badge = qs("#tripBadge");
  const startButton = qs("#startTripButton");
  const blockingText = qs("#tripBlocking");

  if (data.current_trip) {
    // Hay un viaje en curso
    idle.hidden = true;
    active.hidden = false;
    badge.textContent = "En curso";
    badge.className = "badge badge--danger";
    renderCurrentTrip(data.current_trip);
  } else {
    idle.hidden = false;
    active.hidden = true;

    if (data.can_start) {
      startButton.hidden = false;
      blockingText.hidden = true;
      badge.textContent = "Listo";
      badge.className = "badge badge--success";
    } else {
      startButton.hidden = true;
      blockingText.hidden = false;
      blockingText.textContent =
        BLOCKING_MESSAGES[data.blocking_reason] || "No puedes iniciar un viaje.";
      badge.textContent = "Sin viaje";
      badge.className = "badge badge--muted";
    }
  }
}

function renderCurrentTrip(trip) {
  const delivered = trip.orders_delivered;
  const total = trip.orders.length;
  const label = qs("#tripProgressLabel");
  const fill = qs("#tripProgressFill");

  label.textContent = `${delivered} de ${total} entregadas`;
  fill.style.width = total > 0 ? `${(delivered / total) * 100}%` : "0%";

  const list = qs("#ordersList");
  list.innerHTML = trip.orders
    .map((order) => {
      const stateClass = `driver-order--${order.state}`;
      const canStart = order.state === "pending" && trip.state === "in_progress";
      const canDeliver = order.state === "in_delivery";
      const canFail =
        (order.state === "pending" || canDeliver) && trip.state === "in_progress";

      return `
        <div class="driver-order ${stateClass}">
          <span class="driver-order__num">${order.order_index + 1}</span>
          <div class="driver-order__body">
            <div class="driver-order__name">${escapeHtml(order.name)}</div>
            ${order.address ? `<div class="driver-order__address">${escapeHtml(order.address)}</div>` : ""}
            ${order.failure_reason ? `<div class="driver-order__reason">Motivo: ${escapeHtml(order.failure_reason)}</div>` : ""}
          </div>
          <div class="driver-order__actions">
            ${canStart ? `<button class="btn btn--primary btn--sm" type="button" data-order-action="start" data-order-id="${order.id}"><i class="fa-solid fa-play"></i></button>` : ""}
            ${canDeliver ? `<button class="btn btn--success btn--sm" type="button" data-order-action="deliver" data-order-id="${order.id}"><i class="fa-solid fa-check"></i></button>` : ""}
            ${canFail ? `<button class="btn btn--danger btn--sm" type="button" data-order-action="fail" data-order-id="${order.id}"><i class="fa-solid fa-xmark"></i></button>` : ""}
          </div>
        </div>
      `;
    })
    .join("");

  // Wire order buttons
  list.querySelectorAll("[data-order-action]").forEach((button) => {
    button.addEventListener("click", () =>
      handleOrderAction(button.dataset.orderAction, Number(button.dataset.orderId))
    );
  });
}

async function handleOrderAction(action, orderId) {
  const current = await api.get("/driver/trips/current");
  if (!current) return;
  const tripId = current.id;

  if (action === "start") {
    try {
      await api.post(`/driver/trips/${tripId}/orders/${orderId}/start`);
      notify.success("Entrega iniciada.");
      await loadTripStatus();
    } catch (error) {
      notify.error(error.message, { title: "No se pudo iniciar la entrega" });
    }
  } else if (action === "deliver") {
    try {
      await api.post(`/driver/trips/${tripId}/orders/${orderId}/deliver`);
      notify.success("Orden entregada.");
      await loadTripStatus();
    } catch (error) {
      notify.error(error.message, { title: "No se pudo marcar la entrega" });
    }
  } else if (action === "fail") {
    const reason = await askFailReason();
    if (!reason) return;
    try {
      await api.post(`/driver/trips/${tripId}/orders/${orderId}/fail`, { reason });
      notify.warning("Orden marcada como no entregada.");
      await loadTripStatus();
    } catch (error) {
      notify.error(error.message, { title: "No se pudo marcar como fallida" });
    }
  }
}

async function askFailReason() {
  return window.prompt("Motivo de la no entrega (obligatorio):", "Cliente cerrado");
}

async function startTrip() {
  const button = qs("#startTripButton");
  setButtonLoading(button, true, "Iniciando…");
  try {
    const status = await api.get("/driver/trips/can-start");
    if (!status.can_start || !status.route_id) {
      notify.warning(BLOCKING_MESSAGES[status.blocking_reason] || "No puedes iniciar.");
      return;
    }
    await api.post("/driver/trips/start", { route_id: status.route_id });
    notify.success("Viaje iniciado. Buen camino.");
    await loadTripStatus();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo iniciar el viaje" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function endTrip() {
  const current = await api.get("/driver/trips/current");
  if (!current) return;

  const pending = current.orders_pending;
  const message =
    pending > 0
      ? `Tienes ${pending} orden(es) sin entregar. Se marcarán como no entregadas. ¿Confirmas?`
      : "¿Finalizar el viaje?";

  const accepted = await confirmDialog({
    title: "Finalizar viaje",
    message,
    confirmText: "Finalizar",
    danger: true,
  });
  if (!accepted) return;

  try {
    await api.post(`/driver/trips/${current.id}/end`, {
      confirm_pending: true,
      failure_reason: pending > 0 ? "Finalizó el viaje sin entregar" : null,
    });
    notify.success("Viaje finalizado correctamente.");
    await loadTripStatus();
    await loadDashboard();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo finalizar el viaje" });
  }
}

async function loadTripStatus() {
  try {
    const current = await api.get("/driver/trips/current");
    const canStart = await api.get("/driver/trips/can-start");
    renderTripStatus({
      current_trip: current,
      can_start: canStart.can_start,
      blocking_reason: canStart.blocking_reason,
    });
    if (current) {
      renderCurrentTrip(current);
    }
  } catch (error) {
    if (isCancelledError(error)) return;
  }
}

// Wire trip buttons
qs("#startTripButton").addEventListener("click", startTrip);
qs("#endTripButton").addEventListener("click", endTrip);

async function init() {
  // Verificar sesión; si es 401, api.js ya redirige al login.
  const me = await api.get("/driver/me").catch(() => null);
  if (!me) return;

  await Promise.allSettled([loadDashboard(), loadAlerts(), loadTripStatus()]);
  setupPolling(async () => {
    await Promise.allSettled([loadDashboard(), loadAlerts(), loadTripStatus()]);
  }, 5000);
}

init().catch((error) => {
  if (error?.status === 401) return; // api.js ya redirigió
  console.error(error);
  notify.error("No se pudo inicializar el portal del conductor.");
});
