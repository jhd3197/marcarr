"""Look a film's cuts up online, through Prompture's research agent.

When only one version is on disk, nothing local can say what an Extended adds.
People who compared the cuts often published it (every added scene, where it
sits and how long it runs), so a research run asks the web, reads a few of
those pages, and writes a cited answer. A second, small call reads that answer
into each cut's runtime and a list of differences.

What leaves the machine: the film's name and year, and which cuts you have.
What comes back lands for review: every difference is a *proposed* cut range
with its sources, marked rough (published times are for someone else's copy).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from . import ai
from .cuts import edition_labels
from .errors import MarcarrError

if TYPE_CHECKING:
    from .core import Core
    from .jobs import JobContext

log = logging.getLogger("marcarr.research")

TOPIC = "cuts"
SOURCE = "research"
CONFIDENCE = 0.3  # published times are for another copy: a person checks each one


class Edition(BaseModel):
    name: str = Field(description="the cut's name: Theatrical, Extended Edition, Director's Cut...")
    runtime_minutes: float | None = Field(default=None, description="its runtime in minutes, if stated")
    cited: list[int] = Field(default_factory=list, description="citation numbers [n] used")


class Difference(BaseModel):
    edition: str = Field(description="the cut that has this footage (or runs longer here)")
    base: str = Field(default="Theatrical", description="the cut it is compared with")
    kind: Literal["added", "longer", "removed"] = Field(
        description="added: a scene only in this cut; longer: an existing scene runs longer; "
                    "removed: footage the base has and this cut lacks")
    at: str | None = Field(default=None, description="where it starts in that cut, h:mm:ss or mm:ss, "
                                                     "only if the answer states it")
    length_seconds: float | None = Field(default=None, description="how long it runs, only if stated")
    description: str = Field(description="what happens, in one short sentence")
    cited: list[int] = Field(default_factory=list, description="citation numbers [n] used")


class CutsFound(BaseModel):
    editions: list[Edition] = Field(default_factory=list, max_length=8)
    differences: list[Difference] = Field(default_factory=list, max_length=120)


EXTRACT_SYSTEM = (
    "You read a cited research answer about the different cuts of a film and list (1) each cut "
    "with its runtime and (2) every difference between the cuts: scenes added, scenes that run "
    "longer, footage removed. Copy times and lengths exactly as the answer states them and "
    "leave them empty when it does not; never estimate one. Keep each description to one "
    "sentence and cite the [n] it came from. An empty list is a good answer.")


def question_for(title: dict[str, Any], names: list[str]) -> str:
    """The text that leaves the machine."""
    film = f'"{title["name"]}"' + (f" ({title['year']})" if title.get("year") else "")
    have = [n for n in names if n and n.lower() != "theatrical"]
    cuts = " and ".join(dict.fromkeys(have)) if have else "the extended or director's cut"
    return (f"What does {cuts} of the film {film} add or change compared with the theatrical "
            "cut? List every added or extended scene with its time code in that cut and how "
            "long it runs, and give the runtime of each cut.")


class Research:
    def __init__(self, core: Core):
        self.core = core
        self.store = core.store

    def available(self) -> str | None:
        """Why research cannot run here, or None."""
        cfg = self.core.cfg
        if not cfg.research.enabled:
            return "looking things up online is off (Settings > AI)"
        if not cfg.ai.enabled or not cfg.ai.model:
            return "no AI model is set up (Settings > AI)"
        try:
            import prompture.research  # noqa: F401
        except ImportError:
            return "this Prompture has no research agent: update Prompture"
        return None

    def submit(self, title_id: str) -> dict[str, Any]:
        why = self.available()
        if why:
            raise MarcarrError(why)
        t = self.store.title(title_id)
        if t["type"] == "show":
            raise MarcarrError("look up the cuts of a film or an episode, not a whole show")
        return self.core.worker.submit("research", f"Look up the cuts of {t['name']}",
                                       {"title": title_id})

    def job_research(self, payload: dict[str, Any], ctx: JobContext) -> dict[str, Any]:
        why = self.available()
        if why:
            raise MarcarrError(why)
        cfg = self.core.cfg
        if self.store.month_cost() >= cfg.ai.monthly_limit:
            raise MarcarrError(f"this month's AI limit (${cfg.ai.monthly_limit:.2f}) is reached")
        title_id = payload["title"]
        t = self.store.title(title_id)
        videos = [v for v in self.store.videos_of(title_id) if v.get("in_plex", 1)]
        labels = edition_labels(videos)
        question = question_for(t, [labels[v["id"]]["name"] for v in videos])
        ctx.phase(1, 2, "research", "searching and reading")
        report = self._ask(question, ctx)
        data = report.to_dict() if hasattr(report, "to_dict") else dict(report)
        answer = str(data.get("answer") or "").strip()
        sources = [{"n": s.get("n"), "url": s.get("url"), "title": s.get("title") or "",
                    "cited": bool(s.get("cited"))}
                   for s in data.get("sources") or [] if s.get("url") and s.get("opened")]
        cost = float(data.get("cost") or 0.0)
        found = CutsFound()
        ctx.phase(2, 2, "research", "reading the answer")
        if answer and data.get("synthesis") != "none":
            with ai.metered() as meter:
                found = ai.ask_json(cfg.ai, CutsFound, EXTRACT_SYSTEM, _numbered(answer, sources),
                                    max_tokens=6000)
            cost += meter.cost
        self.store.add_usage(None, "research", cost, int((data.get("usage") or {}).get("total_tokens") or 0))
        run = self.store.add_research_run(
            title_id, TOPIC, question, model=str(data.get("model") or cfg.ai.model), answer=answer,
            sources=sources, result=found.model_dump(), cost=cost)
        made = self._land(title_id, videos, labels, found, sources, run["id"])
        self.core.events.emit("research.finished", {"title": title_id, "run": run["id"], "ranges": made})
        return {"run": run["id"], "ranges": made, "cost": round(cost, 4),
                "message": (f"{made} differences found online, waiting for review" if made
                            else "nothing usable found online")}

    def _ask(self, question: str, ctx: JobContext) -> Any:
        from prompture.research import ResearchAgent, ResearchBudget

        cfg = self.core.cfg
        model, _ = ai.model_spec(cfg.ai)
        agent = ResearchAgent(model, depth=cfg.research.depth, driver=ai.driver_for(cfg.ai),
                              budget=ResearchBudget(max_cost=cfg.research.max_cost))
        return agent.run(question)

    def _land(self, title_id: str, videos: list[dict[str, Any]], labels: dict[str, dict[str, Any]],
              found: CutsFound, sources: list[dict[str, Any]], run_id: str) -> int:
        """Each difference becomes a proposed range; one with a time sits on the local
        version of that cut when there is one."""
        urls = {s["n"]: s["url"] for s in sources}
        self.store.drop_cut_proposals(title_id, SOURCE)
        made = 0
        for d in found.differences:
            vid = _video_of(d.edition if d.kind != "removed" else d.base, videos, labels)
            start = end = None
            if d.at:
                try:
                    start = ai.parse_approx(d.at)
                except ai.AIError:
                    start = None
            if start is not None and d.length_seconds and d.length_seconds > 0:
                end = start + float(d.length_seconds)
            elif start is not None:
                start = None if vid is None else start  # a lone time still helps on the timeline
            self.store.add_cut_range(
                title_id, edition=d.edition, base=d.base, kind=d.kind, video_id=vid,
                start=start, end=end, extra=d.length_seconds, source=f"{SOURCE}:{run_id}",
                confidence=CONFIDENCE, note=d.description,
                evidence=[urls[n] for n in d.cited if n in urls])
            made += 1
        return made


def _numbered(answer: str, sources: list[dict[str, Any]]) -> str:
    refs = "\n".join(f"[{s['n']}] {s['title']} {s['url']}" for s in sources)
    return f"{answer}\n\nSources:\n{refs}"


def _video_of(name: str, videos: list[dict[str, Any]], labels: dict[str, dict[str, Any]]) -> str | None:
    """The local version whose cut name matches *name* (Extended ~ Extended Edition)."""
    want = (name or "").lower()
    if not want:
        return None
    key = want.split()[0]
    for v in videos:
        have = (labels.get(v["id"], {}).get("name") or "").lower()
        if have and (have in want or want in have or have.split()[0] == key):
            return str(v["id"])
    return None
