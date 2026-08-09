export type JobStatus = "queued" | "processing" | "succeeded" | "failed";

export interface Job {
  id: string;
  document_id: string;
  status: JobStatus;
  source_name?: string;
  created_at: string;
}

export class DzDocClient {
  constructor(
    private readonly apiKey: string,
    private readonly baseUrl = "http://127.0.0.1:8000",
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers: { Authorization: `Bearer ${this.apiKey}`, ...init?.headers },
    });
    if (!response.ok) throw new Error((await response.json()).detail ?? "Request failed");
    return response.json() as Promise<T>;
  }

  listJobs(): Promise<{ items: Job[] }> {
    return this.request("/v1/jobs");
  }

  upload(file: File, idempotencyKey = crypto.randomUUID()) {
    const body = new FormData();
    body.append("file", file);
    return this.request<{ job: Job }>("/v1/documents", {
      method: "POST",
      headers: { "Idempotency-Key": idempotencyKey },
      body,
    });
  }

  correct(documentId: string, targetId: string, previousText: string, correctedText: string) {
    return this.request(`/v1/documents/${documentId}/corrections`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_id: targetId, previous_text: previousText, corrected_text: correctedText }),
    });
  }
}
