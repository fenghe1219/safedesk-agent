export class ApiRequestError extends Error {
  code: string;
  status: number;
  requestId?: string;

  constructor(message: string, code = "REQUEST_FAILED", status = 0, requestId?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.code = code;
    this.status = status;
    this.requestId = requestId;
  }
}

interface ClientRequestOptions extends RequestInit {
  csrfToken?: string;
}

export async function clientRequest<T>(path: string, options: ClientRequestOptions = {}): Promise<T> {
  const { csrfToken, ...init } = options;
  const headers = new Headers(init.headers);
  if (csrfToken) headers.set("X-CSRF-Token", csrfToken);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiRequestError("无法连接到服务，请稍后重试", "NETWORK_ERROR", 0);
  }

  if (response.status === 204) return undefined as T;

  const data = (await response.json().catch(() => null)) as
    | (T & { error?: { code?: string; message?: string; request_id?: string } })
    | null;

  if (!response.ok) {
    throw new ApiRequestError(
      data?.error?.message ?? "请求失败，请稍后重试",
      data?.error?.code ?? "REQUEST_FAILED",
      response.status,
      data?.error?.request_id
    );
  }

  return data as T;
}
