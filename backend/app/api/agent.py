from __future__ import annotations

import anthropic
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.schemas.agent import AskRequest, AskResponse
from app.services.agent import AgentError, AgentNotConfiguredError, ask

router = APIRouter(tags=["agent"])


@router.post("/ask", response_model=AskResponse)
def ask_question(body: AskRequest, db: Session = Depends(get_db)):
    try:
        return ask(body.question, db, body.dataset_ids)
    except AgentNotConfiguredError as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e)) from e
    except AgentError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e)) from e
    except anthropic.AuthenticationError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "The Anthropic API key was rejected.") from e
    except anthropic.RateLimitError as e:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Rate limited by the Anthropic API. Try again shortly.") from e
    except anthropic.APIStatusError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Anthropic API error: {e.message}") from e
    except anthropic.APIConnectionError as e:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Could not reach the Anthropic API.") from e
