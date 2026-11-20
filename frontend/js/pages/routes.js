import { api } from "../core/api.js";
import { initProtectedPage } from "../core/app.js";
import { confirmDialog, notify } from "../core/notifications.js";
import { debounce, escapeHtml, qs, setButtonLoading } from "../core/helpers.js";
import {
  DEFAULT_CENTER,
  createMap,
  fitToLatLngs,
  numberedIcon,
  routeStyle,
  toLatLngs,
} from "../components/map.js";

const state = {
  routes: [],
  trucks: [],
  search: "",
  mode: "empty",
  routeId: null,
  points: [],
  geometry: null,
  geometryStale: false,
  warning: null,
  routeTruck: null,
  map: null,
  pointMarkers: [],
  line: null,
  fitPending: false,
  uid: 0,
};

const pointsList = qs("#pointsList");

function nextUid() {
  state.uid += 1;
  return `p${state.uid}`;
}

function routeName() {
  const names = state.points.map((point) => point.name.trim()).filter(Boolean);
  if (!state.points.length) return "Nueva ruta";
  if (state.points.length === 1) return names[0] || "Nueva ruta";
  const first = state.points[0].name.trim() || "Punto 1";
  const last =
    state.points[state.points.length - 1].name.trim() || `Punto ${state.points.length}`;
  return `${first} - ${last}`;
}

function syncRouteInList(route) {
  const index = state.routes.findIndex((item) => item.id === route.id);
  if (index >= 0) state.routes[index] = route;
  else state.routes.unshift(route);
  renderRoutesList();
}

function markPointsChanged() {
  state.geometry = null;
  state.geometryStale = true;
  state.warning = null;
  renderWarning();
  updateHeader();
  updateLine();
}

function renderWarning() {
  const element = qs("#routeWarning");
  let message = state.warning;
  if (!message && state.geometryStale) {
    message =
      "Los puntos cambiaron y la geometría anterior ya no corresponde. Guarda la ruta para recalcularla.";
  }
  if (!message && state.points.length >= 2 && !state.geometry) {
    message =
      "Esta ruta no tiene geometría calculada. Guarda o usa «Recalcular ruta» cuando OSRM esté disponible.";
  }
  if (message) {
    qs("#routeWarningText").textContent = message;
    element.classList.add("is-visible");
  } else {
    element.classList.remove("is-visible");
  }
}

function updateHeader() {
  if (state.mode === "empty") return;
  qs("#routeEditorTitle").textContent =
    state.mode === "new" ? "Nueva ruta" : routeName();
  const geometryLabel =
    state.geometry && !state.geometryStale
      ? "Geometría calculada"
      : "Sin geometría calculada";
  const truckLabel = state.routeTruck
    ? ` · Asignada a ${state.routeTruck.plate}`
    : " · Sin camión asignado";
  qs("#routeEditorMeta").textContent = `${state.points.length} punto${
    state.points.length === 1 ? "" : "s"
  } · ${geometryLabel}${truckLabel}`;
  qs("#routePointsCount").textContent = `(${state.points.length})`;
  qs("#deleteRouteButton").classList.toggle("hidden", state.mode === "new");
  qs("#calculateRouteButton").classList.toggle("hidden", state.mode === "new");
  qs("#routeAssign").classList.toggle("hidden", state.mode === "new");
}

function updateAssignOptions() {
  const select = qs("#assignTruckSelect");
  const currentValue = state.routeTruck ? String(state.routeTruck.id) : "";
  select.innerHTML =
    '<option value="">Sin camión asignado</option>' +
    state.trucks
      .map(
        (truck) =>
          `<option value="${truck.id}">${escapeHtml(truck.plate)} · ${escapeHtml(
            truck.brand
          )} ${escapeHtml(truck.model)}</option>`
      )
      .join("");
  select.value = currentValue;
}

