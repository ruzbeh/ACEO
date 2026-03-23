const REPLICATE_API_URL = "https://api.replicate.com/v1";

interface Prediction {
  id: string;
  status: "starting" | "processing" | "succeeded" | "failed" | "canceled";
  output: string | string[] | null;
  error: string | null;
}

function getHeaders(): HeadersInit {
  const token = process.env.REPLICATE_API_TOKEN;
  if (!token) {
    throw new Error("REPLICATE_API_TOKEN is not set");
  }
  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

/**
 * Create a new prediction (generation job) on Replicate.
 */
export async function createPrediction(
  model: string,
  input: Record<string, unknown>
): Promise<Prediction> {
  const [owner, name] = model.split("/");

  const res = await fetch(`${REPLICATE_API_URL}/models/${owner}/${name}/predictions`, {
    method: "POST",
    headers: getHeaders(),
    body: JSON.stringify({ input }),
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(`Replicate API error: ${res.status} ${err.detail || ""}`);
  }

  return res.json();
}

/**
 * Fetch the current state of a prediction by ID.
 */
export async function getPrediction(id: string): Promise<Prediction> {
  const res = await fetch(`${REPLICATE_API_URL}/predictions/${id}`, {
    headers: getHeaders(),
  });

  if (!res.ok) {
    throw new Error(`Failed to fetch prediction: ${res.status}`);
  }

  return res.json();
}

/**
 * Poll a prediction until it reaches a terminal state (succeeded, failed, canceled).
 * Polls every 2 seconds, times out after 5 minutes.
 */
export async function waitForPrediction(
  id: string,
  timeoutMs: number = 300_000
): Promise<Prediction> {
  const start = Date.now();

  while (Date.now() - start < timeoutMs) {
    const prediction = await getPrediction(id);

    if (["succeeded", "failed", "canceled"].includes(prediction.status)) {
      return prediction;
    }

    await new Promise((resolve) => setTimeout(resolve, 2000));
  }

  throw new Error("Prediction timed out");
}
