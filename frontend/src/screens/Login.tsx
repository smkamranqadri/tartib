import { useState, type FormEvent } from "react";
import { login } from "../api";

export default function Login({ onLoggedIn }: { onLoggedIn: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      onLoggedIn();
    } catch {
      setError("Wrong password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="login">
      <h1>Tartib</h1>
      <form onSubmit={submit}>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          placeholder="Password"
          autoFocus
          aria-label="Password"
        />
        <button type="submit" disabled={busy || !password}>
          Enter
        </button>
        {error && <p className="error">{error}</p>}
      </form>
    </main>
  );
}
