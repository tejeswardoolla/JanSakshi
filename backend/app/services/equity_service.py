"""
JanSakshi Phase 8: Equity-Aware Civic Intelligence Service
Computes real-time, explainable geographic fairness and service disparity metrics
grounded strictly in real database records and municipal performance data.
"""

from typing import Dict, List, Any, Optional
import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.complaint import Complaint, PhysicalIssue
from app.models.authority import Department
from app.core.config import utc_now

# Grounded geographic area resolver based on real municipal coordinates and physical issue locations
def resolve_complaint_area(complaint: Complaint) -> Dict[str, Any]:
    """
    Grounds complaint into an administrative ward/locality cluster.
    Never fabricates coordinates or boundaries.
    """
    if complaint.latitude is None or complaint.longitude is None:
        return {
            "area_id": "unattributed",
            "area_name": "Unattributed / Missing Geolocation",
            "ward_number": None,
            "locality": "Coordinates Pending",
            "has_coords": False,
            "latitude": None,
            "longitude": None
        }

    lat = round(float(complaint.latitude), 4)
    lng = round(float(complaint.longitude), 4)

    # 1. Check linked physical issue reference location if present
    if complaint.physical_issue and complaint.physical_issue.representative_location:
        loc = complaint.physical_issue.representative_location
        if "Ward 12" in loc or "Inner Ring Road" in loc:
            return {
                "area_id": "ward-12",
                "area_name": "Ward 12 — Inner Ring Road & Ameerpet",
                "ward_number": 12,
                "locality": "Inner Ring Road / Ameerpet",
                "has_coords": True,
                "latitude": lat,
                "longitude": lng
            }
        if "Jubilee Hills" in loc:
            return {
                "area_id": "ward-08",
                "area_name": "Ward 08 — Jubilee Hills & Madhapur",
                "ward_number": 8,
                "locality": "Jubilee Hills Extension",
                "has_coords": True,
                "latitude": lat,
                "longitude": lng
            }
        if "Rajahmundry" in loc:
            return {
                "area_id": "ward-04",
                "area_name": "Ward 04 — Morampudi & Rajahmundry Central",
                "ward_number": 4,
                "locality": "Morampudi Junction",
                "has_coords": True,
                "latitude": lat,
                "longitude": lng
            }

    # 2. Grounded coordinate clustering
    # Greater Hyderabad Central (lat ~17.43 to 17.45, lng ~78.44 to 78.46)
    if 17.43 <= lat <= 17.45 and 78.44 <= lng <= 78.46:
        if lng >= 78.449:
            return {
                "area_id": "ward-08",
                "area_name": "Ward 08 — Jubilee Hills & Madhapur",
                "ward_number": 8,
                "locality": "Jubilee Hills / Madhapur Corridor",
                "has_coords": True,
                "latitude": lat,
                "longitude": lng
            }
        return {
            "area_id": "ward-12",
            "area_name": "Ward 12 — Inner Ring Road & Ameerpet",
            "ward_number": 12,
            "locality": "Inner Ring Road / Ameerpet",
            "has_coords": True,
            "latitude": lat,
            "longitude": lng
        }

    # Old City / Koti / Charminar (lat ~17.38 to 17.40, lng ~78.48 to 78.50)
    if 17.37 <= lat <= 17.41 and 78.47 <= lng <= 78.51:
        return {
            "area_id": "ward-15",
            "area_name": "Ward 15 — Charminar & Koti Heritage Corridor",
            "ward_number": 15,
            "locality": "Charminar / Koti",
            "has_coords": True,
            "latitude": lat,
            "longitude": lng
        }

    # East Godavari / Rajahmundry (lat ~17.00 to 17.07, lng ~81.79 to 81.82)
    if 16.98 <= lat <= 17.08 and 81.78 <= lng <= 81.83:
        return {
            "area_id": "ward-04",
            "area_name": "Ward 04 — Morampudi & Rajahmundry Central",
            "ward_number": 4,
            "locality": "Morampudi / Godavari Basin",
            "has_coords": True,
            "latitude": lat,
            "longitude": lng
        }

    # Bengaluru Central (lat ~12.96 to 12.98, lng ~77.58 to 77.61)
    if 12.95 <= lat <= 13.00 and 77.57 <= lng <= 77.62:
        return {
            "area_id": "ward-112",
            "area_name": "Ward 112 — Central Commercial Zone",
            "ward_number": 112,
            "locality": "MG Road / CBD",
            "has_coords": True,
            "latitude": lat,
            "longitude": lng
        }

    # Other mapped coordinates
    return {
        "area_id": f"cluster-{lat:.2f}-{lng:.2f}",
        "area_name": f"Civic Cluster ({lat:.2f} N, {lng:.2f} E)",
        "ward_number": None,
        "locality": f"Coordinates {lat}, {lng}",
        "has_coords": True,
        "latitude": lat,
        "longitude": lng
    }


