import { Component, type ReactNode } from 'react';
export class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() { return { failed: true }; }
  render() {
    return this.state.failed ? <main className="center"><section className="card"><h1>We couldn’t open this page.</h1><p className="muted">Reload to try again. Saved account data remains on the server.</p><button className="btn primary" onClick={() => window.location.reload()}>Reload application</button></section></main> : this.props.children;
  }
}
