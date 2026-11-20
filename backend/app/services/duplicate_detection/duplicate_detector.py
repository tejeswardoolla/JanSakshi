import logging
import threading
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from app.core.config import utc_now
from app.models.complaint import Complaint, PhysicalIssue, Evidence, ComplaintEvent, DuplicateMatch
from app.services.duplicate_detection.location_similarity import (
    calculate_haversine_distance,
    calculate_location_similarity,
    get_bounding_box,
)
from app.services.duplicate_detection.category_similarity import calculate_category_similarity
from app.services.duplicate_detection.text_similarity import calculate_text_similarity
from app.services.duplicate_detection.image_similarity import compare_evidence_lists
from app.services.duplicate_detection.scoring import compute_composite_score
from app.services.duplicate_detection.candidate_retrieval import retrieve_candidate_issues

logger = logging.getLogger("jansakshi.duplicate_detection")

# Application-level re-entrant mutex to serialize anchor creation across concurrent worker threads
_anchor_creation_lock = threading.RLock()

class DuplicateDetector:
    """
    Phase 5 Intelligent Duplicate Detection Service:
    Evaluates multi-signal similarity between citizen complaints and physical issues.
    Generates explainable candidate matches and powers human-in-the-loop review workflow.
    """

    @classmethod
    def _create_provisional_anchor(cls, complaint: Complaint, db: Session) -> PhysicalIssue:
        """
        Creates or links an idempotent provisional PhysicalIssue anchor for a geolocated complaint.
        Concurrency-safe across threads (process mutex) and distributed instances (PostgreSQL transaction lock).
        Guarantees that simultaneous requests cannot produce duplicate physical issue anchors.
        """
        lat_tol = 0.0001
        lon_tol = 0.0001
        target_lat = complaint.latitude
        target_lon = complaint.longitude
        target_category = complaint.category
        complaint_id = complaint.complaint_id

        with _anchor_creation_lock:
            if complaint.issue_id:
                existing = db.query(PhysicalIssue).filter(PhysicalIssue.issue_reference_id == complaint.issue_id).first()
                if existing:
                    return existing

            # Distributed advisory transaction lock for PostgreSQL / Neon
            from app.services.issue_id_service import (
                generate_issue_reference_id,
                get_verified_database_dialect,
                _issue_id_seq_mutex,
                is_issue_reference_id_collision,
            )

            dialect_name = get_verified_database_dialect(db)

            if dialect_name == "postgresql" and complaint.latitude is not None and complaint.longitude is not None:
                lock_key = f"jansakshi_anchor_{complaint.category}_{complaint.latitude:.4f}_{complaint.longitude:.4f}"
                try:
                    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:k))"), {"k": lock_key})
                except Exception as lock_err:
                    logger.error(
                        f"PostgreSQL advisory lock acquisition failed for anchor creation on {complaint.complaint_id}: {lock_err}"
                    )
                    db.rollback()
                    raise RuntimeError(
                        f"PostgreSQL advisory lock acquisition failed for provisional anchor creation ({complaint.complaint_id}): {lock_err}"
                    ) from lock_err

            # Check if an anchor already exists at the coordinates and category
            if complaint.latitude is not None and complaint.longitude is not None:
                try:
                    existing_exact = db.query(PhysicalIssue).filter(
                        PhysicalIssue.category == complaint.category,
                        PhysicalIssue.representative_latitude >= complaint.latitude - lat_tol,
                        PhysicalIssue.representative_latitude <= complaint.latitude + lat_tol,
                        PhysicalIssue.representative_longitude >= complaint.longitude - lon_tol,
                        PhysicalIssue.representative_longitude <= complaint.longitude + lon_tol,
                    ).first()
                    if existing_exact:
                        target_complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first() or complaint
                        target_complaint.issue_id = existing_exact.issue_reference_id
                        target_complaint.updated_at = utc_now()
                        db.commit()
                        return existing_exact
                except Exception:
                    db.rollback()
                    raise

            rep_location = (
                complaint.google_maps_url
                if complaint.google_maps_url
                else (
                    f"{complaint.latitude:.4f}, {complaint.longitude:.4f}"
                    if complaint.latitude is not None and complaint.longitude is not None
                    else "Unspecified Location"
                )
            )

            max_anchor_attempts = 3
            with _issue_id_seq_mutex:
                for attempt in range(max_anchor_attempts):
                    try:
                        issue_ref = generate_issue_reference_id(db)

                        # Clearly identify as a provisional anchor; does not trigger automated municipal dispatch
                        anchor = PhysicalIssue(
                            issue_reference_id=issue_ref,
                            category=complaint.category,
                            representative_latitude=complaint.latitude if complaint.latitude is not None else 0.0,
                            representative_longitude=complaint.longitude if complaint.longitude is not None else 0.0,
                            representative_location=f"Provisional Cluster ({rep_location})",
                            description=f"[Provisional Issue Anchor] {complaint.description}",
                            current_status="Open",
                            created_at=utc_now(),
                            updated_at=utc_now(),
                        )

                        target_complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first() or complaint
                        db.add(anchor)
                        target_complaint.issue_id = issue_ref
                        target_complaint.updated_at = utc_now()

                        event = ComplaintEvent(
                            complaint_id=complaint_id,
                            event_type="provisional_issue_anchor_created",
                            previous_value=None,
                            new_value=issue_ref,
                            description=f"Provisional Physical Issue anchor {issue_ref} established for geolocated complaint.",
                            source="ai_duplicate_detector",
                            created_at=utc_now(),
                        )
                        db.add(event)
                        db.commit()

                    except IntegrityError as err:
                        db.rollback()
                        if not is_issue_reference_id_collision(err):
                            raise

                        if target_lat is not None and target_lon is not None:
                            existing_exact = db.query(PhysicalIssue).filter(
                                PhysicalIssue.category == target_category,
                                PhysicalIssue.representative_latitude >= target_lat - lat_tol,
                                PhysicalIssue.representative_latitude <= target_lat + lat_tol,
                                PhysicalIssue.representative_longitude >= target_lon - lon_tol,
                                PhysicalIssue.representative_longitude <= target_lon + lon_tol,
                            ).first()
                            if existing_exact:
                                target_complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first() or complaint
                                target_complaint.issue_id = existing_exact.issue_reference_id
                                target_complaint.updated_at = utc_now()
                                link_event = ComplaintEvent(
                                    complaint_id=complaint_id,
                                    event_type="provisional_issue_anchor_linked",
                                    previous_value=None,
                                    new_value=existing_exact.issue_reference_id,
                                    description=(
                                        f"Associated complaint with existing provisional Physical Issue anchor "
                                        f"{existing_exact.issue_reference_id} after concurrency resolution."
                                    ),
                                    source="ai_duplicate_detector",
                                    created_at=utc_now(),
                                )
                                db.add(link_event)
                                db.commit()
                                return existing_exact

                        if attempt < max_anchor_attempts - 1:
                            continue
                        raise

                    except Exception:
                        db.rollback()
                        raise

                    db.refresh(anchor)
                    return anchor

    @classmethod
    def evaluate_complaint(
        cls,
        complaint_id: str,
        db: Session,
        search_radius_meters: float = 150.0
    ) -> List[DuplicateMatch]:
        """
        Runs duplicate detection for a complaint against nearby PhysicalIssue entities.
        If no nearby PhysicalIssue exists, checks for earlier unlinked complaints nearby
        that have compatible categories, anchors the earlier complaint, or establishes
        a provisional anchor for this complaint.
        Subsequent complaints generate DuplicateMatch candidates with review_status='pending'.
        """
        complaint = db.query(Complaint).filter(Complaint.complaint_id == complaint_id).first()
        if not complaint:
            logger.warning(f"Complaint {complaint_id} not found for duplicate detection.")
            return []

        # Handle complaints with missing coordinates gracefully
        if complaint.latitude is None or complaint.longitude is None:
            logger.info(f"Complaint {complaint_id} has no spatial coordinates; skipping spatial duplicate detection.")
            event = ComplaintEvent(
                complaint_id=complaint.complaint_id,
                event_type="duplicate_evaluation_unlocated",
                previous_value=None,
                new_value="skipped",
                description="Complaint has no spatial coordinates; skipping spatial duplicate detection.",
                source="ai_duplicate_detector",
                created_at=utc_now(),
            )
            db.add(event)
            db.commit()
            return []

        # 1. Retrieve candidate issues within spatial radius
        candidate_tuples = retrieve_candidate_issues(db, complaint, search_radius_meters=search_radius_meters)
        candidates: List[Any] = list(candidate_tuples)

        # 2. If no candidate issues found, search for earlier unlinked complaints nearby with compatible categories
        if len(candidates) == 0:
            min_lat, max_lat, min_lon, max_lon = get_bounding_box(
                complaint.latitude,
                complaint.longitude,
                search_radius_meters
            )
            unlinked_earlier_list = (
                db.query(Complaint)
                .filter(
                    Complaint.complaint_id != complaint.complaint_id,
                    Complaint.issue_id.is_(None),
                    Complaint.latitude.isnot(None),
                    Complaint.longitude.isnot(None),
                    Complaint.latitude >= min_lat,
                    Complaint.latitude <= max_lat,
                    Complaint.longitude >= min_lon,
                    Complaint.longitude <= max_lon,
                    Complaint.created_at <= complaint.created_at
                )
                .order_by(Complaint.created_at.asc(), Complaint.id.asc())
                .all()
            )

            # Evaluate all unlinked candidates, filtering by category compatibility and distance
            eligible_unlinked = []
            for u in unlinked_earlier_list:
                cat_compat = calculate_category_similarity(complaint.category, u.category)
                if cat_compat > 0.0 and u.latitude is not None and u.longitude is not None:
                    d = calculate_haversine_distance(
                        complaint.latitude, complaint.longitude,
                        u.latitude, u.longitude
                    )
                    if d <= search_radius_meters:
                        eligible_unlinked.append((u, d, cat_compat))

            # Sort eligible candidates nearest first
            eligible_unlinked.sort(key=lambda x: (x[1], -x[2]))

            if eligible_unlinked:
                # Anchor the best eligible earlier unlinked complaint
                best_earlier, dist_m, _ = eligible_unlinked[0]
                anchor = cls._create_provisional_anchor(best_earlier, db)
                candidates.append((anchor, round(dist_m, 2)))

        # 3. If still no candidates found, establish provisional anchor for this complaint
        if len(candidates) == 0:
            if not complaint.issue_id:
                cls._create_provisional_anchor(complaint, db)

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
            return []

        logger.info(f"Retrieved {len(candidates)} candidate issues for {complaint_id}")

        matches_created: List[DuplicateMatch] = []
        complaint_evidence_paths = [ev.storage_path for ev in complaint.evidence_files]

        # Ephemeral per-evaluation image hash cache to eliminate redundant downloads and decodes
        eval_image_cache: Dict[str, Tuple[Optional[int], Optional[int]]] = {}

        for issue, distance_meters in candidates:
            # Gather text context from issue and all existing complaints associated with this issue
            issue_descriptions = [issue.description]
            issue_evidence_paths = []
            for linked_comp in issue.complaints:
                if linked_comp.complaint_id != complaint.complaint_id:
                    issue_descriptions.append(linked_comp.description)
                    for ev in linked_comp.evidence_files:
                        issue_evidence_paths.append(ev.storage_path)

            combined_issue_text = " ".join(issue_descriptions)

            # Compute Multi-Signal Similarities
            gps_sim = calculate_location_similarity(distance_meters)
            cat_sim = calculate_category_similarity(complaint.category, issue.category)
            text_sim = calculate_text_similarity(complaint.description, combined_issue_text)
            img_sim = compare_evidence_lists(
                complaint_evidence_paths,
                issue_evidence_paths,
                cache=eval_image_cache
            )

            # Composite Scoring & Dynamic Normalization
            score_data = compute_composite_score(
                gps_score=gps_sim,
                distance_meters=distance_meters,
                text_score=text_sim,
                image_score=img_sim,
                category_score=cat_sim,
            )

            # Only record if categories are compatible (cat_sim > 0.0) AND (similarity meets threshold or very close spatial proximity)
            if cat_sim > 0.0 and (score_data["similarity_score"] >= 0.40 or distance_meters <= 50.0):
                # Check for existing match record
                existing_match = db.query(DuplicateMatch).filter(
                    DuplicateMatch.complaint_id == complaint.complaint_id,
                    DuplicateMatch.candidate_physical_issue_id == issue.issue_reference_id
                ).first()

                if existing_match:
                    # If already reviewed by human, preserve review_status and decision
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
                    existing_match.updated_at = utc_now()
                    match_record = existing_match
                else:
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

        # Audit Logging & Final State Handling
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
            # Candidates existed nearby, but none qualified as duplicate (e.g. distinct problem)
            if not complaint.issue_id:
                cls._create_provisional_anchor(complaint, db)

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
        - Sets approved match review_status to 'approved'
        - Automatically dismisses all other pending duplicate candidates for this complaint
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
        match.updated_at = utc_now()

        # Handle other pending matches for this complaint: clearly distinguish as dismissed/superseded
        sibling_pending = (
            db.query(DuplicateMatch)
            .filter(
                DuplicateMatch.complaint_id == complaint.complaint_id,
                DuplicateMatch.id != match.id,
                DuplicateMatch.review_status == "pending"
            )
            .all()
        )
        for sib in sibling_pending:
            sib.review_status = "dismissed"
            sib.reviewer_id = reviewer_id
            sib.review_reason = f"Automatically dismissed: Complaint associated with Physical Issue {issue.issue_reference_id}."
            sib.reviewed_at = utc_now()
            sib.updated_at = utc_now()

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
            "dismissed_sibling_count": len(sibling_pending),
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
        - If complaint has no other pending matches and no anchor, establishes its own provisional anchor
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
        match.updated_at = utc_now()

        # Check if complaint has no other pending matches and no anchor; if so, create independent anchor
        other_pending = db.query(DuplicateMatch).filter(
            DuplicateMatch.complaint_id == complaint.complaint_id,
            DuplicateMatch.id != match.id,
            DuplicateMatch.review_status == "pending"
        ).first()

        if not other_pending and not complaint.issue_id and complaint.latitude is not None and complaint.longitude is not None:
            cls._create_provisional_anchor(complaint, db)

        event = ComplaintEvent(
            complaint_id=complaint.complaint_id,
            event_type="issue_association_rejected",
            previous_value=match.candidate_physical_issue_id,
            new_value=complaint.issue_id or "independent",
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
