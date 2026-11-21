import { api } from "../core/api.js";
import { initProtectedPage } from "../core/app.js";
import { notify } from "../core/notifications.js";
import {
  alertStatusMeta,
  alertTypeMeta,
  escapeHtml,
  formatDateTime,
  formatHum,
  formatRange,
  formatTemp,
  qs,
  timeAgo,
  toIsoOrNull,
} from "../core/helpers.js";
import { activateModal } from "../components/modal.js";
import { renderPagination } from "../components/pagination.js";
import {
  emptyRow,
  renderTableState,
  setAriaBusy,
  tableError,
  tableSkeleton,
} from "../components/feedback.js";

const params = new URLSearchParams(window.location.search);

const state = {
  page: 1,
  pageSize: 20,
  total: 0,
  truckId: params.get("truck_id") || "",
  type: params.get("type") || "",
  status: params.get("status") || "",
  from: null,
  to: null,
};

const tableBody = qs("#alertsTableBody");
const pagination = qs("#alertsPagination");

function openModal() {
  const modal = qs("#alertModal");
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  modal._deactivate?.();
  modal._deactivate = activateModal(modal, { onClose: closeModal });
}

function closeModal() {
  const modal = qs("#alertModal");
  modal.classList.add("hidden");
  modal._deactivate?.();
  modal._deactivate = null;
  document.body.classList.remove("modal-open");
}

function valueLabel(alert) {
  if (alert.alert_type === "desconexion") return "—";
  return alert.alert_type === "temperatura"
    ? formatTemp(alert.value)
    : formatHum(alert.value);
}

function rangeLabel(alert) {
  if (alert.alert_type === "desconexion") return "—";
  return formatRange(
    alert.min_value,
    alert.max_value,
    alert.alert_type === "temperatura" ? " °C" : " %"
  );
}

function renderRows(alerts) {
  if (!alerts.length) {
    renderTableState(
      tableBody,
      emptyRow(
        7,
        "fa-shield-heart",
        "Sin alertas para estos filtros",
        "Cuando una lectura salga de los rangos configurados aparecerá aquí automáticamente."
      )
    );
    return;
  }
  tableBody.innerHTML = alerts
    .map((alert) => {
      const type = alertTypeMeta(alert.alert_type);
      const status = alertStatusMeta(alert.status);
      const typeClass =
        alert.alert_type === "temperatura"
          ? "alert-type-cell--temperature"
          : alert.alert_type === "humedad"
            ? "alert-type-cell--humidity"
            : "alert-type-cell--offline";
      return `
        <tr>
          <td>
            <div>${formatDateTime(alert.started_at)}</div>
            <div class="muted text-xs">${timeAgo(alert.started_at)}</div>
          </td>
          <td>${
            alert.truck_id
              ? `<a href="truck-detail.html?id=${alert.truck_id}">${escapeHtml(
                  alert.truck_plate || "Camión"
                )}</a>`
              : escapeHtml(alert.device_identifier || "—")
          }</td>
          <td>
            <span class="alert-type-cell ${typeClass}">
              <i class="fa-solid ${type.icon}"></i> ${type.label}
            </span>
          </td>
          <td><span class="alert-value">${valueLabel(alert)}</span></td>
          <td><span class="alert-range">${rangeLabel(alert)}</span></td>
          <td><span class="badge ${status.className}">${status.label}</span></td>
          <td class="cell-actions">
            <button class="btn btn--ghost btn--sm" type="button" data-alert-id="${alert.id}">
              <i class="fa-solid fa-eye"></i> Detalle
            </button>
          </td>
        </tr>
      `;
    })
    .join("");
}

function renderPaginationControls() {
  renderPagination(pagination, {
    page: state.page,
    total: state.total,
    pageSize: state.pageSize,
    itemLabel: "alertas",
    onChange: (page) => {
      state.page = page;
      loadAlerts();
    },
  });
}

async function loadAlerts() {
  const query = new URLSearchParams({
    page: state.page,
    page_size: state.pageSize,
  });
  if (state.truckId) query.set("truck_id", state.truckId);
  if (state.type) query.set("alert_type", state.type);
  if (state.status) query.set("status", state.status);
  if (state.from) query.set("date_from", state.from);
  if (state.to) query.set("date_to", state.to);

  try {
    setAriaBusy(tableBody, true);
    renderTableState(tableBody, tableSkeleton(7, 6, 7));
    const data = await api.get(`/alerts?${query.toString()}`);
    state.total = data.total;
    const totalPages = Math.max(1, Math.ceil(data.total / state.pageSize));
    if (state.page > totalPages) {
      state.page = totalPages;
      return loadAlerts();
    }
    renderRows(data.items);
    renderPaginationControls();
    qs("#alertsCount").textContent = `${data.total} alerta${
      data.total === 1 ? "" : "s"
    } encontrada${data.total === 1 ? "" : "s"}`;

    const active = data.items.filter((alert) => alert.status === "activa").length;
    const resolved = data.items.filter((alert) => alert.status === "resuelta").length;
    qs("#alertsChips").innerHTML = `
      <span class="chip">En esta página: <strong>${active}</strong> activas · <strong>${resolved}</strong> resueltas</span>
    `;
  } catch (error) {
    renderTableState(tableBody, tableError(7, error.message), {
      onRetry: loadAlerts,
    });
    notify.error(error.message, { title: "Error al cargar alertas" });
  } finally {
    setAriaBusy(tableBody, false);
  }
}

