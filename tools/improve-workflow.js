// improve-workflow.js - parallel improvement pass for the Building Self-Improving
// Agents curriculum. Invoke via the Workflow tool:
//   Workflow({ scriptPath: ".../tools/improve-workflow.js",
//              args: { researchPath: "<raw last30days md>", focus: "optional" } })
//
// Pipeline: ANALYZE (gap analysis over fresh research) -> UPDATE (parallel per-note
// edits, additive + sourced) -> AUDIT (wikilinks, mermaid, URLs, py_compile).
// It edits the live Obsidian notes in place; the /improve-curriculum command then
// syncs them into the repo and pushes.

export const meta = {
  name: 'improve-sia-curriculum',
  description: 'Refresh the Self-Improving Agents curriculum from fresh research: gap-analyze, update notes in parallel, then audit consistency.',
  phases: [
    { title: 'Analyze', detail: 'gap analysis over fresh research vs current notes' },
    { title: 'Update', detail: 'parallel additive note updates (sourced only)' },
    { title: 'Audit', detail: 'wikilinks, mermaid, URLs, py_compile, consistency' },
  ],
}

const VAULT = '/Users/yuxinliu/Documents/Obsidian Vault/Self-Improving Agents'
const LAB = '/Users/yuxinliu/self-improving-agent-lab'
const SPEC = '/Users/yuxinliu/code/self-improving-agents-curriculum/tools/curriculum-spec.md'
const researchPath = (args && args.researchPath) || ''
const focus = (args && args.focus) || ''

const NOTES = [
  '00 - Curriculum Map', '01 - What Self-Improving Means',
  '02 - Backends - oMLX and VibeProxy', '03 - The Minimal Agent Loop',
  '04 - Memory Systems', '05 - Reflection and Self-Correction',
  '06 - Skill Acquisition and Curation', '07 - Verification Gates and Layered Control',
  '08 - Self-Modification - The DGM Pattern', '09 - Sandboxing and Safe Execution',
  '10 - Evaluation Harness', '11 - Capstone - Production Agent',
  '12 - Resources and Field Map',
  '13 - Graduating to a Framework',
  '14 - Framework Capstone - Shipping on deepagents',
]

const CHANGE_LIST = {
  type: 'object', additionalProperties: false,
  required: ['changes', 'new_sources'],
  properties: {
    new_sources: { type: 'array', items: { type: 'string' }, description: 'real URLs surfaced this run' },
    changes: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['file', 'instruction', 'sources'],
        properties: {
          file: { type: 'string', description: 'note basename, e.g. "04 - Memory Systems"' },
          instruction: { type: 'string', description: 'concrete additive edit to make' },
          sources: { type: 'array', items: { type: 'string' }, description: 'URLs backing this change' },
        },
      },
    },
  },
}

const MANIFEST = {
  type: 'object', additionalProperties: false,
  required: ['file', 'applied', 'summary'],
  properties: {
    file: { type: 'string' },
    applied: { type: 'boolean' },
    summary: { type: 'string' },
    citations: { type: 'array', items: { type: 'string' } },
  },
}

phase('Analyze')
const analysis = await agent(
  `You are the REFLECT/gap-analysis step for the Self-Improving Agents curriculum.
1. Read the authoring spec IN FULL: Read ${SPEC}
2. Read the fresh research: ${researchPath ? `Read ${researchPath}` : 'No researchPath provided - run `bash /Users/yuxinliu/self-improving-agents-curriculum/tools/refresh-research.sh "' + focus + '"` then read the newest *-raw-refresh.md in ~/.claude/plugins/data/last30days-last30days-skill/research'}
3. Read the current 15 notes under "${VAULT}" (basenames listed below). ${focus ? `Extra focus: ${focus}.` : ''}
4. Produce a CHANGE LIST: only ADDITIVE, HIGH-SIGNAL, SOURCED updates (new paper/tool/finding worth a citation,
   a new diagram, a correction). Map every change to a REAL url from the research. Skip what's already covered.
   Do NOT propose churn or rewrites of working content. It is valid to return an empty changes array if nothing
   new is worth adding.
Notes: ${NOTES.join(' | ')}
Return the change list object.`,
  { label: 'analyze:gaps', phase: 'Analyze', schema: CHANGE_LIST, agentType: 'general-purpose', model: 'sonnet' })

const changes = (analysis && analysis.changes) || []
log(`Gap analysis: ${changes.length} sourced change(s) proposed`)

phase('Update')
let updates = []
if (changes.length) {
  // group changes by file so each note is edited by exactly one agent
  const byFile = {}
  for (const c of changes) (byFile[c.file] = byFile[c.file] || []).push(c)
  updates = await parallel(Object.entries(byFile).map(([file, cs]) => () =>
    agent(
      `Apply these ADDITIVE, SOURCED updates to the Obsidian note "${VAULT}/${file}.md".
Read ${SPEC} for house style (frontmatter, [[wikilinks]], valid \`\`\`mermaid + caption, inline [name](url)
citations from REAL sources only, " - " not em-dashes, Navigation footer). Read the note, then use Edit to
weave in the changes - do not rewrite working sections. Bump the frontmatter "updated:" to 2026-06-08.
Changes to apply (each has backing sources - cite them inline):
${cs.map((c, i) => `${i + 1}. ${c.instruction}  [sources: ${c.sources.join(', ')}]`).join('\n')}
Return the manifest.`,
      { label: `update:${file.slice(0, 18)}`, phase: 'Update', schema: MANIFEST, agentType: 'general-purpose', model: 'sonnet' })))
  updates = updates.filter(Boolean)
} else {
  log('No changes proposed - skipping Update phase (curriculum already current).')
}

phase('Audit')
const AUDIT = {
  type: 'object', additionalProperties: false,
  required: ['broken_wikilinks', 'bad_mermaid', 'suspicious_urls', 'py_compile_ok', 'verdict', 'issues'],
  properties: {
    broken_wikilinks: { type: 'array', items: { type: 'string' } },
    bad_mermaid: { type: 'array', items: { type: 'string' } },
    suspicious_urls: { type: 'array', items: { type: 'string' } },
    py_compile_ok: { type: 'boolean' },
    issues: { type: 'array', items: { type: 'string' } },
    verdict: { type: 'string', enum: ['PASS', 'FIX_NEEDED'] },
  },
}
const audit = await agent(
  `Audit the curriculum after updates. Valid note basenames: ${NOTES.join(' | ')}.
1. Grep every [[wikilink]] across the 15 notes in "${VAULT}"; any target not in the valid set (ignore #headings/externals) -> broken_wikilinks ("file: [[bad]]").
2. Every \`\`\`mermaid fence must be balanced and start with a valid diagram keyword -> else bad_mermaid.
3. Inline link URLs must appear in ${SPEC} OR in ${researchPath || 'the latest research file'} -> else suspicious_urls ("file: url"). Allow localhost/obsidian-internal.
4. Run: cd ${LAB} && find . -name '*.py' -print0 | xargs -0 python3 -m py_compile ; set py_compile_ok = (exit 0).
5. Consistency: notes + spec + scaffold agree on ports (oMLX :8000, VibeProxy :8317) and the embeddings-stay-local rule. Note drift in issues.
verdict = PASS iff broken_wikilinks, bad_mermaid, suspicious_urls all empty AND py_compile_ok. Else FIX_NEEDED. Return the audit object.`,
  { label: 'audit:improve', phase: 'Audit', schema: AUDIT, agentType: 'general-purpose', model: 'sonnet' })

return { proposed: changes.length, updated: updates.map((u) => u.file), audit }
