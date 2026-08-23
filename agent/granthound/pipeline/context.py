"""Per-batch run state. One RunContext per graph invocation, passed through
invocation_state; never a module global (two batches in one process must
not see each other's work)."""

from dataclasses import dataclass, field
from datetime import date, datetime

from granthound.pipeline.deterministic import Fetcher, run_id_for
from granthound.seeds.profile import OrgProfile
from granthound.store.models import DecisionPackage, DeterministicEval, FitRecord, VerifierRecord
from granthound.store.protocol import Store

MAX_REJECTIONS = 2


@dataclass
class ProgramWork:
    """One program's slot for this run: what the deterministic layer found,
    what each LLM node recorded, and the audit flags raised along the way."""

    program_id: str
    url: str
    det: DeterministicEval | None = None
    verifier: VerifierRecord | None = None
    fit: FitRecord | None = None
    package: DecisionPackage | None = None
    flags: list[str] = field(default_factory=list)
    rejections: dict[str, int] = field(default_factory=dict)
    error: str | None = None

    def flag(self, name: str) -> None:
        if name not in self.flags:
            self.flags.append(name)


@dataclass
class RunContext:
    run_id: str
    at: datetime
    store: Store
    fetcher: Fetcher
    org: OrgProfile
    programs: dict[str, ProgramWork]
    node_models: dict[str, str] = field(default_factory=dict)

    @property
    def today(self) -> date:
        """The run's date. Every stage reads this instead of a clock, so a
        replay of the same `at` produces the same deadline math."""
        return self.at.date()

    @property
    def program_ids(self) -> list[str]:
        return sorted(self.programs)

    def work(self, program_id: str) -> ProgramWork | None:
        return self.programs.get(program_id)

    @classmethod
    def create(
        cls, targets: list[tuple[str, str]], at: datetime, *, store: Store, fetcher: Fetcher, org: OrgProfile
    ) -> "RunContext":
        """Build the batch. A duplicate program id is refused rather than
        collapsed: the dict comprehension would keep the last url and drop
        the earlier target silently, so a program the org is watching would
        go unchecked with nothing in the run to say so."""
        programs: dict[str, ProgramWork] = {}
        for program_id, url in targets:
            if program_id in programs:
                raise ValueError(f"duplicate program id in this batch: {program_id}")
            programs[program_id] = ProgramWork(program_id=program_id, url=url)
        return cls(run_id=run_id_for(at), at=at, store=store, fetcher=fetcher, org=org, programs=programs)
