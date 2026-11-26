/**
 * Errores de formulario accesibles (FE-012).
 *
 * - Asocia el mensaje al campo con `aria-describedby`.
 * - Marca el campo con `aria-invalid`.
 * - Anuncia el error con `role="alert"`.
 * - Limpia el error cuando el usuario corrige el valor.
 */

function errorId(field) {
  return `${field.id || field.name || "field"}-error`;
}

function errorContainer(field) {
  return field.closest(".form-field") || field.parentElement || field;
}

function describedBy(field) {
  return (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(Boolean);
}

function watchField(field) {
  if (field.dataset.errorWatched === "true") return;
  field.dataset.errorWatched = "true";
  const clear = () => clearFieldError(field);
  field.addEventListener("input", clear);
  field.addEventListener("change", clear);
}

export function setFieldError(field, message) {
  if (!field || !message) return;
  const id = errorId(field);
  let error = document.getElementById(id);

  if (!error) {
    error = document.createElement("p");
    error.id = id;
    error.className = "field-error";
    error.setAttribute("role", "alert");
    errorContainer(field).append(error);
  }

  error.textContent = message;
  field.setAttribute("aria-invalid", "true");

  const ids = describedBy(field);
  if (!ids.includes(id)) {
    field.setAttribute("aria-describedby", [...ids, id].join(" "));
  }

  watchField(field);
}

export function clearFieldError(field) {
  if (!field) return;
  const id = errorId(field);
  document.getElementById(id)?.remove();
  field.removeAttribute("aria-invalid");

  const ids = describedBy(field).filter((value) => value !== id);
  if (ids.length) field.setAttribute("aria-describedby", ids.join(" "));
  else field.removeAttribute("aria-describedby");
}

export function clearFormErrors(form) {
  if (!form) return;
  form.querySelectorAll('[aria-invalid="true"]').forEach((field) => {
    clearFieldError(field);
  });
}

export function focusFirstError(form) {
  const field = form?.querySelector('[aria-invalid="true"]');
  field?.focus();
  return field;
}
