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
import { renderPagination } from "../components/pagination.js";
import { listSkeleton, panelState, renderTableState } from "../components/feedback.js";

const state = {
  routes: [],
  trucks: [],
  driverOptions: [],
  search: "",
  driverFilter: "",
  page: 1,
  pageSize: 12,
  total: 0,
  mode: "empty",
  routeId: null,
  points: [],
  geometry: null,
  geometryStale: false,
  warning: null,
  routeTruck: null,
  routeDriver: null,
  routeDays: [],
  map: null,
  pointMarkers: [],
  line: null,
  fitPending: false,
  uid: 0,
};

const WEEKDAY_INITIALS = ["D", "L", "M", "X", "J", "V", "S"];

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
  const driverLabel = state.routeDriver
    ? ` · Conductor: ${state.routeDriver.full_name}`
    : " · Sin conductor";
  const daysLabel = state.routeDays.length
    ? ` (${state.routeDays.map((day) => WEEKDAY_INITIALS[day]).join("")})`
    : "";
  const truckLabel = state.routeTruck
    ? ` · Camión del conductor: ${state.routeTruck.plate}`
    : "";
  qs("#routeEditorMeta").textContent = `${state.points.length} punto${
    state.points.length === 1 ? "" : "s"
  } · ${geometryLabel}${driverLabel}${daysLabel}${truckLabel}`;
  qs("#routePointsCount").textContent = `(${state.points.length})`;
  qs("#deleteRouteButton").classList.toggle("hidden", state.mode === "new");
  qs("#calculateRouteButton").classList.toggle("hidden", state.mode === "new");
  qs("#routeTruckInfo").classList.toggle("hidden", state.mode === "new");
  qs("#routeDriverAssign").classList.toggle("hidden", state.mode === "new");
}

