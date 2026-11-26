import { api } from "../core/api.js";
import { initProtectedPage, setupPolling } from "../core/app.js";
import { notify } from "../core/notifications.js";
import {
  escapeHtml,
  formatPercent,
  formatRange,
  formatTemp,
  formatHum,
  qs,
  readingStatusMeta,
  timeAgo,
} from "../core/helpers.js";
import {
  createMap,
  fitToLatLngs,
  routeStyle,
  toLatLngs,
  truckIcon,
} from "../components/map.js";

const state = {
  summary: null,
  trucks: [],
  alerts: [],
  selectedTruckId: "",
  alertIndex: 0,
  tempSignature: "",
  filterSignature: "",
  needsFit: true,
  loadedOnce: false,
  lastGoodUpdate: null,
  connectionOk: true,
  failureNotified: false,
  weatherTimer: null,
  clockTimer: null,
};

let map = null;
const markers = new Map();
const lines = new Map();

const filterSelect = qs("#truckFilter");
const tempTrack = qs("#tempTrack");
const tempEmpty = qs("#tempEmpty");
const statusPanel = qs("#statusPanel");
const statusBadge = qs("#statusBadge");
const connectionBadge = qs("#connectionBadge");
const connectionText = qs("#connectionText");
const lastUpdate = qs("#lastUpdate");
const weatherCard = qs("#weatherCard");
const weatherCity = qs("#weatherCity");

function updateConnection(ok) {
  state.connectionOk = ok;
  connectionBadge.classList.toggle("is-offline", !ok);
  connectionText.textContent = ok ? "En vivo" : "Sin conexión";
}

function updateClockLabels() {
  if (state.lastGoodUpdate) {
    lastUpdate.innerHTML = `<i class="fa-regular fa-clock"></i> Actualizado ${timeAgo(
      state.lastGoodUpdate
    )}`;
  }
}

function renderSummary() {
  const summary = state.summary;
  if (!summary) return;
  qs("#kpiActive").textContent = summary.active_trucks;
  qs("#kpiActiveMeta").textContent = `${summary.total_trucks} ${
    summary.total_trucks === 1 ? "camión" : "camiones"
  } registrado${summary.total_trucks === 1 ? "" : "s"}`;
  qs("#kpiTemperature").textContent =
    summary.avg_temperature === null ? "—" : formatTemp(summary.avg_temperature);
  qs("#kpiTemperatureMeta").textContent =
    summary.avg_temperature === null
      ? "sin lecturas recientes"
      : "lecturas de los últimos 10 min";
  qs("#kpiEffectiveness").textContent = formatPercent(summary.effectiveness);
  qs("#kpiEffectivenessMeta").textContent = `${
    summary.readings_24h
  } lecturas · ${summary.active_alerts} alerta${
    summary.active_alerts === 1 ? "" : "s"
  } activa${summary.active_alerts === 1 ? "" : "s"}`;
}

function renderFilter() {
  const signature = state.trucks.map((truck) => `${truck.id}:${truck.plate}`).join("|");
  if (signature === state.filterSignature) return;
  state.filterSignature = signature;

  if (
    state.selectedTruckId &&
    !state.trucks.some((truck) => String(truck.id) === state.selectedTruckId)
  ) {
    state.selectedTruckId = "";
    state.needsFit = true;
  }

  filterSelect.innerHTML =
    '<option value="">Todos los camiones</option>' +
    state.trucks
      .map(
        (truck) =>
          `<option value="${truck.id}">${escapeHtml(truck.plate)} · ${escapeHtml(
            `${truck.brand} ${truck.model}`
          )}</option>`
      )
      .join("");
  filterSelect.value = state.selectedTruckId;
}

