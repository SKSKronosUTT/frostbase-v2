import { api } from "../core/api.js";
import { initProtectedPage } from "../core/app.js";
import { confirmDialog, notify } from "../core/notifications.js";
import {
  debounce,
  escapeHtml,
  formatDateTime,
  qs,
  setButtonLoading,
} from "../core/helpers.js";
import { renderPagination } from "../components/pagination.js";
import {
  emptyRow,
  renderTableState,
  setAriaBusy,
  tableError,
  tableSkeleton,
} from "../components/feedback.js";
import { activateModal } from "../components/modal.js";

const state = {
  page: 1,
  pageSize: 10,
  search: "",
  active: "true",
  hasTruck: "",
  total: 0,
};

let secretValue = "";

const tableBody = qs("#driversTableBody");
const pagination = qs("#driversPagination");
const driverModal = qs("#driverModal");
const secretModal = qs("#secretModal");
const driverForm = qs("#driverForm");

function openModal(modal) {
  modal.classList.remove("hidden");
  document.body.classList.add("modal-open");
  modal._deactivate?.();
  modal._deactivate = activateModal(modal, { onClose: () => closeModal(modal) });
}

function closeModal(modal) {
  modal.classList.add("hidden");
  modal._deactivate?.();
  modal._deactivate = null;
  if (!document.querySelector(".modal-overlay:not(.hidden)")) {
    document.body.classList.remove("modal-open");
  }
}

