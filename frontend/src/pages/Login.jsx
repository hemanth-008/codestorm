/**
 * Login (Task C7)
 *
 * Basic login form that sets the JWT token.
 */
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, setToken } from '../api';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await login(username, password);
      if (res && res.access_token) {
        setToken(res.access_token);
        // We might want to store it in localStorage, but memory is fine for now
        navigate('/');
      } else {
        setError('Invalid response from server');
      }
    } catch (e) {
      setError(e.message);
    }
    setLoading(false);
  };

  return (
    <div style={{ display: 'flex', justifyContent: 'center', marginTop: 60 }}>
      <div className="panel" style={{ width: '100%', maxWidth: 400 }}>
        <div className="panel-head">
          <span>Authentication</span>
          <span className="tag">Auth</span>
        </div>
        <div className="panel-body">
          <form onSubmit={handleLogin} style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            <div>
              <div className="kpi-label">Username</div>
              <input 
                type="text" 
                className="counter"
                style={{ width: '100%', marginTop: 6, fontSize: 14, fontFamily: 'var(--mono)', borderRadius: 0, padding: 8 }}
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div>
              <div className="kpi-label">Password</div>
              <input 
                type="password" 
                className="counter"
                style={{ width: '100%', marginTop: 6, fontSize: 14, fontFamily: 'var(--mono)', borderRadius: 0, padding: 8 }}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            
            {error && <div className="mono-sm" style={{ color: 'var(--signal)' }}>{error}</div>}

            <button type="submit" className="btn" style={{ fontWeight: 'bold', padding: 12, marginTop: 8 }} disabled={loading}>
              {loading ? 'AUTHENTICATING...' : 'LOGIN'}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