function renderTemperatureCarousel() {
  const signature = state.trucks
    .map(
      (truck) =>
        `${truck.id}:${truck.temperature}:${truck.humidity}:${truck.reading_status}:${truck.active_alerts}:${truck.last_update}`
    )
    .join("|");
  if (signature === state.tempSignature) return;
  state.tempSignature = signature;

  if (!state.trucks.length) {
    tempTrack.innerHTML = "";
    tempEmpty.classList.remove("hidden");
    return;
  }

  tempEmpty.classList.add("hidden");
  const previousScroll = tempTrack.scrollLeft;
  tempTrack.innerHTML = state.trucks
    .map((truck) => {
      const meta = readingStatusMeta(truck.reading_status);
      const badgeClass =
        truck.reading_status === "alerta"
          ? "badge--danger"
          : truck.reading_status === "normal"
            ? "badge--success"
            : "badge--muted";
      return `
        <article class="temp-card ${
          truck.reading_status === "alerta" ? "temp-card--alert" : ""
        }" data-truck-id="${truck.id}" role="button" tabindex="0"
          aria-label="Ver detalle del camión ${escapeHtml(truck.plate)}">
          <div class="temp-card__top">
            <span class="temp-card__plate">${escapeHtml(truck.plate)}</span>
            <span class="badge ${badgeClass} temp-card__status">${meta.label}</span>
          </div>
          <div class="temp-card__value">
            <strong class="${meta.className}">${formatTemp(truck.temperature, false)}</strong>
            <span class="temp-card__unit">°C</span>
          </div>
          <div class="temp-card__meta">
            <span><i class="fa-solid fa-droplet"></i>${formatHum(truck.humidity)}</span>
            <span>${truck.last_update ? timeAgo(truck.last_update) : "Sin lectura"}</span>
          </div>
        </article>
      `;
    })
    .join("");
  tempTrack.scrollLeft = previousScroll;
}

function popupHtml(truck) {
  const statusLabel = readingStatusMeta(truck.reading_status).label;
  return `
    <div class="map-popup__title">${escapeHtml(truck.plate)}</div>
    <div class="map-popup__row"><span>Temperatura</span><strong>${formatTemp(
      truck.temperature
    )}</strong></div>
    <div class="map-popup__row"><span>Humedad</span><strong>${formatHum(
      truck.humidity
    )}</strong></div>
    <div class="map-popup__row"><span>Estado</span><strong>${escapeHtml(statusLabel)}</strong></div>
    <div class="map-popup__row"><span>Última lectura</span><strong>${
      truck.last_update ? timeAgo(truck.last_update) : "—"
    }</strong></div>
    ${
      truck.route
        ? `<div class="map-popup__row"><span>Ruta</span><strong>${escapeHtml(
            truck.route.name
          )}</strong></div>`
        : ""
    }
    <a class="map-popup__link" href="truck-detail.html?id=${truck.id}">Ver detalle del camión</a>
  `;
}

function removeMarker(truckId) {
  const record = markers.get(truckId);
  if (!record) return;
  record.marker.remove();
  markers.delete(truckId);
}

function removeLine(truckId) {
  const record = lines.get(truckId);
  if (!record) return;
  record.line.remove();
  lines.delete(truckId);
}

