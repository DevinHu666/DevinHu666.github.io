// Turn a URDF's STL visuals into one small GLB for the web.
//
//   PROJECT3_DIR=/path/to/project3-python node scripts/build-robot-glb.mjs [urdf] [out.glb]
//
// Defaults to the RPO humanoid in $PROJECT3_DIR/viewer/assets (the ROB 380
// Project 3 folder, which lives outside this repository).
// Each link becomes a top-level node named after the link, holding its first
// <visual> mesh in the link frame (visual origin applied). The page parents
// those nodes under link groups whose matrices come from /xform_world, so the
// GLB carries geometry only, never kinematics.
//
// Pipeline: STL -> weld -> simplify (meshoptimizer) -> meshopt compression.
// 30 MB of STL becomes a few MB at most; the exact numbers are printed.

import { readFileSync, writeFileSync, mkdirSync, copyFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Document, NodeIO } from "@gltf-transform/core";
import { EXTMeshoptCompression, KHRMeshQuantization } from "@gltf-transform/extensions";
import { meshopt, prune, simplify, weld } from "@gltf-transform/functions";
import { MeshoptEncoder, MeshoptSimplifier } from "meshoptimizer";

const here = dirname(fileURLToPath(import.meta.url));
const project3 = process.env.PROJECT3_DIR;
if (!process.argv[2] && !project3) {
  console.error("Set PROJECT3_DIR to your project3-python folder, or pass a URDF path.");
  process.exit(1);
}
const urdfPath = resolve(process.argv[2] ?? join(project3, "viewer/assets/rpo/urdf/rpo.urdf"));
const outPath = resolve(process.argv[3] ?? join(here, "../public/models/rpo.glb"));
const RATIO = 0.12; // keep ~12% of triangles...
const ERROR = 0.002; // ...unless that bends a surface by more than 0.2% of the part's size

const urdf = readFileSync(urdfPath, "utf8").replace(/<!--[\s\S]*?-->/g, "");

const attr = (tag, name) => tag.match(new RegExp(`\\b${name}\\s*=\\s*["']([^"']*)["']`))?.[1];
const vec = (text, fallback) => (text ? text.trim().split(/\s+/).map(Number) : fallback);

function quatFromRpy([r, p, y]) {
  const [cr, sr, cp, sp, cy, sy] = [r, r, p, p, y, y].map((a, i) => (i % 2 ? Math.sin(a / 2) : Math.cos(a / 2)));
  return [
    sr * cp * cy - cr * sp * sy,
    cr * sp * cy + sr * cp * sy,
    cr * cp * sy - sr * sp * cy,
    cr * cp * cy + sr * sp * sy,
  ];
}

function readStl(path) {
  const data = readFileSync(path);
  const count = data.readUInt32LE(80);
  if (84 + count * 50 !== data.length) throw new Error(`${path}: not a binary STL`);
  const positions = new Float32Array(count * 9);
  for (let i = 0; i < count; i += 1) {
    const offset = 84 + i * 50 + 12; // skip the facet normal
    for (let k = 0; k < 9; k += 1) positions[i * 9 + k] = data.readFloatLE(offset + k * 4);
  }
  return positions;
}

// Named materials declared at the top level of <robot>.
const materials = new Map();
for (const match of urdf.matchAll(/<material\b([^>]*)>([\s\S]*?)<\/material>/g)) {
  const rgba = match[2].match(/<color\b[^>]*>/)?.[0];
  if (attr(match[1], "name") && rgba) materials.set(attr(match[1], "name"), vec(attr(rgba, "rgba")));
}

const doc = new Document();
const buffer = doc.createBuffer();
const scene = doc.createScene("robot");
const gltfMaterials = new Map();
let inputTriangles = 0;

for (const match of urdf.matchAll(/<link\b([^>]*[^/])>([\s\S]*?)<\/link>/g)) {
  const link = attr(match[1], "name");
  const visual = match[2].match(/<visual\b[\s\S]*?<\/visual>/)?.[0];
  const meshTag = visual?.match(/<mesh\b[^>]*>/)?.[0];
  if (!link || !meshTag) continue;
  const filename = attr(meshTag, "filename");
  if (!/\.stl$/i.test(filename)) {
    console.warn(`skip ${link}: ${filename} is not STL`);
    continue;
  }
  const meshPath = resolve(dirname(urdfPath), filename.replace(/^package:\/\//, ""));
  const positions = readStl(meshPath);
  inputTriangles += positions.length / 9;

  const scale = vec(attr(meshTag, "scale"), [1, 1, 1]);
  for (let i = 0; i < positions.length; i += 1) positions[i] *= scale[i % 3];

  const materialTag = visual.match(/<material\b[\s\S]*?(?:\/>|<\/material>)/)?.[0];
  const inline = materialTag?.match(/<color\b[^>]*>/)?.[0];
  const rgba = (inline && vec(attr(inline, "rgba"))) ?? materials.get(materialTag && attr(materialTag, "name")) ?? [0.8, 0.8, 0.82, 1];
  const key = rgba.map((v) => v.toFixed(3)).join(",");
  if (!gltfMaterials.has(key)) {
    gltfMaterials.set(
      key,
      doc.createMaterial(`rgba(${key})`).setBaseColorFactor(rgba).setMetallicFactor(0.15).setRoughnessFactor(0.55),
    );
  }

  const position = doc.createAccessor().setType("VEC3").setArray(positions).setBuffer(buffer);
  const primitive = doc.createPrimitive().setAttribute("POSITION", position).setMaterial(gltfMaterials.get(key));
  const mesh = doc.createMesh(link).addPrimitive(primitive);
  const origin = visual.match(/<origin\b[^>]*>/)?.[0];
  const node = doc
    .createNode(link)
    .setMesh(mesh)
    .setTranslation(vec(origin && attr(origin, "xyz"), [0, 0, 0]))
    .setRotation(quatFromRpy(vec(origin && attr(origin, "rpy"), [0, 0, 0])));
  scene.addChild(node);
}

await MeshoptSimplifier.ready;
await MeshoptEncoder.ready;
doc.createExtension(EXTMeshoptCompression).setRequired(true);
doc.createExtension(KHRMeshQuantization).setRequired(true);
await doc.transform(
  weld(),
  simplify({ simplifier: MeshoptSimplifier, ratio: RATIO, error: ERROR }),
  prune(),
  meshopt({ encoder: MeshoptEncoder, level: "high" }),
);

let outputTriangles = 0;
for (const mesh of doc.getRoot().listMeshes()) {
  for (const primitive of mesh.listPrimitives()) outputTriangles += primitive.getIndices().getCount() / 3;
}

const io = new NodeIO().registerExtensions([EXTMeshoptCompression, KHRMeshQuantization]).registerDependencies({
  "meshopt.encoder": MeshoptEncoder,
});
mkdirSync(dirname(outPath), { recursive: true });
const glb = await io.writeBinary(doc);
writeFileSync(outPath, glb);

// The meshes are a modified (simplified) version of the source's design files:
// ship its license and a note next to them.
const license = join(dirname(urdfPath), "..", "LICENSE");
copyFileSync(license, outPath.replace(/\.glb$/, ".LICENSE.txt"));

console.log(
  `${scene.listChildren().length} links, ${inputTriangles.toLocaleString()} -> ${outputTriangles.toLocaleString()} triangles, ` +
    `${(glb.byteLength / 1e6).toFixed(2)} MB -> ${outPath}`,
);