function driverRows(items) {
  return items
    .map((driver) => {
      const fullName = [driver.first_name, driver.middle_name, driver.last_name]
        .filter(Boolean)
        .join(" ");
      return `
        <tr>
          <td><strong>${escapeHtml(fullName)}</strong></td>
          <td>${escapeHtml(driver.email)}</td>
          <td class="cell-muted">${escapeHtml(driver.phone)}</td>
          <td>${
            driver.truck
              ? `<span class="plate">${escapeHtml(driver.truck.plate)}</span>`
              : '<span class="muted">Sin camión</span>'
          }</td>
          <td><span class="badge ${
            driver.is_active ? "badge--success" : "badge--muted"
          }">${driver.is_active ? "Activo" : "Inactivo"}</span></td>
          <td class="cell-muted">${
            driver.last_login ? formatDateTime(driver.last_login) : "Nunca"
          }</td>
          <td class="cell-actions">
            <button class="icon-button" type="button" data-driver-action="edit" data-id="${
              driver.id
            }" title="Editar"><i class="fa-solid fa-pen"></i></button>
            <button class="icon-button" type="button" data-driver-action="truck" data-id="${
              driver.id
            }" title="Camión asignado"><i class="fa-solid fa-truck"></i></button>
            <button class="icon-button" type="button" data-driver-action="reset" data-id="${
              driver.id
            }" data-name="${escapeHtml(fullName)}" title="Restablecer contraseña">
              <i class="fa-solid fa-key"></i>
            </button>
            ${
              driver.is_active
                ? `<button class="icon-button icon-button--danger" type="button" data-driver-action="deactivate" data-id="${driver.id}" data-name="${escapeHtml(
                    fullName
                  )}" title="Desactivar"><i class="fa-solid fa-trash"></i></button>`
                : `<button class="icon-button" type="button" data-driver-action="restore" data-id="${driver.id}" title="Reactivar"><i class="fa-solid fa-arrow-up"></i></button>`
            }
          </td>
        </tr>
      `;
    })
    .join("");
}

async function loadDrivers() {
  try {
    setAriaBusy(tableBody, true);
    renderTableState(tableBody, tableSkeleton(7, 5, 7));
    const params = new URLSearchParams({
      page: state.page,
      page_size: state.pageSize,
      active: state.active,
    });
    if (state.search) params.set("search", state.search);
    if (state.hasTruck) params.set("has_truck", state.hasTruck);

    const data = await api.get(`/drivers?${params.toString()}`);
    state.total = data.total;
    const totalPages = Math.max(1, Math.ceil(data.total / state.pageSize));
    if (state.page > totalPages) {
      state.page = totalPages;
      return loadDrivers();
    }

    renderTableState(
      tableBody,
      data.items.length
        ? driverRows(data.items)
        : emptyRow(
            7,
            "fa-user",
            "Sin conductores para estos filtros",
            state.active === "false"
              ? "No hay conductores inactivos. Los desactivados conservan su correo reservado."
              : "Registra tu primer conductor para comenzar a operar la flota."
          )
    );
    qs("#driversCount").textContent = `${data.total} resultado${
      data.total === 1 ? "" : "s"
    }`;
    renderPagination(pagination, {
      page: state.page,
      total: data.total,
      pageSize: state.pageSize,
      itemLabel: "conductores",
      onChange: (page) => {
        state.page = page;
        loadDrivers();
      },
    });
  } catch (error) {
    if (error?.cancelled) return;
    renderTableState(tableBody, tableError(7, error.message), {
      onRetry: loadDrivers,
    });
    notify.error(error.message, { title: "Error al cargar conductores" });
  } finally {
    setAriaBusy(tableBody, false);
  }
}

async function fillTruckOptions(selectedId = "") {
  const select = qs("#driverTruckSelect");
  const trucks = await api.get("/trucks/options");
  select.innerHTML =
    '<option value="">Sin camión</option>' +
    trucks
      .map(
        (truck) =>
          `<option value="${truck.id}" ${
            String(truck.id) === String(selectedId) ? "selected" : ""
          }>${escapeHtml(truck.label)}</option>`
      )
      .join("");
}

async function openDriverModal(driverId = null) {
  try {
    driverForm.reset();
    qs("#driverPk").value = "";

    if (driverId) {
      const driver = await api.get(`/drivers/${driverId}`);
      qs("#driverModalTitle").textContent = "Editar conductor";
      qs("#driverSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar cambios';
      qs("#driverPk").value = driver.id;
      qs("#driverFirstName").value = driver.first_name;
      qs("#driverLastName").value = driver.last_name;
      qs("#driverMiddleName").value = driver.middle_name || "";
      qs("#driverEmail").value = driver.email;
      qs("#driverPhone").value = driver.phone;
      qs("#driverBirthdate").value = driver.birthdate;
      qs("#driverPasswordField").hidden = true;
      await fillTruckOptions(driver.truck?.id || "");
    } else {
      qs("#driverModalTitle").textContent = "Registrar conductor";
      qs("#driverSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar conductor';
      await fillTruckOptions();
    }

    openModal(driverModal);
    setTimeout(() => qs("#driverFirstName")?.focus(), 50);
  } catch (error) {
    notify.error(error.message, { title: "No se pudo abrir el formulario" });
  }
}

function showSecret(driverLabel, key) {
  secretValue = key;
  qs("#secretDriverLabel").textContent = `Conductor ${driverLabel}`;
  qs("#secretValue").textContent = key;
  openModal(secretModal);
}

async function submitDriver(event) {
  event.preventDefault();
  const id = qs("#driverPk")?.value;
  const payload = {
    first_name: qs("#driverFirstName").value.trim(),
    last_name: qs("#driverLastName").value.trim(),
    middle_name: qs("#driverMiddleName").value.trim() || null,
    email: qs("#driverEmail").value.trim(),
    phone: qs("#driverPhone").value.trim(),
    birthdate: qs("#driverBirthdate").value,
  };
  const truckValue = qs("#driverTruckSelect").value;
  const password = qs("#driverPassword").value;

  const button = qs("#driverSubmit");
  setButtonLoading(button, true, "Guardando…");
  try {
    if (id) {
      await api.patch(`/drivers/${id}`, payload);
      if (truckValue) {
        await api.put(`/drivers/${id}/truck`, { truck_id: Number(truckValue) });
      } else {
        await api.delete(`/drivers/${id}/truck`);
      }
      closeModal(driverModal);
      notify.success("Conductor actualizado correctamente.");
    } else {
      payload.password = password || null;
      payload.truck_id = truckValue ? Number(truckValue) : null;
      const created = await api.post("/drivers", payload);
      closeModal(driverModal);
      if (created.temporary_password) {
        showSecret(
          `${created.first_name} ${created.last_name}`,
          created.temporary_password
        );
      }
      notify.success("Conductor registrado correctamente.");
    }
    await loadDrivers();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo guardar el conductor" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function resetDriverPassword(driverId, driverName) {
  const accepted = await confirmDialog({
    title: "Restablecer contraseña",
    message: `Se generará una contraseña temporal para ${driverName}. Sus sesiones activas quedarán revocadas.`,
    confirmText: "Generar contraseña",
    danger: true,
  });
  if (!accepted) return;
  try {
    const response = await api.post(`/drivers/${driverId}/reset-password`);
    showSecret(driverName, response.temporary_password);
    notify.success("Contraseña temporal generada.");
    await loadDrivers();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo restablecer la contraseña" });
  }
}

async function deactivateDriver(driverId, driverName) {
  const accepted = await confirmDialog({
    title: "Desactivar conductor",
    message: `${driverName} perderá el acceso de inmediato, se liberará su camión y sus rutas quedarán sin conductor activo.`,
    confirmText: "Desactivar",
    danger: true,
  });
  if (!accepted) return;
  try {
    const response = await api.delete(`/drivers/${driverId}`);
    notify.success("Conductor desactivado.");
    if (response.affected_routes?.length) {
      notify.warning(
        `Rutas sin conductor activo: ${response.affected_routes
          .map((route) => route.name)
          .join(", ")}`,
        { title: "Revisa las rutas afectadas" }
      );
    }
    await loadDrivers();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo desactivar el conductor" });
  }
}

async function restoreDriver(driverId) {
  try {
    await api.post(`/drivers/${driverId}/restore`);
    notify.success("Conductor reactivado.");
    await loadDrivers();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo reactivar el conductor" });
  }
}

async function copySecret() {
  if (!secretValue) return;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(secretValue);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = secretValue;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    notify.success("Contraseña copiada al portapapeles.");
  } catch (error) {
    notify.error("No se pudo copiar. Selecciónala manualmente.");
  }
}

function wireEvents() {
  qs("#newDriverButton").addEventListener("click", () => openDriverModal());

  qs("#driverSearch").addEventListener(
    "input",
    debounce((event) => {
      state.search = event.target.value.trim();
      state.page = 1;
      loadDrivers();
    }, 320)
  );
  qs("#driverActiveFilter").addEventListener("change", (event) => {
    state.active = event.target.value;
    state.page = 1;
    loadDrivers();
  });
  qs("#driverTruckFilter").addEventListener("change", (event) => {
    state.hasTruck = event.target.value;
    state.page = 1;
    loadDrivers();
  });

  driverForm.addEventListener("submit", submitDriver);

  tableBody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-driver-action]");
    if (!button) return;
    const { driverAction, id, name } = button.dataset;
    if (driverAction === "edit" || driverAction === "truck") openDriverModal(id);
    if (driverAction === "reset") resetDriverPassword(id, name);
    if (driverAction === "deactivate") deactivateDriver(id, name);
    if (driverAction === "restore") restoreDriver(id);
  });

  document.querySelectorAll("[data-close]").forEach((button) => {
    button.addEventListener("click", () => {
      const modal = document.getElementById(button.dataset.close);
      if (modal) closeModal(modal);
    });
  });

  document.querySelectorAll(".modal-overlay").forEach((overlay) => {
    overlay.addEventListener("click", (event) => {
      if (event.target === overlay) closeModal(overlay);
    });
  });

  qs("#copySecretButton").addEventListener("click", copySecret);
}

async function init() {
  await initProtectedPage();
  wireEvents();
  await loadDrivers();
  const editId = new URLSearchParams(window.location.search).get("edit");
  if (editId) {
    history.replaceState({}, "", "drivers.html");
    openDriverModal(editId);
  }
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar la gestión de conductores.");
  }
});
