import { afterEach, describe, expect, it, vi } from "vitest";
import { streamReview } from "./reviewStream";

afterEach(() => vi.unstubAllGlobals());
function response(text) {
  const bytes = new TextEncoder().encode(text);
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new ReadableStream({
    start(controller) {
      // Split every byte, including Chinese multibyte characters and JSON lines.
      for (const byte of bytes) controller.enqueue(new Uint8Array([byte]));
      controller.close();
    },
  }))));
}
describe("review stream", () => {
  it("decodes fragmented progress and returns only the completed evidence", async () => {
    response('{"type":"progress","phase":"quick","current":1,"total":2}\n{"type":"complete","review_id":"token","engine":"測試","rows":[]}');
    const progress = vi.fn();
    const signal = new AbortController().signal;
    const result = await streamReview("/review_game", { pgn: "1. e4" }, signal, progress);
    expect(progress).toHaveBeenCalledWith(expect.objectContaining({ current: 1 }));
    expect(result.engine).toBe("測試");
    expect(fetch).toHaveBeenCalledWith("/review_game", expect.objectContaining({ signal }));
  });
  it("rejects a truncated review instead of publishing partial results", async () => {
    response('{"type":"progress","current":1}\n');
    await expect(streamReview("/review_game", {}, undefined, vi.fn())).rejects.toThrow("連線中斷");
  });
  it("surfaces worker failures", async () => {
    response('{"type":"error","message":"分析超時"}\n');
    await expect(streamReview("/review_game", {}, undefined, vi.fn())).rejects.toThrow("分析超時");
  });
  it("surfaces a missing engine before reading the stream", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response('{"detail":"Stockfish 未安裝"}', { status: 503 })));
    await expect(streamReview("/review_game", {}, undefined, vi.fn())).rejects.toThrow("Stockfish 未安裝");
  });
});
