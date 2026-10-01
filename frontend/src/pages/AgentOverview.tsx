import { useState } from "react";

import SkillEditorModal, { type PromptFileOption } from "../components/SkillEditorModal";
import { useTender } from "../context/TenderContext";

// A curated overview, not a raw prompt dump — the old "Agent Skills" page listed every raw
// prompt file (Theme Review alone has seven), which doesn't map to "one card per agent" the way
// a human thinks about this system. This page hand-summarises each of the real backend agents
// (backend/app/agents/*.py) instead: what it does, how it does it, and what it needs to be given.
// `promptFiles` is the real, authoritative mapping to backend/app/prompts/*.txt — what "Edit
// Skill" actually opens. Deterministic Checks has none: it's pure code, no model call, no prompt.
interface AgentInfo {
  name: string;
  what: string;
  how: string;
  expected: string;
  promptFiles: PromptFileOption[];
}

const AGENTS: AgentInfo[] = [
  {
    name: "Ingestion",
    what: "Finds every real question in an uploaded tender document.",
    how: "Reads the document's own text with the model, verifying each question is a genuine verbatim excerpt.",
    expected: "A tender document uploaded under Questionnaire.",
    promptFiles: [{ label: "Ingestion", filename: "ingestion_extract_v1.txt" }],
  },
  {
    name: "Decomposition",
    what: "Breaks one question into its component sub-questions, limits, weighting and theme.",
    how: "Regex/table lookup for the numbers; a verbatim-only model call for sub-questions, informed by the tender's own context.",
    expected: "A question to decompose, plus a Strategy upload for best results.",
    promptFiles: [{ label: "Decomposition", filename: "decomposition_extract_v1.txt" }],
  },
  {
    name: "Evidence Score",
    what: "Scores how much one sub-question's own answer reads as concrete, past-tense proof of delivery, out of 5.",
    how: "Judges only the answer's own writing — named detail, quantified outcomes, past tense vs. future-tense promises. Never cross-references the evidence library.",
    expected: "A sub-question's answer text, written in Response Builder before it's composed into the draft.",
    promptFiles: [{ label: "Evidence Score", filename: "evidence_score_v1.txt" }],
  },
  {
    name: "Completeness",
    what: "Checks whether a draft actually addresses each locked sub-question.",
    how: "A closed-book model check per sub-question; every quoted excerpt is verified against the real draft text.",
    expected: "Locked sub-questions and a saved draft version.",
    promptFiles: [{ label: "Completeness", filename: "completeness_check_v1.txt" }],
  },
  {
    name: "Scoring",
    what: "Suggests an indicative score band for a draft.",
    how: "Three independent passes against this tender's own band descriptors; a fourth pass reconciles real disagreement.",
    expected: "This tender's scoring bands and a saved draft.",
    promptFiles: [
      { label: "Scoring pass", filename: "scoring_pass_v1.txt" },
      { label: "Moderator reconciliation", filename: "scoring_moderator_v1.txt" },
    ],
  },
  {
    name: "Deterministic Checks",
    what: "Verifies word/diagram limits and locked constraints — no model involved.",
    how: "Plain code counts the draft and compares it against Decomposition's locked limits.",
    expected: "Locked elements and a saved draft.",
    promptFiles: [],
  },
  {
    name: "Recommendation",
    what: "Suggests up to three prioritised fixes for a draft.",
    how: "Retrieves this tender's own evidence library, then proposes fixes that only ever cite real, retrieved evidence.",
    expected: "Uploaded evidence (case studies/CVs) and a saved draft.",
    promptFiles: [{ label: "Recommendation", filename: "recommendation_v1.txt" }],
  },
  {
    name: "Theme Review",
    what: "A full expert critique of a draft from a specialist reviewer's perspective.",
    how: "Picks one of seven expert prompts by theme; every gap is anchored to a real sub-question and a verified draft quote.",
    expected: "A decomposed, locked question and a saved draft.",
    promptFiles: [
      { label: "Understanding & Outcomes", filename: "theme_review_understanding_outcomes_v1.txt" },
      { label: "Delivery Methodology", filename: "theme_review_delivery_methodology_v1.txt" },
      { label: "Governance & Standards", filename: "theme_review_governance_standards_v1.txt" },
      { label: "Performance, Quality & Standards", filename: "theme_review_performance_quality_v1.txt" },
      { label: "Capability & Knowledge Transfer", filename: "theme_review_capability_knowledge_transfer_v1.txt" },
      { label: "Team & Resourcing", filename: "theme_review_team_resourcing_v1.txt" },
      { label: "Relevant Experience", filename: "theme_review_relevant_experience_v1.txt" },
    ],
  },
  {
    name: "Know Your Client",
    what: "Summarises who the client is and what to keep in mind before writing for them.",
    how: "Reads the Context upload only (never Strategy), honestly reporting nothing if no real client detail is genuinely discussed.",
    expected: "The client background document uploaded under Context.",
    promptFiles: [{ label: "Know Your Client", filename: "kyc_extract_v1.txt" }],
  },
  {
    name: "Methodology",
    what: "Summarises how this client actually evaluates responses.",
    how: "Reads the Strategy upload, honestly reporting nothing if no methodology is genuinely discussed.",
    expected: "The tender instructions document uploaded under Strategy.",
    promptFiles: [{ label: "Methodology", filename: "methodology_extract_v1.txt" }],
  },
  {
    name: "Tender Requirements",
    what: "Builds a traceable register of every requirement in the tender.",
    how: "Chunked extraction across the whole document; every requirement is verified as a genuine verbatim excerpt.",
    expected: "The tender instructions document uploaded under Strategy.",
    promptFiles: [{ label: "Tender Requirements", filename: "tender_requirements_extract_v1.txt" }],
  },
  {
    name: "Scoring Matrix",
    what: "Extracts this tender's own scoring-band descriptors automatically.",
    how: "Classifies each table in the upload, trusting verbatim text only from the one table confirmed as the real matrix.",
    expected: "A scoring matrix table present in the Strategy document.",
    promptFiles: [{ label: "Scoring Matrix", filename: "scoring_matrix_extract_v1.txt" }],
  },
  {
    name: "Procurement Timeline",
    what: "Extracts the competition's key dates and stages.",
    how: "Checks for a timetable table first, falling back to prose if none is found; every stage and date is verbatim-verified.",
    expected: "The tender instructions document uploaded under Strategy.",
    promptFiles: [
      { label: "Table extraction", filename: "procurement_timeline_extract_table_v1.txt" },
      { label: "Prose fallback", filename: "procurement_timeline_extract_prose_v1.txt" },
    ],
  },
];