function renderPoints() {
  if (!state.points.length) {
    pointsList.innerHTML =
      '<div class="points-empty">Agrega al menos dos puntos para calcular la ruta.</div>';
    return;
  }
  pointsList.innerHTML = state.points
    .map(
      (point, index) => `
      <div class="point-row" data-uid="${point.uid}">
        <span class="point-row__order">${index + 1}</span>
        <div>
          <div class="point-row__fields">
            <input class="input" type="text" maxlength="255" data-point-field="name"
              value="${escapeHtml(point.name)}" placeholder="Nombre del punto" aria-label="Nombre del punto ${index + 1}" />
            <input class="input" type="text" maxlength="500" data-point-field="address"
              value="${escapeHtml(point.address || "")}" placeholder="Dirección o descripción" aria-label="Dirección del punto ${index + 1}" />
          </div>
          <div class="point-row__coords" data-coords-for="${point.uid}">
            ${Number(point.latitude).toFixed(5)}, ${Number(point.longitude).toFixed(5)}
          </div>
        </div>
        <div class="point-row__actions">
          <button class="icon-button" type="button" data-point-action="up" data-uid="${point.uid}"
            ${index === 0 ? "disabled" : ""} title="Subir" aria-label="Subir punto"><i class="fa-solid fa-arrow-up"></i></button>
          <button class="icon-button" type="button" data-point-action="down" data-uid="${point.uid}"
            ${index === state.points.length - 1 ? "disabled" : ""} title="Bajar" aria-label="Bajar punto"><i class="fa-solid fa-arrow-down"></i></button>
          <button class="icon-button icon-button--danger" type="button" data-point-action="delete" data-uid="${point.uid}"
            title="Eliminar" aria-label="Eliminar punto"><i class="fa-solid fa-trash"></i></button>
        </div>
      </div>
    `
    )
    .join("");
}

function updateLine() {
  if (!state.map) return;
  if (state.line) {
    state.line.remove();
    state.line = null;
  }
  const hasGeometry =
    Array.isArray(state.geometry) && state.geometry.length > 1 && !state.geometryStale;
  let latLngs = [];
  if (hasGeometry) {
    latLngs = toLatLngs(state.geometry);
  } else if (state.points.length > 1) {
    latLngs = state.points.map((point) => [point.latitude, point.longitude]);
  }
  if (latLngs.length > 1) {
    state.line = L.polyline(latLngs, routeStyle(true, hasGeometry)).addTo(state.map);
  }
}

function rebuildMarkers() {
  state.pointMarkers.forEach(({ marker }) => marker.remove());
  state.pointMarkers = [];
  if (!state.map) return;
  state.points.forEach((point, index) => {
    const marker = L.marker([point.latitude, point.longitude], {
      icon: numberedIcon(index + 1, false),
      draggable: true,
      title: point.name,
    }).addTo(state.map);
    marker.bindTooltip(point.name || `Punto ${index + 1}`, { direction: "top" });
    marker.on("dragend", () => {
      const position = marker.getLatLng();
      point.latitude = position.lat;
      point.longitude = position.lng;
      const coords = pointsList.querySelector(`[data-coords-for="${point.uid}"]`);
      if (coords) {
        coords.textContent = `${point.latitude.toFixed(5)}, ${point.longitude.toFixed(5)}`;
      }
      markPointsChanged();
    });
    state.pointMarkers.push({ marker, uid: point.uid });
  });
}

function renderMap({ fit = false } = {}) {
  if (!state.map) return;
  rebuildMarkers();
  updateLine();
  if (fit || state.fitPending) {
    state.fitPending = false;
    const latLngs = state.points.map((point) => [point.latitude, point.longitude]);
    if (Array.isArray(state.geometry) && !state.geometryStale) {
      latLngs.push(...toLatLngs(state.geometry));
    }
    if (latLngs.length) {
      setTimeout(() => {
        fitToLatLngs(state.map, latLngs, { maxZoom: 15 });
        state.map.invalidateSize();
      }, 80);
    }
  }
}

function showEditor() {
  qs("#routeEditor").hidden = false;
  qs("#routesLayout").classList.add("is-editing");
  setTimeout(() => {
    if (state.map) state.map.invalidateSize();
  }, 60);
}

function showEmptyEditor() {
  qs("#routeEditor").hidden = true;
  qs("#routesLayout").classList.remove("is-editing");
  state.mode = "empty";
  state.routeId = null;
  state.points = [];
  state.geometry = null;
  state.routeTruck = null;
  state.pointMarkers.forEach(({ marker }) => marker.remove());
  state.pointMarkers = [];
  updateLine();
  if (state.map) state.line = null;
  renderRoutesList();
  history.replaceState({}, "", "routes.html");
}

