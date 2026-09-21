/**
 * Re-runs the UI checks slices 23, 24 and 25 proved once and then threw away.
 *
 *     TARTIB_PASSWORD=... node frontend/tools/ui/check.mjs [--url http://localhost:8000] [--head]
 *
 * Every slice so far built a harness like this in a scratch directory and binned it, so nothing
 * could re-run an earlier slice's checks. That is how slice 24's conflict strip reached a phone
 * 430px wide: its own checks never had a conflict on screen, and slice 25's harness was the
 * first thing able to look. This one is committed, so slice 27 can run slice 23's checks.
 *
 * It needs the app running (docker compose up -d --build) and the password in the environment.
 * It creates its own items through the API and deletes them again, so it can run against a
 * database you care about -- but it is a check, not a test fixture: point it at local.
 */
import { chromium } from "playwright-core";

const arg = (name, fallback) => {
  const i = process.argv.indexOf(`--${name}`);
  return i === -1 ? fallback : process.argv[i + 1];
};
const URL = arg("url", process.env.TARTIB_URL || "http://localhost:8000");
const PASSWORD = process.env.TARTIB_PASSWORD;
const HEADED = process.argv.includes("--head");
const PHONE = { width: 390, height: 844 };

const results = [];
const record = (id, ok, note = "") => {
  results.push({ id, ok, note });
  console.log(`${ok ? "  ok" : "FAIL"}  ${id}${note ? `  -- ${note}` : ""}`);
};
/** A check that throws is a failed check, not a crashed run: the rest still tell you something. */
async function check(id, fn) {
  try {
    const note = await fn();
    record(id, true, note || "");
  } catch (e) {
    record(id, false, String(e.message || e).split("\n")[0].slice(0, 160));
  }
}

const srgb = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
const luminance = ([r, g, b]) =>
  0.2126 * srgb(r / 255) + 0.7152 * srgb(g / 255) + 0.0722 * srgb(b / 255);
const contrast = (a, b) => {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
};
const rgb = (s) => s.match(/\d+(\.\d+)?/g).slice(0, 3).map(Number);

/** The api, as the app itself calls it: same cookie, same origin. */
const api = (page, method, path, body) =>
  page.evaluate(
    ([m, p, b]) =>
      fetch(p, {
        method: m,
        headers: b ? { "Content-Type": "application/json" } : undefined,
        body: b ? JSON.stringify(b) : undefined,
      }).then((r) => (r.status === 204 ? null : r.json())),
    [method, path, body ?? null],
  );

