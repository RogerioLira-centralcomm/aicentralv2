import { getJob } from "./api.js";

export async function waitJob(jobId, onTick) {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const job = await getJob(jobId);
    onTick?.(job);
    if (job.status === "done" || job.status === "failed") {
      return job;
    }
    await new Promise((resolve) => setTimeout(resolve, 700));
  }
  throw new Error("A análise ainda está rodando.");
}
