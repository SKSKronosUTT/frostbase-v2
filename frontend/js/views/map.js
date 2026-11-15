import { get } from "../api.js";
import {
  $,
  dateTime,
  emptyState,
  error,
  escapeHtml,
  icon,
  loadingState,
  relative,
  stateBadge,
  truckIcon,
} from "../ui.js";

const BASE = [32.45900929216648, -116.97966765227373];
const COLORS = ["#22d3ee", "#a78bfa", "#f472b6", "#fbbf24", "#34d399", "#fb7185", "#38bdf8", "#c084fc"];

export async function render(view) {
  view.innerHTML = loadingState("Cargando mapa en vivo");
  let map;
  let alive = true;

  async function load() {
    view.innerHTML = loadingState("Cargando mapa en vivo");
    try {
      const [routes, readings] = await Promise.all([get("/routes"), get("/readings/latest").catch(() => [])]);
      if (!alive) return;
      paint(routes, readings);
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Mapa no disponible", err.message, "map", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint(routes, readings) {
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Mapa de flotilla en vivo</h2><p>Posiciones de camiones, últimas lecturas de cadena de frío y geometría de rutas de entrega.</p></div>
        <div class="toolbar"><span class="chip">${readings.length} camiones reportando</span><button class="btn" data-refresh>${icon("refresh")} Actualizar</button></div>
      </div>
      <div class="map-layout">
        <article class="card map-card">
          <div id="map"></div>
          <div class="map-legend">
            <span><i class="map-dot" style="background:#22d3ee"></i>Posición de camión</span>
            <span><i class="map-dot" style="background:#a78bfa"></i>Ruta de entrega</span>
          </div>
        </article>
        <aside class="map-side">
          <article class="card">
            <div class="card-head"><div><h3>Camiones</h3><p>Última muestra de sensores</p></div><span class="badge blue">${readings.length}</span></div>
            ${
              readings.length
                ? `<div class="list">${readings
                    .map(
                      (row) => `<div class="list-item">
                        <div class="list-main"><strong>${escapeHtml(row.truck?.licensePlate || "—")}</strong><small>${row.reading ? `${row.reading.temp.toFixed(1)}°C · ${row.reading.percHumidity}% · ${relative(row.reading.date)}` : "Sin lectura"}</small></div>
                        ${stateBadge("truck", row.truck?.state?.id)}
                      </div>`,
                    )
                    .join("")}</div>`
                : emptyState("Sin posiciones de camiones", "Se necesitan lecturas para ubicar los camiones en el mapa.", "trucks")
            }
          </article>
          <article class="card">
            <div class="card-head"><div><h3>Rutas</h3><p>Geometría de entregas activas</p></div><span class="chip">${routes.length}</span></div>
            ${
              routes.length
                ? `<div class="list">${routes
                    .map(
                      (route, index) => `<button class="list-item" data-route="${route.id}" style="width:100%;background:none;border:0;border-bottom:1px solid var(--border);text-align:left;padding:10px 0;color:inherit">
                        <div class="list-main"><strong>${escapeHtml(route.name)}</strong><small>${route.stores.length} paradas · ${escapeHtml(route.driver?.name?.fullName || "Sin asignar")}</small></div>
                        <span class="map-dot" style="background:${COLORS[index % COLORS.length]}"></span>
                      </button>`,
                    )
                    .join("")}</div>`
                : emptyState("Sin rutas", "Crea rutas para visualizar la geometría de entrega.", "routes")
            }
          </article>
        </aside>
      </div>
    `;

    if (map) {
      map.remove();
      map = null;
    }
    if (!window.L) {
      error("Falta la librería del mapa", "No se pudo cargar Leaflet.");
      return;
    }

    map = window.L.map("map", { zoomControl: true, attributionControl: true }).setView(BASE, 11);
    window.L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; colaboradores de OpenStreetMap",
    }).addTo(map);

    const bounds = [];
    const routeLayers = new Map();
    routes.forEach((route, index) => {
      const points = (route.waypoints || []).map((point) => [point.latitude, point.longitude]);
      if (!points.length) return;
      const color = COLORS[index % COLORS.length];
      const line = window.L.polyline(points, { color, weight: 4, opacity: 0.82 }).addTo(map);
      routeLayers.set(route.id, line);
      bounds.push(...points);
    });

    readings.forEach((row) => {
      const reading = row.reading;
      if (!reading?.location) return;
      const marker = window.L.marker([reading.location.latitude, reading.location.longitude], {
        icon: window.L.divIcon({
          className: "truck-marker-wrap",
          html: `<span class="truck-marker">${truckIcon(19)}</span>`,
          iconSize: [36, 36],
          iconAnchor: [18, 18],
          popupAnchor: [0, -20],
        }),
        title: row.truck?.licensePlate || "Camión",
      }).addTo(map);
      marker.bindPopup(
        `<strong>${escapeHtml(row.truck?.licensePlate || "Camión")}</strong><br>${escapeHtml(row.truck?.brand || "")} ${escapeHtml(row.truck?.model || "")}<br>${reading.temp.toFixed(1)}°C · ${reading.percHumidity}% de humedad<br>${escapeHtml(dateTime(reading.date))}`,
      );
      bounds.push([reading.location.latitude, reading.location.longitude]);
    });

    if (bounds.length) {
      map.fitBounds(bounds, { padding: [42, 42], maxZoom: 13 });
    }

    view.querySelectorAll("[data-route]").forEach((button) =>
      button.addEventListener("click", () => {
        const layer = routeLayers.get(button.dataset.route);
        if (layer) map.fitBounds(layer.getBounds(), { padding: [40, 40] });
      }),
    );

    $("[data-refresh]").addEventListener("click", load);
    setTimeout(() => map?.invalidateSize(), 60);
  }

  await load();
  return () => {
    alive = false;
    if (map) map.remove();
  };
}
