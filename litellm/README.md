# LiteLLM Proxy for Vertex AI Model Garden

This directory contains the configuration to run [LiteLLM](https://github.com/BerriAI/litellm) as a local proxy, providing seamless access to your favorite models from the [Vertex AI Model Garden](https://cloud.google.com/model-garden).

This setup allows you to use OpenAI-compatible clients and tools (like VS Code extensions such as Cline, Roo Code, or Continue.dev) to interact with a variety of models (e.g., Qwen3 Coder) without changing your workflow. For a detailed walkthrough, see the original article: [Build with your Favorite Models from the Vertex AI Model Garden with LiteLLM](https://medium.com/@kweinmeister/build-with-your-favorite-models-from-the-vertex-ai-model-garden-with-litellm-0b140bf52a01).

## Key Files

- [`config.yaml`](config.yaml): Configures the LiteLLM proxy. It defines which Vertex AI models are available, sets up response caching with Redis, and specifies a master key for authenticating to the local proxy.
- [`ai.litellm.proxy.plist`](ai.litellm.proxy.plist): A macOS `launchd` agent that runs the LiteLLM proxy as a persistent background service. It ensures the proxy starts automatically on login and restarts if it ever stops.

## Prerequisites

Before you begin, ensure your local machine is set up for Google Cloud development.

1. **Install Google Cloud CLI:**

   ```bash
   brew install gcloud
   ```

1. **Authenticate with Google Cloud:**
   This command will open a browser for you to log in.

   ```bash
   gcloud auth application-default login
   ```

1. **Set IAM Permissions:**
   Grant your user account permissions to call the Vertex AI endpoint. Replace `your-gcp-project-id` and `your-email@example.com`.

   ```bash
   gcloud projects add-iam-policy-binding your-gcp-project-id \
     --member="user:your-email@example.com" \
     --role="roles/aiplatform.user"
   ```

1. **Enable APIs:**
   Enable the Vertex AI API and the specific model you wish to use.

   ```bash
   gcloud services enable aiplatform.googleapis.com
   ```

   Then, visit the model's page in the Vertex AI Model Garden (e.g., Qwen3 Coder) and click **Enable**.

1. **Install Local Dependencies:**
   Install `uv` (a Python package manager) and `redis` for caching.

   ```bash
   brew install uv redis
   brew services start redis
   ```

## Configuration

The provided [`config.yaml`](config.yaml) is pre-configured to use models from Vertex AI.

1. **Update Project ID:** In [`config.yaml`](config.yaml), replace the placeholder `my-gcp-project-id` with your actual Google Cloud Project ID.
1. **Customize Master Key:** For local use, the default `master_key` is acceptable. For any shared environment, replace `sk-litellm-master-key` with a secure, randomly generated key.

## Running the Proxy

You can run the proxy for a quick test or set it up as a persistent background service.

### Test Run

Execute the following command in your terminal to start the proxy with detailed logging:

```bash
uvx --with google-cloud-aiplatform 'litellm[proxy]' --config ~/.config/litellm/config.yaml --detailed_debug
```

*Note: This command assumes the `config.yaml` is located at `~/.config/litellm/config.yaml`. Adjust the path if you place it elsewhere.*

### Persistent Service (macOS)

The [`ai.litellm.proxy.plist`](ai.litellm.proxy.plist) file is designed to manage the proxy as a background service.

1. **Place the Files:**

   - Copy [`config.yaml`](config.yaml) to `~/.config/litellm/config.yaml`.
   - Copy [`ai.litellm.proxy.plist`](ai.litellm.proxy.plist) to `~/Library/LaunchAgents/ai.litellm.proxy.plist`. Create the directory if it doesn't exist.

1. **Load the Service:**
   This command loads the agent and starts the proxy. It will also run automatically on future logins.

   ```bash
   launchctl load -w ~/Library/LaunchAgents/ai.litellm.proxy.plist
   ```

1. **Manage the Service:**

   - **Unload:** `launchctl unload ~/Library/LaunchAgents/ai.litellm.proxy.plist`
   - **Restart:** `launchctl unload ... && launchctl load -w ...`
   - **Check Logs:** `tail -f ~/Library/Logs/litellm/litellm.stdout.log`

## Connecting a Client

Once the proxy is running, configure your AI client (e.g., Cline in VS Code) with the following settings:

- **API Provider:** `LiteLLM` or `OpenAI-Compatible`
- **Base URL:** `http://0.0.0.0:4000`
- **API Key:** The `master_key` from your `config.yaml`.
- **Model:** The `model_name` you wish to use (e.g., `qwen3-coder`).