function updateMap() {
  if (!map) return;
  const visibleTrucks = state.selectedTruckId
    ? state.trucks.filter((truck) => String(truck.id) === state.selectedTruckId)
    : state.trucks;
  const visibleIds = new Set(visibleTrucks.map((truck) => truck.id));

  for (const truckId of Array.from(markers.keys())) {
    if (!visibleIds.has(truckId)) removeMarker(truckId);
  }
  for (const truckId of Array.from(lines.keys())) {
    if (!visibleIds.has(truckId)) removeLine(truckId);
  }

  let withGps = 0;
  for (const truck of visibleTrucks) {
    const selected = String(truck.id) === state.selectedTruckId;
    const hasGps =
      truck.latitude !== null &&
      truck.longitude !== null &&
      Number.isFinite(Number(truck.latitude)) &&
      Number.isFinite(Number(truck.longitude));

    if (!hasGps) {
      removeMarker(truck.id);
    } else {
      withGps += 1;
      const latLng = [Number(truck.latitude), Number(truck.longitude)];
      const inRoute = truck.status === "en_ruta";
      let record = markers.get(truck.id);
      if (!record) {
        const marker = L.marker(latLng, {
          icon: truckIcon({ inRoute, selected }),
          title: truck.plate,
        }).addTo(map);
        marker.on("click", () => {
          state.selectedTruckId = String(truck.id);
          state.needsFit = true;
          updateMap();
        });
        record = { marker, inRoute, selected, popupHtml: null };
        markers.set(truck.id, record);
      } else {
        record.marker.setLatLng(latLng);
        if (record.inRoute !== inRoute || record.selected !== selected) {
          record.marker.setIcon(truckIcon({ inRoute, selected }));
          record.inRoute = inRoute;
          record.selected = selected;
        }
      }
      const html = popupHtml(truck);
      if (record.popupHtml !== html) {
        if (record.popupHtml === null) {
          record.marker.bindPopup(html);
        } else {
          record.marker.setPopupContent(html);
        }
        record.popupHtml = html;
      }
      record.marker.setZIndexOffset(selected ? 1000 : 0);
    }

    const geometry = truck.route?.geometry;
    if (Array.isArray(geometry) && geometry.length > 1) {
      const signature = `${truck.route.id}:${geometry.length}:${geometry[0]?.join(
        ","
      )}:${geometry[geometry.length - 1]?.join(",")}`;
      const existing = lines.get(truck.id);
      if (existing && existing.signature === signature) {
        existing.line.setStyle(routeStyle(selected, true));
        if (selected) existing.line.bringToFront();
      } else {
        if (existing) existing.line.remove();
        const line = L.polyline(toLatLngs(geometry), routeStyle(selected, true)).addTo(
          map
        );
        if (selected) line.bringToFront();
        lines.set(truck.id, { line, signature });
      }
    } else {
      removeLine(truck.id);
    }
  }

  qs("#mapSummary").textContent = `${visibleTrucks.length} ${
    visibleTrucks.length === 1 ? "camión" : "camiones"
  } · ${withGps} con GPS`;

  if (state.needsFit) {
    state.needsFit = false;
    const latLngs = [];
    for (const truck of visibleTrucks) {
      if (
        truck.latitude !== null &&
        truck.longitude !== null &&
        Number.isFinite(Number(truck.latitude)) &&
        Number.isFinite(Number(truck.longitude))
      ) {
        latLngs.push([Number(truck.latitude), Number(truck.longitude)]);
      }
      if (Array.isArray(truck.route?.geometry)) {
        latLngs.push(...toLatLngs(truck.route.geometry));
      }
    }
    if (latLngs.length) fitToLatLngs(map, latLngs, { maxZoom: 14 });
  }
}

function statusCountsHtml(summary) {
  return `
    <div class="status-panel__counts">
      <span class="status-count"><span class="status-count__dot status-count__dot--route"></span> En ruta <strong>${
        summary.trucks_by_status.en_ruta
      }</strong></span>
      <span class="status-count"><span class="status-count__dot status-count__dot--idle"></span> Disponible <strong>${
        summary.trucks_by_status.disponible
      }</strong></span>
      <span class="status-count"><span class="status-count__dot status-count__dot--maintenance"></span> Mantenimiento <strong>${
        summary.trucks_by_status.mantenimiento
      }</strong></span>
    </div>
  `;
}

