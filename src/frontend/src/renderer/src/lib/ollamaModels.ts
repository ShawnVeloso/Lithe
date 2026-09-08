// ---------------------------------------------------------------------------
// Which local models can actually request a tool.
//
// A model without native tool calling still gets every tool offered to it --
// Lithe disables nothing -- it just describes an action in prose instead of
// emitting a call. That is worth telling the user before they pick one, and
// worth telling them again on the status badge.
//
// This list lives here rather than in either component because it is needed in
// two places: the status badge and the settings picker. A hand-maintained
// second copy is the same shape as the declared-vs-dispatched tool-name bug
// that left 5 of 9 tools unreachable -- the copies agree right up until one is
// edited.
//
// It has to include the shipped default: llama3.2 is what OLLAMA_MODEL falls
// back to in config.py and what the capability evaluation is scored on, and the
// badge was once telling every default user their tools were dead. Note that
// llama3 (no point release) is deliberately absent -- tool calling arrived with
// llama3.1.
// ---------------------------------------------------------------------------
export const TOOL_CAPABLE_OLLAMA_MODELS = [
  'llama3.1',
  'llama3.2',
  'llama3.3',
  'mistral',
  'qwen2.5',
  'command-r'
]

/** Substring match, so `qwen2.5:latest` and `qwen2.5` both count. */
export const supportsTools = (model: string): boolean =>
  TOOL_CAPABLE_OLLAMA_MODELS.some((known) => model.includes(known))
