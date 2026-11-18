"""
JanSakshi Civic Complaint Management Platform
Professional Automated Citizen Acknowledgement Email Template Generator

Produces responsive, email-safe HTML emails and matching plain-text fallbacks
following JanSakshi's civic brand identity:
- Dark Navy (#102B4E / #0F172A)
- Saffron Orange (#F36B21)
- Crisp White (#FFFFFF) & Slate backgrounds (#F1F5F9 / #F8FAFC)
- Clean typography and bulletproof table layout for Gmail, Outlook, and mobile.
"""

import html
from typing import Optional
from app.core.config import EMAIL_LOGO_URL


def render_acknowledgement_email_html(
    complaint_id: str,
    category: str,
    location_display: str,
    submission_datetime_str: str,
    status_display: str,
    evidence_status: str,
    tracking_url: str,
    location_missing: bool = False,
    citizen_name: Optional[str] = None,
    official_email: str = "jansakshiofficial@gmail.com",
    logo_url: Optional[str] = None
) -> str:
    """
    Renders a premium, email-safe HTML acknowledgement email matching
    the JanSakshi civic identity and official brand assets.
    """
    safe_cid = html.escape(complaint_id or "")
    safe_cat = html.escape(category or "General Civic Complaint")
    safe_loc = html.escape(location_display or "Incident Location Pending")
    safe_dt = html.escape(submission_datetime_str or "")
    safe_status = html.escape(status_display or "Received")
    safe_evidence = html.escape(evidence_status or "None provided")
    safe_citizen = html.escape(citizen_name.strip() if citizen_name else "Citizen")
    safe_official_email = html.escape(official_email or "jansakshiofficial@gmail.com")
    safe_tracking_url = html.escape(tracking_url or "")
    resolved_logo_url = logo_url.strip() if (logo_url and logo_url.strip()) else EMAIL_LOGO_URL
    safe_logo_url = html.escape(resolved_logo_url)

    # Location presentation block
    if location_missing:
        location_html = f"""
        <div style="background-color: #FEF2F2; border: 1px solid #FECACA; border-radius: 6px; padding: 10px 14px; margin-top: 4px;">
            <div style="color: #DC2626; font-weight: 700; font-size: 13px;">⚠️ Awaiting Incident Location</div>
            <div style="color: #7F1D1D; font-size: 12px; margin-top: 4px; line-height: 1.45;">
                Please reply directly to this email with your street address, nearby landmark, or a Google Maps link so civic authorities can locate and inspect the site.
            </div>
        </div>
        """
    else:
        location_html = f"""
        <span style="color: #0F172A; font-weight: 600; font-size: 14px;">{safe_loc}</span>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>JanSakshi Complaint Registration – {safe_cid}</title>
    <!--[if mso]>
    <style type="text/css">
        body, table, td, a, span {{ font-family: Arial, Helvetica, sans-serif !important; }}
    </style>
    <![endif]-->
    <style type="text/css">
        /* Client-specific Resets */
        body, table, td, a {{ -webkit-text-size-adjust: 100%; -ms-text-size-adjust: 100%; }}
        table, td {{ mso-table-lspace: 0pt; mso-table-rspace: 0pt; }}
        img {{ -ms-interpolation-mode: bicubic; border: 0; outline: none; text-decoration: none; }}
        table {{ border-collapse: collapse !important; }}
        body {{ margin: 0 !important; padding: 0 !important; width: 100% !important; min-width: 100%; background-color: #F1F5F9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }}

        /* Responsive Utilities */
        @media screen and (max-width: 620px) {{
            .email-container {{ width: 100% !important; margin: auto !important; border-radius: 0 !important; }}
            .content-padding {{ padding: 24px 18px !important; }}
            .header-padding {{ padding: 20px 18px !important; }}
            .card-padding {{ padding: 16px 14px !important; }}
            .mobile-stack {{ display: block !important; width: 100% !important; box-sizing: border-box !important; }}
            .mobile-center {{ text-align: center !important; }}
            .tracking-btn {{ width: 100% !important; display: block !important; padding: 14px 16px !important; box-sizing: border-box !important; text-align: center !important; }}
        }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #F1F5F9; -webkit-font-smoothing: antialiased;">

    <!-- Email Shell Outer Table -->
    <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F1F5F9; table-layout: fixed;">
        <tr>
            <td align="center" style="padding: 24px 12px 32px;">

                <!-- Container 620px max -->
                <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" class="email-container" style="max-width: 620px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 16px rgba(15, 23, 42, 0.08); border: 1px solid #E2E8F0;">

                    <!-- Top Saffron Civic Bar -->
                    <tr>
                        <td style="height: 5px; background-color: #F36B21; font-size: 0; line-height: 0;">&nbsp;</td>
                    </tr>

                    <!-- Header Section: Dark Navy -->
                    <tr>
                        <td class="header-padding" style="background-color: #102B4E; padding: 28px 32px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td valign="middle" align="left">
                                        <!-- Brand Emblem + Text -->
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td valign="middle" style="padding-right: 14px;">
                                                    <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="border-radius: 50%; width: 44px; height: 44px; border: 2px solid #F36B21; overflow: hidden; background-color: #102B4E;">
                                                        <tr>
                                                            <td align="center" valign="middle" style="padding: 0; line-height: 0; font-size: 0;">
                                                                <img src="{safe_logo_url}" alt="JanSakshi Logo" width="44" height="44" style="display: block; width: 44px; height: 44px; border-radius: 50%; object-fit: cover; border: 0;" />
                                                            </td>
                                                        </tr>
                                                    </table>
                                                </td>
                                                <td valign="middle">
                                                    <div style="color: #FFFFFF; font-size: 20px; font-weight: 800; letter-spacing: 1.2px; line-height: 1.1; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                                        Jan<span style="color: #F36B21;">Sakshi</span>
                                                    </div>
                                                    <div style="color: #94A3B8; font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 1.5px; margin-top: 3px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                                        Civic Complaint Management
                                                    </div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                    <td valign="middle" align="right" class="mobile-center" style="padding-top: 4px;">
                                        <span style="display: inline-block; background-color: rgba(255, 255, 255, 0.10); color: #E2E8F0; font-size: 11px; font-weight: 600; padding: 5px 12px; border-radius: 9999px; border: 1px solid rgba(255, 255, 255, 0.16); letter-spacing: 0.5px; text-transform: uppercase;">
                                            Official Acknowledgement
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                    <!-- Main Body Content -->
                    <tr>
                        <td class="content-padding" style="padding: 32px 32px 24px;">

                            <!-- Registration Status Hero -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 24px;">
                                <tr>
                                    <td align="left">
                                        <!-- Green Check Badge -->
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" style="margin-bottom: 14px;">
                                            <tr>
                                                <td style="background-color: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 50%; width: 38px; height: 38px; text-align: center; vertical-align: middle;">
                                                    <span style="color: #059669; font-size: 18px; font-weight: 700; line-height: 38px; display: block;">&#10003;</span>
                                                </td>
                                                <td style="padding-left: 12px; vertical-align: middle;">
                                                    <span style="color: #059669; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px;">
                                                        Grievance Intake Confirmed
                                                    </span>
                                                </td>
                                            </tr>
                                        </table>

                                        <!-- Main Heading -->
                                        <h1 style="color: #0F172A; font-size: 22px; font-weight: 800; line-height: 1.35; margin: 0 0 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                            Your Complaint Has Been Successfully Registered!
                                        </h1>

                                        <!-- Message -->
                                        <p style="color: #334155; font-size: 15px; line-height: 1.6; margin: 0 0 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                            Dear <strong>{safe_citizen}</strong>,
                                        </p>
                                        <p style="color: #475569; font-size: 15px; line-height: 1.6; margin: 0 0 24px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                            Thank you for bringing this issue to our attention. Your complaint has been successfully registered in the JanSakshi civic complaint management system.
                                        </p>
                                    </td>
                                </tr>
                            </table>

                            <!-- Complaint Information Card -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; overflow: hidden; margin-bottom: 28px;">
                                <!-- Card Header / Reference Banner -->
                                <tr>
                                    <td class="card-padding" style="background-color: #F1F5F9; padding: 16px 20px; border-bottom: 1px solid #E2E8F0;">
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td align="left" valign="middle">
                                                    <div style="color: #64748B; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px;">
                                                        Complaint Reference ID
                                                    </div>
                                                    <div style="color: #102B4E; font-size: 21px; font-weight: 800; font-family: 'Consolas', 'Courier New', monospace; letter-spacing: 1.2px; margin-top: 3px;">
                                                        {safe_cid}
                                                    </div>
                                                </td>
                                                <td align="right" valign="middle">
                                                    <span style="display: inline-block; background-color: #DCFCE7; color: #166534; font-size: 12px; font-weight: 700; padding: 5px 12px; border-radius: 9999px; border: 1px solid #86EFAC;">
                                                        &#9679; {safe_status}
                                                    </span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>

                                <!-- Details Table -->
                                <tr>
                                    <td class="card-padding" style="padding: 20px;">
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <!-- Category -->
                                            <tr>
                                                <td valign="top" style="padding: 8px 0; width: 140px; color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                    Category
                                                </td>
                                                <td valign="top" style="padding: 8px 0; color: #0F172A; font-size: 14px; font-weight: 600;">
                                                    <span style="display: inline-block; background-color: #EEF2F6; color: #102B4E; padding: 3px 10px; border-radius: 4px; font-weight: 700; font-size: 13px;">
                                                        {safe_cat}
                                                    </span>
                                                </td>
                                            </tr>

                                            <!-- Incident Location -->
                                            <tr>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                    Incident Location
                                                </td>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7;">
                                                    {location_html}
                                                </td>
                                            </tr>

                                            <!-- Submission Date & Time -->
                                            <tr>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                    Submission Date &amp; Time
                                                </td>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #0F172A; font-size: 14px; font-weight: 500;">
                                                    {safe_dt}
                                                </td>
                                            </tr>

                                            <!-- Current Complaint Status -->
                                            <tr>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                    Current Status
                                                </td>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #0F172A; font-size: 14px; font-weight: 600;">
                                                    {safe_status} <span style="color: #64748B; font-weight: 400; font-size: 13px;">(Registered &amp; Queued for Municipal Triage)</span>
                                                </td>
                                            </tr>

                                            <!-- Evidence Status -->
                                            <tr>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #64748B; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px;">
                                                    Evidence Received
                                                </td>
                                                <td valign="top" style="padding: 8px 0; border-top: 1px solid #EDF2F7; color: #0F172A; font-size: 14px; font-weight: 500;">
                                                    <span style="color: #047857; font-weight: 600;">&#128247; {safe_evidence}</span>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- Prominent Tracking CTA Button -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="margin-bottom: 28px;">
                                <tr>
                                    <td align="center">
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0">
                                            <tr>
                                                <td align="center" style="background-color: #F36B21; border-radius: 8px; box-shadow: 0 4px 12px rgba(243, 107, 33, 0.35);">
                                                    <a href="{safe_tracking_url}" target="_blank" class="tracking-btn" style="display: inline-block; padding: 15px 36px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 14px; font-weight: 800; color: #FFFFFF; text-decoration: none; text-transform: uppercase; letter-spacing: 1px; border-radius: 8px; border: 1px solid #E05615;">
                                                        TRACK YOUR COMPLAINT
                                                    </a>
                                                </td>
                                            </tr>
                                        </table>
                                        <div style="color: #64748B; font-size: 12px; margin-top: 10px; line-height: 1.45;">
                                            Click above to track live inspection progress, department assignment, and resolution verification.
                                        </div>
                                    </td>
                                </tr>
                            </table>

                            <!-- AI Assessment Notice Box -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-left: 4px solid #F36B21; border-radius: 6px; margin-bottom: 24px;">
                                <tr>
                                    <td style="padding: 14px 16px;">
                                        <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                            <tr>
                                                <td valign="top" style="width: 22px; padding-right: 10px; color: #F36B21; font-size: 16px; line-height: 1;">
                                                    &#9432;
                                                </td>
                                                <td valign="top">
                                                    <div style="color: #334155; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 4px;">
                                                        Official AI Assessment Notice
                                                    </div>
                                                    <div style="color: #475569; font-size: 13px; line-height: 1.55;">
                                                        AI-powered assessment provides preliminary category and severity recommendations. Final verification, prioritization and resolution decisions are made by the concerned municipal authorities.
                                                    </div>
                                                </td>
                                            </tr>
                                        </table>
                                    </td>
                                </tr>
                            </table>

                            <!-- What Happens Next / Civic Roadmap -->
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%" style="border-top: 1px solid #E2E8F0; padding-top: 20px; margin-top: 10px;">
                                <tr>
                                    <td>
                                        <div style="color: #0F172A; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;">
                                            What Happens Next?
                                        </div>
                                        <ul style="margin: 0; padding-left: 20px; color: #475569; font-size: 13px; line-height: 1.6;">
                                            <li style="margin-bottom: 6px;">Your report is assigned to the appropriate municipal department based on location and category.</li>
                                            <li style="margin-bottom: 6px;">An engineering inspection team conducts on-site verification and schedules remediation.</li>
                                            <li>You will receive periodic status updates as work orders are executed and completed.</li>
                                        </ul>
                                    </td>
                                </tr>
                            </table>

                        </td>
                    </tr>

                    <!-- Professional Footer: Dark Charcoal/Navy -->
                    <tr>
                        <td style="background-color: #0F172A; padding: 30px 32px; border-top: 1px solid rgba(255, 255, 255, 0.08); text-align: center;">
                            <table role="presentation" border="0" cellpadding="0" cellspacing="0" width="100%">
                                <tr>
                                    <td align="center">
                                        <!-- Footer Title & Civic Message -->
                                        <div style="color: #FFFFFF; font-size: 14px; font-weight: 700; letter-spacing: 1px; text-transform: uppercase; margin-bottom: 6px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;">
                                            JanSakshi Civic Grievance &amp; Redressal Platform
                                        </div>
                                        <div style="color: #94A3B8; font-size: 13px; line-height: 1.6; max-width: 480px; margin: 0 auto 18px;">
                                            Empowering citizens to report, track, and resolve civic infrastructure issues collaboratively through transparent, technology-enabled governance.
                                        </div>

                                        <!-- Official Contact Info Divider -->
                                        <div style="height: 1px; background-color: rgba(255, 255, 255, 0.12); width: 80%; margin: 16px auto;"></div>

                                        <!-- Official Details -->
                                        <div style="color: #CBD5E1; font-size: 12px; line-height: 1.6; margin-bottom: 8px;">
                                            <strong>Municipal Corporation of Rajamahendravaram</strong> &bull; Andhra Pradesh, India<br>
                                            Official Civic Ingestion Desk: <a href="mailto:{safe_official_email}" style="color: #F36B21; text-decoration: none; font-weight: 600;">{safe_official_email}</a>
                                        </div>

                                        <!-- Automated Acknowledgement Note -->
                                        <div style="color: #64748B; font-size: 11px; line-height: 1.5; max-width: 500px; margin: 14px auto 0;">
                                            Please note: This is an automated acknowledgement generated upon receipt of your civic report. To provide additional details, photos, or landmark clarifications, you may reply directly to this email.
                                        </div>

                                        <div style="color: #475569; font-size: 11px; margin-top: 14px;">
                                            &copy; 2026 JanSakshi Platform. All rights reserved.
                                        </div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>

                </table>
                <!-- /Container -->

            </td>
        </tr>
    </table>
    <!-- /Email Shell Outer Table -->

</body>
</html>
"""


