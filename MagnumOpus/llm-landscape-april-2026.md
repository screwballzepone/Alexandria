# LLM Landscape Research — April 2026
**Prepared for:** Opus 4.7 handoff  
**Prepared by:** Claude Code (Sonnet 4.6), 2026-04-26  
**Purpose:** Model selection reference for JANUS agent roster upgrade decisions

---

## TL;DR for Opus 4.7

Three models released this month directly affect the JANUS agent roster:

| Model | Role impact | Action recommended |
|-------|-------------|-------------------|
| **DeepSeek V4-Flash** | Drop-in replacement for `deepseek-chat` orchestrator + @coder | **Pilot immediately** — ~10x coding perf leap vs V3.2, lower cost than Pro, available on OpenRouter and DeepSeek API now |
| **DeepSeek V4-Pro** | Orchestrator fallback / high-stakes missions | Worth testing; 75% discount until 2026-05-05 makes it very cheap to eval |
| **Gemini 3 Flash Preview** | Replaces Gemini 2.5 Flash for all Flash sub-agents (@reviewer, @test-writer, @onboarder, etc.) | Worth piloting — same price tier, "PhD-level reasoning comparable to larger models" |

---

## 1. DeepSeek V4 (Released 2026-04-24, Preview)

### What it is
DeepSeek dropped two MoE models as a preview (not finalized, no GA timeline announced):

| | **V4-Flash** | **V4-Pro** |
|--|--|--|
| Total params | 284B | 1.6T |
| Active params | 13B | 49B |
| Context window | 1M tokens | 1M tokens |
| Architecture | MoE + hybrid attention (CSA+HCA) | Same |

The hybrid attention mechanism (CSA + HCA) is the key architectural upgrade — it dramatically reduces long-context overhead. At 1M tokens, V4-Pro requires only **27% of V3.2's single-token FLOPs** and **10% of KV cache**. V4-Flash is even leaner: **10% of FLOPs, 7% of KV cache** vs V3.2.

### Benchmark highlights vs V3.2
- SWE-bench Verified: V4-Flash 79.0%, V4-Pro 80.6% (V3.2 baseline was ~49%)
- LiveCodeBench: V4-Flash 91.6%, V4-Pro 93.5%
- Vals AI Vibe Code Benchmark: V4 "overwhelmingly" tops open-source weighted models, ~10x improvement vs V3.2
- Both models described as "comparable to GPT-5.4" on coding tasks
- "Closes the gap" with frontier models per DeepSeek and third-party evals

### Pricing (April 2026)

**DeepSeek direct API:**
- V4-Pro: $3.48/M output tokens (normal); **75% discount active until 2026-05-05** → effectively ~$0.87/M
- V4-Flash: $0.28/M output tokens

**OpenRouter:**
- V4-Pro: $0.435/M input, $0.87/M output
- V4-Flash: $0.14/M input, $0.28/M output

**vs current deepseek-chat (V3.2):**
- V4-Flash is cheaper than V3.2 on OpenRouter AND dramatically more capable. No reason not to switch.

### JANUS-specific implications
- **Orchestrator** (`deepseek/deepseek-chat`): V4-Flash is a direct upgrade. Better reasoning + 1M context means less prompt-size anxiety. The Cerebras TPM ceiling was the whole reason we pivoted to DeepSeek — V4-Flash makes this even better.
- **@coder sub-agent**: Current roster lists `@coder → DeepSeek`. V4-Flash's ~10x SWE-bench improvement is massive for mission quality.
- **opencode.json model IDs**: `deepseek/deepseek-v4-flash` and `deepseek/deepseek-v4-pro` (available on OpenRouter). DeepSeek direct API uses `deepseek-v4-flash` and `deepseek-v4-pro`.
- **Preview caveat**: Not GA. Rate limits may be stricter during preview. Monitor for stability before committing to production runs.

---

## 2. Gemini 3 Flash Preview (Released April 2026)

### What it is
Google shipped Gemini 3 Flash as a preview — the successor to Gemini 2.5 Flash. It's now the **default model in the Gemini app**.

Key specs:
- 1,048,576 token context window (same as V4)
- "PhD-level reasoning comparable to larger models"
- Multimodal: text, images, audio, video, PDFs
- Configurable reasoning via thinking levels (minimal → high)
- Structured output + tool use + automatic context caching
- **Gemini 3.1 Flash Lite** also available (cheaper variant)

### Pricing on OpenRouter
| Model | Input | Output |
|-------|-------|--------|
| Gemini 3 Flash Preview | $0.50/M | $3.00/M |
| Gemini 3.1 Flash Lite Preview | $0.25/M | $1.50/M |

Gemini 2.5 Flash (current sub-agent model) was $0.15/M input, $0.60/M output — so Gemini 3 Flash is ~3-5x more expensive but presumably much more capable. **Gemini 3.1 Flash Lite** may be closer to the 2.5 Flash price point and worth evaluating for cheap sub-agents.

### JANUS-specific implications
Current sub-agents that use Gemini 2.5 Flash:
- @reviewer, @onboarder, @memory-writer, @lessons, @test-writer, @security-auditor, @documenter, @dependency-scout, @meta-agent

Switching all of these to Gemini 3 Flash would increase per-run cost. A tiered approach makes sense:
- **High-judgment agents** (@reviewer, @onboarder, @meta-agent): upgrade to Gemini 3 Flash
- **Throughput agents** (@documenter, @memory-writer, @lessons): try Gemini 3.1 Flash Lite first
- **nano-coder**: stays as-is (tiny single-shot use case)

---

