from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from dependencies import get_db, get_current_user

router = APIRouter(
    prefix="/invites",
    tags=["Invites"]
)


@router.post("/events/{event_id}", response_model=schemas.EventInviteResponse)
def send_event_invite(event_id: int, invite: schemas.EventInviteCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.creator_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the event creator can invite users")

    if invite.user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot invite yourself")

    target_user = db.query(models.User).filter(models.User.id == invite.user_id).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")

    friendship = db.query(models.Friendship).filter(
        ((models.Friendship.user_one_id == current_user.id) &
         (models.Friendship.user_two_id == target_user.id)) |
        ((models.Friendship.user_one_id == target_user.id) &
         (models.Friendship.user_two_id == current_user.id))
    ).first()

    if not friendship:
        raise HTTPException(status_code=400, detail="You can only invite friends to events")

    existing_invite = db.query(models.EventInvite).filter(
        models.EventInvite.event_id == event.id,
        models.EventInvite.user_id == target_user.id,
    ).first()
    if existing_invite:
        raise HTTPException(status_code=400, detail="Invite already exists for this user")

    event_invite = models.EventInvite(
        event_id=event.id,
        user_id=target_user.id,
        status="pending"
    )
    db.add(event_invite)
    db.commit()
    db.refresh(event_invite)

    return {
        "id": event_invite.id,
        "event_id": event_invite.event_id,
        "user_id": event_invite.user_id,
        "status": event_invite.status,
        "created_at": event_invite.created_at,
        "event_title": event.title,
        "creator_user_id": current_user.id,
        "creator_email": current_user.email,
    }


@router.get("/", response_model=list[schemas.EventInviteResponse])
def get_received_invites(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    invites = db.query(models.EventInvite).filter(
        models.EventInvite.user_id == current_user.id,
        models.EventInvite.status == "pending"
    ).all()

    results = []
    for invite in invites:
        results.append({
            "id": invite.id,
            "event_id": invite.event_id,
            "user_id": invite.user_id,
            "status": invite.status,
            "created_at": invite.created_at,
            "event_title": invite.event.title,
            "creator_user_id": invite.event.creator_user_id,
            "creator_email": invite.event.creator.email,
        })
    return results


@router.post("/{invite_id}/accept")
def accept_event_invite(invite_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite = db.query(models.EventInvite).filter(models.EventInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    if invite.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to accept this invite")

    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite already processed")

    invite.status = "accepted"
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "event_id": invite.event_id,
        "user_id": invite.user_id,
        "status": invite.status,
        "created_at": invite.created_at,
        "event_title": invite.event.title,
        "creator_user_id": invite.event.creator_user_id,
        "creator_email": invite.event.creator.email,
    }


@router.post("/{invite_id}/decline")
def decline_event_invite(invite_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    invite = db.query(models.EventInvite).filter(models.EventInvite.id == invite_id).first()
    if not invite:
        raise HTTPException(status_code=404, detail="Invite not found")

    if invite.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to decline this invite")

    if invite.status != "pending":
        raise HTTPException(status_code=400, detail="Invite already processed")

    invite.status = "declined"
    db.commit()
    db.refresh(invite)

    return {
        "id": invite.id,
        "event_id": invite.event_id,
        "user_id": invite.user_id,
        "status": invite.status,
        "created_at": invite.created_at,
        "event_title": invite.event.title,
        "creator_user_id": invite.event.creator_user_id,
        "creator_email": invite.event.creator.email,
    }
