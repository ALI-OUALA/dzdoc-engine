export type DzDocJob = {
  id: string;
  document_id: string;
  status: "queued" | "processing" | "succeeded" | "failed";
};

export class DzDocError extends Error {
  constructor(public readonly status: number, message: string) {
    super(message);
  }
}

export class DzDocClient {
  constructor(private readonly apiKey: string, private readonly baseUrl = "http://127.0.0.1:8000") {}

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${this.apiKey}`, ...init.headers },
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({})) as { detail?: string };
      throw new DzDocError(response.status, body.detail ?? "DzDoc request failed");
    }
    return response.status === 204 ? undefined as T : response.json() as Promise<T>;
  }

  jobs() { return this.request<{ items: DzDocJob[] }>("/v1/jobs"); }
  job(id: string) { return this.request<DzDocJob>(`/v1/jobs/${id}`); }
  result<T = unknown>(documentId: string) { return this.request<T>(`/v1/documents/${documentId}/result`); }

  upload(file: Blob, filename: string, idempotencyKey = crypto.randomUUID()) {
    const body = new FormData();
    body.append("file", file, filename);
    return this.request<{ job: DzDocJob }>("/v1/documents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body,
    });
  }

  correct(documentId: string, targetId: string, previousText: string, correctedText: string, reason?: string) {
    return this.request(`/v1/documents/${documentId}/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: targetId, previous_text: previousText, corrected_text: correctedText, reason }),
    });
  }

  delete(documentId: string) {
    return this.request<void>(`/v1/documents/${documentId}`, { method: "DELETE" });
  }
}
