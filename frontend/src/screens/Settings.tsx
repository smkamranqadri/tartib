import type React from "react";
import { ConfirmModal } from "../components/Modal";
import { useEffect, useState } from "react";
import { describe, getConfig, getUsage, logout, type QuotaWindow, setHouseRules } from "../api";
import { speechSupported } from "../Capture";
import { type ChimeSound, chimeSound, playChime, SOUNDS, setChimeSound } from "../chime";
import Card from "../components/Card";
import { AlertIcon, BellIcon, HomeIcon, LayersIcon, SettingsIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import { ErrorLine } from "../components/Status";
import {
  currentSubscription,
  disablePush,
  enablePush,
  type PushState,
  pushState,
  refreshWorker,
  resyncSubscription,
  workerVersion,
} from "../push";
import { useLoad } from "../useLoad";

export default function Settings({ onSignedOut }: { onSignedOut: () => void }) {
  const { data: config, error: configError, loading: configLoading, reload: reloadConfig } = useLoad(getConfig, []);
  // A config that failed to load must not read as one still loading: say why, and offer another go.
  const configFailed = !!configError && !config;
  const standalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;

  return (
    <div className="screen">
      <PageHead crumb="Settings" title="Settings" subtitle="How this copy of Tartib is set up." />
      {configFailed && (
        <div className="load-failed">
          <ErrorLine>{configError}</ErrorLine>
          <button type="button" className="ghost" disabled={configLoading} onClick={reloadConfig}>
            {configLoading ? "Retrying…" : "Retry"}
          </button>
        </div>
      )}
      <Card icon={<AlertIcon />} label="Classifier" aside={<span className="muted">{config ? (config.ai ? "on" : "off") : "…"}</span>}>
        <Row title="Codex CLI" desc="Files every capture in the background.">
          <span className="muted">{config ? (config.ai ? "enabled" : "off") : "…"}</span>
        </Row>
        <Row title="Auto-file threshold" desc="Proposals at or above this confidence file without asking.">
          <span className="muted">{config ? `${Math.round(config.autofile_confidence * 100)}%` : "…"}</span>
        </Row>
        <Row
          stack
          title="What it has done"
          desc="Every classifier and Ask call, since this started being recorded. Calls and tokens disagree when a call times out: it is killed before the CLI reports anything, so it spends the quota and reports nothing."
        >
          <AiUsageBlock />
        </Row>
        <Row
          title="Learning from"
          desc="Filings where you changed what the classifier proposed. It is shown these as examples; until there are some, it has nothing of yours to learn from."
        >
          <span className="muted">
            {config ? (config.corrections === 1 ? "1 correction" : `${config.corrections} corrections`) : "…"}
          </span>
        </Row>
        <Row
          stack
          title="House rules"
          desc="Your own filing rules, in your words. They are added to what the classifier already knows and outrank its own reading. They cannot change how it replies, so nothing you write here can stop captures filing."
        >
          {config && <HouseRules initial={config.house_rules} max={config.house_rules_max} onSaved={reloadConfig} />}
        </Row>
      </Card>
      <Card icon={<HomeIcon />} label="Device">
        <Row title="Voice capture" desc="On-device speech recognition through the mic button.">
          <span className="muted">{speechSupported() ? "Available" : "Not in this browser"}</span>
        </Row>
        <Row title="Session sound" desc="Plays in this tab when a session ends. Just this device.">
          <ChimeSwitch />
        </Row>
        <Row title="Timezone" desc="Used for due dates, reminders, and today.">
          <span className="muted">{config?.tz ?? "…"}</span>
        </Row>
        <Row title="Reminders worker" desc="The background script that shows a reminder when the app is closed.">
          <span className="muted">
            <WorkerVersion />
          </span>
        </Row>
        <Row title="Installed" desc={standalone ? "Running as an app." : "Running in the browser. Add to your home screen for the app."}>
          <span className="muted">{standalone ? "app" : "browser"}</span>
        </Row>
      </Card>
      <Reminders vapidPublic={config ? config.vapid_public : undefined} failed={configFailed} />
      <Card icon={<LayersIcon />} label="Spaces" aside={<span className="muted">{config?.spaces.length ?? "…"}</span>}>
        <Row title="Your spaces" desc="Create, rename, or delete them on the Spaces page. The classifier files only into these.">
          <span className="muted">{config?.spaces.join(" · ") ?? "…"}</span>
        </Row>
      </Card>
      <Card icon={<SettingsIcon />} label="Account">
        <Row title="Sign out" desc="Clears the session cookie on this device.">
          <SignOut onSignedOut={onSignedOut} />
        </Row>
      </Card>
    </div>
  );
}

/** Signing out is asked first (slice 31): on a phone it means typing the password again. */
function SignOut({ onSignedOut }: { onSignedOut: () => void }) {
  const [asking, setAsking] = useState(false);
  return (
    <>
      <button type="button" className="ghost" onClick={() => setAsking(true)}>
        Sign out
      </button>
      <ConfirmModal
        open={asking}
        question="Sign out of this device?"
        detail="You will need the password to come back in."
        confirmLabel="Sign out"
        danger={false}
        onConfirm={() => void logout().then(onSignedOut)}
        onCancel={() => setAsking(false)}
      />
    </>
  );
}

function ChimeSwitch() {
  const [sound, setSound] = useState<ChimeSound>(chimeSound);
  function choose(next: ChimeSound) {
    setChimeSound(next);
    setSound(next);
    void playChime(next); // a tap, so it plays even on iOS, and you hear what you chose
  }
  return (
    <div className="pills" role="group" aria-label="Chime sound">
      {SOUNDS.map((s) => (
        <button key={s.value} type="button" className={sound === s.value ? "active" : ""} aria-pressed={sound === s.value} onClick={() => choose(s.value)}>
          {s.label}
        </button>
      ))}
    </div>
  );
}

function WorkerVersion() {
  const [version, setVersion] = useState<string | undefined>(undefined);
  useEffect(() => {
    // Show what is installed straight away; an update check needs the network, and waiting
    // for it would leave this reading "…" exactly when someone is trying to read it.
    const read = () => workerVersion().then(setVersion);
    read();
    // An update finishes installing before the new worker activates and writes its version,
    // so the reading right after `update()` is the old one. Read again when it takes over.
    const onChange = () => read();
    if ("serviceWorker" in navigator) {
      navigator.serviceWorker.addEventListener("controllerchange", onChange);
    }
    refreshWorker().then(read);
    return () => {
      if ("serviceWorker" in navigator) {
        navigator.serviceWorker.removeEventListener("controllerchange", onChange);
      }
    };
  }, []);
  return <>{version ?? "…"}</>;
}

const WORDING: Record<PushState, string> = {
  loading: "Checking this browser and this install…",
  unsupported: "This browser cannot receive push notifications.",
  "no-key": "This copy of Tartib has no push key set up, so reminders cannot be turned on here.",
  default: "Reminders you set on a task, and one daily summary. Nothing else is ever sent.",
  granted: "Reminders you set on a task, and one daily summary. Nothing else is ever sent.",
  denied: "Notifications are blocked for this site. Browsers do not allow asking again, so this has to be undone in your browser's site settings.",
};

function Reminders({ vapidPublic, failed }: { vapidPublic: string | null | undefined; failed: boolean }) {
  const [state, setState] = useState<PushState>(() => pushState(vapidPublic));
  const [subscribed, setSubscribed] = useState<boolean | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (vapidPublic === undefined) return; // config still loading
    const next = pushState(vapidPublic);
    setState(next);
    // Granted: put the subscription back if the server lost it. Blocked: do not re-register
    // it, but still find out whether one exists, so it can be turned off from here.
    const look =
      next === "granted" && vapidPublic
        ? resyncSubscription(vapidPublic)
        : currentSubscription().then(Boolean);
    look.then(setSubscribed).catch(() => setSubscribed(false));
  }, [vapidPublic]);

  async function toggle(wanted: boolean) {
    setBusy(true);
    setError(null);
    try {
      if (wanted) {
        const next = await enablePush(vapidPublic as string);
        setState(next);
        setSubscribed(next === "granted");
      } else {
        await disablePush();
        setSubscribed(false);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "failed");
      // Never leave the card asserting a state the browser may not be in.
      setSubscribed(await currentSubscription().then(Boolean).catch(() => false));
    } finally {
      setBusy(false);
    }
  }

  const on = state === "granted" && subscribed === true;
  const canAsk = state === "default" || (state === "granted" && subscribed === false);
  // A blocked browser can still be holding a subscription the server is pushing into a void.
  // Leaving no way to drop it would strand that row for good.
  const canTurnOff = subscribed === true;
  // `granted` with `subscribed` still null means the resync call is in flight. Saying
  // "unavailable" there would be a lie told to exactly the people who have this switched on.
  const settling = state === "loading" || (state === "granted" && subscribed === null);
  // "off" wherever the button can turn it on -- including permission granted with no
  // subscription yet, which is otherwise indistinguishable from a browser that cannot do this.
  const aside = settling ? "…" : on ? "on" : state === "denied" ? "blocked" : canAsk ? "off" : "unavailable";

  return (
    <Card icon={<BellIcon />} label="Reminders" aside={<span className="muted">{aside}</span>}>
      {/* No control at all when there is nothing to press: the label and the description
          already say why, and repeating "blocked" in both columns is just noise. */}
      <Row title="Push notifications" desc={failed && state === "loading" ? "Can't tell until this install's settings load." : WORDING[state]}>
        {canAsk ? (
          <button type="button" className="primary" disabled={busy} onClick={() => toggle(true)}>
            {busy ? "Enabling…" : "Enable reminders"}
          </button>
        ) : canTurnOff ? (
          <button type="button" className="ghost" disabled={busy} onClick={() => toggle(false)}>
            {busy ? "Turning off…" : "Turn off"}
          </button>
        ) : null}
      </Row>
      {error ? <ErrorLine>{error}</ErrorLine> : null}
    </Card>
  );
}

