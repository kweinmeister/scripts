# Google Cloud Developer Plugin — Evaluation Dataset

This directory contains the golden evaluation dataset (`evals.json`) used to benchmark AI coding agents equipped with the [Google Cloud Developer Plugin](https://cloud.google.com/blog/topics/developers-practitioners/introducing-the-google-cloud-developer-plugin-for-ai-coding-agents).

The benchmark measures agent performance across five core dimensions: **Security**, **Correctness**, **Discoverability**, **Effectiveness**, and **Efficiency** using [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator) and [Harbor](https://github.com/avast/harbor) sandboxes.

---

## Dataset Format & Schema

The dataset adheres to the [Agent Skills specification](https://agentskills.io) (`evals/evals.json`) natively supported by [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator).

### Schema Specification

```json
{
  "skill_name": "<plugin-or-skill-identifier>",
  "evals": [
    {
      "id": "<unique-case-identifier>",
      "prompt": "<task-prompt-given-to-agent>",
      "expected_output": "<high-level-ground-truth-description>",
      "assertions": [
        "<verifiable-assertion-1>",
        "<verifiable-assertion-2>"
      ],
      "expected_skill": "<primary-target-skill>",
      "acceptable_skills": [
        "<alternative-acceptable-skill-1>",
        "<alternative-acceptable-skill-2>"
      ]
    }
  ]
}
```

### Field Definitions

| Field | Type | Description |
| :--- | :--- | :--- |
| `skill_name` | `string` | Target skill or plugin identifier under evaluation. |
| `evals` | `array` | List of test scenario objects. |
| `id` | `string` | Unique identifier for the scenario (e.g. `gcd-001-explicit-auth`). |
| `prompt` | `string` | The exact prompt provided to the agent in an isolated sandbox. |
| `expected_output` | `string` | Qualitative summary of the correct solution or operational configuration. |
| `assertions` | `array[string]` | Specific, testable criteria scored by the LLM-as-judge (`gemini-3.8-flash`). |
| `expected_skill` | `string` | The primary skill expected to trigger for discoverability and routing evaluation. |
| `acceptable_skills` | `array[string]` | Secondary skills that receive routing credit if invoked by the agent. |

---

## Evaluation Scenarios Matrix ($N=12$)

The scenarios span all four canonical evaluation buckets defined in SkillEvaluator:

| Case ID | Bucket | Target Skill | Scenario Intent | Key Rubric Assertions |
| :--- | :--- | :--- | :--- | :--- |
| **`gcd-001`** | Explicit | `google-cloud-recipe-auth` | Cloud Run batch job authentication to Cloud Storage. | Enforces User-Managed Service Account (UMSA), attaches via `--service-account`, grants `roles/storage.objectViewer`, warns against JSON keys and default compute service accounts. |
| **`gcd-002`** | Explicit | `gcloud` | Cloud Storage volume mounting + Secret Manager injection in Cloud Run. | Specifies `--add-volume` (`type=cloud-storage`, `readonly=true`), mount path, and `--update-secrets`/`--set-secrets`. |
| **`gcd-003`** | Contextual | `gcloud` | Headless CI/CD configuration and non-interactive account switching. | Uses `--format=json`/`--format=value`, named configurations via `gcloud config configurations activate`, and `--quiet`/headless safeguards. |
| **`gcd-004`** | Explicit | `retrieving-developer-knowledge` | Architecture and flag guidance for workloads running > 60 minutes. | Identifies 60-minute hard ceiling on Cloud Run services, recommends Cloud Run Jobs, specifies `--task-timeout` up to 168 hours. |
| **`gcd-005`** | Implicit | `finding-google-skills` | Querying official skill catalog index for BigQuery, GKE, and Spanner skills. | Queries official repository index (`skills.sh`), specifies standard naming conventions (`gke-*`, `spanner-basics`, `bigquery-basics`). |
| **`gcd-006`** | Contextual | `gcloud` | Listing unattached persistent disks with server-side filtering. | Enforces `--project`, applies server-side filter `--filter="-users:*"`, uses `--format="table(name, zone, sizeGb)"`. |
| **`gcd-007`** | Explicit | `google-cloud-recipe-auth` | Least-privilege service-level invoker IAM binding. | Uses `gcloud run services add-iam-policy-binding` on specific service (not project-wide), assigns `roles/run.invoker`. |
| **`gcd-008`** | Contextual | `retrieving-developer-knowledge` | Architectural patterns for continuous 24/7 background queue consumers. | Identifies Cloud Run Worker Pools for always-on non-HTTP processing; contrasts with request-driven services and jobs. |
| **`gcd-009`** | Explicit | `google-cloud-recipe-auth` | Cross-project Secret Manager IAM access. | Grants `roles/secretmanager.secretAccessor` directly on the secret resource in vault project to runtime service account. |
| **`gcd-010`** | Contextual | `gcloud` | Safe batch deletion of Compute Engine instances. | Enforces positional arguments for delete, mandates non-destructive preview via list, requires explicit human confirmation gate. |
| **`gcd-011`** | Contextual | `google-cloud-recipe-auth` | Resolving Application Default Credentials (ADC) errors without JSON keys. | Warns against downloadable service account keys; recommends `gcloud auth application-default login` or service account impersonation (`roles/iam.serviceAccountTokenCreator`). |
| **`gcd-012`** | Contextual | `google-cloud-recipe-onboarding` | Structured onboarding workflow with safety gates and collision handling. | Gathers parameters in structured table, enforces confirmation gate before resource creation, resolves project ID collision with randomized suffix. |

---

## Evaluation Methodology

In the study, these scenarios were run across two experimental arms:
- **Baseline (Arm A)**: Claude Code (`claude-sonnet-5`) without plugin skills.
- **Treatment (Arm B)**: Claude Code (`claude-sonnet-5`) with the Google Cloud Developer Plugin mounted.

Each scenario was evaluated with $k=3$ repeated independent trials ($N=72$ total trials) inside isolated Kubernetes pods on **GKE Autopilot** with **Workload Identity Federation**. Output trajectories were graded by **Gemini 3.8 Flash** hosted on Vertex AI using the 5-dimension rubric defined in the assertions.

### Running with SkillEvaluator

To run this dataset against a local skill or plugin bundle:

```bash
skillevaluator evaluate ./plugin/google-cloud-developer \
  --agents claude-code \
  --agent-model claude-code=claude-sonnet-5 \
  --env-mode gke \
  --n-concurrent 2 \
  --results-dir ./reports/tier3/
```

> **Note**: Execution with `--env-mode gke` relies on upstream SkillEvaluator improvements currently in review. For local execution without GKE, you can run using standard container environments (e.g. `--env-mode docker`).

---

## References

- [Agent Skills Specification](https://agentskills.io)
- [NVIDIA SkillEvaluator](https://github.com/NVIDIA/SkillEvaluator)
- [Google Cloud Developer Plugin Announcement](https://cloud.google.com/blog/topics/developers-practitioners/introducing-the-google-cloud-developer-plugin-for-ai-coding-agents)
- [Official Antigravity Plugin Codelab](https://g.dev/cloud/agent-plugins-codelab-agy)
- [Official Google Cloud Skills Catalog (`skills.sh`)](https://skills.sh/google/skills)
