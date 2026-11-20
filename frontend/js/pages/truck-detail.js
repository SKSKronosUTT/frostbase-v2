import { api } from "../core/api.js";
import { initProtectedPage, setupPolling } from "../core/app.js";
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
  readingStatusMeta,
  timeAgo,
  toIsoOrNull,
  truckStatusMeta,
} from "../core/helpers.js";
import {
  createMap,
  fitToLatLngs,
  routeStyle,
  toLatLngs,
  truckIcon,
} from "../components/map.js";

const truckId = Number(new URLSearchParams(window.location.search).get("id"));

const state = {
  truck: null,
  readingsPage: 1,
  readingsPageSize: 20,
  readingsFrom: null,
  readingsTo: null,
  fitted: false,
  map: null,
  marker: null,
  line: null,
  lineSignature: "",
  loadFailed: false,
};

function readingBadge(reading) {
  if (!reading || !state.truck) {
    return { label: "Sin lectura", className: "badge--muted" };
  }
  const meta = readingStatusMeta(
    reading.temperature < state.truck.temperature_min ||
      reading.temperature > state.truck.temperature_max ||
      reading.humidity < state.truck.humidity_min ||
      reading.humidity > state.truck.humidity_max
      ? "alerta"
      : "normal"
  );
  return {
    label: meta.label,
    className: meta.className === "reading--alert" ? "badge--danger" : "badge--success",
  };
}

function renderDetail() {
  const truck = state.truck;
  document.title = `${truck.plate} | FrostBase`;
  qs("#detailTitle").textContent = `Camión ${truck.plate}`;
  qs("#detailSubtitle").textContent = `${truck.brand} ${truck.model} · ${truck.year}`;
  qs("#heroPlate").textContent = truck.plate;
  qs("#heroVehicle").textContent = `${truck.brand} ${truck.model} · ${truck.year}${
    truck.description ? ` · ${truck.description}` : ""
  }`;

  const status = truckStatusMeta(truck.status);
  const deviceOnline = truck.device?.is_online;
  qs("#heroBadges").innerHTML = `
    <span class="badge ${status.className}">${status.label}</span>
    <span class="status-dot ${deviceOnline ? "is-online" : "is-offline"}">${
      truck.device
        ? deviceOnline
          ? "Dispositivo en línea"
          : "Dispositivo desconectado"
        : "Sin dispositivo"
    }</span>
    ${
      truck.active_alerts > 0
        ? `<span class="badge badge--danger">${truck.active_alerts} alerta${
            truck.active_alerts === 1 ? "" : "s"
          }</span>`
        : ""
    }
  `;
  qs("#editTruckButton").href = `trucks.html?edit=${truck.id}`;

  const reading = truck.current_reading;
  const badge = readingBadge(reading);
  qs("#readingBadge").className = `badge ${badge.className}`;
  qs("#readingBadge").textContent = badge.label;

  if (!reading) {
    qs("#currentReading").innerHTML = `
      <div class="empty-state" style="grid-column: 1 / -1; padding: 22px 10px;">
        <div class="empty-state__icon"><i class="fa-solid fa-satellite-dish"></i></div>
        <strong>Sin lecturas recibidas</strong>
        <p>Este camión todavía no tiene datos de temperatura o humedad.</p>
      </div>
    `;
  } else {
    const tempAlert =
      reading.temperature < truck.temperature_min ||
      reading.temperature > truck.temperature_max;
    const humAlert =
      reading.humidity < truck.humidity_min || reading.humidity > truck.humidity_max;
    qs("#currentReading").innerHTML = `
      <div class="reading-tile ${tempAlert ? "reading-tile--alert" : ""}">
        <div class="reading-tile__label"><i class="fa-solid fa-temperature-half"></i> Temperatura</div>
        <div class="reading-tile__value">${formatTemp(reading.temperature, false)} <small>°C</small></div>
        <div class="reading-tile__meta">Permitido: ${formatRange(
          truck.temperature_min,
          truck.temperature_max,
          " °C"
        )}</div>
      </div>
      <div class="reading-tile ${humAlert ? "reading-tile--alert" : ""}">
        <div class="reading-tile__label"><i class="fa-solid fa-droplet"></i> Humedad</div>
        <div class="reading-tile__value">${formatHum(reading.humidity, false)} <small>%</small></div>
        <div class="reading-tile__meta">Permitido: ${formatRange(
          truck.humidity_min,
          truck.humidity_max,
          " %"
        )}</div>
      </div>
      <div class="reading-tile" style="grid-column: 1 / -1;">
        <div class="reading-tile__label"><i class="fa-regular fa-clock"></i> Última lectura del dispositivo</div>
        <div class="reading-tile__meta" style="margin-top: 0; font-size: 12px; color: var(--text);">
          ${formatDateTime(reading.reading_timestamp)} · recibida ${timeAgo(reading.received_at)}
        </div>
      </div>
    `;
  }

  if (truck.device) {
    const device = truck.device;
    qs("#deviceInfo").innerHTML = `
      <dl class="detail-list">
        <div class="detail-row"><dt>Identificador</dt><dd class="device-identifier">${escapeHtml(
          device.device_id
        )}</dd></div>
        <div class="detail-row"><dt>Estado de conexión</dt><dd>
          <span class="status-dot ${device.is_online ? "is-online" : "is-offline"}">${
            device.is_online ? "En línea" : "Desconectado"
          }</span>
        </dd></div>
        <div class="detail-row"><dt>Última comunicación</dt><dd>${
          device.last_seen
            ? `${timeAgo(device.last_seen)}<br><span class="muted">${formatDateTime(
                device.last_seen
              )}</span>`
            : "Nunca"
        }</dd></div>
        <div class="detail-row"><dt>Registrado</dt><dd>${formatDateTime(
          device.created_at
        )}</dd></div>
      </dl>
      <p class="settings-note" style="margin-top: 12px;">El estado del dispositivo es independiente del estado operativo del camión.</p>
    `;
  } else {
    qs("#deviceInfo").innerHTML = `
      <div class="empty-state" style="padding: 20px 8px;">
        <div class="empty-state__icon"><i class="fa-solid fa-microchip"></i></div>
        <strong>Sin dispositivo asociado</strong>
        <p>Asocia un ESP32-S3 desde la sección Flota para recibir lecturas.</p>
      </div>
    `;
  }

  if (truck.route) {
    qs("#routeInfo").innerHTML = `
      <dl class="detail-list">
        <div class="detail-row"><dt>Ruta</dt><dd>${escapeHtml(truck.route.name)}</dd></div>
        <div class="detail-row"><dt>Estado</dt><dd><span class="badge ${
          truck.route.status === "activa" ? "badge--success" : "badge--muted"
        }">${truck.route.status === "activa" ? "Activa" : "Inactiva"}</span></dd></div>
        <div class="detail-row"><dt>Puntos de entrega</dt><dd>${truck.route.points.length}</dd></div>
      </dl>
      <a class="btn btn--ghost btn--sm btn--block" style="margin-top: 12px;" href="route-detail.html?id=${
        truck.route.id
      }">Ver detalle de la ruta</a>
    `;
  } else {
    qs("#routeInfo").innerHTML = `
      <div class="empty-state" style="padding: 20px 8px;">
        <div class="empty-state__icon"><i class="fa-solid fa-route"></i></div>
        <strong>Sin ruta asignada</strong>
        <p>Asigna una ruta para ver su geometría en el mapa.</p>
      </div>
    `;
  }

  qs("#allAlertsLink").href = `alerts.html?truck_id=${truck.id}`;
  updateMap();
}

