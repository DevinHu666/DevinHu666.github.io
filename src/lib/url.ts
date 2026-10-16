// Prefix a site-relative path with the deploy base ("/" locally, "/<repo>/" on a project page).
export function url(path = ""): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, "");
  return `${base}/${path.replace(/^\//, "")}`;
}