function renderTruckInfo() {
  const status = qs("#routeTruckStatus");
  const text = qs("#routeTruckText");
  const button = qs("#changeTruckButton");

  if (state.routeTruck) {
    status.className = "route-truck-status route-truck-status--ok";
    text.textContent = `Camión del conductor: ${state.routeTruck.plate}`;
    button.hidden = true;
  } else if (state.routeDriver) {
    status.className = "route-truck-status route-truck-status--warn";
    text.textContent = "El conductor aún no tiene camión asignado.";
    button.hidden = false;
    button.textContent = "";
    button.insertAdjacentHTML(
      "afterbegin",
      '<i class="fa-solid fa-truck"></i> Asignar camión al conductor'
    );
  } else {
    status.className = "route-truck-status";
    text.textContent = "Sin conductor: la ruta mostrará su camión cuando tenga dueño.";
    button.hidden = true;
  }
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

function updateMapSummary() {
  const summary = qs("#routeMapSummary");
  if (!summary) return;
  const count = state.points.length;
  summary.textContent = count
    ? `Mapa de la ruta con ${count} punto${count === 1 ? "" : "s"} de entrega.`
    : "Mapa de la ruta sin puntos de entrega.";
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
  updateMapSummary();
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
  state.routeDriver = null;
  state.routeDays = [];
  state.pointMarkers.forEach(({ marker }) => marker.remove());
  state.pointMarkers = [];
  updateLine();
  if (state.map) state.line = null;
  updateMapSummary();
  renderRoutesList();
  history.replaceState({}, "", "routes.html");
}

function renderRoutesList() {
  qs("#routesCount").textContent = state.total
    ? `${state.routes.length} de ${state.total}`
    : "0";
  if (!state.routes.length) {
    const empty = panelState(
      {
        icon: "fa-route",
        title: state.search ? "Sin coincidencias" : "Sin rutas registradas",
        description: state.search
          ? "Prueba con otro nombre de ruta."
          : "Crea una ruta para comenzar a planificar entregas.",
      },
      { retryLabel: "" }
    );
    renderTableState(qs("#routesList"), empty);
    renderPagination(qs("#routesPagination"), {
      page: state.page,
      total: state.total,
      pageSize: state.pageSize,
      itemLabel: "rutas",
      onChange: (page) => {
        state.page = page;
        loadRoutes();
      },
    });
    return;
  }

  qs("#routesList").innerHTML = state.routes
    .map((route) => {
      const status =
        route.status === "activa"
          ? '<span class="badge badge--success">Activa</span>'
          : '<span class="badge badge--muted">Inactiva</span>';
      const driver = route.assigned_driver
        ? `<span><i class="fa-solid fa-user-shield"></i>${escapeHtml(
            route.assigned_driver.full_name
          )}${
            route.delivery_days.length
              ? ` · ${route.delivery_days.map((day) => WEEKDAY_INITIALS[day]).join("")}`
              : ""
          }</span>`
        : '<span><i class="fa-solid fa-user-shield"></i>Sin conductor</span>';
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
            ${driver}
            ${
              route.truck
                ? `<span><i class="fa-solid fa-truck"></i>${escapeHtml(
                    route.truck.plate
                  )} (legado)</span>`
                : ""
            }
          </div>
        </button>
      `;
    })
    .join("");

  renderPagination(qs("#routesPagination"), {
    page: state.page,
    total: state.total,
    pageSize: state.pageSize,
    itemLabel: "rutas",
    onChange: (page) => {
      state.page = page;
      loadRoutes();
    },
  });
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
  state.routeDriver = route.assigned_driver || null;
  state.routeDays = route.delivery_days || [];
  qs("#routeStatus").value = route.status;
  qs("#routeDescription").value = route.description || "";
  updateDriverAssignForm();
  renderTruckInfo();
  renderPoints();
  showEditor();
  updateHeader();
  renderWarning();
  renderMap({ fit });
  // La marca «activa» de la lista debe seguir a la ruta abierta.
  renderRoutesList();
  history.replaceState({}, "", `routes.html?id=${route.id}`);
}

function updateDriverAssignForm() {
  const select = qs("#assignDriverSelect");
  const current = state.routeDriver ? String(state.routeDriver.id) : "";
  const options =
    '<option value="">Sin conductor asignado</option>' +
    state.driverOptions
      .map(
        (driver) =>
          `<option value="${driver.id}" ${
            String(driver.id) === current ? "selected" : ""
          }>${escapeHtml(driver.label)}</option>`
      )
      .join("");
  select.innerHTML = options;
  select.value = current;

  document.querySelectorAll("[data-weekday]").forEach((checkbox) => {
    checkbox.checked = state.routeDays.includes(Number(checkbox.dataset.weekday));
  });
}

function startNewRoute() {
  state.mode = "new";
  state.routeId = null;
  state.points = [];
  state.geometry = null;
  state.geometryStale = false;
  state.warning = null;
  state.routeTruck = null;
  state.routeDriver = null;
  state.routeDays = [];
  qs("#routeStatus").value = "activa";
  qs("#routeDescription").value = "";
  renderTruckInfo();
  updateDriverAssignForm();
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
    if (state.mode === "new") {
      state.page = 1;
      state.search = "";
      const searchInput = qs("#routeSearch");
      if (searchInput) searchInput.value = "";
    }
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

async function goToDriverEdit() {
  if (!state.routeDriver) return;
  window.location.href = `drivers.html?edit=${state.routeDriver.id}`;
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
    listSkeleton(qs("#routesList"), 4, 2);
    const params = new URLSearchParams({
      page: state.page,
      page_size: state.pageSize,
    });
    if (state.search) params.set("search", state.search);
    if (state.driverFilter === "pending") params.set("missing_driver", "true");
    if (state.driverFilter === "assigned") params.set("missing_driver", "false");
    const data = await api.get(`/routes?${params.toString()}`);
    state.total = data.total;
    state.routes = data.items;
    const totalPages = Math.max(1, Math.ceil(data.total / state.pageSize));
    if (state.page > totalPages) {
      state.page = totalPages;
      return loadRoutes();
    }
    renderRoutesList();
  } catch (error) {
    renderTableState(
      qs("#routesList"),
      panelState({
        icon: "fa-triangle-exclamation",
        title: "No se pudieron cargar las rutas",
        description: error.message,
      }),
      { onRetry: loadRoutes }
    );
    notify.error(error.message, { title: "Error al cargar rutas" });
  }
}

async function loadDriverOptions() {
  try {
    state.driverOptions = await api.get("/drivers/options");
    updateDriverAssignForm();
  } catch (error) {
    notify.error(error.message, { title: "No se pudieron cargar los conductores" });
  }
}

async function loadLegacyMismatch() {
  const panel = qs("#legacyMismatchPanel");
  try {
    const rows = await api.get("/routes/legacy-mismatch");
    if (!rows.length) {
      panel.classList.add("hidden");
      return;
    }
    panel.classList.remove("hidden");
    qs("#legacyMismatchCount").textContent = `${rows.length} pendiente${
      rows.length === 1 ? "" : "s"
    }`;
    qs("#legacyMismatchList").innerHTML = rows
      .map((row) => {
        const owner = row.owner ? escapeHtml(row.owner.full_name) : "Sin conductor";
        const legacy = row.legacy_truck ? escapeHtml(row.legacy_truck.plate) : "—";
        const effective = row.effective_truck
          ? escapeHtml(row.effective_truck.plate)
          : "sin camión";
        const convert =
          row.convertible && row.target_driver_id
            ? `<button class="btn btn--ghost btn--sm" type="button" data-convert-driver="${row.target_driver_id}" data-convert-truck="${row.legacy_truck.id}" data-convert-route="${row.route_name}">${escapeHtml(
                row.legacy_truck.plate
              )} → asignar a ${owner}</button>`
            : "";
        return `
          <div class="legacy-mismatch__row">
            <div class="legacy-mismatch__route">
              <strong>${escapeHtml(row.route_name)}</strong>
              <span class="muted">Legado: ${legacy} · Derivado: ${effective} · ${owner}</span>
            </div>
            <p class="legacy-mismatch__hint">${escapeHtml(row.suggestion)}</p>
            ${convert}
          </div>
        `;
      })
      .join("");
    panel.querySelectorAll("[data-convert-driver]").forEach((button) => {
      button.addEventListener("click", () =>
        convertLegacyLink(
          Number(button.dataset.convertDriver),
          Number(button.dataset.convertTruck),
          button.dataset.convertRoute
        )
      );
    });
  } catch (error) {
    /* El reporte es informativo; si falla no bloquea la página. */
    console.warn("No se pudo cargar el reporte de conciliación", error);
  }
}

async function convertLegacyLink(driverId, truckId, routeName) {
  const accepted = await confirmDialog({
    title: "Convertir vínculo legado",
    message: `El camión de «${routeName}» pasará a ser el camión del conductor. Si el conductor ya tenía otro camión, quedará libre.`,
    confirmText: "Convertir",
    danger: false,
  });
  if (!accepted) return;
  try {
    await api.put(`/drivers/${driverId}/truck`, { truck_id: truckId });
    notify.success("Vínculo convertido en asignación del conductor.");
    await loadLegacyMismatch();
    await loadRoutes();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo convertir el vínculo" });
  }
}

async function assignRouteDriver() {
  if (state.mode !== "edit" || !state.routeId) return;
  const driverId = qs("#assignDriverSelect").value;
  const weekdays = Array.from(document.querySelectorAll("[data-weekday]"))
    .filter((checkbox) => checkbox.checked)
    .map((checkbox) => Number(checkbox.dataset.weekday));

  if (!driverId) {
    notify.warning("Selecciona un conductor. Para quitarlo usa «Quitar conductor».");
    return;
  }

  const button = qs("#assignDriverButton");
  setButtonLoading(button, true, "Guardando…");
  try {
    const route = await api.put(`/routes/${state.routeId}/driver`, {
      driver_id: Number(driverId),
      weekdays,
    });
    state.routeDriver = route.assigned_driver;
    state.routeDays = route.delivery_days;
    syncRouteInList(route);
    updateHeader();
    updateDriverAssignForm();
    notify.success("Conductor y calendario guardados correctamente.");
  } catch (error) {
    notify.error(error.message, { title: "No se pudo asignar el conductor" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function removeRouteDriver() {
  if (state.mode !== "edit" || !state.routeId) return;
  if (!state.routeDriver) {
    notify.info("Esta ruta no tiene conductor asignado.");
    return;
  }
  const accepted = await confirmDialog({
    title: "Quitar conductor",
    message: `La ruta quedará sin conductor y sin días de entrega. ${
      state.routeTruck ? "El vínculo legado con el camión se conserva." : ""
    }`,
    confirmText: "Quitar conductor",
    danger: true,
  });
  if (!accepted) return;

  try {
    const route = await api.put(`/routes/${state.routeId}/driver`, {
      driver_id: null,
      weekdays: [],
    });
    state.routeDriver = route.assigned_driver;
    state.routeDays = route.delivery_days;
    syncRouteInList(route);
    updateHeader();
    updateDriverAssignForm();
    notify.success("Conductor retirado de la ruta.");
  } catch (error) {
    notify.error(error.message, { title: "No se pudo quitar el conductor" });
  }
}

function wireEvents() {
  qs("#newRouteButton").addEventListener("click", startNewRoute);
  qs("#saveRouteButton").addEventListener("click", saveRoute);
  qs("#calculateRouteButton").addEventListener("click", calculateRoute);
  qs("#deleteRouteButton").addEventListener("click", deleteRoute);
  qs("#changeTruckButton").addEventListener("click", goToDriverEdit);
  qs("#assignDriverButton").addEventListener("click", assignRouteDriver);
  qs("#removeDriverButton").addEventListener("click", removeRouteDriver);

  qs("#addPointButton").addEventListener("click", () => {
    if (!state.map) return;
    const center = state.map.getCenter();
    addPoint(center.lat, center.lng);
  });

  qs("#routeSearch").addEventListener(
    "input",
    debounce((event) => {
      state.search = event.target.value.trim();
      state.page = 1;
      loadRoutes();
    }, 280)
  );

  qs("#routeDriverFilter").addEventListener("change", (event) => {
    state.driverFilter = event.target.value;
    state.page = 1;
    loadRoutes();
  });

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
  await Promise.all([loadRoutes(), loadDriverOptions(), loadLegacyMismatch()]);
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
