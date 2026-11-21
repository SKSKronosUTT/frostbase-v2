import { api } from "../core/api.js";
import { initProtectedPage } from "../core/app.js";
import { confirmDialog, notify } from "../core/notifications.js";
import {
  debounce,
  escapeHtml,
  formatHum,
  formatTemp,
  qs,
  setButtonLoading,
  timeAgo,
  truckStatusMeta,
} from "../core/helpers.js";
import { activateModal } from "../components/modal.js";
import { renderPagination } from "../components/pagination.js";
import {
  emptyRow,
  renderTableState,
  setAriaBusy,
  tableError,
  tableSkeleton,
} from "../components/feedback.js";

const state = {
  page: 1,
  pageSize: 10,
  search: "",
  status: "",
  total: 0,
  devicesPage: 1,
  devicesPageSize: 10,
  devicesSearch: "",
  devicesTotal: 0,
  devicesLoaded: false,
  tab: "trucks",
};

let secretValue = "";

const trucksBody = qs("#trucksTableBody");
const devicesBody = qs("#devicesTableBody");
const trucksPagination = qs("#trucksPagination");
const devicesPagination = qs("#devicesPagination");
const truckModal = qs("#truckModal");
const deviceModal = qs("#deviceModal");
const secretModal = qs("#secretModal");
const truckForm = qs("#truckForm");
const deviceForm = qs("#deviceForm");

function updateFleetTotals() {
  qs("#fleetTotals").textContent = `${state.total} camión${
    state.total === 1 ? "" : "es"
  } · ${state.devicesTotal} dispositivo${state.devicesTotal === 1 ? "" : "s"}`;
}

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

function truckRows(items) {
  return items
    .map((truck) => {
      const status = truckStatusMeta(truck.status);
      const device = truck.device;
      const online = device?.is_online;
      const current = truck.current_reading;
      const alertIcon =
        truck.active_alerts > 0
          ? ` <i class="fa-solid fa-triangle-exclamation text-danger" title="${truck.active_alerts} alerta(s) activa(s)"></i>`
          : "";
      return `
        <tr>
          <td><span class="plate">${escapeHtml(truck.plate)}</span>${alertIcon}</td>
          <td>
            <div class="vehicle">
              <strong>${escapeHtml(truck.brand)}</strong>
              <span>${escapeHtml(truck.model)} · ${truck.year}</span>
            </div>
          </td>
          <td><span class="badge ${status.className}">${status.label}</span></td>
          <td>
            ${
              truck.route
                ? `<span class="route-name" title="${escapeHtml(truck.route.name)}"><i class="fa-solid fa-route"></i>${escapeHtml(
                    truck.route.name
                  )}</span>`
                : '<span class="muted">Sin ruta</span>'
            }
          </td>
          <td><span class="cell-temp">${formatTemp(current?.temperature)}</span></td>
          <td>${formatHum(current?.humidity)}</td>
          <td>
            <span class="last-comms ${online ? "is-online" : ""}">
              ${
                device
                  ? `${online ? "En línea" : "Desconectado"} · ${timeAgo(device.last_seen)}`
                  : "Sin dispositivo"
              }
            </span>
          </td>
          <td class="cell-actions">
            <a class="icon-button icon-button--primary" href="truck-detail.html?id=${
              truck.id
            }" title="Ver detalle"><i class="fa-solid fa-eye"></i></a>
            <button class="icon-button" type="button" data-action="edit" data-id="${
              truck.id
            }" title="Editar"><i class="fa-solid fa-pen"></i></button>
            <button class="icon-button icon-button--danger" type="button" data-action="delete" data-id="${
              truck.id
            }" data-plate="${escapeHtml(truck.plate)}" title="Eliminar"><i class="fa-solid fa-trash"></i></button>
          </td>
        </tr>
      `;
    })
    .join("");
}

async function loadTrucks() {
  try {
    setAriaBusy(trucksBody, true);
    renderTableState(trucksBody, tableSkeleton(8, 5, 8));
    const params = new URLSearchParams({
      page: state.page,
      page_size: state.pageSize,
    });
    if (state.search) params.set("search", state.search);
    if (state.status) params.set("status", state.status);
    const data = await api.get(`/trucks?${params.toString()}`);
    state.total = data.total;
    const totalPages = Math.max(1, Math.ceil(data.total / state.pageSize));
    if (state.page > totalPages) {
      state.page = totalPages;
      return loadTrucks();
    }
    renderTableState(
      trucksBody,
      data.items.length
        ? truckRows(data.items)
        : emptyRow(
            8,
            "fa-truck",
            "Sin camiones registrados",
            "Registra tu primer camión para comenzar a monitorear la flota."
          )
    );
    qs("#trucksCount").textContent = `${data.total} resultado${
      data.total === 1 ? "" : "s"
    }`;
    renderPagination(trucksPagination, {
      page: state.page,
      total: data.total,
      pageSize: state.pageSize,
      itemLabel: "camiones",
      onChange: (page) => {
        state.page = page;
        loadTrucks();
      },
    });
    updateFleetTotals();
  } catch (error) {
    renderTableState(trucksBody, tableError(8, error.message), {
      onRetry: loadTrucks,
    });
    notify.error(error.message, { title: "Error al cargar camiones" });
  } finally {
    setAriaBusy(trucksBody, false);
  }
}

