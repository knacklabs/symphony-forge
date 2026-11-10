import type { Page } from '@playwright/test';

export type ProblemKind = 'overflow' | 'cut-text' | 'contrast' | 'wrong-screen';

export interface ScreenCheck {
  /** The screen's address, for example `/orders`. */
  path: string;
  /** Also check at 375 pixels. Set it only when the app needs a phone view. */
  phone?: boolean;
  /** Set aside one kind of problem for this screen. Without a reason it does nothing. */
  waive?: { kind: ProblemKind; reason: string };
}

/** Opens the screen, reports each problem on its own `Rendered problem:` line and throws if there is one. */
export function checkScreen(page: Page, screen: ScreenCheck): Promise<void>;
