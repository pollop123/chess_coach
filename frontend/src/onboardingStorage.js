export const ONBOARDING_KEY = "chess-coach.onboarding.v1";

// What each answer to "你目前的程度是？" changes on the play screen.
export const LEVELS = {
  beginner: { botDifficulty: "newbie", importFirst: false, tips: true },
  player: { botDifficulty: "intermediate", importFirst: false, tips: false },
  chesscom: { botDifficulty: "intermediate", importFirst: true, tips: false },
};

export function loadOnboarding() {
  try {
    const saved = JSON.parse(window.localStorage.getItem(ONBOARDING_KEY) || "null");
    return saved && LEVELS[saved.level] ? { level: saved.level, tipsDismissed: Boolean(saved.tipsDismissed) } : null;
  } catch {
    return null;
  }
}

export function saveOnboarding(onboarding) {
  try {
    window.localStorage.setItem(ONBOARDING_KEY, JSON.stringify(onboarding));
  } catch {
    // Private windows can refuse storage; the choice then lasts for this visit only.
  }
}
