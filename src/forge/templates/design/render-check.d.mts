export type ProblemKind = 'overflow' | 'cut-text' | 'low-contrast';

export interface ScreenCheck {
  /** The screen's short name, which each line of the result starts with. */
  name: string;
  /** The screen's address, for example `/orders`. It is the address the page ends on, after any redirect. */
  path: string;
  /** Also check at 375 pixels. Set it only when the app needs a phone view. */
  phone?: boolean;
  /** Set aside one kind of problem for this screen, with the reason. A reason with no words does nothing. */
  waive?: Partial<Record<ProblemKind, string>>;
}

/** What the check uses of a Playwright `Page`. This file imports nothing, so it compiles wherever it is kept. */
export interface ScreenPage {
  goto(url: string): Promise<{ ok(): boolean; status(): number } | null>;
  waitForLoadState(state: 'networkidle', options?: { timeout?: number }): Promise<void>;
  url(): string;
  setViewportSize(size: { width: number; height: number }): Promise<void>;
  emulateMedia(options: { colorScheme: 'light' | 'dark' }): Promise<void>;
  evaluate(pageFunction: () => unknown): Promise<unknown>;
}

/** Opens the screen, writes each problem on its own `Rendered problem:` line and throws if there is one. */
export function checkScreen(page: ScreenPage, screen: ScreenCheck): Promise<void>;
