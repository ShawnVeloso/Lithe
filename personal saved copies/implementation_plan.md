# F-05 — Basic Task Execution (Function Calling)

Enable Lithe to interact with the local filesystem by exposing basic OS functions (rename, move) as tools to the Gemini model. Crucially, these tools will enforce the permission rule: destructive operations require the safeword override.

---

## Proposed Changes

### 1. Tool Definitions

#### [NEW] [tools.py](file:///d:/Lithe/src/backend/tools.py)
A new module containing the functions exposed to the LLM.
- **`rename_file(source: str, destination: str, safeword_active: bool) -> str`**:
  - Checks `safeword_active`.
  - If `False`, returns: `"ERROR: User permission required. Tell the user you cannot execute this without the safeword 'Override Lithe'."`
  - If `True`, performs `os.rename(source, destination)` and returns `"SUCCESS: File renamed."`
- **`delete_file(path: str, safeword_active: bool) -> str`**:
  - Similar logic, but uses `os.remove()`.

*Note: Since Gemini doesn't know about `safeword_active` (it's internal backend state), the tools exposed to Gemini will be dynamically wrapped in `brain.py` so the LLM doesn't have to provide the `safeword_active` argument itself.*

---

### 2. Tool Execution Loop

#### [MODIFY] [brain.py](file:///d:/Lithe/src/backend/brain.py)
Update the `chat()` function to handle the function calling loop required by the `google-genai` SDK.
- Import the tools from `tools.py`.
- Wrap the tools to automatically inject the current `safeword_active` status.
- Update `GenerateContentConfig` to include the `tools` list.
- **Execution Loop**:
  1. Call `generate_content` with the user prompt and tools.
  2. If the response contains `function_calls` (e.g., Gemini decided to call `rename_file`):
     - Execute the called Python function with the provided arguments.
     - Build a list of `function_response` parts.
     - Append the model's `function_call` message and the `function_response` message to the `contents` history array.
     - Call `generate_content` a second time so the LLM can generate a final human-readable response based on the tool's output.
  3. Return the final text response to the user.

#### [MODIFY] [prompts/system_prompt.py](file:///d:/Lithe/src/backend/prompts/system_prompt.py)
- Update `CANDID_SYSTEM_PROMPT` to instruct the LLM on tool usage.
  - *"You have access to tools that can modify the filesystem. If a tool returns a permission error, you must explain to the user that they need to authorize the action by repeating their request with the safeword 'Override Lithe'."*

---

## Design Decisions

> [!IMPORTANT]
> **Stateless Tool Execution**
> Because `server.py` and `brain.py` do not maintain chat history between HTTP requests, if the LLM needs permission, it will tell the user to use the safeword. The user must then say "Override Lithe, rename file X to Y". The backend will process this entirely new message, detect the safeword, and execute the tool successfully in one pass. This guarantees security without requiring complex backend session state.

> [!TIP]
> **Dynamic Tool Wrapping**
> The `google-genai` SDK infers tool schemas from Python function signatures. To prevent the LLM from trying to pass `safeword_active=True` itself (trying to bypass security), we will define standard functions for the LLM (e.g., `def rename(source: str, destination: str)`), and map them to internal functions that have access to the `safeword_active` variable via closures in `brain.py`.

---

## Open Questions

1. **Tool Scope**: For F-05, I plan to add `rename_file` and `delete_file`. Should I also include a `move_file` or `create_directory` tool, or keep it strictly to those two for this milestone?

---

## Verification Plan

### Automated
- Create `test.txt`. Send a prompt to `brain.chat("Rename test.txt to test_renamed.txt")`. Assert that the file is *not* renamed and the response asks for the safeword.
- Send a prompt to `brain.chat("Override Lithe, rename test.txt to test_renamed.txt")`. Assert that the file *is* renamed and the response confirms it.

### Manual
- Run the Electron app, use the Chat UI to ask Lithe to rename a file, observe the permission pushback, and then authorize it with the safeword.
