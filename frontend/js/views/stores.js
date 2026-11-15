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
  success,
} from "../ui.js";

const BASE = { latitude: 32.45900929216648, longitude: -116.97966765227373 };

export async function render(view) {
  view.innerHTML = loadingState("Cargando tiendas");
  let stores = [];
  let search = "";

  async function load() {
    view.innerHTML = loadingState("Cargando tiendas");
    try {
      stores = await get("/stores?include_inactive=true");
      paint();
    } catch (err) {
      view.innerHTML = `<div class="card">${emptyState("Tiendas no disponibles", err.message, "stores", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", load);
    }
  }

  function paint() {
    const term = search.trim().toLowerCase();
    const visible = stores.filter((store) =>
      [store.name, store.location?.address, store.phone].filter(Boolean).some((value) => value.toLowerCase().includes(term)),
    );
    view.innerHTML = `
      <div class="page-head">
        <div><h2>Red de tiendas</h2><p>Puntos de entrega, datos de contacto y coordenadas geográficas.</p></div>
        <div class="toolbar"><button class="btn" data-refresh>${icon("refresh")} Actualizar</button><button class="btn btn-primary" data-new>${icon("plus")} Agregar tienda</button></div>
      </div>
      <article class="card">
        <div class="card-head">
          <label class="field search"><span>Buscar tiendas</span><input data-search type="search" placeholder="Nombre, dirección o teléfono" value="${escapeHtml(search)}"></label>
          <span class="chip">${visible.length} de ${stores.length} tiendas</span>
        </div>
        ${
          visible.length
            ? `<div class="table-wrap"><table>
                <thead><tr><th>Tienda</th><th>Teléfono</th><th>Coordenadas</th><th>Estado</th><th class="num">Acciones</th></tr></thead>
                <tbody>${visible
                  .map(
                    (store) => `<tr>
                      <td><div class="cell-title">${escapeHtml(store.name)}</div><div class="cell-sub">${escapeHtml(store.location?.address || "")}</div></td>
                      <td>${escapeHtml(store.phone || "—")}</td>
                      <td class="mono small">${store.location?.latitude?.toFixed(4)}, ${store.location?.longitude?.toFixed(4)}</td>
                      <td><span class="badge ${store.active ? "green" : "gray"}">${store.active ? "Activa" : "Inactiva"}</span></td>
                      <td><div class="row-actions"><button class="btn btn-sm" data-edit="${store.id}">${icon("edit", 14)} Editar</button>${store.active ? `<button class="btn btn-sm btn-danger" data-remove="${store.id}">${icon("trash", 14)} Desactivar</button>` : ""}</div></td>
                    </tr>`,
                  )
                  .join("")}</tbody>
              </table></div>`
            : emptyState("No se encontraron tiendas", "Agrega una tienda o ajusta tu búsqueda.", "stores")
        }
      </article>
    `;

    $("[data-refresh]").addEventListener("click", load);
    $("[data-new]").addEventListener("click", () => editStore());
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
      button.addEventListener("click", () => editStore(stores.find((store) => store.id === button.dataset.edit))),
    );
    view.querySelectorAll("[data-remove]").forEach((button) =>
      button.addEventListener("click", async () => {
        const store = stores.find((item) => item.id === button.dataset.remove);
        const confirmed = await confirmDialog({
          title: "¿Desactivar tienda?",
          message: `${store?.name} dejará de aparecer en la planificación de rutas y pedidos. Los pedidos históricos se conservan.`,
          confirmLabel: "Desactivar",
          danger: true,
        });
        if (!confirmed) return;
        try {
          await del(`/stores/${store.id}`);
          success("Tienda desactivada", "La tienda se retiró de la planificación activa.");
          await load();
        } catch (err) {
          error("No se pudo desactivar la tienda", err.message);
        }
      }),
    );
  }

  function editStore(store = null) {
    const location = store?.location || BASE;
    openModal({
      title: store ? "Editar tienda" : "Agregar tienda",
      subtitle: store ? store.name : "Crea un nuevo punto de entrega para la red.",
      wide: true,
      body: `<form id="store-form" class="form-grid">
        <label class="field"><span>Nombre de la tienda</span><input name="name" required value="${escapeHtml(store?.name || "")}" placeholder="Nombre de tienda o sucursal"></label>
        <label class="field"><span>Teléfono</span><input name="phone" value="${escapeHtml(store?.phone || "")}" placeholder="+52 000 000 0000"></label>
        <label class="field full"><span>Dirección</span><input name="address" required value="${escapeHtml(location.address || "")}" placeholder="Calle, ciudad, estado"></label>
        <label class="field"><span>Latitud</span><input name="latitude" type="number" step="any" required value="${location.latitude ?? BASE.latitude}"></label>
        <label class="field"><span>Longitud</span><input name="longitude" type="number" step="any" required value="${location.longitude ?? BASE.longitude}"></label>
        <label class="check-row full"><input type="checkbox" name="active" ${store?.active === false ? "" : "checked"}> La tienda está activa para planificación</label>
      </form>`,
      footer: `<button class="btn" data-cancel>Cancelar</button><button class="btn btn-primary" data-submit>${store ? "Guardar cambios" : "Agregar tienda"}</button>`,
      onMount(modal, close) {
        modal.querySelector("[data-cancel]").addEventListener("click", close);
        modal.querySelector("[data-submit]").addEventListener("click", async (event) => {
          const form = modal.querySelector("#store-form");
          if (!form.reportValidity()) return;
          const values = formValues(form);
          const payload = {
            name: values.name.trim(),
            phone: values.phone.trim() || null,
            location: {
              address: values.address.trim(),
              latitude: Number(values.latitude),
              longitude: Number(values.longitude),
            },
            active: values.active === "on",
          };
          const button = event.currentTarget;
          button.disabled = true;
          try {
            if (store) await put(`/stores/${store.id}`, payload);
            else await post("/stores", payload);
            close();
            success(store ? "Tienda actualizada" : "Tienda creada", `${payload.name} está lista para planificación.`);
            await load();
          } catch (err) {
            error("No se pudo guardar la tienda", err.message);
            button.disabled = false;
          }
        });
      },
    });
  }

  await load();
}
