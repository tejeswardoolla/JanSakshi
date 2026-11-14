import re
import datetime
from typing import Optional, List
from fastapi import UploadFile, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.models.complaint import Complaint
from app.repositories import ComplaintRepository
from app.services.storage_service import save_evidence_file, cleanup_orphaned_file
from app.services.id_service import generate_complaint_id
from app.tasks.background_tasks import post_complaint_submission_task

VALID_CATEGORIES = {
    "Road Damage / Potholes",
    "Broken Streetlights",
    "Garbage Accumulation",
    "Drainage Overflow",
    "Water Leakage",
    "Damaged Public Infrastructure",
    "Other",
}

class NormalizedComplaintInput:
    """Normalized payload data accepted by the pipeline from any channel."""
    def __init__(
        self,
        category: str,
        description: str,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        location_accuracy: Optional[float] = None,
        location_source: str = "gps",
        google_maps_url: Optional[str] = None,
        citizen_name: Optional[str] = None,
        citizen_email: Optional[str] = None,
        citizen_phone: Optional[str] = None,
        submission_channel: str = "website",
        evidence_files: Optional[List[UploadFile]] = None,
        pre_saved_evidence: Optional[List[dict]] = None
    ):
        self.category = category
        self.description = description
        self.latitude = latitude
        self.longitude = longitude
        self.location_accuracy = location_accuracy
        self.location_source = location_source
        self.google_maps_url = google_maps_url
        self.citizen_name = citizen_name
        self.citizen_email = citizen_email
        self.citizen_phone = citizen_phone
        self.submission_channel = submission_channel
        self.evidence_files = evidence_files or []
        self.pre_saved_evidence = pre_saved_evidence or []

class ComplaintProcessingPipeline:
    """
    Unified Complaint Processing Pipeline:
    Common entry point for all channels (Website and Email).
    Flow: Validate -> Normalize -> Persist -> Attach Evidence -> Audit Events -> Queue Async Tasks
    """

    def __init__(self, db: Session, background_tasks: Optional[BackgroundTasks] = None):
        self.db = db
        self.background_tasks = background_tasks
        self.repo = ComplaintRepository(db)

    def validate_input(self, inp: NormalizedComplaintInput):
        # 1. Validate Category
        clean_category = inp.category.strip()
        if clean_category not in VALID_CATEGORIES:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category '{inp.category}'. Must be one of: {', '.join(sorted(VALID_CATEGORIES))}"
            )

        # 2. Validate Description
        clean_desc = inp.description.strip()
        if len(clean_desc) < 10:
            raise HTTPException(status_code=400, detail="Description must be at least 10 characters long.")
        if len(clean_desc) > 2000:
            raise HTTPException(status_code=400, detail="Description cannot exceed 2000 characters.")

        # 3. Validate Coordinates
        if inp.latitude is not None and inp.longitude is not None:
            if not (-90 <= inp.latitude <= 90 and -180 <= inp.longitude <= 180):
                raise HTTPException(status_code=400, detail="Coordinates out of valid range (-90 to 90 lat, -180 to 180 lng).")
        elif inp.submission_channel != "email":
            raise HTTPException(status_code=400, detail="Location coordinates are required for website submissions.")

        # 4. Validate Optional Contact Info
        if inp.citizen_email:
            clean_email = inp.citizen_email.strip()
            if clean_email and not re.match(r"[^@]+@[^@]+\.[^@]+", clean_email):
                raise HTTPException(status_code=400, detail="Invalid citizen email format.")

        if inp.citizen_phone:
            clean_phone = inp.citizen_phone.strip()
            if clean_phone and not re.match(r"^[0-9+\-\s()]{7,20}$", clean_phone):
                raise HTTPException(status_code=400, detail="Invalid citizen phone format.")

    async def execute(self, inp: NormalizedComplaintInput) -> Complaint:
        # Step 1: Input Validation
        self.validate_input(inp)

        # Step 2: Process & Save Evidence
        saved_files_metadata = list(inp.pre_saved_evidence)
        video_count = sum(1 for m in saved_files_metadata if "video" in m.get("file_type", "") or m.get("stored_filename", "").endswith(".mp4"))

        if inp.evidence_files:
            try:
                for file in inp.evidence_files:
                    if not file.filename:
                        continue
                    meta = await save_evidence_file(file)
                    if "video" in meta["file_type"] or meta["stored_filename"].endswith(".mp4"):
                        video_count += 1
                        if video_count > 1:
                            raise HTTPException(status_code=400, detail="A maximum of 1 video file is supported per complaint.")
                    saved_files_metadata.append(meta)
            except Exception as e:
                for meta in saved_files_metadata:
                    if meta not in inp.pre_saved_evidence:
                        cleanup_orphaned_file(meta["storage_path"])
                if isinstance(e, HTTPException):
                    raise e
                raise HTTPException(status_code=500, detail=f"Failed processing evidence: {str(e)}")

        # Step 3: Transactional Persistence
        google_maps_url = (
            inp.google_maps_url
            if getattr(inp, "google_maps_url", None)
            else (
                f"https://www.google.com/maps?q={inp.latitude:.6f},{inp.longitude:.6f}"
                if (inp.latitude is not None and inp.longitude is not None)
                else None
            )
        )
        initial_status = "Awaiting Location" if (inp.latitude is None or inp.longitude is None) else "Received"

        try:
            complaint_id = generate_complaint_id(self.db)

            complaint_record = self.repo.create({
                "complaint_id": complaint_id,
                "category": inp.category.strip(),
                "description": inp.description.strip(),
                "latitude": inp.latitude,
                "longitude": inp.longitude,
                "location_accuracy": inp.location_accuracy,
                "location_source": inp.location_source,
                "google_maps_url": google_maps_url,
                "citizen_name": inp.citizen_name.strip() if inp.citizen_name else None,
                "citizen_email": inp.citizen_email.strip() if inp.citizen_email else None,
                "citizen_phone": inp.citizen_phone.strip() if inp.citizen_phone else None,
                "submission_channel": inp.submission_channel,
                "status": initial_status
            })

            # Associate evidence
            for meta in saved_files_metadata:
                self.repo.add_evidence({
                    "complaint_id": complaint_id,
                    "original_filename": meta["original_filename"],
                    "stored_filename": meta["stored_filename"],
                    "file_type": meta["file_type"],
                    "file_size": meta["file_size"],
                    "storage_path": meta["storage_path"]
                })

            # Record initial audit event
            self.repo.add_event(
                complaint_id=complaint_id,
                event_type="complaint_received",
                new_value="Received",
                description=f"Complaint received via {inp.submission_channel} channel.",
                source=inp.submission_channel
            )

            if saved_files_metadata:
                self.repo.add_event(
                    complaint_id=complaint_id,
                    event_type="evidence_uploaded",
                    description=f"{len(saved_files_metadata)} evidence file(s) securely attached.",
                    source=inp.submission_channel
                )

            # Commit transaction safely
            self.db.commit()
            self.db.refresh(complaint_record)

            # Step 4: Dispatch non-blocking background task
            if self.background_tasks:
                self.background_tasks.add_task(post_complaint_submission_task, complaint_id)

            return complaint_record

        except Exception as db_err:
            self.db.rollback()
            for meta in saved_files_metadata:
                cleanup_orphaned_file(meta["storage_path"])
            if isinstance(db_err, HTTPException):
                raise db_err
            raise HTTPException(status_code=500, detail=f"Database persistence failure: {str(db_err)}")

