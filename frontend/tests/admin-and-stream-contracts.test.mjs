import test from "node:test";
import assert from "node:assert/strict";
import { access, readFile } from "node:fs/promises";
import path from "node:path";

const ROOT = path.resolve(process.cwd());

async function read(relPath) {
  return readFile(path.join(ROOT, relPath), "utf-8");
}

async function exists(relPath) {
  try {
    await access(path.join(ROOT, relPath));
    return true;
  } catch {
    return false;
  }
}

test("auth context does not force JSON content-type for FormData", async () => {
  const content = await read("lib/auth-context.tsx");
  assert.match(content, /isFormData/);
  assert.match(content, /!isFormData/);
});

test("root route sends users to the workbench", async () => {
  const content = await read("app/page.tsx");
  assert.match(content, /redirect\("\/engagements"\)/);
});

test("retired project-studio routes stay removed", async () => {
  for (const route of ["app/projects", "app/v2", "app/customize", "app/memory", "app/tasks", "app/permissions"]) {
    assert.equal(await exists(route), false, `${route} should not exist`);
  }
});