export default function AgentOverview() {
  const { selectedTenderId } = useTender();
  const [editing, setEditing] = useState<AgentInfo | null>(null);

  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Agent Overview</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Hover a card to see what that agent does, how it does it, and what it needs to be given. "Edit Skill"
          customises an agent's prompt for the tender you currently have selected only.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {AGENTS.map((agent) => (
          <AgentCard key={agent.name} agent={agent} onEditSkill={() => setEditing(agent)} />
        ))}
      </div>

      {editing && selectedTenderId && (
        <SkillEditorModal
          agentName={editing.name}
          promptFiles={editing.promptFiles}
          tenderId={selectedTenderId}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function AgentCard({ agent, onEditSkill }: { agent: AgentInfo; onEditSkill: () => void }) {
  const { selectedTenderId } = useTender();
  const canEdit = agent.promptFiles.length > 0;

  return (
    <div className="group h-64" style={{ perspective: "1200px" }}>
      <div
        className="relative h-full w-full transition-transform duration-500 ease-in-out group-hover:[transform:rotateY(180deg)]"
        style={{ transformStyle: "preserve-3d" }}
      >
        {/* Front: name only */}
        <div
          className="absolute inset-0 flex items-center justify-center rounded-xl border-2 border-slate-200 bg-white p-5 text-center shadow-sm transition-shadow duration-300 group-hover:border-brand-500 group-hover:shadow-[0_0_10px_1px_rgba(0,51,141,0.35)]"
          style={{ backfaceVisibility: "hidden" }}
        >
          <p className="text-lg font-semibold text-slate-800">{agent.name}</p>
        </div>

        {/* Back: what / how / expected */}
        <div
          className="absolute inset-0 flex flex-col justify-center gap-3 rounded-xl border-2 border-brand-500 bg-white p-5 shadow-[0_0_10px_1px_rgba(0,51,141,0.35)]"
          style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}
        >
          <p className="text-xs leading-snug">
            <span className="font-semibold text-brand-700">What: </span>
            <span className="text-slate-600">{agent.what}</span>
          </p>
          <p className="text-xs leading-snug">
            <span className="font-semibold text-brand-700">How: </span>
            <span className="text-slate-600">{agent.how}</span>
          </p>
          <p className="text-xs leading-snug">
            <span className="font-semibold text-brand-700">Expected: </span>
            <span className="text-slate-600">{agent.expected}</span>
          </p>
          {canEdit && (
            <button
              onClick={onEditSkill}
              disabled={!selectedTenderId}
              title={selectedTenderId ? undefined : "Select a tender first"}
              className="mt-1 w-fit rounded-md border border-brand-300 px-2.5 py-1 text-[11px] font-medium text-brand-700 hover:bg-brand-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Edit Skill
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