async function loadTrucks() {
  try {
    const trucks = await api.get("/trucks/options");
    const select = qs("#alertTruck");
    select.innerHTML =
      '<option value="">Todos</option>' +
      trucks
        .map(
          (truck) => `<option value="${truck.id}">${escapeHtml(truck.label)}</option>`
        )
        .join("");
    select.value = state.truckId;
  } catch (error) {
    notify.error(error.message, { title: "No se pudieron cargar los camiones" });
  }
}

async function showAlert(alertId) {
  openModal();
  qs("#alertModalBody").innerHTML =
    '<div class="loading-block"><span class="spinner"></span> Cargando detalle…</div>';
  qs("#alertTruckLink").classList.add("hidden");
  try {
    const alert = await api.get(`/alerts/${alertId}`);
    const type = alertTypeMeta(alert.alert_type);
    const status = alertStatusMeta(alert.status);
    qs("#alertModalSubtitle").textContent = `${
      alert.truck_plate || alert.device_identifier || "Dispositivo"
    } · ${formatDateTime(alert.started_at)}`;

    const isActive = alert.status === "activa";
    qs("#alertModalBody").innerHTML = `
      <div class="alert-detail-hero ${
        isActive ? "alert-detail-hero--active" : "alert-detail-hero--resolved"
      }">
        <i class="fa-solid ${isActive ? "fa-fire" : "fa-circle-check"}"></i>
        <div>
          <strong>${isActive ? "Alerta activa" : "Alerta resuelta"}</strong>
          <p>${escapeHtml(alert.message || type.label)}</p>
        </div>
      </div>
      <div class="alert-detail-grid">
        <dl class="detail-list">
          <div class="detail-row"><dt>Tipo</dt><dd><i class="fa-solid ${
            type.icon
          }"></i> ${type.label}</dd></div>
          <div class="detail-row"><dt>Estado</dt><dd><span class="badge ${
            status.className
          }">${status.label}</span></dd></div>
          <div class="detail-row"><dt>Valor detectado</dt><dd>${valueLabel(alert)}</dd></div>
          <div class="detail-row"><dt>Rango permitido</dt><dd>${rangeLabel(alert)}</dd></div>
        </dl>
        <dl class="detail-list">
          <div class="detail-row"><dt>Camión</dt><dd>${escapeHtml(
            alert.truck_plate || "—"
          )}</dd></div>
          <div class="detail-row"><dt>Dispositivo</dt><dd>${escapeHtml(
            alert.device_identifier || "—"
          )}</dd></div>
          <div class="detail-row"><dt>Inicio</dt><dd>${formatDateTime(
            alert.started_at
          )}</dd></div>
          <div class="detail-row"><dt>Resolución</dt><dd>${
            alert.resolved_at ? formatDateTime(alert.resolved_at) : "Pendiente"
          }</dd></div>
        </dl>
      </div>
    `;

    if (alert.truck_id) {
      qs("#alertTruckLink").href = `truck-detail.html?id=${alert.truck_id}`;
      qs("#alertTruckLink").classList.remove("hidden");
    }
  } catch (error) {
    qs("#alertModalBody").innerHTML = `<div class="empty-state">
      <div class="empty-state__icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
      <strong>No se pudo cargar el detalle</strong>
      <p>${escapeHtml(error.message)}</p>
    </div>`;
  }
}

function applyFiltersFromInputs() {
  state.truckId = qs("#alertTruck").value;
  state.type = qs("#alertType").value;
  state.status = qs("#alertStatus").value;
  state.from = toIsoOrNull(qs("#alertFrom").value);
  state.to = toIsoOrNull(qs("#alertTo").value);
  if (state.from && state.to && new Date(state.from) > new Date(state.to)) {
    notify.warning("La fecha inicial no puede ser posterior a la fecha final.");
    return false;
  }
  state.page = 1;
  const url = new URLSearchParams();
  if (state.truckId) url.set("truck_id", state.truckId);
  if (state.type) url.set("type", state.type);
  if (state.status) url.set("status", state.status);
  history.replaceState({}, "", url.toString() ? `alerts.html?${url}` : "alerts.html");
  return true;
}

function wireEvents() {
  qs("#alertsFilterForm").addEventListener("submit", (event) => {
    event.preventDefault();
    if (applyFiltersFromInputs()) loadAlerts();
  });

  qs("#clearAlertFilters").addEventListener("click", () => {
    qs("#alertTruck").value = "";
    qs("#alertType").value = "";
    qs("#alertStatus").value = "";
    qs("#alertFrom").value = "";
    qs("#alertTo").value = "";
    state.from = null;
    state.to = null;
    if (applyFiltersFromInputs()) loadAlerts();
  });

  tableBody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-alert-id]");
    if (button) showAlert(button.dataset.alertId);
  });

  qs("#alertModal").addEventListener("click", (event) => {
    if (event.target === qs("#alertModal")) closeModal();
  });
  document.querySelectorAll("[data-close='alertModal']").forEach((button) => {
    button.addEventListener("click", closeModal);
  });
}

async function init() {
  await initProtectedPage();
  wireEvents();
  qs("#alertType").value = state.type;
  qs("#alertStatus").value = state.status;
  await Promise.all([loadTrucks(), loadAlerts()]);
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar el historial de alertas.");
  }
});
