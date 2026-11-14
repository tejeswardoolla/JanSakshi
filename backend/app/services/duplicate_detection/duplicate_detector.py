import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from app.core.config import utc_now
from app.models.complaint import Complaint, PhysicalIssue, Evidence, ComplaintEvent, DuplicateMatch
from app.services.duplicate_detection.location_similarity import (
    calculate_haversine_distance,
    calculate_location_similarity,
)
from app.services.duplicate_detection.category_similarity import calculate_category_similarity
from app.services.duplicate_detection.text_similarity import calculate_text_similarity
from app.services.duplicate_detection.image_similarity import compare_evidence_lists
from app.services.duplicate_detection.scoring import compute_composite_score
from app.services.duplicate_detection.candidate_retrieval import retrieve_candidate_issues

logger = logging.getLogger("jansakshi.duplicate_detection")

class DuplicateDetector:
    """
    Phase 5 Intelligent Duplicate Detection Service:
    Evaluates multi-signal similarity between citizen complaints and physical issues.
    Generates explainable candidate matches and powers human-in-the-loop review workflow.
    """

    @classmethod
    def evaluate_complaint(
        cls,
        complaint_id: str,
        db: Session,
        search_radius_meters: float = 150.0
    ) -> List[DuplicateMatch]:
        """
        Runs duplicate detection for a complaint against nearby PhysicalIssue entities.
        Persists DuplicateMatch candidate records and logs audit events.
        """
        complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not complaint:
            logger.warning(f"Complaint {complaint_id} not found for duplicate detection.")
            return []

        # 1. Retrieve candidates within spatial radius
        candidates = retrieve_candidate_issues(db, complaint, search_radius_meters=search_radius_meters)
        logger.info(f"Retrieved {len(candidates)} candidate issues for {complaint_id}")

        matches_created: List[DuplicateMatch] = []
        complaint_evidence_paths = [ev.storage_path for ev in complaint.evidence_files]

        for issue, distance_meters in candidates:
            # 2. Gather text context from issue and all existing complaints associated with this issue
            issue_descriptions = [issue.description]
            issue_evidence_paths = []
            for linked_comp in issue.complaints:
                if linked_comp.complaint_id != complaint.complaint_id:
                    issue_descriptions.append(linked_comp.description)
                    for ev in linked_comp.evidence_files:
                        issue_evidence_paths.append(ev.storage_path)

            # Combined issue text representation
            combined_issue_text = " ".join(issue_descriptions)

            # 3. Compute Multi-Signal Similarities
            gps_sim = calculate_location_similarity(distance_meters)
            cat_sim = calculate_category_similarity(complaint.category, issue.category)
            text_sim = calculate_text_similarity(complaint.description, combined_issue_text)
            img_sim = compare_evidence_lists(complaint_evidence_paths, issue_evidence_paths)

            # 4. Composite Scoring & Dynamic Normalization
            score_data = compute_composite_score(
                gps_score=gps_sim,
                distance_meters=distance_meters,
                text_score=text_sim,
                image_score=img_sim,
                category_score=cat_sim,
            )

            # Only record if similarity meets minimum threshold or spatial proximity is very close
            if score_data["similarity_score"] >= 0.40 or (distance_meters <= 50.0 and cat_sim > 0.0):
                # Check for existing match record
                existing_match = db.query(DuplicateMatch).filter(
                    DuplicateMatch.complaint_id == complaint.complaint_id,
                    DuplicateMatch.candidate_physical_issue_id == issue.issue_reference_id
                ).first()

                if existing_match:
                    # Update existing record
                    existing_match.similarity_score = score_data["similarity_score"]
                    existing_match.gps_similarity = gps_sim
                    existing_match.gps_distance_meters = distance_meters
                    existing_match.text_similarity = text_sim
                    existing_match.image_similarity = img_sim
                    existing_match.category_similarity = cat_sim
                    existing_match.confidence_level = score_data["confidence_level"]
                    existing_match.recommendation = score_data["recommendation"]
                    existing_match.matching_explanation = score_data["matching_explanation"]
                    existing_match.warning_signals = score_data["warning_signals"]
                    match_record = existing_match
                else:
                    # Create new candidate match
                    match_record = DuplicateMatch(
                        complaint_id=complaint.complaint_id,
                        candidate_physical_issue_id=issue.issue_reference_id,
                        similarity_score=score_data["similarity_score"],
                        gps_similarity=gps_sim,
                        gps_distance_meters=distance_meters,
                        text_similarity=text_sim,
                        image_similarity=img_sim,
                        category_similarity=cat_sim,
                        confidence_level=score_data["confidence_level"],
                        recommendation=score_data["recommendation"],
                        matching_explanation=score_data["matching_explanation"],
                        warning_signals=score_data["warning_signals"],
                        review_status="pending",
                        created_at=utc_now(),
                        updated_at=utc_now(),
                    )
                    db.add(match_record)

                matches_created.append(match_record)

        # 5. Audit Logging
        if matches_created:
            high_count = sum(1 for m in matches_created if m.confidence_level == "high")
            event = ComplaintEvent(
                complaint_id=complaint.complaint_id,
                event_type="duplicate_candidates_identified",
                previous_value=None,
                new_value=f"{len(matches_created)} candidate(s) ({high_count} high-confidence)",
                description=f"Phase 5 Duplicate Detection identified {len(matches_created)} potential physical issue matches requiring human verification.",
                source="ai_duplicate_detector",
                created_at=utc_now(),
            )
            db.add(event)
        else:
            event = ComplaintEvent(
                complaint_id=complaint.complaint_id,
                event_type="duplicate_evaluation_clean",
                previous_value=None,
                new_value="0 matches",
                description="Phase 5 Duplicate Detection evaluated complaint against nearby physical issues: no candidate duplicates found.",
                source="ai_duplicate_detector",
                created_at=utc_now(),
            )
            db.add(event)

        db.commit()
        return matches_created

    @classmethod
    def approve_match(
        cls,
        db: Session,
        match_id: int,
        reviewer_id: str = "authority_reviewer",
        review_reason: Optional[str] = "Approved after manual inspection of location and evidence."
    ) -> Dict[str, Any]:
        """
        Approves candidate duplicate match:
        - Links complaint to candidate physical issue (complaint.issue_id = candidate_physical_issue_id)
        - Never modifies original complaint coordinates, description, or citizen metadata
        - Sets review_status to 'approved'
        - Logs audit event
        """
        match = db.query(DuplicateMatch).filter(DuplicateMatch.id == match_id).first()
        if not match:
            raise ValueError(f"DuplicateMatch with ID {match_id} not found.")

        complaint = db.query(Complaint).filter(Complaint.complaint_id == match.complaint_id).first()
        if not complaint:
            raise ValueError(f"Complaint {match.complaint_id} not found.")

        issue = db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == match.candidate_physical_issue_id).first()
        if not issue:
            raise ValueError(f"PhysicalIssue {match.candidate_physical_issue_id} not found.")

        old_issue_id = complaint.issue_id
        complaint.issue_id = issue.issue_reference_id
        complaint.updated_at = utc_now()

        match.review_status = "approved"
        match.reviewer_id = reviewer_id
        match.review_reason = review_reason
        match.reviewed_at = utc_now()

        # Audit event
        event = ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="issue_association_approved",
            previous_value=old_issue_id or "unassigned",
            new_value=issue.issue_reference_id,
            description=f"Duplicate candidate match approved by {reviewer_id}. Associated with {issue.issue_reference_id}. Reason: {review_reason}",
            source="human_reviewer",
            created_at=utc_now(),
        )
        db.add(event)
        db.commit()

        return {
            "status": "success",
            "message": f"Complaint {complaint.complaint_id} linked to Physical Issue {issue.issue_reference_id}.",
            "match_id": match.id,
            "complaint_id": complaint.complaint_id,
            "issue_reference_id": issue.issue_reference_id,
            "review_status": "approved",
        }

    @classmethod
    def reject_match(
        cls,
        db: Session,
        match_id: int,
        reviewer_id: str = "authority_reviewer",
        review_reason: Optional[str] = "Rejected: distinct physical problem requiring independent intervention."
    ) -> Dict[str, Any]:
        """
        Rejects candidate duplicate match:
        - Preserves complaint as independent record
        - Sets review_status to 'rejected'
        - Logs audit event
        """
        match = db.query(DuplicateMatch).filter(DuplicateMatch.id == match_id).first()
        if not match:
            raise ValueError(f"DuplicateMatch with ID {match_id} not found.")

        complaint = db.query(Complaint).filter(Complaint.complaint_id == match.complaint_id).first()
        if not complaint:
            raise ValueError(f"Complaint {match.complaint_id} not found.")

        match.review_status = "rejected"
        match.reviewer_id = reviewer_id
        match.review_reason = review_reason
        match.reviewed_at = utc_now()

        event = ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="issue_association_rejected",
            previous_value=match.candidate_physical_issue_id,
            new_value="independent",
            description=f"Candidate match with {match.candidate_physical_issue_id} rejected by {reviewer_id}. Reason: {review_reason}",
            source="human_reviewer",
            created_at=utc_now(),
        )
        db.add(event)
        db.commit()

        return {
            "status": "success",
            "message": f"Candidate match rejected. Complaint {complaint.complaint_id} remains independent.",
            "match_id": match.id,
            "complaint_id": complaint.complaint_id,
            "candidate_physical_issue_id": match.candidate_physical_issue_id,
            "review_status": "rejected",
        }

