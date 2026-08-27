from enum import Enum

from pydantic import BaseModel, Field, HttpUrl


class ExperienceLevel(str, Enum):
    internship = "1"
    entry_level = "2"
    associate = "3"
    mid_senior = "4"
    director = "5"
    executive = "6"

    @property
    def label(self) -> str:
        return {
            ExperienceLevel.internship: "Internship",
            ExperienceLevel.entry_level: "Entry level",
            ExperienceLevel.associate: "Associate",
            ExperienceLevel.mid_senior: "Mid-Senior level",
            ExperienceLevel.director: "Director",
            ExperienceLevel.executive: "Executive",
        }[self]


class JobType(str, Enum):
    full_time = "F"
    part_time = "P"
    contract = "C"
    temporary = "T"
    volunteer = "V"
    internship = "I"
    other = "O"

    @property
    def label(self) -> str:
        return {
            JobType.full_time: "Full-time",
            JobType.part_time: "Part-time",
            JobType.contract: "Contract",
            JobType.temporary: "Temporary",
            JobType.volunteer: "Volunteer",
            JobType.internship: "Internship",
            JobType.other: "Other",
        }[self]


class WorkModel(str, Enum):
    on_site = "1"
    remote = "2"
    hybrid = "3"

    @property
    def label(self) -> str:
        return {
            WorkModel.on_site: "On-site",
            WorkModel.remote: "Remote",
            WorkModel.hybrid: "Hybrid",
        }[self]


class TimePosted(str, Enum):
    any_time = ""
    past_24_hours = "r86400"
    past_week = "r604800"
    past_month = "r2592000"

    @property
    def label(self) -> str:
        return {
            TimePosted.any_time: "Any time",
            TimePosted.past_24_hours: "Past 24 hours",
            TimePosted.past_week: "Past week",
            TimePosted.past_month: "Past month",
        }[self]


class Seniority(str, Enum):
    any = "Any"
    intern = "Intern"
    junior = "Junior"
    mid = "Mid-level"
    senior = "Senior"
    staff = "Staff"
    lead = "Lead"
    principal = "Principal"
    manager = "Manager"

    @property
    def query_prefixes(self) -> list[str]:
        return {
            Seniority.any: [""],
            Seniority.intern: ["Intern", "Internship"],
            Seniority.junior: ["Junior", "Entry Level"],
            Seniority.mid: ["Mid Level", ""],
            Seniority.senior: ["Senior", "Sr"],
            Seniority.staff: ["Staff"],
            Seniority.lead: ["Lead"],
            Seniority.principal: ["Principal"],
            Seniority.manager: ["Manager"],
        }[self]


class SearchFilters(BaseModel):
    location: str = ""
    experience_level: ExperienceLevel | None = None
    job_type: JobType | None = None
    work_model: WorkModel | None = None
    time_posted: TimePosted = TimePosted.any_time
    easy_apply: bool = False
    under_10_applicants: bool = False

    def to_params(self, keywords: str, start: int) -> dict[str, str | int | bool]:
        params: dict[str, str | int | bool] = {"keywords": keywords, "start": start}
        if self.location:
            params["location"] = self.location
        if self.easy_apply:
            params["f_AL"] = "true"
        if self.under_10_applicants:
            params["f_JIYN"] = "true"
        if self.experience_level:
            params["f_E"] = self.experience_level.value
        if self.job_type:
            params["f_JT"] = self.job_type.value
        if self.work_model:
            params["f_WT"] = self.work_model.value
        if self.time_posted.value:
            params["f_TPR"] = self.time_posted.value
        return params


class JobSummary(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    post_time: str = ""
    url: HttpUrl | str
    search_query: str


class JobDetails(BaseModel):
    description: str = ""
    criteria: dict[str, str] = Field(default_factory=dict)


class JobRecord(JobSummary):
    seniority: Seniority = Seniority.any
    requested_positions: str = ""
    status: str = "New"
    seniority_match_score: int | None = None
    details: JobDetails = Field(default_factory=JobDetails)

    def to_flat_dict(self) -> dict[str, object]:
        return {
            "linkedin_job_id": self.job_id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "post_time": self.post_time,
            "url": str(self.url),
            "seniority": self.seniority.value,
            "requested_positions": self.requested_positions,
            "search_query": self.search_query,
            "status": self.status,
            "seniority_match_score": self.seniority_match_score,
            "description": self.details.description,
            "criteria": "; ".join(
                f"{key}: {value}" for key, value in self.details.criteria.items()
            ),
            "work_model": self.details.criteria.get("Work model", "")
            or self.details.criteria.get("Workplace type", ""),
            "job_type": self.details.criteria.get("Employment type", "")
            or self.details.criteria.get("Job type", ""),
            "experience_level": self.details.criteria.get("Seniority level", ""),
        }


def labels_for(enum_type: type[Enum]) -> list[tuple[str, str]]:
    """Return ``(label, value)`` pairs for a labeled enum, in declaration order."""
    return [(str(getattr(item, "label", item.value)), item.value) for item in enum_type]


def optional_labels_for(enum_type: type[Enum]) -> list[tuple[str, str]]:
    """Like :func:`labels_for` but prepends an ``Any`` option with empty value."""
    return [("Any", ""), *labels_for(enum_type)]