function updateMap() {
  const truck = state.truck;
  if (!state.map || !truck) return;
  const reading = truck.current_reading;
  const hasGps =
    reading &&
    reading.latitude !== null &&
    reading.longitude !== null &&
    Number.isFinite(Number(reading.latitude)) &&
    Number.isFinite(Number(reading.longitude));

  if (hasGps) {
    const latLng = [Number(reading.latitude), Number(reading.longitude)];
    qs("#gpsText").textContent = `${latLng[0].toFixed(5)}, ${latLng[1].toFixed(5)}`;
    if (!state.marker) {
      state.marker = L.marker(latLng, {
        icon: truckIcon({ inRoute: truck.status === "en_ruta", selected: true }),
        title: truck.plate,
      }).addTo(state.map);
      state.marker.bindPopup(`
        <div class="map-popup__title">${escapeHtml(truck.plate)}</div>
        <div class="map-popup__row"><span>Temperatura</span><strong>${formatTemp(
          reading.temperature
        )}</strong></div>
        <div class="map-popup__row"><span>Humedad</span><strong>${formatHum(
          reading.humidity
        )}</strong></div>
        <div class="map-popup__row"><span>Última lectura</span><strong>${timeAgo(
          reading.received_at
        )}</strong></div>
      `);
    } else {
      state.marker.setLatLng(latLng);
    }
  } else {
    qs("#gpsText").textContent = "Sin coordenadas GPS";
    if (state.marker) {
      state.marker.remove();
      state.marker = null;
    }
  }

  const geometry = truck.route?.geometry;
  if (Array.isArray(geometry) && geometry.length > 1) {
    const signature = `${truck.route.id}:${geometry.length}:${geometry[0]?.join(
      ","
    )}:${geometry[geometry.length - 1]?.join(",")}`;
    if (signature !== state.lineSignature) {
      if (state.line) state.line.remove();
      state.line = L.polyline(toLatLngs(geometry), routeStyle(true, true)).addTo(
        state.map
      );
      state.lineSignature = signature;
      state.fitted = false;
    }
  } else if (state.line) {
    state.line.remove();
    state.line = null;
    state.lineSignature = "";
  }

  qs("#mapUpdated").textContent = reading
    ? `Última lectura ${timeAgo(reading.received_at)}`
    : "Sin lecturas";

  if (!state.fitted) {
    const latLngs = [];
    if (hasGps) latLngs.push([Number(reading.latitude), Number(reading.longitude)]);
    if (Array.isArray(geometry)) latLngs.push(...toLatLngs(geometry));
    if (latLngs.length) {
      state.fitted = true;
      setTimeout(() => {
        fitToLatLngs(state.map, latLngs, { maxZoom: 14 });
        state.map.invalidateSize();
      }, 60);
    }
  }
}