function deviceRows(items) {
  return items
    .map((device) => {
      const online = device.is_online;
      return `
        <tr>
          <td><span class="device-identifier">${escapeHtml(device.device_id)}</span></td>
          <td>${
            device.truck_plate
              ? escapeHtml(device.truck_plate)
              : '<span class="muted">Sin asignar</span>'
          }</td>
          <td>
            <span class="status-dot ${online ? "is-online" : "is-offline"}">${
              online ? "En línea" : "Desconectado"
            }</span>
          </td>
          <td class="cell-muted">${
            device.last_seen ? timeAgo(device.last_seen) : "Nunca"
          }</td>
          <td class="cell-muted">${timeAgo(device.created_at)}</td>
          <td class="cell-actions">
            <button class="icon-button" type="button" data-device-action="edit" data-id="${
              device.id
            }" title="Asignar camión"><i class="fa-solid fa-pen"></i></button>
            <button class="icon-button icon-button--primary" type="button" data-device-action="rotate" data-id="${
              device.id
            }" data-name="${escapeHtml(device.device_id)}" title="Regenerar clave"><i class="fa-solid fa-key"></i></button>
          </td>
        </tr>
      `;
    })
    .join("");
}

async function loadDevices() {
  try {
    setAriaBusy(devicesBody, true);
    renderTableState(devicesBody, tableSkeleton(6, 5, 6));
    const params = new URLSearchParams({
      page: state.devicesPage,
      page_size: state.devicesPageSize,
    });
    if (state.devicesSearch) params.set("search", state.devicesSearch);
    const data = await api.get(`/devices?${params.toString()}`);
    state.devicesTotal = data.total;
    state.devicesLoaded = true;
    const totalPages = Math.max(1, Math.ceil(data.total / state.devicesPageSize));
    if (state.devicesPage > totalPages) {
      state.devicesPage = totalPages;
      return loadDevices();
    }
    renderTableState(
      devicesBody,
      data.items.length
        ? deviceRows(data.items)
        : emptyRow(
            6,
            "fa-microchip",
            "Sin dispositivos registrados",
            "Registra un ESP32-S3 para recibir lecturas de temperatura, humedad y GPS."
          )
    );
    qs("#devicesCount").textContent = `${data.total} dispositivo${
      data.total === 1 ? "" : "s"
    }`;
    renderPagination(devicesPagination, {
      page: state.devicesPage,
      total: data.total,
      pageSize: state.devicesPageSize,
      itemLabel: "dispositivos",
      onChange: (page) => {
        state.devicesPage = page;
        loadDevices();
      },
    });
    updateFleetTotals();
  } catch (error) {
    renderTableState(devicesBody, tableError(6, error.message), {
      onRetry: loadDevices,
    });
    notify.error(error.message, { title: "Error al cargar dispositivos" });
  } finally {
    setAriaBusy(devicesBody, false);
  }
}

async function ensureReferences() {
  const [routes, devices, trucks] = await Promise.all([
    api.get("/routes/options"),
    api.get("/devices/all"),
    api.get("/trucks/options"),
  ]);
  return { routes, devices, trucks };
}

function fillTruckOptions(select, trucks, selectedId = null) {
  select.innerHTML =
    '<option value="">Sin asignar</option>' +
    trucks
      .map(
        (truck) =>
          `<option value="${truck.id}" ${
            String(truck.id) === String(selectedId) ? "selected" : ""
          }>${escapeHtml(truck.label)}</option>`
      )
      .join("");
}

