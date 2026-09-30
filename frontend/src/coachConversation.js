function positionKey(fen) {
  return typeof fen === "string" ? fen.split(" ").slice(0, 4).join(" ") : null;
}

export function buildCoachConversation(messages, fen) {
  const current = positionKey(fen);
  return messages
    .filter((message) => (
      current && positionKey(message.fen) === current && message.text?.trim()
      && !message.error && ["user", "model"].includes(message.role)
    ))
    .slice(-8)
    .map((message) => ({
      role: message.role,
      text: message.text.slice(0, 1500),
      fen: message.fen,
      mode: message.mode || "position"
    }));
}

// Source tags such as [L1][T1] stay in the API text for other clients, but
// beginners read the answer without them; "查看依據" lists the sources instead.
const SOURCE_TAGS = /[ \t]*\[[A-Z]\d{1,2}\]/g;

export function coachDisplayText(text, hasSources) {
  return hasSources && typeof text === "string" ? text.replace(SOURCE_TAGS, "") : text;
}
