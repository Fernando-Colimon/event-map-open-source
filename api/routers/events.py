from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import models
import schemas
from dependencies import get_db, get_current_user

router = APIRouter(
    prefix="/events",
    tags=["Events"]
)


def is_event_visible(event: models.Event, current_user: models.User, db: Session) -> bool:
    if event.creator_user_id == current_user.id:
        return True

    if event.visibility == "public":
        return True

    if event.visibility == "invite_only":
        invite = db.query(models.EventInvite).filter(
            models.EventInvite.event_id == event.id,
            models.EventInvite.user_id == current_user.id,
        ).first()
        return invite is not None

    if event.visibility == "private":
        # Friends may see private events
        friendship = db.query(models.Friendship).filter(
            ((models.Friendship.user_one_id == event.creator_user_id) &
             (models.Friendship.user_two_id == current_user.id)) |
            ((models.Friendship.user_one_id == current_user.id) &
             (models.Friendship.user_two_id == event.creator_user_id))
        ).first()
        if friendship:
            return True

        # Accepted invite also allows access
        accepted_invite = db.query(models.EventInvite).filter(
            models.EventInvite.event_id == event.id,
            models.EventInvite.user_id == current_user.id,
            models.EventInvite.status == "accepted",
        ).first()
        return accepted_invite is not None

    return False


@router.post("/", response_model=schemas.EventResponse)
def create_event(event: schemas.EventCreate, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    if event.visibility == "friends":
        raise HTTPException(status_code=400, detail="Visibility 'friends' is no longer supported")

    db_event = models.Event(
        creator_user_id=current_user.id,
        title=event.title,
        description=event.description,
        visibility=event.visibility,
        start_time=event.start_time,
        end_time=event.end_time,
        capacity=event.capacity,
        location_name=event.location_name,
        latitude=event.latitude,
        longitude=event.longitude,
    )

    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event


@router.get("/", response_model=list[schemas.EventResponse])
def get_events(current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    events = db.query(models.Event).all()
    visible_events = [event for event in events if is_event_visible(event, current_user, db)]
    return visible_events


@router.get("/{event_id}", response_model=schemas.EventResponse)
def get_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not is_event_visible(event, current_user, db):
        raise HTTPException(status_code=403, detail="Not authorized to view this event")

    return event

@router.delete("/{event_id}", status_code=204)
def delete_event(event_id: int, current_user: models.User = Depends(get_current_user), db: Session = Depends(get_db)):
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.creator_user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this event")
    db.delete(event)
    db.commit()
    