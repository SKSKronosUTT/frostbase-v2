import { api } from "../core/api.js";
import { initProtectedPage } from "../core/app.js";
import { notify } from "../core/notifications.js";
import { escapeHtml, formatDateTime, qs, timeAgo } from "../core/helpers.js";
import {
  createMap,
  fitToLatLngs,
  numberedIcon,
  routeStyle,
  toLatLngs,
} from "../components/map.js";

const routeId = Number(new URLSearchParams(window.location.search).get("id"));

let map = null;

function renderRoute(route) {
  document.title = `${route.name} | FrostBase`;
  qs("#routeTitle").textContent = route.name;
  qs("#routeSubtitle").textContent = route.description || "Ruta de reparto";
  qs("#editRouteButton").href = `routes.html?id=${route.id}`;
  qs("#geometryStatus").textContent = route.geometry?.length
    ? "Geometría calculada"
    : "Sin geometría";

  const status =
    route.status === "activa"
      ? '<span class="badge badge--success">Activa</span>'
      : '<span class="badge badge--muted">Inactiva</span>';
  qs("#routeInfo").innerHTML = `
    <dl class="detail-list">
      <div class="detail-row"><dt>Estado</dt><dd>${status}</dd></div>
      <div class="detail-row"><dt>Descripción</dt><dd>${
        escapeHtml(route.description) || '<span class="muted">Sin descripción</span>'
      }</dd></div>
      <div class="detail-row"><dt>Puntos de entrega</dt><dd>${route.points.length}</dd></div>
      <div class="detail-row"><dt>Camión asignado</dt><dd>${
        route.truck
          ? `<a href="truck-detail.html?id=${route.truck.id}">${escapeHtml(
              route.truck.plate
            )}</a>`
          : '<span class="muted">Sin asignar</span>'
      }</dd></div>
      <div class="detail-row"><dt>Creada</dt><dd>${formatDateTime(route.created_at)}</dd></div>
      <div class="detail-row"><dt>Actualizada</dt><dd>${timeAgo(route.updated_at)}</dd></div>
    </dl>
  `;

  const points = route.points.slice().sort((a, b) => a.order_index - b.order_index);
  qs("#pointsCount").textContent = `${points.length} puntos`;
  qs("#routePoints").innerHTML = points.length
    ? `<div class="route-point-list">${points
        .map(
          (point, index) => `
          <div class="route-point">
            <span class="route-point__num">${index + 1}</span>
            <div>
              <div class="route-point__name">${escapeHtml(point.name)}</div>
              ${
                point.address
                  ? `<div class="route-point__address">${escapeHtml(point.address)}</div>`
                  : ""
              }
              <div class="route-point__coords">${Number(point.latitude).toFixed(
                5
              )}, ${Number(point.longitude).toFixed(5)}</div>
            </div>
          </div>
        `
        )
        .join("")}</div>`
    : '<div class="empty-state empty-state--small"><div class="empty-state__icon"><i class="fa-solid fa-location-dot"></i></div><strong>Sin puntos</strong></div>';

  const hasGeometry = Array.isArray(route.geometry) && route.geometry.length > 1;
  qs("#geometryWarning").classList.toggle("hidden", hasGeometry);

  const pointCount = points.length;
  qs("#routeDetailMapSummary").textContent = pointCount
    ? `Mapa de la ruta con ${pointCount} punto${
        pointCount === 1 ? "" : "s"
      } de entrega${hasGeometry ? " y geometría calculada." : " y línea entre puntos."}`
    : "Mapa de la ruta sin puntos de entrega.";

  points.forEach((point, index) => {
    L.marker([Number(point.latitude), Number(point.longitude)], {
      icon: numberedIcon(index + 1),
      title: point.name,
    })
      .bindPopup(
        `<div class="map-popup__title">${index + 1}. ${escapeHtml(point.name)}</div>
         ${
           point.address
             ? `<div class="map-popup__row"><span>Dirección</span><strong>${escapeHtml(
                 point.address
               )}</strong></div>`
             : ""
         }`
      )
      .addTo(map);
  });

  let lineLatLngs = [];
  if (hasGeometry) {
    lineLatLngs = toLatLngs(route.geometry);
    L.polyline(lineLatLngs, routeStyle(true, true)).addTo(map);
  } else if (points.length > 1) {
    lineLatLngs = points.map((point) => [
      Number(point.latitude),
      Number(point.longitude),
    ]);
    L.polyline(lineLatLngs, routeStyle(true, false)).addTo(map);
  }

  const allLatLngs = [
    ...lineLatLngs,
    ...points.map((point) => [Number(point.latitude), Number(point.longitude)]),
  ];
  if (allLatLngs.length) {
    setTimeout(() => {
      fitToLatLngs(map, allLatLngs, { maxZoom: 15 });
      map.invalidateSize();
    }, 100);
  }
}

async function init() {
  if (!Number.isInteger(routeId) || routeId <= 0) {
    window.location.replace("routes.html");
    return;
  }
  await initProtectedPage();
  map = createMap("routeDetailMap", { zoom: 12 });
  try {
    const route = await api.get(`/routes/${routeId}`);
    renderRoute(route);
  } catch (error) {
    if (error.status === 404) {
      notify.error("La ruta solicitada no existe.");
      setTimeout(() => window.location.replace("routes.html"), 1400);
    } else {
      notify.error(error.message, { title: "Error al cargar la ruta" });
    }
  }
  window.addEventListener("resize", () => map.invalidateSize());
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar el detalle de la ruta.");
  }
});