function renderReadings(data) {
  const truck = state.truck;
  const rows = data.items;
  qs("#readingsSummary").textContent = `${data.total} lectura${
    data.total === 1 ? "" : "s"
  } registrada${data.total === 1 ? "" : "s"}`;

  if (!rows.length) {
    qs("#readingsBody").innerHTML = `<tr><td colspan="5">
      <div class="empty-state" style="padding: 26px 12px;">
        <div class="empty-state__icon"><i class="fa-solid fa-chart-line"></i></div>
        <strong>Sin lecturas en el periodo</strong>
        <p>Ajusta los filtros de fecha o espera nuevas lecturas del dispositivo.</p>
      </div>
    </td></tr>`;
    qs("#readingsPagination").innerHTML = "";
    return;
  }

  qs("#readingsBody").innerHTML = rows
    .map((reading) => {
      const tempAlert =
        reading.temperature < truck.temperature_min ||
        reading.temperature > truck.temperature_max;
      const humAlert =
        reading.humidity < truck.humidity_min || reading.humidity > truck.humidity_max;
      const gps =
        reading.latitude !== null && reading.longitude !== null
          ? `${Number(reading.latitude).toFixed(5)}, ${Number(
              reading.longitude
            ).toFixed(5)}`
          : "—";
      return `
        <tr>
          <td>${formatDateTime(reading.reading_timestamp)}</td>
          <td class="${tempAlert ? "text-danger" : ""}" style="font-variant-numeric: tabular-nums;">${formatTemp(
            reading.temperature
          )}</td>
          <td class="${humAlert ? "text-danger" : ""}" style="font-variant-numeric: tabular-nums;">${formatHum(
            reading.humidity
          )}</td>
          <td class="cell-muted" style="font-variant-numeric: tabular-nums;">${gps}</td>
          <td class="cell-muted">${timeAgo(reading.received_at)}</td>
        </tr>
      `;
    })
    .join("");

  const totalPages = Math.max(1, Math.ceil(data.total / state.readingsPageSize));
  const start = (data.page - 1) * state.readingsPageSize + 1;
  const end = Math.min(data.page * state.readingsPageSize, data.total);
  qs("#readingsPagination").innerHTML = `
    <span class="pagination__info">Mostrando ${start}–${end} de ${data.total}</span>
    <div class="pagination__controls">
      <button class="icon-button" type="button" data-reading-page="${
        data.page - 1
      }" ${data.page <= 1 ? "disabled" : ""} aria-label="Anterior"><i class="fa-solid fa-chevron-left"></i></button>
      <span class="pagination__page">Página ${data.page} de ${totalPages}</span>
      <button class="icon-button" type="button" data-reading-page="${
        data.page + 1
      }" ${data.page >= totalPages ? "disabled" : ""} aria-label="Siguiente"><i class="fa-solid fa-chevron-right"></i></button>
    </div>
  `;
  qs("#readingsPagination")
    .querySelectorAll("[data-reading-page]")
    .forEach((button) => {
      button.addEventListener("click", () => {
        if (button.disabled) return;
        state.readingsPage = Number(button.dataset.readingPage);
        loadReadings();
      });
    });
}

