export async function streamReview(url, payload, signal, onProgress) {
  const response = await fetch(url, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload), signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(typeof error.detail === "string" ? error.detail : "分析服務暫時無法使用。");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = null;
  function consume(line) {
    if (!line.trim()) return;
    const event = JSON.parse(line);
    if (event.type === "error") throw new Error(event.message || "分析未完成。");
    if (event.type === "progress") onProgress(event);
    if (event.type === "complete") completed = event;
  }
  try {
    while (true) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (buffer.length > 5000000) throw new Error("分析回應過大。");
      let end;
      while ((end = buffer.indexOf("\n")) >= 0) {
        consume(buffer.slice(0, end)); buffer = buffer.slice(end + 1);
      }
      if (done) break;
    }
    consume(buffer);
    if (!completed || !Array.isArray(completed.rows) || !completed.review_id) throw new Error("分析連線中斷，請重新分析。");
    return completed;
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock(); }
}
