// @ts-check
import { defineConfig } from "astro/config";

// GitHub Pages: a user site (https://<user>.github.io) is served from "/",
// a project site (https://<user>.github.io/<repo>/) from "/<repo>/".
// The deploy workflow sets both; locally they default to "/".
export default defineConfig({
  site: process.env.SITE_URL ?? "http://localhost:4321",
  base: process.env.BASE_PATH ?? "/",
  trailingSlash: "always",
});