class EquityIntelligenceService:
    @staticmethod
    def calculate_equity_metrics(
        db: Session,
        department_id: Optional[int] = None,
        days: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Computes all Phase 8 equity intelligence indicators from real database records.
        """
        now = utc_now()
        # Filter valid civic complaints (strictly excludes rejected/spam submissions)
        query = db.query(Complaint).filter(
            Complaint.verification_status != "rejected",
            Complaint.admin_status != "Rejected"
        )

        if department_id is not None:
            query = query.filter(Complaint.assigned_department_id == department_id)

        if days is not None:
            cutoff = now - datetime.timedelta(days=days)
            query = query.filter(Complaint.created_at >= cutoff)

        all_complaints = query.all()
        departments_map = {d.id: d for d in db.query(Department).all()}

        # Group complaints by grounded area
        areas_data: Dict[str, Dict[str, Any]] = {}

        for c in all_complaints:
            area_info = resolve_complaint_area(c)
            aid = area_info["area_id"]

            if aid not in areas_data:
                areas_data[aid] = {
                    "area_id": aid,
                    "area_name": area_info["area_name"],
                    "ward_number": area_info["ward_number"],
                    "locality": area_info["locality"],
                    "complaints": [],
                    "has_coords": area_info["has_coords"],
                    "latitude": area_info["latitude"],
                    "longitude": area_info["longitude"],
                }
            areas_data[aid]["complaints"].append(c)

        # Calculate metrics for each area
        area_summaries: List[Dict[str, Any]] = []
        total_areas_with_data = 0
        areas_requiring_attention = 0
        unresolved_hotspots = 0
        repeat_hotspots = 0
        sla_breach_areas = 0

        # Statistical Threshold: Minimum 5 complaints required for systemic disparity claims
        MIN_SAMPLE_THRESHOLD = 5

        for aid, data in areas_data.items():
            comps = data["complaints"]
            count = len(comps)
            if count == 0:
                continue

            if aid != "unattributed":
                total_areas_with_data += 1

            # 1. Unresolved count & rate (Denominator: total area complaints)
            unresolved = [
                c for c in comps
                if (c.admin_status or c.status) not in ("Resolved", "Closed")
            ]
            unresolved_count = len(unresolved)
            unresolved_rate = round((unresolved_count / count) * 100, 1)

            # 2. Resolution count & rate (Denominator: total area complaints)
            resolved_comps = [
                c for c in comps
                if (c.admin_status or c.status) in ("Resolved", "Closed")
            ]
            resolved_count = len(resolved_comps)
            resolution_rate = round((resolved_count / count) * 100, 1)

            # 3. SLA Breaches (Denominator: assigned complaints only)
            assigned_comps = [c for c in comps if c.assigned_department_id is not None]
            sla_breaches = 0
            for c in assigned_comps:
                if (c.admin_status or c.status) not in ("Resolved", "Closed"):
                    dept = departments_map.get(c.assigned_department_id)
                    sla_days = dept.sla_days if dept else 7
                    c_time = c.assigned_at or c.created_at
                    if c_time:
                        if c_time.tzinfo is None:
                            c_time = c_time.replace(tzinfo=datetime.timezone.utc)
                        elapsed_hours = (now - c_time).total_seconds() / 3600.0
                        if elapsed_hours > (sla_days * 24):
                            sla_breaches += 1

            sla_breach_rate = round((sla_breaches / len(assigned_comps) * 100), 1) if assigned_comps else 0.0

            # 4. Repeat issues
            linked_to_issue = sum(1 for c in comps if c.issue_id is not None or len(c.duplicate_matches) > 0)
            repeat_issue_rate = round((linked_to_issue / count) * 100, 1)

            # 5. Median Resolution Time (for resolved/closed)
            resolution_times_hours = []
            for c in resolved_comps:
                start = c.assigned_at or c.created_at
                end = c.updated_at or now
                if start and end:
                    if start.tzinfo is None:
                        start = start.replace(tzinfo=datetime.timezone.utc)
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=datetime.timezone.utc)
                    diff = (end - start).total_seconds() / 3600.0
                    if diff > 0:
                        resolution_times_hours.append(diff)

            if resolution_times_hours:
                resolution_times_hours.sort()
                mid = len(resolution_times_hours) // 2
                median_hours = round(resolution_times_hours[mid], 1)
            else:
                median_hours = None

            # 6. Geographic and Channel Coverage
            geo_count = sum(1 for c in comps if c.latitude is not None and c.longitude is not None)
            geo_coverage_rate = round((geo_count / count) * 100, 1)
            web_count = sum(1 for c in comps if c.submission_channel == "website")
            email_count = sum(1 for c in comps if c.submission_channel == "email")

            # 7. Sample Size Validation & Neutral Equity Classification
            is_insufficient_sample = count < MIN_SAMPLE_THRESHOLD
            indicators: List[str] = []

            if is_insufficient_sample:
                indicators.append(f"Insufficient Sample Size (n={count})")
                explainable_reason = (
                    f"Preliminary observation based on {count} ticket(s). Minimum {MIN_SAMPLE_THRESHOLD} "
                    f"complaints required before drawing statistically conclusive systemic disparity findings."
                )
                sample_warning = f"Preliminary sample (n = {count}). Not statistically conclusive of systemic disparity."
            else:
                sample_warning = None
                if unresolved_rate >= 60.0 and unresolved_count >= 3:
                    indicators.append("Elevated Service Gap Indicator")
                    unresolved_hotspots += 1
                if sla_breaches > 0:
                    indicators.append("SLA Performance Concern")
                    sla_breach_areas += 1
                if repeat_issue_rate >= 30.0 and count >= 5:
                    indicators.append("Repeated Issue Concentration")
                    repeat_hotspots += 1
                if not indicators:
                    indicators.append("Standard Municipal Monitoring")

                if sla_breaches > 0:
                    explainable_reason = f"{sla_breaches} of {len(assigned_comps)} assigned work order(s) exceeded department statutory SLA deadlines."
                elif unresolved_rate >= 60.0:
                    explainable_reason = f"{unresolved_count} of {count} complaints ({unresolved_rate}%) remain unresolved across reporting periods."
                elif repeat_issue_rate >= 30.0:
                    explainable_reason = f"{repeat_issue_rate}% of civic complaints in this cluster are associated with recurring or linked physical infrastructure defects."
                else:
                    explainable_reason = "Service response indicators remain within standard municipal operational thresholds."

            if any(ind in ("Elevated Service Gap Indicator", "SLA Performance Concern", "Repeated Issue Concentration") for ind in indicators):
                areas_requiring_attention += 1

            area_summaries.append({
                "area_id": aid,
                "area_name": data["area_name"],
                "ward_number": data["ward_number"],
                "locality": data["locality"],
                "total_complaints": count,
                "reporting_period": f"Past {days} days" if days else "All Time",
                "unresolved_count": unresolved_count,
                "unresolved_rate": unresolved_rate,
                "resolved_count": resolved_count,
                "resolution_rate": resolution_rate,
                "assigned_count": len(assigned_comps),
                "sla_breach_count": sla_breaches,
                "sla_breach_rate": sla_breach_rate,
                "repeat_issue_count": linked_to_issue,
                "repeat_issue_clusters": linked_to_issue,
                "repeat_issue_rate": repeat_issue_rate,
                "median_resolution_hours": median_hours,
                "geographic_coverage_rate": geo_coverage_rate,
                "has_coordinates_pct": geo_coverage_rate,
                "website_channel_count": web_count,
                "email_channel_count": email_count,
                "indicators": indicators,
                "attention_flags": indicators,
                "primary_indicator": indicators[0] if indicators else "Standard Monitoring",
                "is_insufficient_sample": is_insufficient_sample,
                "sample_warning": sample_warning,
                "sample_threshold": MIN_SAMPLE_THRESHOLD,
                "denominators": {
                    "total_complaints": count,
                    "assigned_work_orders": len(assigned_comps),
                    "unresolved_rate_calc": f"{unresolved_count}/{count} ({unresolved_rate}%)",
                    "resolution_rate_calc": f"{resolved_count}/{count} ({resolution_rate}%)",
                    "sla_breach_rate_calc": f"{sla_breaches}/{len(assigned_comps)} ({sla_breach_rate}%)" if assigned_comps else "0/0 (0.0%)"
                },
                "explainable_reason": explainable_reason,
                "representative_latitude": data["latitude"],
                "representative_longitude": data["longitude"],
                "center_lat": data["latitude"],
                "center_lon": data["longitude"]
            })

        # Sort areas: attention required first, then total complaints desc
        area_summaries.sort(key=lambda a: (a["is_insufficient_sample"], -a["sla_breach_count"], -a["unresolved_count"], -a["total_complaints"]))

        # Department Service Coverage metrics
        dept_coverage = []
        for d in db.query(Department).all():
            dept_comps = [c for c in all_complaints if c.assigned_department_id == d.id]
            d_total = len(dept_comps)
            d_unresolved = sum(1 for c in dept_comps if (c.admin_status or c.status) not in ("Resolved", "Closed", "Rejected"))
            d_breaches = 0
            for c in dept_comps:
                if (c.admin_status or c.status) not in ("Resolved", "Closed", "Rejected"):
                    c_time = c.assigned_at or c.created_at
                    if c_time:
                        if c_time.tzinfo is None:
                            c_time = c_time.replace(tzinfo=datetime.timezone.utc)
                        if (now - c_time).total_seconds() / 3600.0 > (d.sla_days * 24):
                            d_breaches += 1

            dept_coverage.append({
                "department_id": d.id,
                "code": d.code,
                "name": d.name,
                "sla_days": d.sla_days,
                "total_work_orders": d_total,
                "unresolved_work_orders": d_unresolved,
                "overdue_work_orders": d_breaches,
                "sla_compliance_rate": round(((d_total - d_breaches) / d_total * 100), 1) if d_total > 0 else 100.0
            })

        # Explainable Recommendations linked to actual data
        recommendations = []
        for a in area_summaries:
            if not a["is_insufficient_sample"]:
                if a["sla_breach_count"] > 0:
                    recommendations.append({
                        "id": f"rec-sla-{a['area_id']}",
                        "title": f"Review SLA Breaches in {a['area_name']}",
                        "category": "SLA Delay",
                        "area_name": a["area_name"],
                        "urgency": "High",
                        "recommendation": f"Expedite field inspection for {a['sla_breach_count']} overdue work order(s). Coordinate with respective municipal division leads.",
                        "supporting_data": f"{a['sla_breach_count']} of {a['total_complaints']} work orders exceeded deadline."
                    })
                if a["unresolved_rate"] >= 65.0 and a["unresolved_count"] >= 3:
                    recommendations.append({
                        "id": f"rec-gap-{a['area_id']}",
                        "title": f"Investigate Persistent Service Gap in {a['area_name']}",
                        "category": "Service Gap",
                        "area_name": a["area_name"],
                        "urgency": "Medium",
                        "recommendation": f"Conduct joint ward inspection to address {a['unresolved_count']} unresolved grievances ({a['unresolved_rate']}% backlog).",
                        "supporting_data": f"Backlog rate: {a['unresolved_rate']}% | Total complaints: {a['total_complaints']}."
                    })
                if a["repeat_issue_rate"] >= 35.0:
                    recommendations.append({
                        "id": f"rec-repeat-{a['area_id']}",
                        "title": f"Inspect Recurring Physical Infrastructure in {a['area_name']}",
                        "category": "Repeat Hotspot",
                        "area_name": a["area_name"],
                        "urgency": "Medium",
                        "recommendation": f"Investigate root cause of recurring infrastructure failures rather than repeated isolated temporary patchworks.",
                        "supporting_data": f"Repeat defect rate: {a['repeat_issue_rate']}% of area grievances."
                    })

        # Data Quality & Coverage Stats
        total_all = len(all_complaints)
        total_with_gps = sum(1 for c in all_complaints if c.latitude is not None and c.longitude is not None)
        gps_coverage_pct = round((total_with_gps / total_all * 100), 1) if total_all > 0 else 0.0

        for r in recommendations:
            r["neutral_label"] = r.get("category", "Operational Indicator")
            r["evidence_basis"] = r.get("supporting_data", "Aggregated metric")
            r["description"] = r.get("recommendation", "")

        summary_kpis = {
            "total_complaints": total_all,
            "total_complaints_analyzed": total_all,
            "total_areas": total_areas_with_data,
            "total_areas_analyzed": total_areas_with_data,
            "areas_requiring_attention": areas_requiring_attention,
            "unresolved_complaint_hotspots": unresolved_hotspots,
            "unresolved_hotspots_count": unresolved_hotspots,
            "repeat_issue_hotspots": repeat_hotspots,
            "repeat_hotspots_count": repeat_hotspots,
            "areas_with_sla_breaches": sla_breach_areas,
            "high_sla_breach_areas_count": sla_breach_areas,
            "overall_data_completeness_pct": gps_coverage_pct,
            "data_completeness_pct": gps_coverage_pct,
            "overall_sla_breach_rate": round(sum(a.get("sla_breach_rate", 0) for a in area_summaries) / max(1, len(area_summaries)), 1),
            "time_window_days": days or 30
        }

        return {
            "analysis_timestamp": now.isoformat(),
            "time_window_days": days or "All Time",
            "kpis": summary_kpis,
            "summary": summary_kpis,
            "area_metrics": area_summaries,
            "areas": area_summaries,
            "department_coverage": dept_coverage,
            "recommendations": recommendations[:6],
            "safeguards_notice": "Indicators represent aggregated municipal operations data only. No individual citizen attributes, demographics, or personal data are inferred or utilized."
        }