/** `stack` puts the control under the text at full width, for anything wider than a value or a
 *  switch -- the theme list is the only one so far. */
/** "300 minutes" means nothing at a glance; "5 hour" does. */
function describeWindow(minutes: number): string {
  if (minutes >= 1440) return `${Math.round(minutes / 1440)} day`;
  if (minutes >= 60) return `${Math.round(minutes / 60)} hour`;
  return `${minutes} minute`;
}

/** What the AI has done. The cost is shown only once `cost_verified` says the arithmetic has
 *  been reconciled against a real call -- it was, on 2026-09-22 -- and it always says it is an
 *  estimate, because the subscription reports no cost at all and the rates are list prices. */
function AiUsageBlock() {
  const { data, error, loading } = useLoad(getUsage, []);
  if (loading && !data) return <span className="muted">…</span>;
  if (error || !data) return <ErrorLine>{error ?? "No usage recorded."}</ErrorLine>;
  if (!data.calls) return <span className="muted">Nothing recorded yet.</span>;
  const seconds = Math.round(data.duration_ms / 1000);
  /* Whichever window is fullest is the one about to stop you, so that is the one to show. */
  const windows = [data.quota?.primary, data.quota?.secondary].filter(
    (w): w is QuotaWindow => !!w && w.used_percent !== null,
  );
  const fullest = windows.sort((a, b) => (b.used_percent ?? 0) - (a.used_percent ?? 0))[0];
  const quota = fullest ? { ...fullest, used_percent: fullest.used_percent ?? 0 } : null;
  const perCapture = data.captures ? Math.round(data.total_tokens / data.captures) : 0;
  const perCaptureCost = data.captures ? (data.cost / data.captures).toFixed(4) : "0.0000";
  return (
    <div className="usage">
      <p>
        <b>{data.calls}</b> {data.calls === 1 ? "call" : "calls"} ·{" "}
        <b>{data.total_tokens.toLocaleString()}</b> tokens ·{" "}
        <b>{seconds}s</b> of waiting
      </p>
      {!!data.captures && (
        <p className="muted small">
          About {perCapture.toLocaleString()} tokens per capture, across {data.captures}.
        </p>
      )}
      {!!data.failed && (
        <p className="muted small">
          {data.failed} failed.
          {data.usage_limit.count > 0 && (
            <>
              {" "}
              {data.usage_limit.count} of them hit the subscription limit
              {data.usage_limit.resets_at ? `, last reporting a reset at ${data.usage_limit.resets_at}` : ""}.
            </>
          )}
        </p>
      )}
      {quota && (
        <p className={quota.used_percent >= 80 ? "quota tight" : "quota"}>
          Quota <b>{Math.round(quota.used_percent)}% used</b> of the{" "}
          {quota.window_minutes ? describeWindow(quota.window_minutes) : "current"} window
          {quota.resets_at ? `, resets ${quota.resets_at}` : ""}.
        </p>
      )}
      {data.cost_verified && (
        <p className="muted small">
          About <b>${data.cost.toFixed(4)}</b> at list price, or ${perCaptureCost} a capture. An
          estimate twice over: the subscription reports no cost at all, and these are list rates.
        </p>
      )}
      <p className="muted small">
        {data.model ? `Model ${data.model}.` : "No model pinned; the CLI chooses."}{" "}
        Most of each call is the CLI's own instructions, not yours.
      </p>
    </div>
  );
}

