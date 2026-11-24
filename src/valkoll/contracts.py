"""Pydantic v2 data contracts for the Valkoll review pipeline."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KommunReportRate(BaseModel):
    """One row of Valkoll's published per-kommun table.

    Attributes:
        kod: Four-digit kommun code (SCB), as published in the row's data attribute.
        namn: Kommun name.
        rapporter: Reports with this kommun, excluding test reports and likely duplicates.
        rostberattigade: Eligible voters, riksdag election 2026, final count.
        per_10k_published: Rate per 10 000 eligible voters as printed on the page.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kod: str = Field(pattern=r"^\d{4}$")
    namn: str = Field(min_length=1)
    rapporter: int = Field(ge=0)
    rostberattigade: int = Field(gt=0)
    per_10k_published: float = Field(ge=0)

    @model_validator(mode="after")
    def rate_matches_counts(self) -> "KommunReportRate":
        """Fail loudly if the printed rate does not follow from the printed counts."""
        recomputed = round(self.rapporter / self.rostberattigade * 10_000, 2)
        if abs(recomputed - self.per_10k_published) > 0.005 + 1e-9:
            raise ValueError(
                f"{self.namn}: published rate {self.per_10k_published} "
                f"!= recomputed {recomputed}"
            )
        return self


class EligibleVotersKommun(BaseModel):
    """Eligible voters per kommun from Valmyndigheten's final count, riksdag election 2026.

    Attributes:
        kod: Four-digit kommun code (SCB).
        namn: Kommun name as Valmyndigheten writes it.
        rostberattigade: Eligible voters in the kommun.
        roster: Votes cast in the kommun, valid and invalid.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    kod: str = Field(pattern=r"^\d{4}$")
    namn: str = Field(min_length=1)
    rostberattigade: int = Field(gt=0)
    roster: int = Field(ge=0)

    @model_validator(mode="after")
    def votes_within_electorate(self) -> "EligibleVotersKommun":
        """Fail loudly if more votes are recorded than there are eligible voters."""
        if self.roster > self.rostberattigade:
            raise ValueError(f"{self.namn}: {self.roster} votes > {self.rostberattigade} eligible")
        return self


class IncidentReport(BaseModel):
    """One row of Valmyndigheten's incident report file, sheet "Rapporter valadmin".

    Attributes:
        rad: Row number in the Excel file, counted as Excel does (header on row 3, first report on row 4).
        inkommen: When the report was received.
        incident: When the incident happened, if given.
        representerar: Who reported (Valkansli, Röstmottagning, Länsstyrelse, Utlandsmyndighet).
        lan: County, if given.
        kommun: Kommun or mission abroad, if given.
        kategori: Valmyndigheten's category, if given.
        underkategori: Valmyndigheten's subcategory, if given.
        plats: Place of the incident, if given.
        lansstyrelse: County administrative board named in the report, if any.
        beskrivning: Free text. Personal data is already replaced by Valmyndigheten; never sent to external services.
        sekretess: True when the text is withheld under secrecy.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    rad: int = Field(ge=4)
    inkommen: datetime
    incident: datetime | None
    representerar: Literal["Valkansli", "Röstmottagning", "Länsstyrelse", "Utlandsmyndighet"]
    lan: str | None
    kommun: str | None
    plats: str | None
    kategori: str | None
    underkategori: str | None
    lansstyrelse: str | None
    beskrivning: str | None
    sekretess: bool
