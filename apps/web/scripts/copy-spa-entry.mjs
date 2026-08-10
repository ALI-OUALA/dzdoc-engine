import { copyFile, mkdir } from "node:fs/promises";

const appDirectory = new URL("../dist/app/", import.meta.url);

await mkdir(appDirectory, { recursive: true });
await copyFile(new URL("../dist/index.html", import.meta.url), new URL("index.html", appDirectory));
