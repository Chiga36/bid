"""Know Your Client (KYC) agent.

One LLM call per "Strategy and Context" document: what does this document genuinely reveal about
the client, and what should the bid team keep in mind before writing the tender response for them
specifically? This is synthesis, not verbatim extraction — same no-fabrication standard as
methodology.py, since inventing client detail that isn't really in the document is worse than
reporting nothing found.

Like every other agent, this module never touches the database directly — routers own fetching and
persisting; this only holds the LLM call.
"""
from typing import Optional

from app import llm_client
from app.models import KYCExtraction

AGENT_NAME = "kyc"


def extract_kyc(document_text: str, tender_id: Optional[int] = None) -> Optional[KYCExtraction]:
    result: KYCExtraction = llm_client.call_structured(
        agent=AGENT_NAME,
        prompt_file="kyc_extract_v1.txt",
        variables={"document_text": document_text},
        response_model=KYCExtraction,
        tender_id=tender_id,
    )
    if not result.client_info_found:
        return None
    return result
