import { del, get } from "../api.js";
import {
  $,
  DAYS,
  currency,
  dateTime,
  emptyState,
  error,
  escapeHtml,
  icon,
  lineChart,
  loadingState,
  num,
  pct,
  progressMeter,
  relative,
  stateBadge,
  success,
  timeOnly,
} from "../ui.js";

const AVG_TICKET = 2450;
const AVG_COST_RATIO = 0.62;

export async function render(view) {
  view.innerHTML = loadingState("Cargando telemetría de la flotilla");
  let alive = true;

  async function load(isRefresh = false) {
    if (!isRefresh) view.innerHTML = loadingState("Cargando telemetría de la flotilla");
    try {
      const summary = await get("/dashboard/summary");
      if (!alive) return;
      paint(summary);
      if (isRefresh) success("Panel actualizado", "La telemetría más reciente ya está visible.");
    } catch (err) {
      if (!alive) return;
      view.innerHTML = `<div class="card">${emptyState("Telemetría no disponible", err.message, "alert", '<button class="btn" data-retry>Reintentar</button>')}</div>`;
      view.querySelector("[data-retry]")?.addEventListener("click", () => load());
    }
  }

  function financeBar(label, value, max, tone = "") {
    const ratio = max ? Math.min(100, Math.round((value / max) * 100)) : 0;
    return `<div class="finance-bar"><small>${escapeHtml(label)}</small><strong>${currency(value)}</strong><div class="progress ${tone}"><span style="width:${ratio}%"></span></div></div>`;
  }

  function paint(summary) {
    const { kpis, fleet, trend, latestReadings, recentAlerts, routesToday, parameters } = summary;
    const maxFleet = Math.max(...fleet.map((row) => row.count), 1);
    const alerts = recentAlerts || [];
    const readings = latestReadings || [];
    const routes = routesToday || [];

    const delivered = kpis.orders.delivered || 0;
    const pending = kpis.orders.pending || 0;
    const estimatedRevenue = delivered * AVG_TICKET;
    const estimatedCost = Math.round(estimatedRevenue * AVG_COST_RATIO);
    const estimatedMargin = estimatedRevenue - estimatedCost;
    const marginPct = estimatedRevenue ? Math.round((estimatedMargin / estimatedRevenue) * 100) : 0;
    const financeMax = Math.max(estimatedRevenue, estimatedCost, estimatedMargin, 1);
    const globalProgress = kpis.orders.today
      ? Math.min(100, Math.round((delivered / kpis.orders.today) * 100))
      : 0;

    view.innerHTML = `
      <div class="page-head">
        <div>
          <p class="eyebrow">Panel operativo</p>
          <h2>Resumen de flotilla</h2>
          <p>Salud de la cadena de frío en vivo en ${num(kpis.trucks.total)} camiones y ${num(kpis.orders.today)} pedidos de hoy.</p>
        </div>
        <div class="toolbar">
          <span class="chip">Ventana desde ${timeOnly(summary.windowSince)}</span>
          <button class="btn" data-refresh>${icon("refresh")} Actualizar</button>
        </div>
      </div>

      <div class="bento-grid">
        <article class="card kpi span-3">
          <div class="kpi-top"><div><p class="kpi-label">Camiones disponibles</p><p class="kpi-value">${num(kpis.trucks.available)}</p></div><span class="kpi-icon">${icon("trucks")}</span></div>
          <div class="kpi-foot"><strong>${num(kpis.trucks.inRoute)}</strong> en ruta · <strong>${num(kpis.trucks.maintenance)}</strong> en mantenimiento</div>
        </article>
        <article class="card kpi span-3">
          <div class="kpi-top"><div><p class="kpi-label">Pedidos de hoy</p><p class="kpi-value">${num(kpis.orders.today)}</p></div><span class="kpi-icon">${icon("orders")}</span></div>
          <div class="kpi-foot"><strong>${num(delivered)}</strong> entregados · <strong>${num(pending)}</strong> pendientes</div>
        </article>
        <article class="card kpi span-3">
          <div class="kpi-top"><div><p class="kpi-label">Alertas activas</p><p class="kpi-value">${num(kpis.alerts.active)}</p></div><span class="kpi-icon">${icon("alert")}</span></div>
          <div class="kpi-foot"><strong>${num(kpis.alerts.temperature)}</strong> temperatura · <strong>${num(kpis.alerts.door)}</strong> puerta</div>
        </article>
        <article class="card kpi span-3">
          <div class="kpi-top"><div><p class="kpi-label">Cumplimiento térmico</p><p class="kpi-value">${pct(kpis.environment.temperatureCompliance)}</p></div><span class="kpi-icon">${icon("temp")}</span></div>
          <div class="kpi-foot">Objetivo de ${parameters.minTemperature}°C a ${parameters.maxTemperature}°C</div>
        </article>

        <article class="card span-8">
          <div class="card-head">
            <div><h3>Tendencia ambiental</h3><p>Temperatura y humedad promedio de la flotilla en las últimas 24 horas</p></div>
            <div class="pill-row">
              <span class="chart-pill"><i style="background:#38bdf8"></i>Temperatura</span>
              <span class="chart-pill"><i style="background:#f472b6"></i>Humedad</span>
            </div>
          </div>
          ${lineChart(trend)}
          <div class="chart-stat">
            <div><strong>${summary.kpis.environment.avgTemperature}°C</strong><br><span>Temperatura promedio</span></div>
            <div><strong>${summary.kpis.environment.avgHumidity}%</strong><br><span>Humedad promedio</span></div>
            <div><strong>${num(summary.kpis.environment.readings)}</strong><br><span>Lecturas procesadas</span></div>
          </div>
        </article>

        <article class="card span-4">
          <div class="card-head">
            <div><h3>Seguimiento de rutas</h3><p>Proyectos de entrega activos hoy</p></div>
            <span class="badge ${globalProgress >= 80 ? "green" : globalProgress >= 40 ? "blue" : "yellow"}">${globalProgress}%</span>
          </div>
          ${
            routes.length
              ? `<div class="project-list">${routes
                  .slice(0, 4)
                  .map((route) => {
                    const total = route.ordersTotal ?? route.stores.length;
                    const done = route.ordersDelivered ?? 0;
                    const ratio = total ? Math.min(100, Math.round((done / total) * 100)) : globalProgress;
                    const tone = ratio >= 100 ? "green" : ratio >= 50 ? "" : "yellow";
                    return `<div class="project-row">
                      <div class="project-top"><strong>${escapeHtml(route.name)}</strong><span class="badge ${ratio >= 100 ? "green" : ratio >= 50 ? "blue" : "yellow"}">${ratio}%</span></div>
                      <div class="project-meta">${escapeHtml(route.driver?.name?.fullName || "Conductor sin asignar")} · ${route.stores.length} paradas</div>
                      <div class="progress ${tone}"><span style="width:${ratio}%"></span></div>
                      <div class="project-foot"><span>${num(done)}/${num(total)} entregas</span><span>${route.deliverDays.map((day) => DAYS[day]?.[0] || "").join(" ") || "Hoy"}</span></div>
                    </div>`;
                  })
                  .join("")}</div>`
              : emptyState("Sin rutas hoy", "No hay entregas programadas para hoy.", "routes")
          }
        </article>

        <article class="card span-4">
          <div class="card-head">
            <div><h3>Reporte financiero</h3><p>Estimación operativa del día</p></div>
            <span class="kpi-icon">${icon("wallet")}</span>
          </div>
          <div class="finance-hero">
            <div>
              <p class="eyebrow">Ingreso estimado</p>
              <div class="finance-value">${currency(estimatedRevenue)}</div>
              <span class="finance-delta">${icon("trend", 13)} ${marginPct}% de margen</span>
            </div>
            <div class="finance-ring" style="--value:${marginPct}"><span>${marginPct}%</span></div>
          </div>
          <div class="finance-bars">
            ${financeBar("Facturado", estimatedRevenue, financeMax)}
            ${financeBar("Costo operativo", estimatedCost, financeMax, "yellow")}
            ${financeBar("Margen bruto", estimatedMargin, financeMax, "green")}
          </div>
          <p class="faint small" style="margin-top:12px">Estimación basada en pedidos entregados y ticket promedio.</p>
        </article>

        <article class="card span-4">
          <div class="card-head"><div><h3>Estado de la flotilla</h3><p>Disponibilidad actual</p></div><span class="chip">${num(kpis.trucks.total)} total</span></div>
          <div class="fleet-bars">
            ${fleet.map((row) => progressMeter(row.label, row.count, maxFleet, row.id === "AV" ? "green" : row.id === "IR" ? "" : row.id === "IM" ? "yellow" : "red")).join("")}
          </div>
          <div class="list" style="margin-top:18px">
            <div class="list-item"><div class="list-main"><strong>Cumplimiento de humedad</strong><small>Lecturas entre ${parameters.minHumidity}% y ${parameters.maxHumidity}%</small></div><span class="badge ${kpis.environment.humidityCompliance >= 90 ? "green" : "yellow"}">${pct(kpis.environment.humidityCompliance)}</span></div>
            <div class="list-item"><div class="list-main"><strong>Viajes</strong><small>${num(kpis.trips.completedToday)} completados hoy</small></div><span class="badge blue">${num(kpis.trips.active)} activos</span></div>
            <div class="list-item"><div class="list-main"><strong>Rutas programadas</strong><small>${num(kpis.routes.active)} rutas activas en la red</small></div><span class="badge gray">${num(kpis.routes.today)} hoy</span></div>
          </div>
        </article>

        <article class="card span-4">
          <div class="card-head"><div><h3>Alertas recientes</h3><p>Incidentes abiertos de cadena de frío</p></div><span class="badge ${alerts.length ? "red" : "green"}">${alerts.length ? `${alerts.length} abiertas` : "Todo en orden"}</span></div>
          ${
            alerts.length
              ? `<div class="list">${alerts
                  .map(
                    (alert) => `<div class="list-item">
                      <div class="list-main">
                        <strong>${escapeHtml(alert.alertType?.description || "Alerta de cadena de frío")}</strong>
                        <small>${escapeHtml(alert.reading?.truck?.licensePlate || "Sin camión")} · ${relative(alert.date)}${alert.reading ? ` · ${alert.reading.temp.toFixed(1)}°C` : ""}</small>
                      </div>
                      <div class="pill-row">${stateBadge("alert", alert.alertType?.id)}${alert.state ? `<button class="btn btn-sm" data-ack="${alert.id}">Reconocer</button>` : ""}</div>
                    </div>`,
                  )
                  .join("")}</div>`
              : emptyState("Sin alertas abiertas", "Todos los camiones monitoreados están dentro del rango.", "shield")
          }
        </article>

        <article class="card span-7">
          <div class="card-head">
            <div><h3>Últimas lecturas</h3><p>Muestra más reciente de sensores por camión</p></div>
            <a class="btn btn-sm btn-ghost" href="#/map">Abrir mapa ${icon("chevron", 14)}</a>
          </div>
          ${
            readings.length
              ? `<div class="table-wrap"><table>
                  <thead><tr><th>Camión</th><th>Estado</th><th class="num">Temp.</th><th class="num">Humedad</th><th>Puerta</th><th>Muestreo</th></tr></thead>
                  <tbody>${readings
                    .map(
                      (row) => `<tr>
                        <td><div class="cell-title">${escapeHtml(row.truck?.licensePlate || "—")}</div><div class="cell-sub">${escapeHtml(row.truck?.brand || "")} ${escapeHtml(row.truck?.model || "")}</div></td>
                        <td>${stateBadge("truck", row.truck?.state?.id, row.truck?.state?.description)}</td>
                        <td class="num">${row.reading ? `${row.reading.temp.toFixed(1)}°C` : "—"}</td>
                        <td class="num">${row.reading ? `${row.reading.percHumidity}%` : "—"}</td>
                        <td>${row.reading ? `<span class="badge ${row.reading.doorState ? "red" : "green"}">${row.reading.doorState ? "Abierta" : "Cerrada"}</span>` : "—"}</td>
                        <td><span title="${dateTime(row.reading?.date)}">${relative(row.reading?.date)}</span></td>
                      </tr>`,
                    )
                    .join("")}</tbody>
                </table></div>`
              : emptyState("Aún no hay lecturas", "Los datos de sensores aparecerán cuando los camiones reporten.", "temp")
          }
        </article>

        <article class="card span-5">
          <div class="card-head"><div><h3>Rutas de hoy</h3><p>${DAYS[new Date().getDay()]} · agenda de entregas</p></div><a class="btn btn-sm" href="#/routes">Gestionar rutas ${icon("chevron", 14)}</a></div>
          ${
            routes.length
              ? `<div class="list">${routes
                  .map(
                    (route) => `<div class="list-item">
                      <div class="list-main"><strong>${escapeHtml(route.name)}</strong><small>${escapeHtml(route.driver?.name?.fullName || "Conductor sin asignar")} · ${route.stores.length} paradas</small></div>
                      <div class="pill-row">${route.driver ? `<span class="badge green">Asignada</span>` : `<span class="badge yellow">Sin conductor</span>`}</div>
                    </div>`,
                  )
                  .join("")}</div>`
              : emptyState("Sin rutas hoy", "No hay entregas programadas para hoy.", "routes")
          }
        </article>
      </div>
    `;

    view.querySelector("[data-refresh]")?.addEventListener("click", (event) => {
      event.currentTarget.disabled = true;
      load(true).finally(() => {
        if (view.contains(event.currentTarget)) event.currentTarget.disabled = false;
      });
    });

    view.querySelectorAll("[data-ack]").forEach((button) => {
      button.addEventListener("click", async () => {
        button.disabled = true;
        try {
          await del(`/alerts/${button.dataset.ack}`);
          success("Alerta reconocida", "El incidente se retiró de la cola de abiertos.");
          load(true);
        } catch (err) {
          error("No se pudo reconocer la alerta", err.message);
          button.disabled = false;
        }
      });
    });
  }

  await load();
  return () => {
    alive = false;
  };
}
