function getToken() {
  const m = document.cookie.match(/(?:^|; )admin_token=([^;]*)/);
  return m ? decodeURIComponent(m[1]) : null;
}

async function api(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(path, { ...options, headers });
  if (res.status === 401) {
    window.location.href = "/admin/login";
    return null;
  }
  return res;
}

function setCookie(name, value, days = 1) {
  const d = new Date();
  d.setTime(d.getTime() + days * 86400000);
  document.cookie = `${name}=${encodeURIComponent(value)};expires=${d.toUTCString()};path=/`;
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("uz-UZ", {
    day: "2-digit", month: "2-digit", year: "numeric",
    hour: "2-digit", minute: "2-digit",
  });
}