async function openTruckModal(truckId = null) {
  try {
    const references = await ensureReferences();
    truckForm.reset();
    qs("#truckId").value = "";

    const routeSelect = qs("#truckRoute");
    routeSelect.innerHTML =
      '<option value="">Sin ruta</option>' +
      references.routes
        .map(
          (route) => `<option value="${route.id}">${escapeHtml(route.label)}</option>`
        )
        .join("");

    const deviceSelect = qs("#truckDevice");
    deviceSelect.innerHTML =
      '<option value="">Sin dispositivo</option>' +
      references.devices
        .map((device) => {
          const assigned = device.truck_plate
            ? ` · en ${device.truck_plate}`
            : " · sin asignar";
          return `<option value="${device.id}">${escapeHtml(
            device.device_id
          )}${escapeHtml(assigned)}</option>`;
        })
        .join("");

    if (truckId) {
      const truck = await api.get(`/trucks/${truckId}`);
      qs("#truckModalTitle").textContent = "Editar camión";
      qs("#truckSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar cambios';
      qs("#truckId").value = truck.id;
      qs("#truckBrand").value = truck.brand;
      qs("#truckModel").value = truck.model;
      qs("#truckYear").value = truck.year;
      qs("#truckPlate").value = truck.plate;
      qs("#truckStatus").value = truck.status;
      qs("#truckDescription").value = truck.description || "";
      routeSelect.value = truck.route?.id || "";
      deviceSelect.value = truck.device?.id || "";
    } else {
      qs("#truckModalTitle").textContent = "Registrar camión";
      qs("#truckSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar camión';
      qs("#truckYear").value = new Date().getFullYear();
    }

    openModal(truckModal);
    setTimeout(() => qs("#truckBrand").focus(), 50);
  } catch (error) {
    notify.error(error.message, { title: "No se pudo abrir el formulario" });
  }
}

async function submitTruck(event) {
  event.preventDefault();
  if (!truckForm.reportValidity()) return;
  const id = qs("#truckId").value;
  const payload = {
    brand: qs("#truckBrand").value.trim(),
    model: qs("#truckModel").value.trim(),
    year: Number(qs("#truckYear").value),
    plate: qs("#truckPlate").value.trim().toUpperCase(),
    status: qs("#truckStatus").value,
    description: qs("#truckDescription").value.trim() || null,
    route_id: qs("#truckRoute").value ? Number(qs("#truckRoute").value) : null,
    device_id: qs("#truckDevice").value ? Number(qs("#truckDevice").value) : null,
  };

  const button = qs("#truckSubmit");
  const currentPlate = payload.plate;
  if (payload.route_id) {
    try {
      const route = await api.get(`/routes/${payload.route_id}`);
      const assignedPlate = route.truck?.plate || "";
      if (assignedPlate && assignedPlate !== currentPlate) {
        const accepted = await confirmDialog({
          title: "Reasignar ruta",
          message: `La ruta está asignada al camión ${assignedPlate}. Si continúas, ese camión quedará sin ruta y se asignará a ${currentPlate}.`,
          confirmText: "Reasignar",
          danger: false,
        });
        if (!accepted) return;
      }
    } catch (error) {
      notify.error(error.message, {
        title: "No se pudo verificar la ruta",
      });
      return;
    }
  }

  setButtonLoading(button, true, "Guardando…");
  try {
    if (id) {
      await api.put(`/trucks/${id}`, payload);
      notify.success("Camión actualizado correctamente.");
    } else {
      await api.post("/trucks", payload);
      notify.success("Camión registrado correctamente.");
    }
    closeModal(truckModal);
    await loadTrucks();
    if (state.devicesLoaded) await loadDevices();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo guardar el camión" });
  } finally {
    setButtonLoading(button, false);
  }
}

async function deleteTruck(truckId, plate) {
  const accepted = await confirmDialog({
    title: "Eliminar camión",
    message: `Se eliminará el camión ${plate} de la flota. Su historial de lecturas y alertas se conservará. Esta acción no se puede deshacer.`,
    confirmText: "Eliminar camión",
    danger: true,
  });
  if (!accepted) return;
  try {
    await api.delete(`/trucks/${truckId}`);
    notify.success("Camión eliminado de la flota.");
    await loadTrucks();
    if (state.devicesLoaded) await loadDevices();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo eliminar el camión" });
  }
}

async function openDeviceModal(device = null) {
  try {
    const references = await ensureReferences();
    deviceForm.reset();
    qs("#devicePk").value = "";
    fillTruckOptions(qs("#deviceTruck"), references.trucks, device?.truck_id || null);
    const identifier = qs("#deviceIdentifier");
    identifier.disabled = false;

    if (device) {
      qs("#deviceModalTitle").textContent = "Editar dispositivo";
      qs("#deviceSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar cambios';
      qs("#devicePk").value = device.id;
      identifier.value = device.device_id;
      identifier.disabled = true;
      qs("#deviceIdentifierHint").textContent =
        "El identificador físico no se puede modificar.";
    } else {
      qs("#deviceModalTitle").textContent = "Registrar dispositivo";
      qs("#deviceSubmit").innerHTML =
        '<i class="fa-solid fa-floppy-disk"></i> Guardar dispositivo';
      qs("#deviceIdentifierHint").textContent =
        "Se usará para autenticar sus lecturas.";
    }

    openModal(deviceModal);
    setTimeout(() => {
      if (!device) identifier.focus();
    }, 50);
  } catch (error) {
    notify.error(error.message, { title: "No se pudo abrir el formulario" });
  }
}

async function submitDevice(event) {
  event.preventDefault();
  if (!deviceForm.reportValidity()) return;
  const id = qs("#devicePk").value;
  const truckId = qs("#deviceTruck").value ? Number(qs("#deviceTruck").value) : null;
  const button = qs("#deviceSubmit");
  setButtonLoading(button, true, "Guardando…");
  try {
    if (id) {
      await api.put(`/devices/${id}`, { truck_id: truckId });
      notify.success("Dispositivo actualizado correctamente.");
      closeModal(deviceModal);
    } else {
      const created = await api.post("/devices", {
        device_id: qs("#deviceIdentifier").value.trim(),
        truck_id: truckId,
      });
      closeModal(deviceModal);
      showSecret(created.device_id, created.device_key);
      notify.success("Dispositivo registrado. Guarda su clave de acceso.");
    }
    await loadDevices();
    await loadTrucks();
  } catch (error) {
    notify.error(error.message, { title: "No se pudo guardar el dispositivo" });
  } finally {
    setButtonLoading(button, false);
  }
}

function showSecret(deviceLabel, key) {
  secretValue = key;
  qs("#secretDeviceLabel").textContent = `Dispositivo ${deviceLabel}`;
  qs("#secretValue").textContent = key;
  openModal(secretModal);
}

async function copySecret() {
  if (!secretValue) return;
  try {
    if (navigator.clipboard && window.isSecureContext) {
      await navigator.clipboard.writeText(secretValue);
    } else {
      const textarea = document.createElement("textarea");
      textarea.value = secretValue;
      textarea.style.position = "fixed";
      textarea.style.opacity = "0";
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      textarea.remove();
    }
    notify.success("Clave copiada al portapapeles.");
  } catch (error) {
    notify.error("No se pudo copiar la clave. Selecciónala manualmente.");
  }
}

async function rotateDeviceKey(deviceId, deviceName) {
  const accepted = await confirmDialog({
    title: "Regenerar clave del dispositivo",
    message: `La clave actual de ${deviceName} dejará de funcionar de inmediato. Deberás actualizar el ESP32-S3 o el simulador con la nueva clave.`,
    confirmText: "Regenerar clave",
    danger: true,
  });
  if (!accepted) return;
  try {
    const updated = await api.post(`/devices/${deviceId}/rotate-key`, {});
    showSecret(updated.device_id, updated.device_key);
    notify.success("Nueva clave generada.");
  } catch (error) {
    notify.error(error.message, { title: "No se pudo regenerar la clave" });
  }
}

function switchTab(tab) {
  state.tab = tab;
  document.querySelectorAll("[data-tab]").forEach((button) => {
    const active = button.dataset.tab === tab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
  });
  qs("#trucksPanel").hidden = tab !== "trucks";
  qs("#devicesPanel").hidden = tab !== "devices";
  if (tab === "devices" && !state.devicesLoaded) {
    loadDevices();
  }
}

function wireEvents() {
  qs("#newTruckButton").addEventListener("click", () => openTruckModal());
  qs("#newDeviceButton").addEventListener("click", () => openDeviceModal());

  document.querySelectorAll("[data-tab]").forEach((button) => {
    button.addEventListener("click", () => switchTab(button.dataset.tab));
  });

  qs("#truckSearch").addEventListener(
    "input",
    debounce((event) => {
      state.search = event.target.value.trim();
      state.page = 1;
      loadTrucks();
    }, 320)
  );
  qs("#truckStatusFilter").addEventListener("change", (event) => {
    state.status = event.target.value;
    state.page = 1;
    loadTrucks();
  });
  qs("#deviceSearch").addEventListener(
    "input",
    debounce((event) => {
      state.devicesSearch = event.target.value.trim();
      state.devicesPage = 1;
      loadDevices();
    }, 320)
  );

  truckForm.addEventListener("submit", submitTruck);
  deviceForm.addEventListener("submit", submitDevice);

  trucksBody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-action]");
    if (!button) return;
    if (button.dataset.action === "edit") openTruckModal(button.dataset.id);
    if (button.dataset.action === "delete") {
      deleteTruck(button.dataset.id, button.dataset.plate);
    }
  });

  devicesBody.addEventListener("click", async (event) => {
    const button = event.target.closest("[data-device-action]");
    if (!button) return;
    if (button.dataset.deviceAction === "rotate") {
      rotateDeviceKey(button.dataset.id, button.dataset.name);
    }
    if (button.dataset.deviceAction === "edit") {
      try {
        const device = await api.get(`/devices/${button.dataset.id}`);
        openDeviceModal(device);
      } catch (error) {
        notify.error(error.message);
      }
    }
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
  await Promise.all([loadTrucks(), loadDevices()]);
  const editId = new URLSearchParams(window.location.search).get("edit");
  if (editId) {
    history.replaceState({}, "", "trucks.html");
    openTruckModal(editId);
  }
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar la gestión de flota.");
  }
});
