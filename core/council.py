"""Council Mode — multi-character reasoning and debate for plans.

Inspired by the AI-native engineering pipeline where multiple agents
review, debate, and push back on each other's work.

Characters act as specialised reasoning personas:
  Volt   (Engineer)  — checks feasibility, identifies technical blockers
  Sage   (Analyst)   — evaluates risks, considers edge cases
  Nova   (Creative)  — proposes alternatives, thinks laterally
  Blaze  (Critic)    — stress-tests the plan, devil's advocate

Usage:
    from core.council import convene_council
    verdict = convene_council(
        proposal="Deploy the new Hand scheduler to production",
        context="We just rewrote the scheduler with thread timeouts",
    )
    print(verdict["consensus"])   # approve / revise / reject
    print(verdict["amendments"])  # list of suggested changes
"""

import json
import logging
import time
from dataclasses import dataclass, asdict
from typing import Optional

_log = logging.getLogger("council")


# ---------------------------------------------------------------------------
# Council members — each has a name, role, and system prompt bias
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CouncilMember:
    name: str
    role: str
    bias: str           # short personality/perspective descriptor
    system_prompt: str   # injected into LLM call


COUNCIL_MEMBERS = [
    CouncilMember(
        name="Volt",
        role="Engineer",
        bias="practical, implementation-focused",
        system_prompt=(
            "You are Volt, OnyxKraken's chief engineer. "
            "You evaluate proposals for TECHNICAL FEASIBILITY. "
            "Focus on: can this actually be built? what dependencies are needed? "
            "what could break? are there simpler alternatives? "
            "Be direct and specific. Flag blockers immediately."
        ),
    ),
    CouncilMember(
        name="Sage",
        role="Analyst",
        bias="cautious, risk-aware, thorough",
        system_prompt=(
            "You are Sage, OnyxKraken's risk analyst. "
            "You evaluate proposals for RISKS AND EDGE CASES. "
            "Focus on: what can go wrong? security implications? "
            "scalability concerns? hidden assumptions? "
            "Be methodical. Rate risk as LOW/MEDIUM/HIGH."
        ),
    ),
    CouncilMember(
        name="Nova",
        role="Creative",
        bias="lateral thinker, alternative approaches",
        system_prompt=(
            "You are Nova, OnyxKraken's creative strategist. "
            "You evaluate proposals for CREATIVE ALTERNATIVES. "
            "Focus on: is there a better way? what are we not considering? "
            "what if we combined this with something else? "
            "Be imaginative but grounded."
        ),
    ),
    CouncilMember(
        name="Blaze",
        role="Critic",
        bias="devil's advocate, stress-tester",
        system_prompt=(
            "You are Blaze, OnyxKraken's devil's advocate. "
            "You STRESS-TEST proposals by finding weaknesses. "
            "Focus on: why might this fail? what's the worst case? "
            "what would a hostile user do? what's the hidden cost? "
            "Be tough but fair. If something is genuinely good, say so."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Council session
# ---------------------------------------------------------------------------

@dataclass
class CouncilVote:
    member: str
    role: str
    verdict: str          # approve / revise / reject
    reasoning: str
    concerns: list[str]
    suggestions: list[str]


@dataclass
class CouncilVerdict:
    proposal: str
    consensus: str          # approve / revise / reject
    votes: list[CouncilVote]
    amendments: list[str]   # merged suggestions
    risk_level: str         # LOW / MEDIUM / HIGH
    timestamp: float
    duration: float


def convene_council(
    proposal: str,
    context: str = "",
    members: Optional[list[CouncilMember]] = None,
) -> dict:
    """Convene the council to debate a proposal.

    Args:
        proposal: The plan or action to evaluate.
        context: Additional context (recent events, constraints, etc.).
        members: Override default council members (optional).

    Returns:
        Dict with keys: consensus, votes, amendments, risk_level, duration.
    """
    if members is None:
        members = COUNCIL_MEMBERS

    start = time.time()
    votes: list[CouncilVote] = []

    for member in members:
        try:
            vote = _get_member_vote(member, proposal, context)
            votes.append(vote)
        except Exception as e:
            _log.warning(f"Council member {member.name} failed: {e}")
            votes.append(CouncilVote(
                member=member.name,
                role=member.role,
                verdict="abstain",
                reasoning=f"Failed to evaluate: {e}",
                concerns=[],
                suggestions=[],
            ))

    # Tally votes
    verdict_counts = {"approve": 0, "revise": 0, "reject": 0, "abstain": 0}
    all_concerns = []
    all_suggestions = []

    for v in votes:
        verdict_counts[v.verdict] = verdict_counts.get(v.verdict, 0) + 1
        all_concerns.extend(v.concerns)
        all_suggestions.extend(v.suggestions)

    # Determine consensus
    if verdict_counts["reject"] >= 2:
        consensus = "reject"
    elif verdict_counts["approve"] >= 3:
        consensus = "approve"
    elif verdict_counts["revise"] >= 2 or verdict_counts["reject"] >= 1:
        consensus = "revise"
    else:
        consensus = "approve"

    # Determine risk level from Sage's assessment (or default)
    risk_level = "MEDIUM"
    for v in votes:
        if v.role == "Analyst":
            for concern in v.concerns:
                if "HIGH" in concern.upper():
                    risk_level = "HIGH"
                elif "LOW" in concern.upper() and risk_level != "HIGH":
                    risk_level = "LOW"

    # Deduplicate suggestions
    seen = set()
    amendments = []
    for s in all_suggestions:
        key = s.lower().strip()
        if key not in seen and s:
            seen.add(key)
            amendments.append(s)

    duration = time.time() - start

    verdict = CouncilVerdict(
        proposal=proposal[:200],
        consensus=consensus,
        votes=votes,
        amendments=amendments[:10],
        risk_level=risk_level,
        timestamp=time.time(),
        duration=round(duration, 1),
    )

    _log.info(f"Council verdict: {consensus} ({verdict_counts}) "
              f"— {len(amendments)} amendments, risk={risk_level}, "
              f"{duration:.1f}s")

    # Return as dict for easy serialization
    return {
        "proposal": verdict.proposal,
        "consensus": verdict.consensus,
        "votes": [asdict(v) for v in verdict.votes],
        "amendments": verdict.amendments,
        "risk_level": verdict.risk_level,
        "duration": verdict.duration,
        "vote_summary": verdict_counts,
    }


def _get_member_vote(member: CouncilMember, proposal: str,
                     context: str) -> CouncilVote:
    """Get a single council member's vote on the proposal."""
    from agent.model_router import router

    user_prompt = f"PROPOSAL:\n{proposal}\n"
    if context:
        user_prompt += f"\nCONTEXT:\n{context}\n"
    user_prompt += (
        "\nEvaluate this proposal from your perspective.\n"
        "Respond with ONLY a JSON object:\n"
        "{\n"
        '  "verdict": "approve" or "revise" or "reject",\n'
        '  "reasoning": "your key argument in 1-2 sentences",\n'
        '  "concerns": ["concern 1", "concern 2"],\n'
        '  "suggestions": ["suggestion 1", "suggestion 2"]\n'
        "}\n"
        "Output ONLY the JSON."
    )

    raw = router.get_content("reasoning", [
        {"role": "system", "content": member.system_prompt},
        {"role": "user", "content": user_prompt},
    ])

    try:
        from core.utils import extract_json
        result = extract_json(raw)
        if result is None:
            raise ValueError("Could not parse JSON from response")
    except Exception:
        # Fallback: try to extract verdict from raw text
        raw_lower = raw.lower()
        if "reject" in raw_lower:
            v = "reject"
        elif "revise" in raw_lower:
            v = "revise"
        else:
            v = "approve"
        return CouncilVote(
            member=member.name,
            role=member.role,
            verdict=v,
            reasoning=raw[:200],
            concerns=[],
            suggestions=[],
        )

    return CouncilVote(
        member=member.name,
        role=member.role,
        verdict=result.get("verdict", "abstain"),
        reasoning=result.get("reasoning", ""),
        concerns=result.get("concerns", [])[:5],
        suggestions=result.get("suggestions", [])[:5],
    )