def render_acknowledgement_email_text(
    complaint_id: str,
    category: str,
    location_display: str,
    submission_datetime_str: str,
    status_display: str,
    evidence_status: str,
    tracking_url: str,
    location_missing: bool = False,
    citizen_name: Optional[str] = None,
    official_email: str = "jansakshiofficial@gmail.com"
) -> str:
    """
    Renders a matching structured plain-text fallback acknowledgement email.
    """
    citizen_greeting = f"Dear {citizen_name.strip()}," if citizen_name else "Dear Citizen,"

    if location_missing:
        location_block = (
            "Status: Awaiting Incident Location\n"
            "Action Required: Please reply directly to this email with your street address, nearby landmark, or a Google Maps link so civic authorities can locate and inspect the site."
        )
    else:
        location_block = f"Location: {location_display}"

    return f"""======================================================================
JANSAKSHI – CIVIC COMPLAINT MANAGEMENT
Municipal Corporation of Rajamahendravaram
Official Grievance Registration Acknowledgement
======================================================================

{citizen_greeting}

Thank you for bringing this issue to our attention. Your complaint has been successfully registered in the JanSakshi civic complaint management system.

----------------------------------------------------------------------
COMPLAINT INFORMATION
----------------------------------------------------------------------
Reference ID:         {complaint_id}
Category:             {category}
{location_block}
Submission Date/Time: {submission_datetime_str}
Current Status:       {status_display} (Registered & Queued for Municipal Triage)
Evidence Received:    {evidence_status}

----------------------------------------------------------------------
TRACK YOUR COMPLAINT
----------------------------------------------------------------------
You can track real-time inspection progress, municipal department assignment,
and resolution verification at any time using the link below:

{tracking_url}

----------------------------------------------------------------------
AI ASSESSMENT NOTICE
----------------------------------------------------------------------
AI-powered assessment provides preliminary category and severity recommendations.
Final verification, prioritization and resolution decisions are made by the
concerned municipal authorities.

----------------------------------------------------------------------
WHAT HAPPENS NEXT?
----------------------------------------------------------------------
1. Your report is assigned to the appropriate municipal department based on
   location and category.
2. An engineering inspection team conducts on-site verification and schedules
   remediation.
3. You will receive status updates as work orders are executed and completed.

----------------------------------------------------------------------
JANSAKSHI CIVIC GRIEVANCE & REDRESSAL PLATFORM
Empowering citizens to report, track, and resolve civic infrastructure issues
collaboratively through transparent, technology-enabled governance.

Official Civic Ingestion Desk: {official_email}
Municipal Corporation of Rajamahendravaram, Andhra Pradesh, India

Please note: This is an automated acknowledgement generated upon receipt of
your civic report. To provide additional details, photos, or landmark
clarifications, you may reply directly to this email.

© 2026 JanSakshi Platform. All rights reserved.
======================================================================
"""