function renderAlerts(data) {
  const alerts = data.items;
  if (!alerts.length) {
    qs("#alertsList").innerHTML = `
      <div class="empty-state" style="padding: 20px 8px;">
        <div class="empty-state__icon"><i class="fa-solid fa-shield-heart"></i></div>
        <strong>Sin alertas registradas</strong>
        <p>Este camión no ha superado los rangos configurados.</p>
      </div>
    `;
    return;
  }

  qs("#alertsList").innerHTML = `<div class="detail-list">${alerts
    .map((alert) => {
      const type = alertTypeMeta(alert.alert_type);
      const status = alertStatusMeta(alert.status);
      const value =
        alert.alert_type === "desconexion"
          ? "Desconectado"
          : alert.alert_type === "temperatura"
            ? formatTemp(alert.value)
            : formatHum(alert.value);
      return `
        <div class="detail-row" style="align-items: center;">
          <div>
            <div style="font-size: 12.5px; font-weight: 600;"><i class="fa-solid ${
              type.icon
            }" style="color: var(--text-soft); margin-right: 5px;"></i>${
              type.label
            }</div>
            <div class="muted" style="font-size: 11px;">${timeAgo(alert.started_at)} · ${value}</div>
          </div>
          <span class="badge ${status.className}">${status.label}</span>
        </div>
      `;
    })
    .join("")}</div>
    <a class="btn btn--ghost btn--sm btn--block" style="margin-top: 12px;" href="alerts.html?truck_id=${
      truckId
    }">Ver todas las alertas</a>`;
}

async function loadTruck() {
  try {
    state.truck = await api.get(`/trucks/${truckId}`);
    state.loadFailed = false;
    renderDetail();
  } catch (error) {
    if (error.status === 404) {
      notify.error("El camión solicitado no existe o fue eliminado.");
      setTimeout(() => window.location.replace("trucks.html"), 1400);
    } else if (!state.loadFailed) {
      notify.error(error.message, { title: "Error al cargar el camión" });
    }
    state.loadFailed = true;
  }
}

async function loadReadings() {
  const params = new URLSearchParams({
    page: state.readingsPage,
    page_size: state.readingsPageSize,
  });
  if (state.readingsFrom) params.set("date_from", state.readingsFrom);
  if (state.readingsTo) params.set("date_to", state.readingsTo);
  try {
    const data = await api.get(`/readings/truck/${truckId}?${params.toString()}`);
    renderReadings(data);
  } catch (error) {
    qs("#readingsBody").innerHTML = `<tr><td colspan="5">
      <div class="empty-state" style="padding: 24px 10px;">
        <div class="empty-state__icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
        <strong>No se pudieron cargar las lecturas</strong>
        <p>${escapeHtml(error.message)}</p>
      </div>
    </td></tr>`;
  }
}

async function loadAlerts() {
  try {
    const data = await api.get(`/alerts?truck_id=${truckId}&page=1&page_size=5`);
    renderAlerts(data);
  } catch (error) {
    qs("#alertsList").innerHTML = `<div class="empty-state" style="padding: 20px 8px;">
      <div class="empty-state__icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
      <strong>No se pudieron cargar las alertas</strong>
      <p>${escapeHtml(error.message)}</p>
    </div>`;
  }
}

async function refreshAll() {
  await Promise.allSettled([loadTruck(), loadReadings(), loadAlerts()]);
}

function wireEvents() {
  qs("#readingsFilterForm").addEventListener("submit", (event) => {
    event.preventDefault();
    state.readingsFrom = toIsoOrNull(qs("#readingsFrom").value);
    state.readingsTo = toIsoOrNull(qs("#readingsTo").value);
    if (
      state.readingsFrom &&
      state.readingsTo &&
      new Date(state.readingsFrom) > new Date(state.readingsTo)
    ) {
      notify.warning("La fecha inicial no puede ser posterior a la final.");
      return;
    }
    state.readingsPage = 1;
    loadReadings();
  });

  qs("#clearReadingsFilter").addEventListener("click", () => {
    qs("#readingsFrom").value = "";
    qs("#readingsTo").value = "";
    state.readingsFrom = null;
    state.readingsTo = null;
    state.readingsPage = 1;
    loadReadings();
  });

  window.addEventListener("resize", () => {
    if (state.map) setTimeout(() => state.map.invalidateSize(), 120);
  });
}

async function init() {
  if (!Number.isInteger(truckId) || truckId <= 0) {
    window.location.replace("trucks.html");
    return;
  }
  await initProtectedPage();
  state.map = createMap("truckMap", { zoom: 13 });
  wireEvents();
  await refreshAll();
  setupPolling(refreshAll, 10000);
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar el detalle del camión.");
  }
});