## 3. Other Notable April 2026 Releases

### Claude Opus 4 (Anthropic, released 2026-04-02)
- Extended autonomous coding sessions + agentic tool use
- SWE-bench Verified: 72.1%
- 200K context window
- **This is what Opus 4.7 is** — it already knows itself.

### Claude Mythos Preview (Anthropic, released 2026-04-07)
- Available only to ~50 partner orgs via "Project Glasswing"
- Focus: cybersecurity, reasoning, coding
- "Step change" above Claude Opus 4.6
- Pricing: $25/$125 per million input/output tokens
- Not accessible for JANUS use — listed for completeness.

### GPT-5 Turbo (OpenAI, released 2026-04-07)
- Native image + audio generation inside same model as text
- Not currently in JANUS roster; not a recommended swap given cost/access.

### Qwen 3.6-Plus (Alibaba, released early April 2026)
- Agentic coding focus, 1M context
- MIT license (open weight)
- Worth watching as @coder alternative if DeepSeek V4 has preview instability

### Gemma 4 31B Dense (Google, released 2026-04-02)
- Apache 2.0, outperforms models 20x its size on benchmarks
- Could be interesting for self-hosted sub-agents if Cerebras ever gets a Gemma 4 slot

---

## 4. Recommended Action Plan for Opus 4.7

### Immediate (this session or next):
1. **Swap orchestrator + @coder to `deepseek/deepseek-v4-flash`**
   - Edit `.opencode/opencode.json`: `model`, `small_model` → `deepseek/deepseek-v4-flash`
   - Edit `.opencode/agent/orchestrator.md` frontmatter → `model: deepseek/deepseek-v4-flash`
   - Edit `@coder` agent frontmatter similarly
   - Run smoke test 12 against prompt-27 to validate

2. **Try V4-Pro orchestrator** with the 75% discount before it expires 2026-05-05:
   - Swap orchestrator only, keep @coder on V4-Flash
   - Compare seam report score

### Short-term:
3. **Pilot Gemini 3 Flash for @reviewer**
   - Single sub-agent swap; measure verdict quality vs 2.5 Flash
   - If PASS/WARN rates improve, roll out to @onboarder, @meta-agent

4. **Update AGENTS.md** to reflect new model roster (currently documents old Cerebras models)

5. **Update project-map.json** config gotcha entry — it currently notes "config uses cerebras/qwen..." which is now stale after the Cerebras→DeepSeek pivot.

### Watch list:
- DeepSeek V4 GA announcement (no timeline given; preview may have rate limits)
- Gemini 3 Flash Lite pricing — if it drops toward 2.5 Flash pricing, bulk-upgrade all flash sub-agents
- Qwen 3.6-Plus self-hosting viability (relevant if you want to reduce API costs long-term)

---

## 5. Current JANUS Agent Roster (as of 2026-04-26)

For reference, what the agent roster looks like after today's DeepSeek pivot:

| Agent | Current model | Recommended upgrade |
|-------|--------------|---------------------|
| @orchestrator | deepseek/deepseek-chat (V3.2) | deepseek/deepseek-v4-flash |
| @coder | deepseek/deepseek-chat (V3.2) | deepseek/deepseek-v4-flash |
| @reviewer | google/gemini-2.5-flash | google/gemini-3-flash-preview |
| @onboarder | google/gemini-2.5-flash | google/gemini-3-flash-preview |
| @test-writer | google/gemini-2.5-flash | google/gemini-3.1-flash-lite-preview |
| @documenter | google/gemini-2.5-flash | google/gemini-3.1-flash-lite-preview |
| @memory-writer | google/gemini-2.5-flash | google/gemini-3.1-flash-lite-preview |
| @lessons | google/gemini-2.5-flash | google/gemini-3.1-flash-lite-preview |
| @nano-coder | google/gemini-2.5-flash | no change (tiny single-shot) |
| @explorer | grok-4-20-beta | no change (X/Twitter grounding useful) |
| @architect | anthropic/claude-sonnet-4-6 | no change |
| title agent | cerebras/llama3.1-8b | no change (tiny, separate bucket) |

---

## Sources

- [DeepSeek V4 Preview Release | DeepSeek API Docs](https://api-docs.deepseek.com/news/news260424)
- [DeepSeek previews new AI model that 'closes the gap' with frontier models | TechCrunch](https://techcrunch.com/2026/04/24/deepseek-previews-new-ai-model-that-closes-the-gap-with-frontier-models/)
- [DeepSeek V4 — almost on the frontier, a fraction of the price | Simon Willison](https://simonwillison.net/2026/Apr/24/deepseek-v4/)
- [DeepSeek V4-Pro on OpenRouter](https://openrouter.ai/deepseek/deepseek-v4-pro)
- [DeepSeek V4-Flash on OpenRouter](https://openrouter.ai/deepseek/deepseek-v4-flash)
- [DeepSeek V4-Pro Review: Benchmarks, Pricing & Architecture](https://www.buildfastwithai.com/blogs/deepseek-v4-pro-review-2026)
- [Gemini 3 Flash Preview on OpenRouter](https://openrouter.ai/google/gemini-3-flash-preview)
- [New LLM Releases April 2026 | Fazm Blog](https://fazm.ai/blog/new-llm-releases-april-2026)
- [deepseek-ai/DeepSeek-V4-Flash · Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash)
- [deepseek-ai/DeepSeek-V4-Pro · Hugging Face](https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro)
- [DeepSeek Models & Pricing | DeepSeek API Docs](https://api-docs.deepseek.com/quick_start/pricing)