function renderStatus() {
  const summary = state.summary;
  const alerts = state.alerts;
  if (alerts.length === 0) {
    statusBadge.className = "badge badge--success";
    statusBadge.textContent = "Operativo";
    statusPanel.innerHTML = `
      <div class="status-panel__hero">
        <div class="status-panel__icon"><i class="fa-regular fa-face-smile"></i></div>
        <div>
          <strong>Todo bien</strong>
          <p>Ningún camión fuera de los rangos permitidos.</p>
        </div>
      </div>
      ${summary ? statusCountsHtml(summary) : ""}
    `;
    return;
  }

  statusBadge.className = "badge badge--danger";
  statusBadge.textContent = `${alerts.length} alerta${alerts.length === 1 ? "" : "s"}`;
  if (state.alertIndex >= alerts.length) state.alertIndex = 0;
  const alert = alerts[state.alertIndex];
  const isDisconnect = alert.alert_type === "desconexion";
  const value = isDisconnect
    ? "Sin comunicación"
    : alert.alert_type === "temperatura"
      ? formatTemp(alert.value)
      : formatHum(alert.value);
  const range =
    alert.min_value !== null && alert.max_value !== null
      ? formatRange(
          alert.min_value,
          alert.max_value,
          alert.alert_type === "temperatura" ? " °C" : " %"
        )
      : null;
  const typeLabel =
    alert.alert_type === "temperatura"
      ? "Temperatura fuera de rango"
      : alert.alert_type === "humedad"
        ? "Humedad fuera de rango"
        : "Dispositivo desconectado";

  statusPanel.innerHTML = `
    <div class="status-panel__hero status-panel__hero--alert">
      <div class="status-panel__icon"><i class="fa-solid fa-fire"></i></div>
      <div>
        <strong>${alerts.length} alerta${alerts.length === 1 ? "" : "s"} activa${
          alerts.length === 1 ? "" : "s"
        }</strong>
        <p>Revisa la cadena de frío de la flota.</p>
      </div>
    </div>
    <div class="alert-carousel">
      <div class="alert-carousel__item">
        <div class="alert-carousel__top">
          <span class="alert-carousel__truck">${escapeHtml(
            alert.truck_plate || alert.device_identifier || "Dispositivo"
          )}</span>
          <span class="badge badge--danger badge--plain">${escapeHtml(typeLabel)}</span>
        </div>
        <div class="alert-carousel__value">
          Valor: <strong>${value}</strong>${range ? ` · Rango: ${range}` : ""}
        </div>
        <p class="alert-carousel__message">${escapeHtml(alert.message || typeLabel)}</p>
        <div class="alert-carousel__footer">
          <span>${timeAgo(alert.started_at)}</span>
          ${
            alert.truck_id
              ? `<a href="truck-detail.html?id=${alert.truck_id}">Ver camión <i class="fa-solid fa-arrow-right"></i></a>`
              : ""
          }
        </div>
      </div>
      ${
        alerts.length > 1
          ? `<div class="alert-carousel__nav">
              <button class="icon-button" type="button" data-alert-nav="prev" aria-label="Alerta anterior"><i class="fa-solid fa-chevron-left"></i></button>
              <span>${state.alertIndex + 1} de ${alerts.length}</span>
              <button class="icon-button" type="button" data-alert-nav="next" aria-label="Alerta siguiente"><i class="fa-solid fa-chevron-right"></i></button>
            </div>`
          : ""
      }
    </div>
    ${summary ? statusCountsHtml(summary) : ""}
  `;
}

function renderWeather(weather) {
  weatherCity.textContent = weather.city || "Tijuana";
  if (!weather.available) {
    weatherCard.innerHTML = `
      <div class="empty-state empty-state--compact">
        <div class="empty-state__icon"><i class="fa-solid fa-cloud"></i></div>
        <strong>Clima no disponible</strong>
        <p>${escapeHtml(weather.error || "No se pudo consultar el clima exterior.")}</p>
      </div>
    `;
    return;
  }
  weatherCard.innerHTML = `
    <div class="weather-card__top">
      <span class="weather-card__city">Exterior · ${escapeHtml(weather.city)}</span>
      <span class="weather-card__city ${weather.stale ? "weather-card__stale" : ""}">
        ${weather.stale ? "Datos en caché" : timeAgo(weather.updated_at)}
      </span>
    </div>
    <div class="weather-card__main">
      <div class="weather-card__icon"><i class="fa-solid ${escapeHtml(
        weather.icon || "fa-cloud"
      )}"></i></div>
      <div>
        <div class="weather-card__temp">${formatTemp(weather.temperature)}</div>
        <div class="weather-card__condition">${escapeHtml(
          weather.condition || "Condición desconocida"
        )}</div>
      </div>
    </div>
    <div class="weather-card__meta">
      <span><i class="fa-solid fa-droplet"></i> ${formatHum(weather.humidity)}</span>
      <span><i class="fa-solid fa-wind"></i> ${
        weather.wind_speed === null || weather.wind_speed === undefined
          ? "—"
          : `${Number(weather.wind_speed).toFixed(0)} km/h`
      }</span>
      <span>Actualizado ${timeAgo(weather.updated_at)}</span>
    </div>
  `;
}

