import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../hooks/useAuth';

export default function Login() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('Admin@123');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(e) {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await login(username, password);
      navigate('/', { replace: true });
    } catch (err) {
      setError(err.message || 'Login failed');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login-wrap">
      <div className="login-card">
        <div className="login-brand">
          <div className="brand-logo" style={{ width: 42, height: 42, fontSize: 18 }}>CP</div>
          <div>
            <div className="login-title">CYBERPULSE AI</div>
            <div className="brand-sub">Cybercrime Intelligence</div>
          </div>
        </div>
        <div className="login-sub">Sign in to the fusion-cell command center. Proactive cash-withdrawal threat prediction for I4C &amp; banking fraud cells.</div>
        <form onSubmit={submit}>
          <label className="field">
            <span className="lbl">Username</span>
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoFocus autoComplete="username" />
          </label>
          <label className="field">
            <span className="lbl">Password</span>
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" />
          </label>
          <button className="btn btn-primary" style={{ width: '100%', justifyContent: 'center', padding: '11px' }} disabled={busy}>
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
          <div className="login-error">{error}</div>
        </form>
        <div className="login-hint">Prototype · validated on synthetic data</div>
      </div>
    </div>
  );
}