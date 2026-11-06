export interface SSEFrame<T = unknown> {
  event: string;
  data: T;
}

export async function consumeSSE<T = unknown>(
  response: Response,
  onFrame: (frame: SSEFrame<T>) => void
): Promise<void> {
  if (!response.body) throw new Error("当前浏览器不支持流式响应");
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  const dispatch = (rawFrame: string) => {
    let event = "message";
    const dataLines: string[] = [];
    for (const line of rawFrame.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      if (line.startsWith("data:")) dataLines.push(line.slice(5).trimStart());
    }
    if (!dataLines.length) return;
    onFrame({ event, data: JSON.parse(dataLines.join("\n")) as T });
  };

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let boundary = buffer.indexOf("\n\n");
    while (boundary >= 0) {
      const frame = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      if (frame.trim()) dispatch(frame);
      boundary = buffer.indexOf("\n\n");
    }
  }
  buffer += decoder.decode();
  if (buffer.trim()) dispatch(buffer.replace(/\r\n/g, "\n"));
}
