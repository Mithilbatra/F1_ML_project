// @ts-check
const { test, expect } = require("@playwright/test");

const TABS = [
  ["dashboard", "Season"],
  ["weekend", "Race weekend"],
  ["races", "Race results"],
  ["standings", "Championship standings"],
  ["telemetry", "Telemetry"],
  ["strategy", "Strategy"],
  ["model", "Model performance"],
  ["predict", "Race prediction"],
  ["fantasy", "Fantasy optimiser"],
  ["raceline", "Racing line"],
  ["console", "Console"],
];

/** Attach console-error / pageerror collectors to a page. */
function collectErrors(page) {
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(`console: ${m.text()}`); });
  page.on("pageerror", (e) => errors.push(`pageerror: ${e.message}`));
  return errors;
}

test.describe("Pit Wall dashboard", () => {
  test("every tab switches, renders its heading, and throws no errors", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/");
    // The dashboard hydrates from the API; wait for real content, not the shell.
    await expect(page.locator("#dash-stats .stat")).not.toHaveCount(0);

    for (const [view, heading] of TABS) {
      await page.locator(`.tab[data-view="${view}"]`).click();
      const section = page.locator(`#view-${view}`);
      await expect(section).toBeVisible();
      // The dashboard h1 is rewritten to "2025 season" once data loads, so match
      // case-insensitively rather than against the static markup.
      await expect(section.locator("h1")).toContainText(new RegExp(heading, "i"));
    }

    expect(errors, `Unexpected page/console errors:\n${errors.join("\n")}`).toEqual([]);
  });

  test("core data views load real content", async ({ page }) => {
    await page.goto("/");

    // Standings: a full drivers table with clickable driver links.
    await page.locator('.tab[data-view="standings"]').click();
    await expect(page.locator("#standings-drivers tbody tr").first()).toBeVisible();
    await expect(page.locator("#standings-drivers .driver-link").first()).toBeVisible();

    // Model: the honest metrics render (top-3 hit rate vs the qualifying baseline).
    await page.locator('.tab[data-view="model"]').click();
    await expect(page.locator("#model-body")).not.toBeEmpty();
  });

  test("driver profile modal is keyboard accessible (open, Esc, focus return)", async ({ page }) => {
    await page.goto("/");
    await page.locator('.tab[data-view="standings"]').click();

    const link = page.locator("#standings-drivers .driver-link").first();
    await expect(link).toBeVisible();
    await link.focus();
    await page.keyboard.press("Enter");

    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible();
    await expect(dialog).toHaveAttribute("aria-modal", "true");

    await page.keyboard.press("Escape");
    await expect(dialog).toHaveCount(0);

    // Focus must return to the element that opened the dialog.
    await expect(link).toBeFocused();
  });

  // The telemetry scrubber is a live-FastF1 feature: comparing two laps needs the
  // full car_data channels, which may require a network fetch. When that data is
  // available the slider must be keyboard-operable; when it isn't (offline CI),
  // the test skips rather than flaking.
  test("telemetry scrubber responds to the keyboard", async ({ page }) => {
    test.setTimeout(120_000);
    await page.goto("/");
    await page.locator('.tab[data-view="telemetry"]').click();

    // Defaults populate to the latest season/round; just pick a session and run.
    await expect(page.locator("#tel-d1 option").first()).toBeVisible({ timeout: 60_000 })
      .catch(() => {});

    const d1 = page.locator("#tel-d1");
    const hasDrivers = await d1.locator("option").count();
    test.skip(hasDrivers < 2, "No telemetry session data available (offline).");

    await page.locator("#tel-run").click();

    // Wait for either the scrubber or a failure status; skip if the data didn't load.
    const slider = page.locator('[role="slider"]').first();
    const appeared = await slider.waitFor({ state: "visible", timeout: 90_000 })
      .then(() => true).catch(() => false);
    test.skip(!appeared, "Telemetry comparison did not produce a scrubber (no lap data).");

    await slider.focus();
    const before = await slider.getAttribute("aria-valuenow");
    await page.keyboard.press("ArrowRight");
    await expect
      .poll(async () => slider.getAttribute("aria-valuenow"))
      .not.toBe(before);

    // The live readout is announced through aria-valuetext.
    await expect(slider).toHaveAttribute("aria-valuetext", /.+/);
  });
});
