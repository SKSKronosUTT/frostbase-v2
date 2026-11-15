import { del, get, post, put } from "../api.js";
import {
  $,
  confirmDialog,
  dateOnly,
  emptyState,
  error,
  escapeHtml,
  formValues,
  icon,
  loadingState,
  openModal,
  success,
} from "../ui.js";

export async function render(view) {
  view.innerHTML = loadingState("Cargando conductores");
  let drivers = [];
  let trucks = [];
  let search = "";

  async function load() {
    view.innerHTML = loadingState("Cargando conductores");
    try {
      [drivers, trucks] = await Promise.all([get("/users/drivers"), get("/trucks")]);
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Conductores no disponibles", err.message, "drivers", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint() {
    const term = search.trim().toLowerCase();
    const visible = drivers.filter((driver) =>
      [driver.name?.fullName, driver.email, driver.phone].filter(Boolean).some((value) => value.toLowerCase().includes(term)),
    );
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Conductores</h2><p>Equipo de entrega, datos de contacto y camiones asignados por defecto.</p></div>
        <div class="toolbar"><button class="btn" data-refresh>${icon("refresh")} Actualizar</button><button class="btn btn-primary" data-new>${icon("plus")} Agregar conductor</button></div>
      </div>
      <article class="card">
        <div class="card-head">
          <label class="field search"><span>Buscar conductores</span><input data-search type="search" placeholder="Nombre, correo o teléfono" value="${escapeHtml(search)}"></label>
          <span class="chip">${visible.length} de ${drivers.length} conductores</span>
        </div>
        ${
          visible.length
            ? `<div class="table-wrap"><table>
                <thead><tr><th>Conductor</th><th>Correo</th><th>Teléfono</th><th>Fecha de nacimiento</th><th>Camión por defecto</th><th>Estado</th><th class="num">Acciones</th></tr></thead>
                <tbody>${visible
                  .map(
                    (driver) => `<tr>
                      <td><div style="display:flex;align-items:center;gap:10px"><span class="avatar">${escapeHtml((driver.name?.firstName?.[0] || "") + (driver.name?.lastName?.[0] || ""))}</span><div><div class="cell-title">${escapeHtml(driver.name?.fullName || "Conductor sin nombre")}</div><div class="cell-sub">Conductor</div></div></div></td>
                      <td>${escapeHtml(driver.email)}</td>
                      <td>${escapeHtml(driver.phone || "—")}</td>
                      <td>${dateOnly(driver.birthDate)}</td>
                      <td>${driver.truckDefault ? `<span class="truck-plate">${escapeHtml(driver.truckDefault.licensePlate)}</span>` : '<span class="faint small">Sin asignar</span>'}</td>
                      <td><span class="badge ${driver.active === false ? "gray" : "green"}">${driver.active === false ? "Inactivo" : "Activo"}</span></td>
                      <td><div class="row-actions"><button class="btn btn-sm" data-edit="${driver.id}">${icon("edit", 14)} Editar</button>${driver.active === false ? "" : `<button class="btn btn-sm btn-danger" data-remove="${driver.id}">${icon("trash", 14)} Desactivar</button>`}</div></td>
                    </tr>`,
                  )
                  .join("")}</tbody>
              </table></div>`
            : emptyState("No se encontraron conductores", "Agrega un conductor o ajusta tu búsqueda.", "drivers")
        }
      </article>
    `;

    $("[data-refresh]").addEventListener("click", load);
    $("[data-new]").addEventListener("click", () => editDriver());
    const input = $("[data-search]");
    input.addEventListener("input", (event) => {
      search = event.target.value;
      const position = event.target.selectionStart;
      paint();
      const next = $("[data-search]");
      next.focus();
      next.setSelectionRange(position, position);
    });
    view.querySelectorAll("[data-edit]").forEach((button) =>
      button.addEventListener("click", () => editDriver(drivers.find((driver) => driver.id === button.dataset.edit))),
    );
    view.querySelectorAll("[data-remove]").forEach((button) =>
      button.addEventListener("click", async () => {
        const driver = drivers.find((item) => item.id === button.dataset.remove);
        const confirmed = await confirmDialog({
          title: "¿Desactivar conductor?",
          message: `${driver?.name?.fullName} dejará de estar disponible para asignación de rutas.`,
          confirmLabel: "Desactivar",
          danger: true,
        });
        if (!confirmed) return;
        try {
          await del(`/users/${driver.id}`);
          success("Conductor desactivado", "El conductor se retiró de las asignaciones activas.");
          await load();
        } catch (err) {
          error("No se pudo desactivar el conductor", err.message);
        }
      }),
    );
  }

  function editDriver(driver = null) {
    openModal({
      title: driver ? "Editar conductor" : "Agregar conductor",
      subtitle: driver ? driver.name?.fullName : "Crea un perfil de conductor para asignaciones de ruta.",
      wide: true,
      body: `<form id="driver-form" class="form-grid">
        <label class="field"><span>Nombre</span><input name="firstName" required value="${escapeHtml(driver?.name?.firstName || "")}"></label>
        <label class="field"><span>Apellido</span><input name="lastName" required value="${escapeHtml(driver?.name?.lastName || "")}"></label>
        <label class="field"><span>Segundo apellido</span><input name="middleName" value="${escapeHtml(driver?.name?.middleName || "")}"></label>
        <label class="field"><span>Teléfono</span><input name="phone" value="${escapeHtml(driver?.phone || "")}" placeholder="+52 000 000 0000"></label>
        <label class="field"><span>Correo electrónico</span><input name="email" type="email" required value="${escapeHtml(driver?.email || "")}"></label>
        <label class="field"><span>Fecha de nacimiento</span><input name="birthDate" type="date" value="${driver?.birthDate ? driver.birthDate.slice(0, 10) : ""}"></label>
        <label class="field"><span>Camión por defecto</span><select name="truckDefault"><option value="">Asignación automática</option>${trucks
          .map((truck) => `<option value="${truck.id}" ${driver?.truckDefault?.id === truck.id ? "selected" : ""}>${escapeHtml(truck.licensePlate)} — ${escapeHtml(truck.brand)} ${escapeHtml(truck.model)}</option>`)
          .join("")}</select></label>
        <label class="field"><span>${driver ? "Nueva contraseña (opcional)" : "Contraseña"}</span><input name="password" type="password" ${driver ? "" : "required"} placeholder="${driver ? "Déjala en blanco para conservar la actual" : "Al menos 6 caracteres"}"></label>
        ${driver ? `<label class="check-row full"><input type="checkbox" name="active" ${driver.active === false ? "" : "checked"}> El conductor está activo</label>` : ""}
      </form>`,
      footer: `<button class="btn" data-cancel>Cancelar</button><button class="btn btn-primary" data-submit>${driver ? "Guardar cambios" : "Agregar conductor"}</button>`,
      onMount(modal, close) {
        modal.querySelector("[data-cancel]").addEventListener("click", close);
        modal.querySelector("[data-submit]").addEventListener("click", async (event) => {
          const form = modal.querySelector("#driver-form");
          if (!form.reportValidity()) return;
          const values = formValues(form);
          const payload = {
            firstName: values.firstName.trim(),
            lastName: values.lastName.trim(),
            middleName: values.middleName.trim() || null,
            email: values.email.trim(),
            phone: values.phone.trim() || null,
            birthDate: values.birthDate || null,
            idTruckDefault: values.truckDefault || null,
            isAdmin: false,
          };
          if (values.password) payload.password = values.password;
          if (driver) payload.active = values.active === "on";
          const button = event.currentTarget;
          button.disabled = true;
          try {
            if (driver) await put(`/users/${driver.id}`, payload);
            else await post("/users", payload);
            close();
            success(driver ? "Conductor actualizado" : "Conductor agregado", `${payload.firstName} ${payload.lastName} está listo para asignaciones.`);
            await load();
          } catch (err) {
            error("No se pudo guardar el conductor", err.message);
            button.disabled = false;
          }
        });
      },
    });
  }

  await load();
}
