import axios from "axios";

export const tenantApi = (slug) => {
  const inst = axios.create({ baseURL: `${process.env.REACT_APP_BACKEND_URL}/api/t/${slug}` });
  inst.interceptors.request.use((c) => {
    const t = localStorage.getItem(`hs_token_${slug}`);
    if (t) c.headers.Authorization = `Bearer ${t}`;
    return c;
  });
  return inst;
};

export const errText = (e) => {
  const d = e?.response?.data?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || "").join(" ");
  return e?.message || "Something went wrong";
};
