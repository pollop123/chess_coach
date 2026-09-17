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