/** The house-rules editor. Saves on demand, not on every keystroke: this text is sent to the
 *  classifier on every capture, and a half-typed rule is worse than none. */
function HouseRules({ initial, max, onSaved }: { initial: string; max: number; onSaved: () => void }) {
  const [text, setText] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [clearing, setClearing] = useState(false);
  const dirty = text.trim() !== initial.trim();

  async function save(next: string) {
    setBusy(true);
    setMsg(null);
    try {
      const { house_rules } = await setHouseRules(next);
      setText(house_rules);
      setMsg(house_rules ? "Saved." : "Cleared.");
      onSaved();
    } catch (e) {
      setMsg(describe(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="house-rules">
      <textarea
        value={text}
        maxLength={max}
        rows={4}
        onChange={(e) => setText(e.target.value)}
        placeholder="Anything about the car goes in home, never finance."
        aria-label="House rules"
      />
      <div className="house-rules-foot">
        <span className="muted small">
          {text.length}/{max}
        </span>
        <button type="button" className="ghost" disabled={busy || !text} onClick={() => setClearing(true)}>
          Clear
        </button>
        <button type="button" className="primary" disabled={busy || !dirty} onClick={() => void save(text)}>
          {busy ? "Saving…" : "Save"}
        </button>
      </div>
      {msg && <p className="muted small">{msg}</p>}
      <ConfirmModal
        open={clearing}
        question="Clear your house rules?"
        detail="The classifier goes back to its own reading of where things belong. Nothing already filed moves."
        confirmLabel="Clear"
        busy={busy}
        onConfirm={() => {
          setClearing(false);
          void save("");
        }}
        onCancel={() => setClearing(false)}
      />
    </div>
  );
}

function Row({ title, desc, stack, children }: { title: string; desc: string; stack?: boolean; children: React.ReactNode }) {
  return (
    <div className={`pref ${stack ? "stacked" : ""}`}>
      <div className="pref-text">
        <span className="pref-title">{title}</span>
        <span className="pref-desc muted">{desc}</span>
      </div>
      <div className="pref-ctl">{children}</div>
    </div>
  );
}
