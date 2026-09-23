export const $ = (id) => document.getElementById(id);
export async function request(path, data) {
  const response = await fetch(
    path,
    data === undefined
      ? { signal: AbortSignal.timeout(30000) }
      : {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Microscope-Client": "local-ui",
          },
          body: JSON.stringify(data),
          signal: AbortSignal.timeout(60000),
        },
  );
  const result = await response.json();
  if (!response.ok)
    throw new Error(result.error || `Request failed (${response.status})`);
  return result;
}
export const cameraCommand = (action, data = {}) =>
  request(`/api/camera/${action}`, data);
export function feedback(message, error = false) {
  $("feedback").textContent = message;
  $("feedback").classList.toggle("error", error);
}
export function download(blob, name) {
  const url = URL.createObjectURL(blob),
    link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}
