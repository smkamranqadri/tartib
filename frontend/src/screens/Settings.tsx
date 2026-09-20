import type React from "react";
import { useEffect, useState } from "react";
import { getConfig, logout } from "../api";
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
          <button type="button" className="ghost" onClick={() => logout().then(onSignedOut)}>
            Sign out
          </button>
        </Row>
      </Card>
    </div>
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
    <div className="seg">
      {SOUNDS.map((s) => (
        <button key={s.value} type="button" className={sound === s.value ? "on" : ""} onClick={() => choose(s.value)}>
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

function Row({ title, desc, children }: { title: string; desc: string; children: React.ReactNode }) {
  return (
    <div className="pref">
      <div className="pref-text">
        <span className="pref-title">{title}</span>
        <span className="pref-desc muted">{desc}</span>
      </div>
      <div className="pref-ctl">{children}</div>
    </div>
  );
}
