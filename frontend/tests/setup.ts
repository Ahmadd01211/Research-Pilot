import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup, configure } from '@testing-library/react';
afterEach(cleanup);
// Lazy routes load slower when the whole suite runs in parallel; 1 s default was flaky.
configure({ asyncUtilTimeout: 4000 });

if (!HTMLDialogElement.prototype.showModal) {
  HTMLDialogElement.prototype.showModal = function () { this.open = true; };
  HTMLDialogElement.prototype.close = function () { this.open = false; };
}