function renderRoutesList() {
  const search = state.search.toLowerCase();
  const filtered = state.routes.filter((route) =>
    route.name.toLowerCase().includes(search)
  );
  qs("#routesCount").textContent = `${state.routes.length}`;
  if (!filtered.length) {
    qs("#routesList").innerHTML = `
      <div class="empty-state" style="padding: 30px 18px;">
        <div class="empty-state__icon"><i class="fa-solid fa-route"></i></div>
        <strong>${state.routes.length ? "Sin coincidencias" : "Sin rutas registradas"}</strong>
        <p>${state.routes.length ? "Prueba con otro nombre de ruta." : "Crea una ruta para comenzar a planificar entregas."}</p>
      </div>
    `;
    return;
  }

  qs("#routesList").innerHTML = filtered
    .map((route) => {
      const status =
        route.status === "activa"
          ? '<span class="badge badge--success">Activa</span>'
          : '<span class="badge badge--muted">Inactiva</span>';
      return `
        <button class="route-list-item ${
          route.id === state.routeId ? "is-active" : ""
        }" type="button" data-route-id="${route.id}">
          <div class="route-list-item__top">
            <span class="route-list-item__name">${escapeHtml(route.name)}</span>
            ${status}
          </div>
          <div class="route-list-item__meta">
            <span><i class="fa-solid fa-location-dot"></i>${route.points.length} puntos</span>
            ${
              route.truck
                ? `<span><i class="fa-solid fa-truck"></i>${escapeHtml(route.truck.plate)}</span>`
                : '<span><i class="fa-solid fa-truck"></i>Sin asignar</span>'
            }
          </div>
        </button>
      `;
    })
    .join("");
}

function applyRoute(route, { fit = true } = {}) {
  state.mode = "edit";
  state.routeId = route.id;
  state.points = route.points
    .slice()
    .sort((a, b) => a.order_index - b.order_index)
    .map((point) => ({
      uid: nextUid(),
      id: point.id,
      name: point.name,
      address: point.address || "",
      latitude: Number(point.latitude),
      longitude: Number(point.longitude),
    }));
  state.geometry = route.geometry;
  state.geometryStale = false;
  state.warning = route.warning || null;
  state.routeTruck = route.truck || null;
  qs("#routeStatus").value = route.status;
  qs("#routeDescription").value = route.description || "";
  updateAssignOptions();
  renderPoints();
  showEditor();
  updateHeader();
  renderWarning();
  renderMap({ fit });
  history.replaceState({}, "", `routes.html?id=${route.id}`);
}

function startNewRoute() {
  state.mode = "new";
  state.routeId = null;
  state.points = [];
  state.geometry = null;
  state.geometryStale = false;
  state.warning = null;
  state.routeTruck = null;
  qs("#routeStatus").value = "activa";
  qs("#routeDescription").value = "";
  updateAssignOptions();
  renderPoints();
  showEditor();
  updateHeader();
  renderWarning();
  if (state.map) {
    state.map.setView(DEFAULT_CENTER, 12);
    setTimeout(() => state.map.invalidateSize(), 60);
  }
  renderMap({ fit: false });
  history.replaceState({}, "", "routes.html");
  renderRoutesList();
}

function addPoint(latitude, longitude, { fit = false } = {}) {
  if (state.mode === "empty") return;
  if (state.points.length >= 50) {
    notify.warning("Una ruta puede tener como máximo 50 puntos.");
    return;
  }
  state.points.push({
    uid: nextUid(),
    name: `Punto ${state.points.length + 1}`,
    address: "",
    latitude,
    longitude,
  });
  markPointsChanged();
  renderPoints();
  renderMap({ fit });
}

function handlePointAction(action, uid) {
  const index = state.points.findIndex((point) => point.uid === uid);
  if (index === -1) return;

  if (action === "delete") {
    state.points.splice(index, 1);
    markPointsChanged();
    renderPoints();
    renderMap();
    return;
  }

  const target = action === "up" ? index - 1 : index + 1;
  if (target < 0 || target >= state.points.length) return;
  const [point] = state.points.splice(index, 1);
  state.points.splice(target, 0, point);
  markPointsChanged();
  renderPoints();
  renderMap();
}

