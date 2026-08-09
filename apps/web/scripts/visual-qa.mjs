import { mkdir, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const baseUrl = process.env.DZDOC_WEB_URL ?? "http://127.0.0.1:5173";
const output = new URL("../test-results/visual/", import.meta.url);
await mkdir(output, { recursive: true });

const browser = await chromium.launch({
  executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  headless: true,
});
const results = [];

for (const profile of [
  { name: "desktop", viewport: { width: 1440, height: 1000 } },
  { name: "mobile", viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true },
]) {
  const context = await browser.newContext(profile);
  for (const route of [
    { name: "landing", path: "/" },
    { name: "platform", path: "/app" },
  ]) {
    const page = await context.newPage();
    const errors = [];
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    page.on("pageerror", (error) => errors.push(error.message));
    const response = await page.goto(`${baseUrl}${route.path}`, { waitUntil: "domcontentloaded", timeout: 20_000 });
    await page.waitForTimeout(800);
    const title = await page.locator("h1").first().textContent({ timeout: 3_000 }).catch(() => null);
    if (!title) errors.push(`missing h1: ${(await page.locator("body").innerText()).slice(0, 240)}`);
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
    await page.screenshot({ path: fileURLToPath(new URL(`${route.name}-${profile.name}-final.png`, output)), fullPage: route.name === "landing", timeout: 15_000 });
    if (profile.name === "mobile" && route.name === "platform") {
      await page.getByRole("button", { name: "Evidence" }).click();
      await page.getByRole("heading", { name: "Review evidence" }).waitFor();
      await page.waitForTimeout(350);
      await page.screenshot({ path: fileURLToPath(new URL("platform-mobile-evidence-final.png", output)), timeout: 15_000 });
    }
    results.push({ profile: profile.name, route: route.path, status: response?.status(), title, overflow, errors });
    await page.close();
  }
  await context.close();
}

await browser.close();
await writeFile(new URL("results.json", output), JSON.stringify(results, null, 2));
console.log(JSON.stringify(results, null, 2));
if (results.some((result) => result.status !== 200 || result.overflow || result.errors.length)) process.exitCode = 1;
