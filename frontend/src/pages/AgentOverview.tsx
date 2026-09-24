// A curated overview, not a raw prompt dump — the old "Agent Skills" page listed every raw
// prompt file (Theme Review alone has seven), which doesn't map to "one card per agent" the way
// a human thinks about this system. This page hand-summarises each of the real backend agents
// (backend/app/agents/*.py) instead: what it does, how it does it, and what it needs to be given.
// The full raw prompts are still readable directly in backend/app/prompts/ for anyone who wants
// that level of detail.
interface AgentInfo {
  name: string;
  what: string;
  how: string;
  expected: string;
}

const AGENTS: AgentInfo[] = [
  {
    name: "Ingestion",
    what: "Finds every real question in an uploaded tender document.",
    how: "Reads the document's own text with the model, verifying each question is a genuine verbatim excerpt.",
    expected: "A tender document uploaded under Questionnaire.",
  },
  {
    name: "Decomposition",
    what: "Breaks one question into its component sub-questions, limits, weighting and theme.",
    how: "Regex/table lookup for the numbers; a verbatim-only model call for sub-questions, informed by the tender's own context.",
    expected: "A question to decompose, plus Strategy and Context uploads for best results.",
  },
  {
    name: "Completeness",
    what: "Checks whether a draft actually addresses each locked sub-question.",
    how: "A closed-book model check per sub-question; every quoted excerpt is verified against the real draft text.",
    expected: "Locked sub-questions and a saved draft version.",
  },
  {
    name: "Scoring",
    what: "Suggests an indicative score band for a draft.",
    how: "Three independent passes against this tender's own band descriptors; a fourth pass reconciles real disagreement.",
    expected: "This tender's scoring bands and a saved draft.",
  },
  {
    name: "Deterministic Checks",
    what: "Verifies word/diagram limits and locked constraints — no model involved.",
    how: "Plain code counts the draft and compares it against Decomposition's locked limits.",
    expected: "Locked elements and a saved draft.",
  },
  {
    name: "Recommendation",
    what: "Suggests up to three prioritised fixes for a draft.",
    how: "Retrieves this tender's own evidence library, then proposes fixes that only ever cite real, retrieved evidence.",
    expected: "Uploaded evidence (case studies/CVs) and a saved draft.",
  },
  {
    name: "Theme Review",
    what: "A full expert critique of a draft from a specialist reviewer's perspective.",
    how: "Picks one of seven expert prompts by theme; every gap is anchored to a real sub-question and a verified draft quote.",
    expected: "A decomposed, locked question and a saved draft.",
  },
  {
    name: "Methodology",
    what: "Summarises how this client actually evaluates responses.",
    how: "Reads the Strategy and Context upload, honestly reporting nothing if no methodology is genuinely discussed.",
    expected: "The tender instructions document uploaded under Strategy and Context.",
  },
  {
    name: "Tender Requirements",
    what: "Builds a traceable register of every requirement in the tender.",
    how: "Chunked extraction across the whole document; every requirement is verified as a genuine verbatim excerpt.",
    expected: "The tender instructions document uploaded under Strategy and Context.",
  },
  {
    name: "Scoring Matrix",
    what: "Extracts this tender's own scoring-band descriptors automatically.",
    how: "Classifies each table in the upload, trusting verbatim text only from the one table confirmed as the real matrix.",
    expected: "A scoring matrix table present in the Strategy and Context document.",
  },
  {
    name: "Procurement Timeline",
    what: "Extracts the competition's key dates and stages.",
    how: "Checks for a timetable table first, falling back to prose if none is found; every stage and date is verbatim-verified.",
    expected: "The tender instructions document uploaded under Strategy and Context.",
  },
];

export default function AgentOverview() {
  return (
    <div className="flex flex-col gap-4">
      <div>
        <h1 className="text-lg font-semibold text-slate-900">Agent Overview</h1>
        <p className="mt-1 max-w-2xl text-sm text-slate-500">
          Hover a card to see what that agent does, how it does it, and what it needs to be given.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {AGENTS.map((agent) => (
          <AgentCard key={agent.name} agent={agent} />
        ))}
      </div>
    </div>
  );
}

function AgentCard({ agent }: { agent: AgentInfo }) {
  return (
    <div className="group h-60" style={{ perspective: "1200px" }}>
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
        </div>
      </div>
    </div>
  );
}
