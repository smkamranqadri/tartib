/**
 * Re-runs the UI checks slices 23, 24 and 25 proved once and then threw away, and since
 * 2026-09-22 the fixes after v2.0 (F1, F2) and slices 31 to 33.
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
      // The page clips horizontal overflow, so a control pushed off the side scrolls nothing and
      // the check above cannot see it. A space's header held four and lost Delete that way.
      await page.goto(`${URL}/spaces/${space}`);
      await page.locator(".title-actions").waitFor({ timeout: 8000 });
      const off = await page.evaluate(() =>
        [...document.querySelectorAll(".title-actions button")]
          .filter((b) => b.getBoundingClientRect().right > document.documentElement.clientWidth + 1)
          .map((b) => b.textContent.trim()),
      );
      if (off.length) throw new Error(`off screen on a space: ${off.join(", ")}`);
      return "4 screens, and a space's controls on screen";
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

        // Clear asks first, in the modal (slice 31): nothing is cleared until it is confirmed.
        await page.locator(".house-rules-foot button.ghost").dispatchEvent("click");
        await page.locator("dialog.modal[open]").waitFor({ timeout: 5000 });
        if (!(await api(page, "GET", "/api/config")).house_rules)
          throw new Error("cleared before it was confirmed");
        await page.locator("dialog.modal[open] button.danger").click();
        await page.waitForTimeout(700);
        if ((await api(page, "GET", "/api/config")).house_rules !== "")
          throw new Error("Clear did not clear");
        return "saved, persisted, asked, cleared";
      } finally {
        // Never leave someone's real filing rules changed by a check.
        await api(page, "PUT", "/api/config/house-rules", { text: before });
      }
    });

    // --- slice 29: what the AI has done ---
    await check("S29 the usage readout renders and stays honest", async () => {
      await page.goto(`${URL}/settings`);
      await page.waitForSelector(".pref", { timeout: 10000 });
      await page.waitForTimeout(900);
      const row = await page.evaluate(() => {
        const r = [...document.querySelectorAll(".pref")].find((x) =>
          x.textContent.includes("What it has done"),
        );
        return r ? r.querySelector(".pref-ctl").innerText.replace(/\s+/g, " ").trim() : null;
      });
      if (!row) throw new Error("no usage row on Settings");
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      if (overflow > 1) throw new Error(`settings overflows by ${overflow}px`);
      // Until the token arithmetic is reconciled against a real call, no money may appear.
      const { cost_verified } = await api(page, "GET", "/api/usage");
      if (!cost_verified && /[$£€]/.test(row)) throw new Error("showed an unverified cost");
      return row.slice(0, 60);
    });

    // --- fixes after v2.0, proved once by hand on 2026-09-22 and kept here so they stay fixed ---
    await check("F1 a save does not reload the note in a space's split view", async () => {
      // Every save bumps `version`, which refetches the open item; ItemPage showed its skeleton
      // for that, which unmounted the editor mid-sentence (c91fbf9).
      const wide = await browser.newContext({ viewport: { width: 1400, height: 900 } });
      const desk = await wide.newPage();
      try {
        await desk.request.post(`${URL}/api/login`, { data: { password: PASSWORD } });
        await desk.goto(`${URL}/spaces/${space}?item=${note.id}`);
        await desk.locator(".split-item .text-body .md").waitFor({ timeout: 10000 });
        await desk.evaluate(() => {
          window.__skeleton = 0;
          new MutationObserver(() => {
            if (document.querySelector(".split-item .skeleton")) window.__skeleton++;
          }).observe(document.body, { subtree: true, childList: true });
        });
        await desk.locator(".split-item .md p").last().click();
        await desk.locator(".split-item .cm-editor").waitFor({ timeout: 8000 });
        await desk.keyboard.press("End");
        await desk.keyboard.type(" saved");
        await desk.waitForTimeout(3500);
        const skeletons = await desk.evaluate(() => window.__skeleton);
        const open = await desk.locator(".split-item .cm-editor").count();
        if (skeletons || !open) throw new Error(`skeleton ${skeletons}x, editor open ${open}`);
        const text = (await api(desk, "GET", `/api/items/${note.id}`)).raw_text;
        if (!text.endsWith(" saved")) throw new Error("the edit did not reach the server");
        return "no skeleton, editor open, saved";
      } finally {
        await wide.close();
      }
    });

    await check("F2 a checklist box ticks where it is drawn", async () => {
      const list = await api(page, "POST", "/api/items", {
        shape: "note",
        space,
        text: "UI check list\n\n- [ ] first\n- [ ] second\n\n```\n- [ ] not a box\n```",
      });
      made.push(list.id);
      await page.goto(`${URL}/items/${list.id}`);
      const boxes = page.locator(".text-body .md li.md-task > input");
      await boxes.first().waitFor({ timeout: 8000 });
      await boxes.nth(1).tap();
      await page.waitForTimeout(1500);
      const text = (await api(page, "GET", `/api/items/${list.id}`)).raw_text;
      if (!text.includes("- [ ] first\n- [x] second")) throw new Error(JSON.stringify(text));
      if (!text.includes("- [ ] not a box")) throw new Error("ticked inside a code block");
      if (await page.locator(".cm-editor").count()) throw new Error("the tap opened the editor");
      return "second box ticked, code untouched";
    });

    // --- slice 31: the first line is the title ---
    await check("S31 the title is shown once, as a title", async () => {
      const titled = await api(page, "POST", "/api/items", {
        shape: "task",
        space,
        text: "UI check title\n\nthe words under it",
      });
      made.push(titled.id);
      await page.goto(`${URL}/items/${titled.id}`);
      await page.locator(".text-body .md").waitFor({ timeout: 8000 });
      const seen = await page.evaluate(() => {
        const card = document.querySelector(".text-body").closest(".card");
        return {
          times: card.innerText.split("UI check title").length - 1,
          styled: document.querySelector(".text-body .md-title")?.textContent ?? null,
          heading: !!document.querySelector(".item-title"),
        };
      });
      if (seen.times !== 1) throw new Error(`shown ${seen.times} times`);
      if (seen.styled !== "UI check title") throw new Error(`title line is ${seen.styled}`);
      if (seen.heading) throw new Error("the old heading is back");
      return "once, styled";
    });

    // --- slice 31: every question asks in a modal ---
    await check("S31 delete asks in a modal; Escape keeps the item", async () => {
      const doomed = await api(page, "POST", "/api/items", { shape: "note", space, text: "UI check delete" });
      made.push(doomed.id);
      await page.goto(`${URL}/items/${doomed.id}`);
      const del = page.locator(".item-aside button.danger", { hasText: "Delete" });
      await del.waitFor({ timeout: 8000 });
      await del.tap();
      const modal = page.locator("dialog.modal[open]");
      await modal.waitFor({ timeout: 5000 });
      const box = await modal.locator(".modal-panel").boundingBox();
      const vw = page.viewportSize().width;
      if (box.x < 15 || box.x + box.width > vw - 15) throw new Error(`panel at ${box.x}+${box.width} of ${vw}`);
      const small = await modal.locator("button").evaluateAll((bs) =>
        bs.filter((b) => Math.min(b.getBoundingClientRect().width, b.getBoundingClientRect().height) < 44).length,
      );
      if (small) throw new Error(`${small} modal button(s) under 44px`);
      await page.keyboard.press("Escape");
      await page.waitForTimeout(300);
      if (await page.locator("dialog.modal[open]").count()) throw new Error("Escape did not close it");
      const still = await page.evaluate((id) => fetch(`/api/items/${id}`).then((r) => r.status), doomed.id);
      if (still !== 200) throw new Error("Escape deleted it");
      await del.tap();
      await page.locator("dialog.modal[open] button.danger").click();
      await page.waitForTimeout(800);
      const gone = await page.evaluate((id) => fetch(`/api/items/${id}`).then((r) => r.status), doomed.id);
      if (gone !== 404) throw new Error(`after confirming: ${gone}`);
      return "asked, Escape kept it, confirm deleted it";
    });

    // --- slice 32: Pick for me ---
    // The AI is stubbed at the network: this checks the button, the modal and Today refilling,
    // not the model, and a UI run must not spend quota. The stub stars a real task the way a pick
    // would, so Today's reload has something true to show. The endpoint has its own tests.
    await check("S32 Pick for me asks in a modal and Today refills", async () => {
      const undated = await api(page, "POST", "/api/items", { shape: "task", space, text: "UI check pick" });
      made.push(undated.id);
      let sent = null;
      await page.route("**/api/pick", async (route) => {
        sent = JSON.parse(route.request().postData() || "{}");
        const item = await (await page.request.patch(`${URL}/api/items/${undated.id}`, { data: { starred: true } })).json();
        await route.fulfill({ json: { picks: [{ item, reason: "stub" }] } });
      });
      await page.goto(`${URL}/`);
      const open = page.locator(".area-today .card-aside button", { hasText: "Pick for me" });
      await open.waitFor({ timeout: 8000 });
      const head = await page.locator(".area-today .card-head").boundingBox();
      const btn = await open.boundingBox();
      if (btn.x + btn.width > head.x + head.width + 1) throw new Error("button overflows the card head");
      if (Math.min(btn.width, btn.height) < 44) throw new Error(`button ${btn.width}x${btn.height}`);
      await open.tap();
      const modal = page.locator("dialog.modal[open]");
      await modal.waitFor({ timeout: 5000 });
      await modal.locator("input.pick-steer").fill("an hour");
      await modal.locator("button.primary", { hasText: "Pick" }).click();
      await page.locator(".area-today", { hasText: "UI check pick" }).waitFor({ timeout: 8000 });
      await page.unroute("**/api/pick");
      if (await page.locator("dialog.modal[open]").count()) throw new Error("the modal stayed open");
      if (sent?.steer !== "an hour") throw new Error(`sent ${JSON.stringify(sent)}`);
      return "modal, steer sent, picked task on Today";
    });

    // --- slice 33: links between items ---
    await check("S33 a link opens its target, a missing one dims, the target lists it", async () => {
      const stamp = Date.now();
      const target = await api(page, "POST", "/api/items", { shape: "note", space, text: `UI link target ${stamp}` });
      made.push(target.id);
      const source = await api(page, "POST", "/api/items", {
        shape: "note",
        space,
        text: `UI link source ${stamp}\n\nsee [[UI link target ${stamp}]] and [[UI link nowhere ${stamp}]]`,
      });
      made.push(source.id);
      await page.goto(`${URL}/items/${source.id}`);
      const link = page.locator(".text-body a.md-link");
      await link.waitFor({ timeout: 8000 });
      if ((await link.getAttribute("href")) !== `/items/${target.id}`) throw new Error(`href ${await link.getAttribute("href")}`);
      const missing = page.locator(".text-body .md-link-missing");
      if ((await missing.count()) !== 1) throw new Error("the missing link is not dimmed");
      const [fg, bg] = await link.evaluate((el) => {
        let e = el;
        let c = "rgba(0, 0, 0, 0)";
        while (e && c.startsWith("rgba(0, 0, 0, 0)")) {
          c = getComputedStyle(e).backgroundColor;
          e = e.parentElement;
        }
        return [getComputedStyle(el).color, c];
      });
      const ratio = contrast(rgb(fg), rgb(bg));
      if (ratio < 4.5) throw new Error(`link contrast ${ratio.toFixed(2)}:1`);
      await link.tap();
      await page.waitForURL(`**/items/${target.id}`, { timeout: 8000 });
      if (await page.locator(".cm-editor").count()) throw new Error("the tap opened the editor");
      const from = page.locator(".linked-from .rows li");
      await from.first().waitFor({ timeout: 8000 });
      if (!(await from.first().innerText()).includes(`UI link source ${stamp}`)) throw new Error("Linked from misses the source");
      return `opened, missing dimmed, listed back, ${ratio.toFixed(2)}:1`;
    });

    await check("S33 [[ offers items and writes the link", async () => {
      const stamp = Date.now();
      const target = await api(page, "POST", "/api/items", { shape: "task", space, text: `Picker target ${stamp}` });
      made.push(target.id);
      const note = await api(page, "POST", "/api/items", { shape: "note", space, text: `Picker note ${stamp}` });
      made.push(note.id);
      await page.goto(`${URL}/items/${note.id}`);
      await page.locator(".text-body .md").waitFor({ timeout: 8000 });
      await page.locator(".text-body .md").tap();
      const editor = page.locator(".cm-content");
      await editor.waitFor({ timeout: 8000 });
      await page.keyboard.press("End");
      await page.keyboard.type(` [[Picker target ${String(stamp).slice(0, 6)}`);
      const option = page.locator(".cm-tooltip-autocomplete li", { hasText: `Picker target ${stamp}` });
      await option.waitFor({ timeout: 8000 });
      const detail = await page.locator(".cm-tooltip-autocomplete li").first().innerText();
      if (!detail.includes(space)) throw new Error(`no space shown: ${detail}`);
      await option.click();
      // The autosave waits for a pause, then the network: poll rather than guess how long.
      let text = "";
      for (let i = 0; i < 20 && !text.endsWith(`[[Picker target ${stamp}]]`); i++) {
        await page.waitForTimeout(250);
        text = (await api(page, "GET", `/api/items/${note.id}`)).raw_text;
      }
      if (!text.endsWith(`[[Picker target ${stamp}]]`)) throw new Error(JSON.stringify(text));
      return "offered with its space, inserted, saved";
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
