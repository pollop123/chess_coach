import { coachDisplayText } from "./coachConversation";

export function CoachMessage({ message }) {
  const sources = Array.isArray(message.sources) ? message.sources : [];
  return (
    <div className={`chat-bubble ${message.role === "user" ? "is-user" : "is-model"}`}>
      <div>{coachDisplayText(message.text, sources.length > 0)}</div>
      {sources.length > 0 ? (
        <details className="coach-sources">
          <summary>查看依據（{sources.length}）</summary>
          <ul>
            {sources.map((source) => (
              <li key={source.id}>
                <strong>[{source.id}] {source.title}</strong>
                <span> · {source.kind === "knowledge" ? "一般棋理" : "本局分析"}</span>
                <p>{source.text}</p>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
