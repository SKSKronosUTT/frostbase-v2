import { del, get, post, put } from "../api.js";
import {
  $,
  confirmDialog,
  emptyState,
  error,
  escapeHtml,
  formValues,
  icon,
  loadingState,
  openModal,
  relative,
  stateBadge,
  success,
} from "../ui.js";

export async function render(view) {
  view.innerHTML = loadingState("Cargando flotilla");
  let trucks = [];
  let states = [];
  let readings = new Map();
  let stateFilter = "";

  async function load() {
    view.innerHTML = loadingState("Cargando flotilla");
    try {
      const [truckData, stateData, readingData] = await Promise.all([
        get("/trucks"),
        get("/trucks/states"),
        get("/readings/latest").catch(() => []),
      ]);
      trucks = truckData;
      states = stateData;
      readings = new Map((readingData || []).map((row) => [row.truck?.id, row.reading]));
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Flotilla no disponible", err.message, "trucks", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint() {
    const visible = trucks.filter((truck) => !stateFilter || truck.state?.id === stateFilter);
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Flotilla</h2><p>${trucks.length} camiones refrigerados en toda la cadena de frío.</p></div>
        <div class="toolbar">
          <label class="field"><span>Estado</span><select data-filter>
            <option value="">Todos los estados</option>
            ${states.map((state) => `<option value="${state.id}" ${stateFilter === state.id ? "selected" : ""}>${escapeHtml(state.description)}</option>`).join("")}
          </select></label>
          <button class="btn" data-refresh>${icon("refresh")} Actualizar</button>
          <button class="btn btn-primary" data-new>${icon("plus")} Agregar camión</button>
        </div>
      </div>
      ${
        visible.length
          ? `<div class="truck-grid">${visible
              .map((truck) => {
                const reading = readings.get(truck.id);
                return `<article class="card truck-card">
                  <div class="truck-visual">${icon("trucks", 44)}</div>
                  <div class="route-top">
                    <div><h3>${escapeHtml(truck.brand)} ${escapeHtml(truck.model)}</h3><span class="truck-plate">${escapeHtml(truck.licensePlate)}</span></div>
                    ${stateBadge("truck", truck.state?.id, truck.state?.description)}
                  </div>
                  <div class="meta-grid">
                    <div><span>Temperatura</span><strong>${reading ? `${reading.temp.toFixed(1)}°C` : "—"}</strong></div>
                    <div><span>Humedad</span><strong>${reading ? `${reading.percHumidity}%` : "—"}</strong></div>
                    <div><span>Puerta</span><strong>${reading ? (reading.doorState ? "Abierta" : "Cerrada") : "—"}</strong></div>
                    <div><span>Última muestra</span><strong>${reading ? relative(reading.date) : "—"}</strong></div>
                  </div>
                  <div class="row-actions" style="justify-content:flex-start">
                    <button class="btn btn-sm" data-edit="${truck.id}">${icon("edit", 14)} Editar</button>
                    ${truck.state?.id !== "OS" ? `<button class="btn btn-sm btn-danger" data-remove="${truck.id}">${icon("trash", 14)} Fuera de servicio</button>` : ""}
                  </div>
                </article>`;
              })
              .join("")}</div>`
          : emptyState("Ningún camión coincide", "Ajusta el filtro de estado o agrega un nuevo camión.", "trucks")
      }
    `;

    $("[data-refresh]").addEventListener("click", load);
    $("[data-new]").addEventListener("click", () => editTruck());
    $("[data-filter]").addEventListener("change", (event) => {
      stateFilter = event.target.value;
      paint();
    });
    view.querySelectorAll("[data-edit]").forEach((button) =>
      button.addEventListener("click", () => editTruck(trucks.find((truck) => truck.id === button.dataset.edit))),
    );
    view.querySelectorAll("[data-remove]").forEach((button) =>
      button.addEventListener("click", async () => {
        const truck = trucks.find((item) => item.id === button.dataset.remove);
        const confirmed = await confirmDialog({
          title: "¿Marcar camión fuera de servicio?",
          message: `${truck?.licensePlate} se marcará fuera de servicio y quedará excluido de la planificación de viajes.`,
          confirmLabel: "Fuera de servicio",
          danger: true,
        });
        if (!confirmed) return;
        try {
          await del(`/trucks/${truck.id}`);
          success("Camión actualizado", `${truck.licensePlate} ahora está fuera de servicio.`);
          await load();
        } catch (err) {
          error("No se pudo actualizar el camión", err.message);
        }
      }),
    );
  }

  function editTruck(truck = null) {
    openModal({
      title: truck ? "Editar camión" : "Agregar camión",
      subtitle: truck ? `${truck.brand} ${truck.model}` : "Registra una nueva unidad refrigerada.",
      body: `<form id="truck-form" class="form-grid">
        <label class="field"><span>Marca</span><input name="brand" required value="${escapeHtml(truck?.brand || "")}" placeholder="p. ej. Isuzu"></label>
        <label class="field"><span>Modelo</span><input name="model" required value="${escapeHtml(truck?.model || "")}" placeholder="p. ej. NPR"></label>
        <label class="field"><span>Placa</span><input name="licensePlate" required value="${escapeHtml(truck?.licensePlate || "")}" placeholder="ABC-123-A"></label>
        <label class="field"><span>Estado</span><select name="state">${states
          .map((state) => `<option value="${state.id}" ${truck?.state?.id === state.id ? "selected" : ""}>${escapeHtml(state.description)}</option>`)
          .join("")}</select></label>
      </form>`,
      footer: `<button class="btn" data-cancel>Cancelar</button><button class="btn btn-primary" data-submit>${truck ? "Guardar cambios" : "Agregar camión"}</button>`,
      onMount(modal, close) {
        modal.querySelector("[data-cancel]").addEventListener("click", close);
        modal.querySelector("[data-submit]").addEventListener("click", async (event) => {
          const form = modal.querySelector("#truck-form");
          if (!form.reportValidity()) return;
          const values = formValues(form);
          const payload = {
            brand: values.brand.trim(),
            model: values.model.trim(),
            licensePlate: values.licensePlate.trim().toUpperCase(),
            idStateTruck: values.state,
          };
          const button = event.currentTarget;
          button.disabled = true;
          try {
            if (truck) await put(`/trucks/${truck.id}`, payload);
            else await post("/trucks", payload);
            close();
            success(truck ? "Camión actualizado" : "Camión agregado", `${payload.licensePlate} se guardó en la flotilla.`);
            await load();
          } catch (err) {
            error("No se pudo guardar el camión", err.message);
            button.disabled = false;
          }
        });
      },
    });
  }

  await load();
}
