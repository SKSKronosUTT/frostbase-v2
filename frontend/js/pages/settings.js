import { api } from "../core/api.js";
import { initProtectedPage, openPasswordChangeModal } from "../core/app.js";
import { getCachedAdmin } from "../core/auth.js";
import { notify } from "../core/notifications.js";
import { toggleTheme } from "../core/theme.js";
import {
  escapeHtml,
  formatDateTime,
  qs,
  setButtonLoading,
  timeAgo,
} from "../core/helpers.js";
import {
  clearFormErrors,
  focusFirstError,
  setFieldError,
} from "../components/form-errors.js";

const form = qs("#settingsForm");
const saveButton = qs("#saveSettings");

let currentSettings = null;
let currentAdmin = null;

const fields = {
  temperatureIdeal: qs("#temperatureIdeal"),
  temperatureTolerance: qs("#temperatureTolerance"),
  humidityIdeal: qs("#humidityIdeal"),
  humidityTolerance: qs("#humidityTolerance"),
  offlineTimeout: qs("#offlineTimeout"),
  weatherCity: qs("#weatherCity"),
  weatherLatitude: qs("#weatherLatitude"),
  weatherLongitude: qs("#weatherLongitude"),
};

function numberValue(input) {
  const raw = input.value.trim();
  if (raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function updatePreviews() {
  const tempIdeal = numberValue(fields.temperatureIdeal);
  const tempTolerance = numberValue(fields.temperatureTolerance);
  const humIdeal = numberValue(fields.humidityIdeal);
  const humTolerance = numberValue(fields.humidityTolerance);

  qs("#temperatureRangePreview").textContent =
    tempIdeal !== null && tempTolerance !== null
      ? `${(tempIdeal - tempTolerance).toFixed(1)} °C a ${(
          tempIdeal + tempTolerance
        ).toFixed(1)} °C`
      : "—";
  qs("#humidityRangePreview").textContent =
    humIdeal !== null && humTolerance !== null
      ? `${(humIdeal - humTolerance).toFixed(1)} % a ${(
          humIdeal + humTolerance
        ).toFixed(1)} %`
      : "—";
}

function renderAccount() {
  if (!currentAdmin) return;
  qs("#accountInfo").innerHTML = `
    <div class="detail-row"><dt>Usuario</dt><dd>${escapeHtml(currentAdmin.username)}</dd></div>
    <div class="detail-row"><dt>Correo</dt><dd>${escapeHtml(currentAdmin.email)}</dd></div>
    <div class="detail-row"><dt>Último acceso</dt><dd>${
      currentAdmin.last_login
        ? `${formatDateTime(currentAdmin.last_login)}<div class="muted text-xs">${timeAgo(
            currentAdmin.last_login
          )}</div>`
        : "—"
    }</dd></div>
    <div class="detail-row"><dt>Cuenta creada</dt><dd>${formatDateTime(
      currentAdmin.created_at
    )}</dd></div>
  `;
}

function fillForm(settings) {
  currentSettings = settings;
  fields.temperatureIdeal.value = settings.temperature_ideal;
  fields.temperatureTolerance.value = settings.temperature_tolerance;
  fields.humidityIdeal.value = settings.humidity_ideal;
  fields.humidityTolerance.value = settings.humidity_tolerance;
  fields.offlineTimeout.value = settings.offline_timeout_seconds;
  fields.weatherCity.value = settings.weather_city;
  fields.weatherLatitude.value = settings.weather_latitude;
  fields.weatherLongitude.value = settings.weather_longitude;
  qs("#settingsUpdated").textContent = `Última actualización: ${formatDateTime(
    settings.updated_at
  )} · ${timeAgo(settings.updated_at)}`;
  updatePreviews();
}

function validate(payload) {
  if (payload.temperature_ideal - payload.temperature_tolerance < -80) {
    return {
      field: fields.temperatureTolerance,
      message: "El límite mínimo de temperatura no puede ser menor a -80 °C.",
    };
  }
  if (payload.temperature_ideal + payload.temperature_tolerance > 60) {
    return {
      field: fields.temperatureTolerance,
      message: "El límite máximo de temperatura no puede superar 60 °C.",
    };
  }
  if (payload.humidity_ideal - payload.humidity_tolerance < 0) {
    return {
      field: fields.humidityTolerance,
      message: "El límite mínimo de humedad no puede ser menor a 0 %.",
    };
  }
  if (payload.humidity_ideal + payload.humidity_tolerance > 100) {
    return {
      field: fields.humidityTolerance,
      message: "El límite máximo de humedad no puede superar 100 %.",
    };
  }
  if (payload.temperature_tolerance <= 0) {
    return {
      field: fields.temperatureTolerance,
      message: "La tolerancia de temperatura debe ser mayor que 0.",
    };
  }
  if (payload.humidity_tolerance <= 0) {
    return {
      field: fields.humidityTolerance,
      message: "La tolerancia de humedad debe ser mayor que 0.",
    };
  }
  if (
    payload.offline_timeout_seconds < 10 ||
    payload.offline_timeout_seconds > 86400
  ) {
    return {
      field: fields.offlineTimeout,
      message: "El tiempo de desconexión debe estar entre 10 y 86400 segundos.",
    };
  }
  if (!payload.weather_city) {
    return {
      field: fields.weatherCity,
      message: "Indica una ciudad para el clima.",
    };
  }
  return null;
}

async function handleSubmit(event) {
  event.preventDefault();
  const offlineTimeout = numberValue(fields.offlineTimeout);
  const payload = {
    temperature_ideal: numberValue(fields.temperatureIdeal),
    temperature_tolerance: numberValue(fields.temperatureTolerance),
    humidity_ideal: numberValue(fields.humidityIdeal),
    humidity_tolerance: numberValue(fields.humidityTolerance),
    offline_timeout_seconds:
      offlineTimeout === null ? null : Math.round(offlineTimeout),
    weather_city: fields.weatherCity.value.trim(),
    weather_latitude: numberValue(fields.weatherLatitude),
    weather_longitude: numberValue(fields.weatherLongitude),
  };

  clearFormErrors(form);

  const required = [
    [
      fields.temperatureIdeal,
      payload.temperature_ideal,
      "Indica la temperatura ideal.",
    ],
    [
      fields.temperatureTolerance,
      payload.temperature_tolerance,
      "Indica la tolerancia de temperatura.",
    ],
    [fields.humidityIdeal, payload.humidity_ideal, "Indica la humedad ideal."],
    [
      fields.humidityTolerance,
      payload.humidity_tolerance,
      "Indica la tolerancia de humedad.",
    ],
    [
      fields.offlineTimeout,
      payload.offline_timeout_seconds,
      "Indica el tiempo de desconexión.",
    ],
    [fields.weatherCity, payload.weather_city, "Indica una ciudad para el clima."],
    [fields.weatherLatitude, payload.weather_latitude, "Indica la latitud."],
    [fields.weatherLongitude, payload.weather_longitude, "Indica la longitud."],
  ];

  let hasMissing = false;
  for (const [field, value, message] of required) {
    if (value === null || value === "") {
      setFieldError(field, message);
      hasMissing = true;
    }
  }
  if (hasMissing) {
    focusFirstError(form);
    return;
  }

  const problem = validate(payload);
  if (problem) {
    setFieldError(problem.field, problem.message);
    focusFirstError(form);
    return;
  }

  setButtonLoading(saveButton, true, "Guardando…");
  try {
    const settings = await api.put("/settings", payload);
    fillForm(settings);
    clearFormErrors(form);
    notify.success("La configuración se guardó correctamente.");
  } catch (error) {
    notify.error(error.message, { title: "No se pudo guardar" });
  } finally {
    setButtonLoading(saveButton, false);
  }
}

async function init() {
  currentAdmin = await initProtectedPage();
  renderAccount();
  form.addEventListener("submit", handleSubmit);
  [
    fields.temperatureIdeal,
    fields.temperatureTolerance,
    fields.humidityIdeal,
    fields.humidityTolerance,
  ].forEach((input) => input.addEventListener("input", updatePreviews));

  qs("#resetSettings").addEventListener("click", () => {
    if (!currentSettings) return;
    clearFormErrors(form);
    fillForm(currentSettings);
    notify.info("Cambios descartados.");
  });

  qs("#settingsThemeToggle").addEventListener("click", () => {
    toggleTheme(getCachedAdmin());
  });

  qs("#changePasswordButton").addEventListener("click", () => {
    openPasswordChangeModal();
  });

  window.addEventListener("frostbase:theme", () => {
    const icon = qs("#settingsThemeToggle i");
    if (!icon) return;
    const isDark = document.documentElement.dataset.theme === "dark";
    icon.className = isDark ? "fa-solid fa-sun" : "fa-solid fa-moon";
  });

  try {
    fillForm(await api.get("/settings"));
  } catch (error) {
    notify.error(error.message, { title: "No se pudo cargar la configuración" });
  }
}

init().catch((error) => {
  if (error.message !== "redirecting") {
    console.error(error);
    notify.error("No se pudo inicializar la configuración.");
  }
});
