export type JobStatus = "queued" | "processing" | "succeeded" | "failed";

export interface Job {
  id: string;
  document_id: string;
  status: JobStatus;
  capability: "cpu" | "gpu";
  attempt_count: number;
  error?: { code: string; message: string } | null;
  created_at: string;
  finished_at?: string | null;
}

export interface Submission {
  created: boolean;
  document: { id: string; source_name: string; size_bytes: number; status: string };
  job: Job;
}

export type CanonicalResult = Record<string, unknown> & {
  document_id?: string;
  source_name?: string;
  pages?: Array<Record<string, unknown>>;
  extractions?: Array<Record<string, unknown>>;
};

export class ApiError extends Error {
  constructor(message: string, readonly status: number) {
    super(message);
  }
}

export class DzDocClient {
  constructor(
    private readonly apiKey: string,
    private readonly baseUrl = import.meta.env.VITE_DZDOC_API_URL || "/api",
  ) {}

  private async request<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${this.baseUrl.replace(/\/$/, "")}${path}`, {
      ...init,
      headers: {
        ...(this.apiKey ? { Authorization: `Bearer ${this.apiKey}` } : {}),
        ...init?.headers,
      },
    });
    if (!response.ok) {
      const payload = await response.json().catch(() => ({ detail: response.statusText }));
      throw new ApiError(String(payload.detail ?? "Request failed"), response.status);
    }
    return response.json() as Promise<T>;
  }

  health(): Promise<{ status: string }> {
    return this.request("/healthz");
  }

  listJobs(): Promise<{ items: Job[] }> {
    return this.request("/v1/jobs");
  }

  getJob(jobId: string): Promise<Job> {
    return this.request(`/v1/jobs/${jobId}`);
  }

  getResult(documentId: string): Promise<CanonicalResult> {
    return this.request(`/v1/documents/${documentId}/result`);
  }

  upload(file: File, idempotencyKey = crypto.randomUUID()): Promise<Submission> {
    const body = new FormData();
    body.append("file", file);
    return this.request("/v1/documents", {
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