async function main() {
  if (!PASSWORD) throw new Error("TARTIB_PASSWORD is not set");
  const browser = await chromium.launch({ channel: "chrome", headless: !HEADED });
  const context = await browser.newContext({ viewport: PHONE, hasTouch: true, isMobile: true });
  const page = await context.newPage();
  const made = [];

  try {
    await page.goto(URL);
    await page.fill('input[type="password"]', PASSWORD);
    await page.click('button[type="submit"]');
    // nav.pills is the desktop nav and is present but zero-height on a phone; .app is the shell.
    await page.waitForSelector(".app", { timeout: 15000 });
    if (await page.locator('input[type="password"]').count()) throw new Error("login failed");

    const spaces = (await api(page, "GET", "/api/spaces")).spaces;
    const space = spaces.find((s) => s && s !== "Unfiled") || spaces[0];
    const note = await api(page, "POST", "/api/items", {
      shape: "note",
      space,
      text: "UI check note\n\nA **bold** word and a second line.",
    });
    made.push(note.id);
    // A star only renders on a task row (ItemRow: `isTask && editable`), so the offline-edit
    // check needs one of each.
    const task = await api(page, "POST", "/api/items", {
      shape: "task",
      space,
      text: "UI check task",
      due: new Date(Date.now() + 864e5).toISOString().slice(0, 10),
    });
    made.push(task.id);

    // --- slice 23: the UI language ---
    await check("S23 body text clears 4.5:1 on its own surface", async () => {
      await page.goto(`${URL}/items/${note.id}`);
      await page.waitForSelector(".item, main");
      const pair = await page.evaluate(() => {
        const el = document.querySelector("main p, main .item, main");
        const bgOf = (n) => {
          for (let e = n; e; e = e.parentElement) {
            const c = getComputedStyle(e).backgroundColor;
            if (c && !c.startsWith("rgba(0, 0, 0, 0)")) return c;
          }
          return getComputedStyle(document.body).backgroundColor;
        };
        return [getComputedStyle(el).color, bgOf(el)];
      });
      const ratio = contrast(rgb(pair[0]), rgb(pair[1]));
      if (ratio < 4.5) throw new Error(`${ratio.toFixed(2)}:1`);
      return `${ratio.toFixed(2)}:1`;
    });

    await check("S23 muted text clears 4.5:1", async () => {
      const ratios = await page.evaluate(() => {
        const bgOf = (n) => {
          for (let e = n; e; e = e.parentElement) {
            const c = getComputedStyle(e).backgroundColor;
            if (c && !c.startsWith("rgba(0, 0, 0, 0)")) return c;
          }
          return getComputedStyle(document.body).backgroundColor;
        };
        return [...document.querySelectorAll(".muted")]
          .slice(0, 8)
          .map((el) => [getComputedStyle(el).color, bgOf(el)]);
      });
      if (!ratios.length) return "no muted text on this screen";
      const worst = Math.min(...ratios.map(([c, b]) => contrast(rgb(c), rgb(b))));
      if (worst < 4.5) throw new Error(`worst ${worst.toFixed(2)}:1`);
      return `worst ${worst.toFixed(2)}:1`;
    });

    // --- slice 22/25: the phone ---
    await check("S22 no horizontal scroll at 390px", async () => {
      for (const path of ["/", "/inbox", "/spaces", `/items/${note.id}`]) {
        await page.goto(URL + path);
        await page.waitForTimeout(250);
        const over = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        if (over > 1) throw new Error(`${path} overflows by ${over}px`);
      }
      return "4 screens";
    });

    await check("S22 tap targets reach 44px", async () => {
      await page.goto(`${URL}/inbox`);
      await page.waitForTimeout(400);
      const small = await page.evaluate(() => {
        const out = [];
        for (const el of document.querySelectorAll("button, a, input[type=checkbox], .tap-box")) {
          const r = el.getBoundingClientRect();
          if (r.width === 0 || r.height === 0) continue;
          const box = el.closest(".tap-box") || el;
          const b = box.getBoundingClientRect();
          if (Math.min(b.width, b.height) < 44)
            out.push(`${el.tagName.toLowerCase()} ${Math.round(b.width)}x${Math.round(b.height)}`);
        }
        return out.slice(0, 4);
      });
      if (small.length) throw new Error(small.join(", "));
      return "none under 44px";
    });

    // --- slice 24: presentation and the editor you tap into ---
    await check("S24 markdown renders as markup, not asterisks", async () => {
      await page.goto(`${URL}/items/${note.id}`);
      await page.waitForSelector("strong, .markdown", { timeout: 8000 });
      const bold = await page.locator("strong", { hasText: "bold" }).count();
      if (!bold) throw new Error("no <strong> for **bold**");
      return "<strong> present";
    });

    await check("S24 tapping the text opens the editor", async () => {
      await page.goto(`${URL}/items/${note.id}`);
      await page.waitForSelector("strong, .markdown", { timeout: 8000 });
      const target = page.locator(".markdown, main p").first();
      // The ask bar and the tab bar are fixed over the foot of a list, and force:true still
      // dispatches at the element's coordinates. dispatchEvent is what lands (knowledge, s25).
      await target.dispatchEvent("click");
      await page.waitForSelector(".cm-content, textarea", { timeout: 8000 });
      return "editor open";
    });

    // --- slice 25: offline ---
    await check("S25 a cold start offline still shows data", async () => {
      await page.goto(`${URL}/`);
      await page.waitForTimeout(1200); // let the worker cache the api responses
      const fresh = await context.newPage();
      await context.setOffline(true);
      try {
        await fresh.goto(`${URL}/`);
        await fresh.waitForTimeout(1500);
        const text = await fresh.evaluate(() => document.body.innerText);
        if (/Can't reach Tartib|Failed to fetch/i.test(text)) throw new Error("screen is an error");
        if (!/ago|offline/i.test(text)) throw new Error("no line saying how old this is");
        return "data and a stale line";
      } finally {
        await context.setOffline(false);
        await fresh.close();
      }
    });

    await check("S25 an edit made offline says it is waiting", async () => {
      // The star lives on a row, not on the item page. Exact labels: "Start session" also
      // contains "tar", which a looser locator happily matched.
      await page.goto(`${URL}/inbox/recent`);
      await page.waitForSelector(".item-row, main", { timeout: 8000 });
      await page.waitForTimeout(600);
      await context.setOffline(true);
      try {
        const star = page.locator('[aria-label="Star"], [aria-label="Unstar"]').first();
        // A check that cannot find its control has checked nothing. Saying "ok" here is how a
        // suite quietly stops testing what it claims to.
        if (!(await star.count())) throw new Error("no star control on the recent list");
        await star.dispatchEvent("click");
        await page.waitForTimeout(800);
        const text = await page.evaluate(() => document.body.innerText);
        if (!/waiting to send/i.test(text)) throw new Error("no 'waiting to send'");
        return "queued and said so";
      } finally {
        await context.setOffline(false);
        await page.waitForTimeout(1200); // let the queue drain before the next check
      }
    });
    // --- slice 27: the house rules editor ---
    await check("S27 house rules save, persist and clear", async () => {
      const before = (await api(page, "GET", "/api/config")).house_rules;
      try {
        await page.goto(`${URL}/settings`);
        await page.waitForSelector(".house-rules textarea", { timeout: 10000 });
        const overflow = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        if (overflow > 1) throw new Error(`settings overflows by ${overflow}px`);
        const small = await page.evaluate(() =>
          [...document.querySelectorAll(".house-rules-foot button")]
            .map((b) => b.getBoundingClientRect())
            .filter((r) => Math.min(r.width, r.height) < 44).length,
        );
        if (small) throw new Error(`${small} control(s) under 44px`);

        await page.fill(".house-rules textarea", "UI check rule: the car goes in home.");
        await page.locator(".house-rules-foot button.primary").dispatchEvent("click");
        await page.waitForTimeout(700);
        await page.reload();
        await page.waitForSelector(".house-rules textarea", { timeout: 10000 });
        const saved = await page.inputValue(".house-rules textarea");
        if (!saved.includes("the car goes in home")) throw new Error("did not persist a reload");

        await page.locator(".house-rules-foot button.ghost").dispatchEvent("click");
        await page.waitForTimeout(700);
        if ((await api(page, "GET", "/api/config")).house_rules !== "")
          throw new Error("Clear did not clear");
        return "saved, persisted, cleared";
      } finally {
        // Never leave someone's real filing rules changed by a check.
        await api(page, "PUT", "/api/config/house-rules", { text: before });
      }
    });

  } finally {
    for (const id of made) await api(page, "DELETE", `/api/items/${id}`).catch(() => {});
    await browser.close();
  }

  const failed = results.filter((r) => !r.ok);
  console.log(`\n${results.length - failed.length}/${results.length} checks passed`);
  if (failed.length) process.exit(1);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
