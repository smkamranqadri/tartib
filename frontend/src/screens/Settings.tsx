import type React from "react";
import { getConfig, logout } from "../api";
import { speechSupported } from "../Capture";
import Card from "../components/Card";
import { AlertIcon, HomeIcon, LayersIcon, SettingsIcon } from "../components/Icons";
import PageHead from "../components/PageHead";
import { useTheme } from "../theme";
import { useLoad } from "../useLoad";

export default function Settings({ onSignedOut }: { onSignedOut: () => void }) {
  const { theme, setTheme } = useTheme();
  const config = useLoad(getConfig, []).data;
  const standalone = window.matchMedia("(display-mode: standalone)").matches || (navigator as { standalone?: boolean }).standalone === true;

  return (
    <div className="screen">
      <PageHead eyebrow="Settings" title="Preferences" />
      <Card icon={<SettingsIcon />} label="Appearance" aside={<span className="muted">{theme}</span>}>
        <Row title="Theme" desc="Light or dark. Follows your system until you choose.">
          <div className="seg">
            <button type="button" className={theme === "light" ? "on" : ""} onClick={() => setTheme("light")}>
              Light
            </button>
            <button type="button" className={theme === "dark" ? "on" : ""} onClick={() => setTheme("dark")}>
              Dark
            </button>
          </div>
        </Row>
      </Card>
      <Card icon={<AlertIcon />} label="Classifier" aside={<span className="muted">{config ? (config.ai ? "on" : "off") : "…"}</span>}>
        <Row title="Codex CLI" desc="Files every capture in the background.">
          <span className="muted">{config ? (config.ai ? "enabled" : "off") : "…"}</span>
        </Row>
        <Row title="Claude fallback" desc="Used when Codex fails or hits its limit.">
          <span className="muted">{config ? (config.fallback ? "enabled" : "off") : "…"}</span>
        </Row>
        <Row title="Auto-file threshold" desc="Proposals at or above this confidence file without asking.">
          <span className="muted">{config ? `${Math.round(config.autofile_confidence * 100)}%` : "…"}</span>
        </Row>
      </Card>
      <Card icon={<HomeIcon />} label="Device">
        <Row title="Voice capture" desc="On-device speech recognition through the mic button.">
          <span className="muted">{speechSupported() ? "Available" : "Not in this browser"}</span>
        </Row>
        <Row title="Timezone" desc="Used for due dates, reminders, and today.">
          <span className="muted">{config?.tz ?? "…"}</span>
        </Row>
        <Row title="Installed" desc={standalone ? "Running as an app." : "Running in the browser. Add to your home screen for the app."}>
          <span className="muted">{standalone ? "app" : "browser"}</span>
        </Row>
      </Card>
      <Card icon={<LayersIcon />} label="Spaces" aside={<span className="muted">{config?.spaces.length ?? "…"}</span>}>
        <Row title="Configured spaces" desc="Set by TARTIB_SPACES in .env. The classifier files only into these.">
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
