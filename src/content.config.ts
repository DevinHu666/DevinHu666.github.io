import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { z } from "astro/zod";

// One Markdown file per project. Only "published" projects get a page;
// "in-progress" and "planned" ones appear as cards, so a new project is
// a new file here and nothing else.
const projects = defineCollection({
  loader: glob({ pattern: "*.md", base: "./src/content/projects" }),
  schema: z.object({
    title: z.string(),
    summary: z.string(),
    status: z.enum(["published", "in-progress", "planned"]),
    order: z.number(), // lower first
    course: z.string().optional(), // e.g. "ROB 380 · Project 3"
    courseProject: z.number().optional(), // AutoRob project number
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
    date: z.string().optional(), // "2026-10"
    video: z.string().optional(), // a video file in public/, shown above the demo
    videoCaption: z.string().optional(),
    demo: z.enum(["p1-astar", "p2-pendularm", "p3-rickroll"]).optional(), // interactive block shown above the write-up
    highlights: z.array(z.string()).default([]), // short, numeric where possible
  }),
});

export const collections = { projects };