function buildPayload() {
  if (state.points.length < 2) {
    notify.warning("Agrega al menos dos puntos de entrega.");
    return null;
  }
  const namesMissing = state.points.some((point) => !point.name.trim());
  if (namesMissing) {
    notify.warning("Todos los puntos deben tener un nombre.");
    return null;
  }
  const coordinates = new Set(
    state.points.map((point) => `${point.latitude},${point.longitude}`)
  );
  if (coordinates.size < 2) {
    notify.warning("Los puntos deben tener coordenadas distintas.");
    return null;
  }
  return {
    description: qs("#routeDescription").value.trim() || null,
    status: qs("#routeStatus").value,
    points: state.points.map((point, index) => ({
      name: point.name.trim(),
      address: point.address.trim() || null,
      latitude: point.latitude,
      longitude: point.longitude,
      order_index: index,
    })),
  };
}

async function saveRoute() {
  const payload = buildPayload();
  if (!payload) return;
  const button = qs("#saveRouteButton");
  setButtonLoading(button, true, "Guardando…");
  try {
    const route =
      state.mode === "new"
        ? await api.post("/routes", payload)
        : await api.put(`/routes/${state.routeId}`, payload);
    await loadRoutes();
    applyRoute(route);
    syncRouteInList(route);
    if (route.warning) {
      notify.warning(route.warning, { title: "Ruta guardada sin geometría" });
    } else {
      notify.success("Ruta guardada y geometría calculada correctamente.");
    }
  } catch (error) {
    notify.error(error.message, { title: "No se pudo guardar la ruta" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function calculateRoute() {
  if (state.mode !== "edit" || !state.routeId) return;
  if (state.geometryStale) {
    notify.warning("Guarda los cambios de los puntos antes de recalcular la ruta.");
    return;
  }
  const button = qs("#calculateRouteButton");
  setButtonLoading(button, true, "Calculando…");
  try {
    const route = await api.post(`/routes/${state.routeId}/calculate`, {});
    state.geometry = route.geometry;
    state.warning = null;
    state.geometryStale = false;
    state.routeTruck = route.truck || null;
    syncRouteInList(route);
    updateHeader();
    renderWarning();
    renderMap({ fit: true });
    notify.success("Geometría de la ruta recalculada con OSRM.");
  } catch (error) {
    notify.error(error.message, { title: "No se pudo calcular la ruta" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function assignRoute() {
  if (state.mode !== "edit" || !state.routeId) return;
  const value = qs("#assignTruckSelect").value;
  const targetTruckId = value ? Number(value) : null;

  if (!targetTruckId && !state.routeTruck) {
    notify.info("La ruta ya no tiene un camión asignado.");
    return;
  }
  if (targetTruckId && state.routeTruck && state.routeTruck.id === targetTruckId) {
    notify.info("La ruta ya está asignada a ese camión.");
    return;
  }
  if (targetTruckId && state.routeTruck) {
    const accepted = await confirmDialog({
      title: "Reasignar ruta",
      message: `La ruta está asignada al camión ${state.routeTruck.plate}. Si continúas, ese camión quedará sin ruta.`,
      confirmText: "Reasignar",
      danger: false,
    });
    if (!accepted) return;
  }

  const button = qs("#assignRouteButton");
  setButtonLoading(button, true, "Aplicando…");
  try {
    if (!targetTruckId) {
      await api.put(`/trucks/${state.routeTruck.id}`, { route_id: null });
      const route = await api.get(`/routes/${state.routeId}`);
      state.routeTruck = null;
      syncRouteInList(route);
      updateHeader();
      updateAssignOptions();
      notify.success("Ruta desasignada del camión.");
    } else {
      const route = await api.post(`/routes/${state.routeId}/assign`, {
        truck_id: targetTruckId,
      });
      state.routeTruck = route.truck || null;
      syncRouteInList(route);
      updateHeader();
      updateAssignOptions();
      notify.success("Ruta asignada al camión correctamente.");
    }
  } catch (error) {
    notify.error(error.message, { title: "No se pudo aplicar la asignación" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteRoute() {
  if (state.mode !== "edit" || !state.routeId) return;
  const route = state.routes.find((item) => item.id === state.routeId);
  const accepted = await confirmDialog({
    title: "Eliminar ruta",
    message: `Se eliminará la ruta «${route?.name || routeName()}». Si está asignada a un camión, quedará sin ruta. Esta acción no se puede deshacer.`,
    confirmText: "Eliminar ruta",
    danger: true,
  });
  if (!accepted) return;
  try {
    await api.delete(`/routes/${state.routeId}`);
    notify.success("Ruta eliminada correctamente.");
    showEmptyEditor();
    await loadRoutes();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo eliminar la ruta" });
  }
}

async function loadRoutes() {
  try {
    const data = await api.get("/routes?page=1&page_size=100");
    state.routes = data.items;
    renderRoutesList();
  } catch (error) {
    qs("#routesList").innerHTML = `<div class="empty-state" style="padding: 30px 18px;">
      <div class="empty-state__icon"><i class="fa-solid fa-triangle-exclamation"></i></div>
      <strong>No se pudieron cargar las rutas</strong>
      <p>${escapeHtml(error.message)}</p>
    </div>`;
    notify.error(error.message, { title: "Error al cargar rutas" });
  }
}

async function loadTrucks() {
  try {
    const data = await api.get("/trucks?page=1&page_size=100");
    state.trucks = data.items;
    updateAssignOptions();
  } catch (error) {
    notify.error(error.message, { title: "No se pudieron cargar los camiones" });
  }
}

function wireEvents() {
  qs("#newRouteButton").addEventListener("click", startNewRoute);
  qs("#saveRouteButton").addEventListener("click", saveRoute);
  qs("#calculateRouteButton").addEventListener("click", calculateRoute);
  qs("#deleteRouteButton").addEventListener("click", deleteRoute);
  qs("#assignRouteButton").addEventListener("click", assignRoute);

  qs("#addPointButton").addEventListener("click", () => {
    if (!state.map) return;
    const center = state.map.getCenter();
    addPoint(center.lat, center.lng);
  });

  qs("#routeSearch").addEventListener(
    "input",
    debounce((event) => {
      state.search = event.target.value.trim();
      renderRoutesList();
    }, 180)
  );

  qs("#routesList").addEventListener("click", (event) => {
    const item = event.target.closest("[data-route-id]");
    if (!item) return;
    const route = state.routes.find(
      (entry) => entry.id === Number(item.dataset.routeId)
    );
    if (route) applyRoute(route);
  });

  pointsList.addEventListener("input", (event) => {
    const field = event.target.dataset.pointField;
    if (!field) return;
    const row = event.target.closest("[data-uid]");
    const point = state.points.find((entry) => entry.uid === row?.dataset.uid);
    if (!point) return;
    point[field] = event.target.value;
    if (field === "name") {
      updateHeader();
      const markerRecord = state.pointMarkers.find((entry) => entry.uid === point.uid);
      if (markerRecord) {
        markerRecord.marker.setTooltipContent(point.name || "Punto");
      }
    }
  });

  pointsList.addEventListener("click", (event) => {
    const button = event.target.closest("[data-point-action]");
    if (!button || button.disabled) return;
    handlePointAction(button.dataset.pointAction, button.dataset.uid);
  });

  state.map.on("click", (event) => {
    if (state.mode === "empty") return;
    addPoint(event.latlng.lat, event.latlng.lng);
  });

  window.addEventListener("resize", () => {
    if (state.map) setTimeout(() => state.map.invalidateSize(), 120);
  });
}

async function init() {
  await initProtectedPage();
  state.map = createMap("routeMap", { zoom: 12 });
  wireEvents();
  await Promise.all([loadRoutes(), loadTrucks()]);
  const id = Number(new URLSearchParams(window.location.search).get("id"));
  if (id) {
    let route = state.routes.find((item) => item.id === id);
    if (!route) {
      try {
        route = await api.get(`/routes/${id}`);
      } catch (error) {
        notify.error("La ruta solicitada no existe.", { title: "Ruta no encontrada" });
      }
    }
    if (route) applyRoute(route);
  }
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar la gestión de rutas.");
  }
});
