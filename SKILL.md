# 🤖 ANTIGRAVITY AI CORE AGENT SPECIFICATION & USER PREFERENCES (SKILL.md)

> **[CRITICAL SYSTEM DIRECTIVE]**
> This document defines the primary operating parameters, tool execution protocols, skill automation matrices, web development standards, and explicit user preferences for any AI Agent working in this workspace. All AI models MUST strictly adhere to these instructions.

---

## 👤 1. USER PREFERENCES & WORKING HABITS

1. **Permission Popup Mitigation (Highest Priority)**:
   - The user is extremely sensitive to unnecessary Windows system permission popups (`run_command` approvals).
   - NEVER use terminal commands (`powershell`, `bash`, `cmd`) for file reading, searching, or directory listing.
   - Only trigger terminal execution when strictly necessary (e.g., dev servers, builds, package installations, git operations).

2. **Proactive Skill Automation (Zero Manual Keyword Requirement)**:
   - The user expects the AI to be fully autonomous.
   - Automatically detect the task context and invoke the relevant skill package without requiring the user to type explicit trigger keywords.

3. **No AI Fluff / Zero Slop Communication**:
   - The user dislikes robotic filler phrases (e.g., "Sure, I'd be happy to help!", "Certainly!", apologizing excessively).
   - Communicate like a senior engineer: crisp, direct, factual, and concise.

4. **Premium UI/UX Quality**:
   - When requested to build or modify UIs, produce state-of-the-art designs (modern typography, curated HSL color schemes, dynamic micro-animations, no generic placeholders).

---

## 🛠️ 2. TOOL SELECTION PROTOCOL & STRICT BANS

To eliminate redundant permission prompts, enforce the following tool mapping:

| Intent / Operation | ❌ FORBIDDEN Terminal Commands | ✅ MANDATORY Built-in API Tool | Rationale |
| :--- | :--- | :--- | :--- |
| **Search File Contents** | `Select-String`, `grep`, `findstr` | `grep_search` | Native IDE search; zero permission popups. |
| **Read File Contents** | `Get-Content`, `cat`, `type` | `view_file` | Safe, sliceable reading without terminal execution. |
| **Browse Directory** | `Get-ChildItem`, `ls`, `dir`, `tree` | `list_dir` | High performance native directory inspection. |
| **Create / Modify Files** | `Set-Content`, `echo >` | `write_to_file` / `replace_file_content` | Precise file manipulation avoiding encoding issues. |

### Allowed Terminal Operations (`run_command` Only)
Use `run_command` ONLY for operations that genuinely require shell execution:
* Local server execution (e.g., `npm run dev`, `vite`)
* Package installation (e.g., `npm install`, `pip install`)
* Build and compilation (e.g., `npm run build`, `npx` scripts)
* Version control (e.g., `git commit`, `git status`, `git restore`)
* Automated test execution

---

## ⚡ 3. AUTOMATED SKILL INVOCATION MATRIX

Automatically load and apply the following skills based on context:

| Context / Task Domain | Skill Name | Automated Behavior & Directive |
| :--- | :--- | :--- |
| **Complex Decisions / Tradeoffs / Strategy** | `llm-council` | Simulate a 5-expert advisory council to pressure-test options, peer-review anonymously, and synthesize an objective recommendation. |
| **Frontend UI / Styling / Layout Design** | `impeccable` | Inject premium UI design principles (curated HSL palettes, Google Fonts like Inter/Outfit, glassmorphism, micro-animations, no placeholder images). |
| **Code Review / Refactoring / Architecture** | `improve` | Perform deep code and UI audit, identifying logic bugs, type safety issues, and refactoring to production standards. |
| **Technical Explanation / General Chat** | `stop-slop` | Eliminate conversational fluff, AI boilerplate, and repetitive pleasantries. Output crisp, high-density responses. |
| **Video Analysis / Transcript / Summary** | `claude-video` | Extract keyframes, generate structured summaries, and derive accurate transcripts for video links/files. |

---

## 🎨 4. APP DEVELOPMENT & FRONTEND DESIGN STANDARDS

1. **Technology Stack**:
   - Structure & Logic: HTML5 + Modern JavaScript / TypeScript.
   - Styling: Vanilla CSS by default for granular animation control; avoid adding TailwindCSS unless explicitly requested.
   - Web App Framework: Use Vite (`npx -y create-vite@latest ./`) or Next.js for complex applications.
2. **Design Quality (Non-Negotiable)**:
   - Typography: Always load modern fonts via Google Fonts (Inter, Roboto, Outfit, etc.).
   - Palette: Use harmonious HSL color tokens and sleek dark/light mode contrasts.
   - Micro-Interactions: Implement hover states, smooth transitions (`cubic-bezier`), and interactive feedback.
   - Media: Generate real demonstration assets via `generate_image` tool instead of placeholder boxes.
3. **SEO & Semantics**:
   - Single `<h1>` tag per page hierarchy.
   - Unique HTML `id` attributes for testability.
   - Descriptive title tags and meta tags.

---

## 📝 5. WORKFLOW & VERIFICATION PROTOCOL

1. **Planning Mode**:
   - For major architectural shifts or multi-file features, create `implementation_plan.md` first and obtain approval.
   - Upon task completion, document results in `walkthrough.md`.
2. **Empirical Verification Rule**:
   - NEVER declare a bug fixed or feature complete without executing validation commands (e.g., verifying builds or running tests).
   - If an error occurs, inspect the complete, un-truncated error log as the FIRST step before forming diagnostic hypotheses.

---

## 🚫 7. STRICT ANTI-MOCK & ANTI-DUMMY DATA DIRECTIVE (IRONCLAD RULE)

1. **Absolute Prohibition of Unsanctioned Mock/Dummy Data**:
   - When writing code, API clients, UI components, or backend logic, the AI is **STRICTLY FORBIDDEN** from inventing fake/mock data, hardcoded dummy arrays, simulated JSON, or dummy fallbacks to mask missing real endpoints, databases, or environment variables.
2. **Mandatory Chinese Explanation Before Mocking**:
   - If real APIs or datasets are unavailable, the AI MUST NOT silently introduce mock data.
   - The AI MUST first explain to the user in Traditional Chinese:
     - Exactly what real data/API is missing.
     - Why real integration cannot proceed directly.
     - The implications of using temporary placeholder data.
   - The AI MUST obtain explicit user consent in Chinese before injecting any temporary mock data into the codebase.
