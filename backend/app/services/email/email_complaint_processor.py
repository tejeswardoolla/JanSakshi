import re
import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from fastapi import BackgroundTasks

from app.core.config import utc_now
from app.models.complaint import Complaint, ComplaintEvent
from app.models.email_message import EmailMessage
from app.pipeline.complaint_pipeline import ComplaintProcessingPipeline, NormalizedComplaintInput
from app.services.email.gemini_email_extractor import GeminiEmailExtractor, GeminiEmailExtractionResult
from app.services.email.attachment_processor import AttachmentProcessor
from app.services.email.acknowledgement_service import AcknowledgementService
from app.services.email.email_intent_classifier import (
    EmailIntentClassifier,
    DecisionType,
    ClassificationResult
)

logger = logging.getLogger("jansakshi.email.complaint_processor")

class EmailComplaintProcessor:
    """
    Master service for ingesting incoming emails into JanSakshi:
    - Guarantees strict duplicate prevention via unique gmail_message_id
    - Evaluates 4-layer intent classification to filter non-civic emails
    - Routes ambiguous messages to Admin Review Desk
    - Extracts structured data with Gemini AI for confirmed civic complaints
    - Processes supported attachments safely
    - Executes the Unified Complaint Processing Pipeline
    - Handles follow-up / location clarification replies
    - Sends automated citizen acknowledgement ONLY for confirmed civic complaints
    """

    @classmethod
    async def process_raw_email(
        cls,
        db: Session,
        message_data: Dict[str, Any],
        background_tasks: Optional[BackgroundTasks] = None
    ) -> Dict[str, Any]:
        """
        Processes a parsed Gmail message dictionary through the unified complaint pipeline.
        """
        gmail_msg_id = message_data["gmail_message_id"]
        gmail_thread_id = message_data.get("gmail_thread_id")
        sender_email = message_data["sender_email"].strip().lower()
        sender_name = message_data.get("sender_name")
        subject = message_data.get("subject", "")
        snippet = message_data.get("snippet", "")
        body_plain = message_data.get("body_plain", "")
        body_html = message_data.get("body_html", "")
        received_at = message_data.get("received_at", utc_now())
        attachments = message_data.get("attachments", [])

        # ------------------------------------------------------------------
        # 1. STRICT IDEMPOTENCY CHECK (Duplicate Prevention)
        # ------------------------------------------------------------------
        existing_msg = db.query(EmailMessage).filter(EmailMessage.gmail_message_id == gmail_msg_id).first()
        if existing_msg and existing_msg.processing_status in ("processed", "ignored", "needs_review"):
            logger.info(f"Gmail message {gmail_msg_id} already recorded. Status: {existing_msg.processing_status}")
            return {
                "status": "already_processed",
                "message": f"Message {gmail_msg_id} previously processed with status {existing_msg.processing_status}.",
                "complaint_id": existing_msg.complaint_id,
                "email_record_id": existing_msg.id
            }

        # Initialize or reuse tracking entity
        if existing_msg:
            email_record = existing_msg
            email_record.processing_status = "processing"
            email_record.error_details = None
        else:
            email_record = EmailMessage(
                gmail_message_id=gmail_msg_id,
                gmail_thread_id=gmail_thread_id,
                sender_email=sender_email,
                sender_name=sender_name,
                subject=subject[:510],
                snippet=snippet[:1000] if snippet else None,
                body_plain=body_plain,
                body_html=body_html,
                received_at=received_at,
                processing_status="processing",
                created_at=utc_now(),
                updated_at=utc_now(),
            )
            db.add(email_record)

        db.commit()

        try:
            # ------------------------------------------------------------------
            # 2. THREAD CONTINUITY CHECK (Existing Complaint Link)
            # ------------------------------------------------------------------
            target_complaint: Optional[Complaint] = None
            thread_has_complaint = False

            # Check matching thread ID from previous emails
            if gmail_thread_id:
                prev_thread_email = db.query(EmailMessage).filter(
                    EmailMessage.gmail_thread_id == gmail_thread_id,
                    EmailMessage.complaint_id != None
                ).first()
                if prev_thread_email and prev_thread_email.complaint:
                    target_complaint = prev_thread_email.complaint
                    thread_has_complaint = True

            # Also check if subject/body contains referenced complaint ID
            ref_match = re.search(r'\b(JS-\d{4}-\d{5})\b', f"{subject}\n{body_plain}", re.IGNORECASE)
            if ref_match and not target_complaint:
                ref_id = ref_match.group(1).upper()
                c_cand = db.query(Complaint).filter(Complaint.complaint_id == ref_id).first()
                if c_cand:
                    target_complaint = c_cand
                    thread_has_complaint = True

            # ------------------------------------------------------------------
            # 3. 4-LAYER EMAIL INTENT CLASSIFICATION GATE
            # ------------------------------------------------------------------
            classification: ClassificationResult = await EmailIntentClassifier.classify(
                subject=subject,
                body_plain=body_plain,
                body_html=body_html,
                snippet=snippet,
                sender_email=sender_email,
                sender_name=sender_name or "",
                thread_has_complaint=thread_has_complaint
            )

            # Case A: NON_CIVIC (Account alerts, OTPs, receipts, marketing, system bounces)
            if classification.decision == DecisionType.NON_CIVIC:
                email_record.is_civic_complaint = False
                email_record.extracted_category = classification.category
                email_record.processing_status = "ignored"
                email_record.error_details = f"Non-civic email filtered [{classification.category}]: {classification.reason}"
                email_record.extracted_metadata = json.dumps({"classification": classification.model_dump()})
                db.commit()
                logger.info(f"Email {gmail_msg_id} filtered as NON_CIVIC ({classification.category}): {classification.reason}")
                return {
                    "status": "ignored",
                    "reason": classification.reason,
                    "category": classification.category,
                    "email_record_id": email_record.id
                }

            # Case B: NEEDS_ADMIN_REVIEW (Ambiguous, unclassified, or low confidence)
            if classification.decision == DecisionType.NEEDS_ADMIN_REVIEW:
                email_record.is_civic_complaint = None
                email_record.extracted_category = classification.category
                email_record.processing_status = "needs_review"
                email_record.error_details = f"Requires admin review [{classification.category}]: {classification.reason}"
                email_record.extracted_metadata = json.dumps({"classification": classification.model_dump()})
                db.commit()
                logger.info(f"Email {gmail_msg_id} routed to NEEDS_ADMIN_REVIEW: {classification.reason}")
                return {
                    "status": "needs_review",
                    "reason": classification.reason,
                    "category": classification.category,
                    "email_record_id": email_record.id
                }

            # Case C: CIVIC_FOLLOW_UP (Update to an existing verified complaint)
            if classification.decision == DecisionType.CIVIC_FOLLOW_UP and target_complaint:
                # Perform structured extraction to check for updated coordinates/landmarks
                extraction: GeminiEmailExtractionResult = await GeminiEmailExtractor.extract(
                    subject=subject,
                    body=body_plain,
                    sender_email=sender_email
                )

                email_record.is_follow_up = True
                email_record.complaint_id = target_complaint.complaint_id
                email_record.extracted_category = target_complaint.category
                email_record.extracted_location_text = extraction.location_text
                email_record.extracted_metadata = extraction.model_dump_json()

                # If existing complaint was missing location and follow-up provides it
                if (target_complaint.latitude is None or target_complaint.longitude is None) and (extraction.latitude is not None and extraction.longitude is not None):
                    old_status = target_complaint.status
                    target_complaint.latitude = extraction.latitude
                    target_complaint.longitude = extraction.longitude
                    target_complaint.location_source = "maps_url" if extraction.google_maps_url else "email_follow_up"
                    target_complaint.google_maps_url = extraction.google_maps_url or f"https://www.google.com/maps?q={extraction.latitude:.6f},{extraction.longitude:.6f}"
                    target_complaint.status = "Received"
                    target_complaint.updated_at = utc_now()

                    event = ComplaintEvent(
                        complaint_id=target_complaint.complaint_id,
                        event_type="location_clarification_provided",
                        previous_value=old_status,
                        new_value=f"{extraction.latitude:.5f}, {extraction.longitude:.5f}",
                        description=f"Citizen clarified incident location via email reply: {extraction.location_text or 'GPS coordinates'}",
                        source="email_follow_up",
                        created_at=utc_now()
                    )
                    db.add(event)
                else:
                    event = ComplaintEvent(
                        complaint_id=target_complaint.complaint_id,
                        event_type="email_follow_up_received",
                        previous_value=None,
                        new_value=subject[:100],
                        description=f"Citizen sent follow-up email: {body_plain[:200]}",
                        source="email_follow_up",
                        created_at=utc_now()
                    )
                    db.add(event)

                email_record.processing_status = "processed"
                db.commit()
                logger.info(f"Linked follow-up email {gmail_msg_id} to existing complaint {target_complaint.complaint_id}")
                return {
                    "status": "follow_up_processed",
                    "complaint_id": target_complaint.complaint_id,
                    "email_record_id": email_record.id
                }

            # ------------------------------------------------------------------
            # 4. CONFIRMED CIVIC COMPLAINT -> STRUCTURED EXTRACTION & PIPELINE
            # ------------------------------------------------------------------
            extraction: GeminiEmailExtractionResult = await GeminiEmailExtractor.extract(
                subject=subject,
                body=body_plain,
                sender_email=sender_email
            )

            email_record.is_civic_complaint = True
            email_record.extracted_category = extraction.category if extraction.category != "Other" else classification.category
            email_record.extracted_location_text = extraction.location_text
            email_record.extracted_metadata = extraction.model_dump_json()
            # 5. ATTACHMENT PROCESSING & EVIDENCE SAVING
            # ------------------------------------------------------------------
            saved_evidence = []
            attachments_info = []
            for att in attachments:
                meta = AttachmentProcessor.process_attachment(
                    filename=att["filename"],
                    content_bytes=att["data"],
                    mime_type=att.get("mime_type")
                )
                if meta:
                    saved_evidence.append(meta)
                    attachments_info.append({
                        "filename": meta["original_filename"],
                        "file_size": meta["file_size"],
                        "file_type": meta["file_type"]
                    })

            email_record.has_attachments = bool(saved_evidence)
            email_record.attachments_count = len(saved_evidence)
            email_record.attachments_info = json.dumps(attachments_info) if attachments_info else None

            # ------------------------------------------------------------------
            # 6. UNIFIED COMPLAINT PROCESSING PIPELINE EXECUTION
            # ------------------------------------------------------------------
            has_coords = extraction.latitude is not None and extraction.longitude is not None
            location_src = "maps_url" if extraction.google_maps_url else ("email_parsed" if has_coords else "email_pending_clarification")

            normalized_input = NormalizedComplaintInput(
                category=extraction.category,
                description=extraction.description,
                latitude=extraction.latitude,
                longitude=extraction.longitude,
                location_source=location_src,
                google_maps_url=extraction.google_maps_url,
                citizen_name=sender_name,
                citizen_email=sender_email,
                submission_channel="email",
                pre_saved_evidence=saved_evidence
            )

            pipeline = ComplaintProcessingPipeline(db=db, background_tasks=background_tasks)
            complaint_record = await pipeline.execute(normalized_input)

            email_record.complaint_id = complaint_record.complaint_id
            email_record.processing_status = "awaiting_information" if (extraction.latitude is None) else "processed"
            db.commit()

            # Record landmark and coordinate distinction in audit history
            if extraction.location_text:
                coord_note = (
                    f"Exact coordinates captured ({location_src}): {extraction.latitude:.5f}, {extraction.longitude:.5f}"
                    if has_coords else "Exact GPS coordinates pending clarification"
                )
                loc_event = ComplaintEvent(
                    complaint_id=complaint_record.complaint_id,
                    event_type="location_landmark_identified",
                    previous_value=None,
                    new_value=extraction.location_text[:128],
                    description=f"Landmark/address extracted: '{extraction.location_text}'. {coord_note}.",
                    source="email_extraction",
                    created_at=utc_now()
                )
                db.add(loc_event)
                db.commit()

            # ------------------------------------------------------------------
            # 7. AUTOMATIC CITIZEN ACKNOWLEDGEMENT EMAIL
            # ------------------------------------------------------------------
            AcknowledgementService.send_acknowledgement(
                db=db,
                complaint=complaint_record,
                email_record=email_record,
                location_missing=(extraction.latitude is None)
            )

            logger.info(f"Successfully created complaint {complaint_record.complaint_id} from email {gmail_msg_id}")
            return {
                "status": "success",
                "complaint_id": complaint_record.complaint_id,
                "tracking_token": complaint_record.tracking_token,
                "category": complaint_record.category,
                "email_record_id": email_record.id,
                "location_status": "captured" if (extraction.latitude is not None) else "awaiting_clarification",
                "evidence_count": len(saved_evidence)
            }

        except Exception as e:
            logger.error(f"Failed processing email {gmail_msg_id}: {e}", exc_info=True)
            db.rollback()
            # Update failed status in a fresh transaction
            email_record = db.query(EmailMessage).filter(EmailMessage.gmail_message_id == gmail_msg_id).first()
            if email_record:
                email_record.processing_status = "failed"
                email_record.error_details = str(e)
                db.commit()
            return {
                "status": "failed",
                "error": str(e),
                "gmail_message_id": gmail_msg_id
            }

