import { get, getUser, post, put } from "../api.js";
import {
  $,
  emptyState,
  error,
  escapeHtml,
  formValues,
  icon,
  info,
  loadingState,
  success,
  todayInput,
  warning,
} from "../ui.js";

export async function render(view) {
  view.innerHTML = loadingState("Cargando configuración");
  let parameters;

  async function load() {
    view.innerHTML = loadingState("Cargando configuración");
    try {
      parameters = await get("/parameters");
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Configuración no disponible", err.message, "settings", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint() {
    const user = getUser();
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Configuración</h2><p>Umbrales de cadena de frío, controles del simulador e información de la cuenta.</p></div>
        <span class="chip">Administrador</span>
      </div>
      <div class="settings-grid">
        <article class="card">
          <div class="card-head"><div><h3>Umbrales de cadena de frío</h3><p>Se usan para calcular el cumplimiento y revisar alertas.</p></div><span class="kpi-icon">${icon("shield")}</span></div>
          <form id="parameters-form" class="stack">
            <div class="range-row">
              <label class="field"><span>Temperatura mínima (°C)</span><input name="minTemperature" type="number" step="0.1" required value="${parameters.minTemperature}"></label>
              <label class="field"><span>Temperatura máxima (°C)</span><input name="maxTemperature" type="number" step="0.1" required value="${parameters.maxTemperature}"></label>
            </div>
            <div class="range-row">
              <label class="field"><span>Humedad mínima (%)</span><input name="minHumidity" type="number" min="0" max="100" required value="${parameters.minHumidity}"></label>
              <label class="field"><span>Humedad máxima (%)</span><input name="maxHumidity" type="number" min="0" max="100" required value="${parameters.maxHumidity}"></label>
            </div>
            <div class="note"><strong>Ventana de cumplimiento:</strong> una lectura es conforme cuando la temperatura está entre los valores mínimo y máximo y la humedad se mantiene dentro de su rango.</div>
            <div class="row-actions" style="justify-content:flex-start"><button class="btn btn-primary" type="submit">${icon("check")} Guardar umbrales</button></div>
          </form>
        </article>

        <article class="card">
          <div class="card-head"><div><h3>Simulador demo</h3><p>Crea pedidos, viajes y telemetría realista para un día específico.</p></div><span class="kpi-icon">${icon("sync")}</span></div>
          <div class="stack">
            <label class="field"><span>Fecha objetivo</span><input id="sim-date" type="date" value="${todayInput()}"></label>
            <div class="grid" style="grid-template-columns:1fr 1fr;gap:8px">
              <button class="btn" data-sim="orders">${icon("orders")} Pedidos</button>
              <button class="btn" data-sim="trips">${icon("routes")} Viajes</button>
              <button class="btn" data-sim="check">${icon("clock")} Marcar atrasos</button>
              <button class="btn" data-sim="range">${icon("play")} Simular semana</button>
            </div>
            <div class="note"><strong>Pedidos</strong> completa las tiendas sin pedido para la fecha. <strong>Viajes</strong> genera recorridos para las rutas programadas ese día y registra lecturas. <strong>Simular semana</strong> simula siete días terminando en la fecha objetivo.</div>
            <p id="sim-result" class="small muted"></p>
          </div>
        </article>

        <article class="card">
          <div class="card-head"><div><h3>Cuenta</h3><p>Administrador con sesión iniciada</p></div><span class="avatar">${escapeHtml((user?.name?.firstName?.[0] || "") + (user?.name?.lastName?.[0] || ""))}</span></div>
          <div class="list">
            <div class="list-item"><div class="list-main"><strong>${escapeHtml(user?.name?.fullName || "—")}</strong><small>${escapeHtml(user?.email || "")}</small></div><span class="badge blue">Administrador</span></div>
            <div class="list-item"><div class="list-main"><strong>Teléfono</strong><small>${escapeHtml(user?.phone || "Sin definir")}</small></div></div>
            <div class="list-item"><div class="list-main"><strong>Camión por defecto</strong><small>${escapeHtml(user?.truckDefault?.licensePlate || "Sin asignar")}</small></div></div>
          </div>
        </article>

        <article class="card">
          <div class="card-head"><div><h3>Acerca de Frostbase</h3><p>Plataforma de control de cadena de frío</p></div><span class="kpi-icon">${icon("snow")}</span></div>
          <div class="list">
            <div class="list-item"><div class="list-main"><strong>Versión</strong><small>1.0.0</small></div><span class="chip">FastAPI</span></div>
            <div class="list-item"><div class="list-main"><strong>Base de datos</strong><small>PostgreSQL</small></div><span class="chip">Postgres</span></div>
            <div class="list-item"><div class="list-main"><strong>API base</strong><small>/api</small></div><span class="chip">REST</span></div>
          </div>
          <div class="note" style="margin-top:12px">Frostbase mantiene las entregas refrigeradas conforme con telemetría de temperatura, humedad y puerta en vivo.</div>
        </article>
      </div>
    `;

    $("#parameters-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = event.currentTarget;
      if (!form.reportValidity()) return;
      const values = formValues(form);
      const button = form.querySelector("button[type=submit]");
      button.disabled = true;
      try {
        parameters = await put("/parameters", {
          minTemperature: Number(values.minTemperature),
          maxTemperature: Number(values.maxTemperature),
          minHumidity: Number(values.minHumidity),
          maxHumidity: Number(values.maxHumidity),
        });
        success("Umbrales guardados", "Los cálculos de cumplimiento ahora usan los nuevos rangos.");
        paint();
      } catch (err) {
        error("No se pudieron guardar los umbrales", err.message);
        button.disabled = false;
      }
    });

    view.querySelectorAll("[data-sim]").forEach((button) =>
      button.addEventListener("click", async () => {
        const date = $("#sim-date").value || todayInput();
        const action = button.dataset.sim;
        const result = $("#sim-result");
        button.disabled = true;
        result.textContent = "Ejecutando simulador…";
        try {
          if (action === "orders") {
            const created = await post("/simulator/orders", { date });
            result.textContent = `${created.length} pedidos creados para ${date}.`;
            success("Pedidos simulados", `${created.length} pedidos nuevos agregados para ${date}.`);
          } else if (action === "trips") {
            const created = await post("/simulator/trips", { date });
            result.textContent = `${created.length} viajes generados para ${date}.`;
            success("Viajes simulados", `${created.length} recorridos de entrega generados.`);
          } else if (action === "check") {
            const late = await post("/simulator/check");
            result.textContent = `${late.length} pedidos marcados como atrasados.`;
            success("Atrasos revisados", `${late.length} pedidos pasaron a la cola de atrasados.`);
          } else {
            const start = new Date(`${date}T00:00:00`);
            start.setDate(start.getDate() - 6);
            const startDate = start.toISOString().slice(0, 10);
            const summary = await post(`/simulator/generate/${startDate}/${date}`);
            const errors = summary.filter((row) => row.error).length;
            result.textContent = `${summary.length} días simulados${errors ? ` · ${errors} días omitidos` : ""}.`;
            if (errors) warning("Semana simulada con omisiones", `${summary.length - errors} días generados, ${errors} omitidos.`);
            else success("Semana simulada", `Actividad generada del ${startDate} al ${date}.`);
          }
          info("Actualiza las vistas", "Abre monitoreo o el mapa para ver la nueva actividad.");
        } catch (err) {
          result.textContent = "";
          error("El simulador falló", err.message);
        } finally {
          button.disabled = false;
        }
      }),
    );
  }

  await load();
}
