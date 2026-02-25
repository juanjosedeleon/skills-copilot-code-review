"""
Announcement endpoints for the High School Management System API
"""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from bson import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _validate_teacher(teacher_username: Optional[str]) -> Dict[str, Any]:
    if not teacher_username:
        raise HTTPException(
            status_code=401,
            detail="Authentication required for this action"
        )

    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    return teacher


def _parse_date_or_none(date_str: Optional[str], field_name: str) -> Optional[date]:
    if date_str is None or date_str == "":
        return None

    try:
        return date.fromisoformat(date_str)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be in YYYY-MM-DD format"
        ) from exc


def _serialize_announcement(announcement: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(announcement["_id"]),
        "message": announcement["message"],
        "start_date": announcement.get("start_date"),
        "expiration_date": announcement["expiration_date"]
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_announcements() -> List[Dict[str, Any]]:
    """Get currently active announcements for public display."""
    today = date.today().isoformat()
    query = {
        "expiration_date": {"$gte": today},
        "$or": [
            {"start_date": None},
            {"start_date": ""},
            {"start_date": {"$lte": today}}
        ]
    }

    announcements = announcements_collection.find(query).sort("expiration_date", 1)
    return [_serialize_announcement(announcement) for announcement in announcements]


@router.get("/manage", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: Optional[str] = Query(None)) -> List[Dict[str, Any]]:
    """Get all announcements, including expired, for management UI."""
    _validate_teacher(teacher_username)

    announcements = announcements_collection.find({}).sort([
        ("expiration_date", 1),
        ("start_date", 1)
    ])
    return [_serialize_announcement(announcement) for announcement in announcements]


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Create a new announcement. Expiration date is required."""
    _validate_teacher(teacher_username)

    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    parsed_start = _parse_date_or_none(start_date, "start_date")
    parsed_expiration = _parse_date_or_none(expiration_date, "expiration_date")
    if parsed_expiration is None:
        raise HTTPException(status_code=400, detail="expiration_date is required")

    if parsed_start and parsed_start > parsed_expiration:
        raise HTTPException(
            status_code=400,
            detail="expiration_date must be on or after start_date"
        )

    new_announcement = {
        "message": message,
        "start_date": parsed_start.isoformat() if parsed_start else None,
        "expiration_date": parsed_expiration.isoformat()
    }

    result = announcements_collection.insert_one(new_announcement)
    created = announcements_collection.find_one({"_id": result.inserted_id})
    return _serialize_announcement(created)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: str,
    expiration_date: str,
    start_date: Optional[str] = None,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, Any]:
    """Update an existing announcement."""
    _validate_teacher(teacher_username)

    message = message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")

    parsed_start = _parse_date_or_none(start_date, "start_date")
    parsed_expiration = _parse_date_or_none(expiration_date, "expiration_date")
    if parsed_expiration is None:
        raise HTTPException(status_code=400, detail="expiration_date is required")

    if parsed_start and parsed_start > parsed_expiration:
        raise HTTPException(
            status_code=400,
            detail="expiration_date must be on or after start_date"
        )

    try:
        object_id = ObjectId(announcement_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid announcement id") from exc

    result = announcements_collection.update_one(
        {"_id": object_id},
        {
            "$set": {
                "message": message,
                "start_date": parsed_start.isoformat() if parsed_start else None,
                "expiration_date": parsed_expiration.isoformat()
            }
        }
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    updated = announcements_collection.find_one({"_id": object_id})
    return _serialize_announcement(updated)


@router.delete("/{announcement_id}", response_model=Dict[str, str])
def delete_announcement(
    announcement_id: str,
    teacher_username: Optional[str] = Query(None)
) -> Dict[str, str]:
    """Delete an announcement."""
    _validate_teacher(teacher_username)

    try:
        object_id = ObjectId(announcement_id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Invalid announcement id") from exc

    result = announcements_collection.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
