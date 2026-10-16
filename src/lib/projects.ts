import { getCollection, type CollectionEntry } from "astro:content";

export type Project = CollectionEntry<"projects">;

export async function projects(): Promise<Project[]> {
  return (await getCollection("projects")).sort((a, b) => a.data.order - b.data.order);
}