async function loadWeather() {
  try {
    const weather = await api.get("/dashboard/weather");
    renderWeather(weather);
  } catch (error) {
    renderWeather({
      available: false,
      city: "Tijuana",
      error: error.message,
    });
  }
}

async function loadDashboard() {
  try {
    const [summaryResult, trucksResult, alertsResult] = await Promise.allSettled([
      api.get("/dashboard/summary"),
      api.get("/dashboard/trucks"),
      api.get("/dashboard/alerts"),
    ]);

    const failures = [summaryResult, trucksResult, alertsResult].filter(
      (result) => result.status === "rejected"
    );
    if (failures.length === 3) throw failures[0].reason;

    if (summaryResult.status === "fulfilled") state.summary = summaryResult.value;
    if (trucksResult.status === "fulfilled") state.trucks = trucksResult.value;
    if (alertsResult.status === "fulfilled") state.alerts = alertsResult.value;
    state.lastGoodUpdate = new Date();
    state.loadedOnce = true;
    if (!state.connectionOk) {
      notify.success("Conexión restablecida con el servidor.");
      state.failureNotified = false;
    }
    updateConnection(true);
    updateClockLabels();
    renderSummary();
    renderFilter();
    renderTemperatureCarousel();
    renderStatus();
    updateMap();
  } catch (error) {
    if (error?.cancelled) return;
    updateConnection(false);
    if (!state.failureNotified) {
      notify.error(
        "No se pudo actualizar el panel. Se conservan los últimos datos válidos.",
        { title: "Problema de conexión" }
      );
      state.failureNotified = true;
    }
    if (!state.loadedOnce) {
      qs("#mapSummary").textContent = "Sin datos disponibles";
    }
    console.error(error);
  }
}

function wireEvents() {
  filterSelect.addEventListener("change", () => {
    state.selectedTruckId = filterSelect.value;
    state.needsFit = true;
    updateMap();
  });

  qs("#tempPrev").addEventListener("click", () => {
    tempTrack.scrollBy({ left: -210, behavior: "smooth" });
  });
  qs("#tempNext").addEventListener("click", () => {
    tempTrack.scrollBy({ left: 210, behavior: "smooth" });
  });

  tempTrack.addEventListener("click", (event) => {
    const card = event.target.closest("[data-truck-id]");
    if (card) window.location.href = `truck-detail.html?id=${card.dataset.truckId}`;
  });
  tempTrack.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" && event.key !== " ") return;
    const card = event.target.closest("[data-truck-id]");
    if (card) {
      event.preventDefault();
      window.location.href = `truck-detail.html?id=${card.dataset.truckId}`;
    }
  });

  statusPanel.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-alert-nav]");
    if (!nav) return;
    const total = state.alerts.length;
    if (!total) return;
    state.alertIndex =
      nav.dataset.alertNav === "next"
        ? (state.alertIndex + 1) % total
        : (state.alertIndex - 1 + total) % total;
    renderStatus();
  });

  window.addEventListener("resize", () => {
    if (map) setTimeout(() => map.invalidateSize(), 120);
  });
}

async function init() {
  await initProtectedPage();
  map = createMap("dashboardMap", { zoom: 12, lazy: true });
  wireEvents();
  loadWeather();
  state.weatherTimer = window.setInterval(loadWeather, 10 * 60 * 1000);
  state.clockTimer = window.setInterval(updateClockLabels, 5000);
  setupPolling(loadDashboard, 10000);
  window.addEventListener(
    "beforeunload",
    () => {
      window.clearInterval(state.weatherTimer);
      window.clearInterval(state.clockTimer);
    },
    { once: true }
  );
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar el panel de control.");
  }
});
