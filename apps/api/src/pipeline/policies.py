"""RenditionPolicy — fail-closed adaptation/judge outcomes (S6 / design §6.2)."""

from __future__ import annotations

from enum import StrEnum

from src.pipeline.contracts._common import FidelityVerdict, FitVerdict
from src.pipeline.contracts.judge import JudgeOutput


class RenditionAction(StrEnum):
    ship = "ship"
    retry_fidelity = "retry_fidelity"
    retry_fit = "retry_fit"
    show_original_with_warning = "show_original_with_warning"
    ship_low_confidence = "ship_low_confidence"


class RenditionPolicy:
    @staticmethod
    def on_verdict(verdict: JudgeOutput, *, fidelity_attempt: int, fit_attempt: int) -> RenditionAction:  # noqa: E501
        fid = verdict.fidelity.verdict
        fit = verdict.audience_fit.verdict
        if fid == FidelityVerdict.fail:
            if fidelity_attempt < 1:
                return RenditionAction.retry_fidelity
            return RenditionAction.show_original_with_warning
        if fit == FitVerdict.fail:
            if fit_attempt < 1:
                return RenditionAction.retry_fit
            return RenditionAction.ship_low_confidence
        if fit == FitVerdict.weak:
            return RenditionAction.ship_low_confidence
        return RenditionAction.ship
