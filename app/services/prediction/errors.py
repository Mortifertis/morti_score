from fastapi import HTTPException, status


def raise_prediction_error(
    *,
    status_code: int,
    code: str,
    message: str,
    extra: dict[str, int] | None = None,
) -> None:
    detail: dict[str, object] = {
        "code": code,
        "message": message,
    }
    if extra:
        detail.update(extra)
    raise HTTPException(status_code=status_code, detail=detail)


def raise_insufficient_team_history(team_side: str) -> None:
    raise_prediction_error(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code=f"insufficient_{team_side}_team_history",
        message=(
            f"{team_side.capitalize()} team does not have enough "
            "historical matches for prediction."
        ),
    )
