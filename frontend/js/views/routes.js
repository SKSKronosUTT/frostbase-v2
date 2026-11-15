import { get, post } from "../api.js";
import {
  $,
  DAYS,
  emptyState,
  error,
  escapeHtml,
  icon,
  info,
  loadingState,
  openModal,
  stateBadge,
  success,
  warning,
} from "../ui.js";

export async function render(view) {
  view.innerHTML = loadingState("Cargando rutas");
  let routes = [];
  let trucks = [];
  let dayFilter = "";

  async function load() {
    view.innerHTML = loadingState("Cargando rutas");
    try {
      [routes, trucks] = await Promise.all([get("/routes"), get("/trucks")]);
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Rutas no disponibles", err.message, "routes", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint() {
    const visible = routes.filter((route) => dayFilter === "" || route.deliverDays.includes(Number(dayFilter)));
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Rutas de entrega</h2><p>Planes semanales, conductores asignados y secuencia de tiendas.</p></div>
        <div class="toolbar">
          <label class="field"><span>Día de entrega</span><select data-day>
            <option value="">Semana completa</option>
            ${DAYS.map((day, index) => `<option value="${index}" ${String(index) === dayFilter ? "selected" : ""}>${day}</option>`).join("")}
          </select></label>
          <button class="btn" data-refresh>${icon("refresh")} Actualizar</button>
        </div>
      </div>
      ${
        visible.length
          ? `<div class="route-grid">${visible
              .map(
                (route) => `<article class="card route-card">
                  <div class="route-top">
                    <div><h3>${escapeHtml(route.name)}</h3><p class="small muted">${escapeHtml(route.driver?.name?.fullName || "Sin conductor asignado")}</p></div>
                    <span class="chip">${route.stores.length} paradas</span>
                  </div>
                  <div class="day-pills">${DAYS.map((day, index) => `<span class="day-pill ${route.deliverDays.includes(index) ? "on" : ""}" title="${day}">${day[0]}</span>`).join("")}</div>
                  <div class="route-stops">
                    ${route.stores
                      .slice(0, 4)
                      .map(
                        (item, index) => `<div class="stop"><span class="stop-no">${item.sequence || index + 1}</span><div><strong>${escapeHtml(item.store?.name || "Tienda")}</strong><div class="faint small">${escapeHtml(item.store?.location?.address || "")}</div></div></div>`,
                      )
                      .join("")}
                    ${route.stores.length > 4 ? `<div class="faint small">+ ${route.stores.length - 4} paradas más</div>` : ""}
                  </div>
                  <div class="pill-row">
                    ${route.driver ? `<span class="badge green">Conductor asignado</span>` : `<span class="badge yellow">Requiere conductor</span>`}
                    ${route.driver?.truckDefault ? `<span class="badge blue">${escapeHtml(route.driver.truckDefault.licensePlate)}</span>` : ""}
                  </div>
                  <div class="row-actions" style="justify-content:flex-start">
                    <button class="btn btn-sm" data-detail="${route.id}">${icon("chevron", 14)} Ver detalles</button>
                    <button class="btn btn-sm btn-primary" data-start="${route.id}">${icon("play", 14)} Iniciar viaje</button>
                  </div>
                </article>`,
              )
              .join("")}</div>`
          : emptyState("Sin rutas para este día", "Elige otro día de entrega o revisa la semana completa.", "routes")
      }
    `;

    $("[data-refresh]").addEventListener("click", load);
    $("[data-day]").addEventListener("change", (event) => {
      dayFilter = event.target.value;
      paint();
    });
    view.querySelectorAll("[data-detail]").forEach((button) =>
      button.addEventListener("click", () => showDetails(routes.find((route) => route.id === button.dataset.detail))),
    );
    view.querySelectorAll("[data-start]").forEach((button) =>
      button.addEventListener("click", () => startTrip(routes.find((route) => route.id === button.dataset.start), button)),
    );
  }

  async function showDetails(route) {
    if (!route) return;
    openModal({
      title: route.name,
      subtitle: `${route.stores.length} paradas · ${route.driver?.name?.fullName || "conductor sin asignar"}`,
      wide: true,
      body: `<div id="route-detail-body">${loadingState("Cargando pedidos de la ruta")}</div>`,
      footer: `<button class="btn" data-close-modal>Cerrar</button><a class="btn btn-primary" href="#/map">${icon("map", 16)} Abrir mapa en vivo</a>`,
      onMount(modal, close) {
        modal.querySelector("[data-close-modal]").addEventListener("click", close);
        modal.querySelector('a[href="#/map"]').addEventListener("click", close);
        loadDetails(route, modal.querySelector("#route-detail-body"));
      },
    });
  }

  async function loadDetails(route, target) {
    try {
      const pending = await get(`/routes/${route.id}/pending`);
      target.innerHTML = `
        <div class="grid split-2" style="gap:14px">
          <div>
            <div class="card-head"><div><h3>Secuencia de paradas</h3><p>Plan de entrega ordenado</p></div><span class="chip">${route.stores.length} paradas</span></div>
            <div class="route-stops" style="max-height:360px">
              ${route.stores
                .map(
                  (item, index) => `<div class="stop"><span class="stop-no">${item.sequence || index + 1}</span><div><strong>${escapeHtml(item.store?.name || "Tienda")}</strong><div class="faint small">${escapeHtml(item.store?.location?.address || "")}</div><div class="faint small">${escapeHtml(item.store?.phone || "Sin teléfono")}</div></div></div>`,
                )
                .join("") || '<p class="muted small">No hay tiendas asignadas.</p>'}
            </div>
          </div>
          <div>
            <div class="card-head"><div><h3>Pedidos pendientes</h3><p>Listos para esta ruta</p></div><span class="badge ${pending.length ? "blue" : "green"}">${pending.length}</span></div>
            ${
              pending.length
                ? `<div class="list">${pending
                    .map(
                      (order) => `<div class="list-item"><div class="list-main"><strong>${escapeHtml(order.store?.name || "Tienda")}</strong><small>${escapeHtml(order.state?.description || "")}</small></div>${stateBadge("order", order.state?.id)}</div>`,
                    )
                    .join("")}</div>`
                : `<div class="note">Todos los pedidos de esta ruta están al día. Inicia un viaje para comenzar el recorrido.</div>`
            }
            <div class="note" style="margin-top:12px"><strong>Conductor:</strong> ${escapeHtml(route.driver?.name?.fullName || "Sin asignar")}<br><strong>Camión:</strong> ${escapeHtml(route.driver?.truckDefault?.licensePlate || "Asignar camión disponible")}</div>
          </div>
        </div>`;
    } catch (err) {
      target.innerHTML = `<div class="note">${escapeHtml(err.message)}</div>`;
    }
  }

  async function startTrip(route, button) {
    if (!route) return;
    if (!route.driver) {
      warning("Sin conductor asignado", "Asigna un conductor a esta ruta antes de iniciar un viaje.");
      return;
    }
    let truck = route.driver.truckDefault;
    if (!truck) {
      truck = trucks.find((item) => item.state?.id === "AV");
    }
    if (!truck) {
      warning("Sin camiones disponibles", "Todos los camiones están en ruta, en mantenimiento o fuera de servicio.");
      return;
    }
    button.disabled = true;
    try {
      await post("/trips/start", {
        truckId: truck.id,
        driverId: route.driver.id,
        routeId: route.id,
      });
      success("Viaje iniciado", `${truck.licensePlate} ya está en la ruta ${route.name}.`);
      info("Siguiente paso", "Sigue el viaje desde el mapa en vivo.");
    } catch (err) {
      error("No se pudo iniciar el viaje", err.message);
    } finally {
      button.disabled = false;
    }
  }

  await load();
}
