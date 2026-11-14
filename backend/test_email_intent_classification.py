import asyncio
import unittest
import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.email.email_intent_classifier import (
    EmailIntentClassifier,
    DecisionType,
    ClassificationResult
)

# -----------------------------------------------------------------------------
# TEST CORPUS (34 DIVERSE REAL-WORLD SAMPLES)
# -----------------------------------------------------------------------------
CORPUS = [
    # --- Category: Account Security Notifications (Expected: NON_CIVIC) ---
    {
        "id": "SEC-01",
        "sender": "noreply@higgsfield.ai",
        "subject": "New device signed in to your Higgsfield AI account",
        "body": "A new device just signed in to your Higgsfield AI account. Sign in type: OAuth, Device: Windows Chrome, Location: Rajamahendravaram. Visit https://higgsfield.ai/_clerk/v1/tickets/accept?ticket=xyz to revoke.",
        "expected": DecisionType.NON_CIVIC,
        "type": "account_security"
    },
    {
        "id": "SEC-02",
        "sender": "no-reply@accounts.google.com",
        "subject": "Security alert: New login from Chrome on Windows",
        "body": "Your Google Account was just signed in to from a new Windows device. If this was you, you don't need to do anything. If not, check your account activity.",
        "expected": DecisionType.NON_CIVIC,
        "type": "account_security"
    },
    {
        "id": "SEC-03",
        "sender": "notifications@github.com",
        "subject": "[GitHub] A new personal access token was generated",
        "body": "We noticed a new personal access token was created on your GitHub account. If you did not initiate this action, revoke it immediately.",
        "expected": DecisionType.NON_CIVIC,
        "type": "account_security"
    },
    {
        "id": "SEC-04",
        "sender": "account-update@amazon.in",
        "subject": "Amazon password changed successfully",
        "body": "The password for your Amazon account has been successfully reset. If you didn't request this change, please contact customer support immediately.",
        "expected": DecisionType.NON_CIVIC,
        "type": "account_security"
    },

    # --- Category: OTP & Authentication (Expected: NON_CIVIC) ---
    {
        "id": "OTP-01",
        "sender": "alerts@icicibank.com",
        "subject": "Your OTP for Internet Banking Login",
        "body": "948201 is your One-Time Password (OTP) for logging in. Do not share this OTP with anyone, including bank officials. Valid for 5 minutes.",
        "expected": DecisionType.NON_CIVIC,
        "type": "otp"
    },
    {
        "id": "OTP-02",
        "sender": "noreply@uber.com",
        "subject": "Your Uber verification code",
        "body": "Your Uber login code is 4829. Never share this code with anyone.",
        "expected": DecisionType.NON_CIVIC,
        "type": "otp"
    },
    {
        "id": "OTP-03",
        "sender": "verify@swiggy.in",
        "subject": "Swiggy Login Verification Code",
        "body": "Use code 719302 to complete your sign in. This code expires in 10 minutes.",
        "expected": DecisionType.NON_CIVIC,
        "type": "otp"
    },

    # --- Category: Account Lifecycle & Welcome (Expected: NON_CIVIC) ---
    {
        "id": "LIFE-01",
        "sender": "welcome@notion.so",
        "subject": "Welcome to Notion!",
        "body": "Thanks for signing up for Notion. Getting started with your personal workspace is easy. Check out our quickstart templates.",
        "expected": DecisionType.NON_CIVIC,
        "type": "lifecycle"
    },
    {
        "id": "LIFE-02",
        "sender": "accounts@figma.com",
        "subject": "Please confirm your email address",
        "body": "Welcome to Figma! Confirm your email address to activate your account and start collaborating with your team.",
        "expected": DecisionType.NON_CIVIC,
        "type": "lifecycle"
    },
    {
        "id": "LIFE-03",
        "sender": "info@twitter.com",
        "subject": "Confirm your registration",
        "body": "Complete your registration by clicking the link below. Thanks for joining X.",
        "expected": DecisionType.NON_CIVIC,
        "type": "lifecycle"
    },

    # --- Category: Financial, Invoices & Receipts (Expected: NON_CIVIC) ---
    {
        "id": "FIN-01",
        "sender": "invoice+statements@stripe.com",
        "subject": "Your receipt from GitHub, Inc. (Invoice #GH-90214)",
        "body": "Your credit card charged $20.00 for GitHub Team subscription. Order total: $20.00. Payment successful via Stripe.",
        "expected": DecisionType.NON_CIVIC,
        "type": "billing"
    },
    {
        "id": "FIN-02",
        "sender": "no-reply@swiggy.in",
        "subject": "Order Delivered - Invoice for Swiggy Order #93029148",
        "body": "Thank you for ordering with Swiggy. Order total: ₹450. Payment received via UPI. Download your tax invoice here.",
        "expected": DecisionType.NON_CIVIC,
        "type": "billing"
    },
    {
        "id": "FIN-03",
        "sender": "no-reply@razorpay.com",
        "subject": "Payment successful for order #ORD-49204",
        "body": "Your payment of INR 1,299 was successful. Transaction ID: pay_Nks029fk2. Razorpay payment confirmation.",
        "expected": DecisionType.NON_CIVIC,
        "type": "billing"
    },

    # --- Category: Marketing & Newsletters (Expected: NON_CIVIC) ---
    {
        "id": "MKT-01",
        "sender": "newsletter@tldr.tech",
        "subject": "TLDR Tech: The latest in AI and tech news (Weekly Digest)",
        "body": "Welcome to today's edition of TLDR. Big updates in LLMs this week. Click here to unsubscribe or manage your email preferences.",
        "expected": DecisionType.NON_CIVIC,
        "type": "marketing"
    },
    {
        "id": "MKT-02",
        "sender": "promotions@flipkart.com",
        "subject": "Special discount: Up to 50% off on electronics this weekend!",
        "body": "Limited time offer! Use promotional code SAVE50 at checkout. View in browser. Unsubscribe from this list.",
        "expected": DecisionType.NON_CIVIC,
        "type": "marketing"
    },
    {
        "id": "MKT-03",
        "sender": "digest@medium.com",
        "subject": "Stories for you from Medium Daily Digest",
        "body": "Top stories recommended based on your reading list. Unsubscribe here.",
        "expected": DecisionType.NON_CIVIC,
        "type": "marketing"
    },

    # --- Category: Platform / Social / Code Repo (Expected: NON_CIVIC) ---
    {
        "id": "SOC-01",
        "sender": "notifications@github.com",
        "subject": "[GitHub] Pull request #42 opened: Add dark mode theme",
        "body": "tejeswar opened pull request #42 in JanSakshi/backend. 3 commits pushed. Review requested.",
        "expected": DecisionType.NON_CIVIC,
        "type": "platform"
    },
    {
        "id": "SOC-02",
        "sender": "jira@atlassian.net",
        "subject": "[JIRA] (MUNICIPAL-104) Assigned to you on Jira",
        "body": "Ashok assigned task MUNICIPAL-104 to you: Update API documentation for sprint 4.",
        "expected": DecisionType.NON_CIVIC,
        "type": "platform"
    },
    {
        "id": "SOC-03",
        "sender": "invitations@linkedin.com",
        "subject": "Invitation to connect on LinkedIn from Ramesh Kumar",
        "body": "Ramesh Kumar would like to join your professional network on LinkedIn. View invitation.",
        "expected": DecisionType.NON_CIVIC,
        "type": "platform"
    },

    # --- Category: System Bounces & Auto-replies (Expected: NON_CIVIC) ---
    {
        "id": "BNC-01",
        "sender": "mailer-daemon@googlemail.com",
        "subject": "Delivery Status Notification (Failure)",
        "body": "** Message blocked ** Your message to noreply@higgsfield.ai has been blocked. 550 5.1.1 Address not found.",
        "expected": DecisionType.NON_CIVIC,
        "type": "bounce"
    },
    {
        "id": "BNC-02",
        "sender": "postmaster@outlook.com",
        "subject": "Undelivered Mail Returned to Sender",
        "body": "This is the mail delivery subsystem. The following address had permanent fatal errors: user@nonexistent.domain. Mail delivery failed.",
        "expected": DecisionType.NON_CIVIC,
        "type": "bounce"
    },
    {
        "id": "BNC-03",
        "sender": "officer@rajamahendravaram.gov.in",
        "subject": "Automatic reply: Out of Office",
        "body": "I am currently out of the office on annual leave until next Monday. For urgent queries please contact the control room.",
        "expected": DecisionType.NON_CIVIC,
        "type": "bounce"
    },

    # --- Category: Delivery & Shipping (Expected: NON_CIVIC) ---
    {
        "id": "SHP-01",
        "sender": "shipment@amazon.in",
        "subject": "Your package has shipped! Track package #402-920194",
        "body": "Your order is out for delivery. Tracking number: BLUEDART92049. Shipment delivered by 8 PM today.",
        "expected": DecisionType.NON_CIVIC,
        "type": "shipping"
    },
    {
        "id": "SHP-02",
        "sender": "tracking@fedex.com",
        "subject": "FedEx Tracking Update for Order #90219",
        "body": "Your international package has cleared customs and is in transit. FedEx tracking update.",
        "expected": DecisionType.NON_CIVIC,
        "type": "shipping"
    },

    # --- Category: Spam / Scam (Expected: NON_CIVIC) ---
    {
        "id": "SPM-01",
        "sender": "claims@lottery-winner-2026.org",
        "subject": "Congratulations you have won $1,000,000 in international lottery",
        "body": "You are the lucky beneficiary of funds. Urgent wire transfer awaiting your passport copy. Claim your reward now.",
        "expected": DecisionType.NON_CIVIC,
        "type": "spam"
    },

    # --- Category: Genuine Civic Complaints (Expected: CIVIC_COMPLAINT) ---
    {
        "id": "CIV-01",
        "sender": "citizen.rajesh@gmail.com",
        "subject": "Severe pothole causing accidents near Morampudi Junction",
        "body": "Respected Municipal Commissioner, there is a very deep and dangerous pothole right in the middle of Morampudi Junction. Yesterday a two-wheeler fell down. Please repair this road damage urgently.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_road"
    },
    {
        "id": "CIV-02",
        "sender": "sita.k@yahoo.co.in",
        "subject": "Broken streetlights along Danavaipeta main road",
        "body": "None of the streetlights are functioning on Danavaipeta 4th street for the past 5 days. The entire lane is pitch dark and unsafe for women walking at night. Please fix the street lights.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_lighting"
    },
    {
        "id": "CIV-03",
        "sender": "venkat.r@gmail.com",
        "subject": "Uncollected garbage dump overflowing near RTC Complex",
        "body": "Huge pile of garbage has been rotting near RTC bus stand gate for over a week. The municipal waste bins are completely overflowing and spreading foul smell. Stray cattle are eating plastic. Kindly arrange garbage collection.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_sanitation"
    },
    {
        "id": "CIV-04",
        "sender": "resident_society@outlook.com",
        "subject": "Drainage overflow and open manhole in Tilak Road",
        "body": "Heavy sewage water is spilling across Tilak Road due to a choked sewer line. An open manhole cover is completely invisible under the dirty water. It is a major hazard for pedestrians and school children. Immediate drainage repair needed.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_drainage"
    },
    {
        "id": "CIV-05",
        "sender": "k.lakshman@rediffmail.com",
        "subject": "Drinking water pipeline burst near Kambala Park",
        "body": "Main drinking water supply pipeline has burst near the east entrance of Kambala Park. Thousands of liters of municipal water are being wasted and flooding the road. Please dispatch the water department team.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_water"
    },
    {
        "id": "CIV-06",
        "sender": "nagaraju.m@gmail.com",
        "subject": "Damaged public footpath and broken railing at Godavari Ghat",
        "body": "The public footpath tiles are collapsed and the safety railing along the river viewpoint is broken. Senior citizens visit this park daily. This public infrastructure needs immediate repair.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_infra"
    },
    {
        "id": "CIV-07",
        "sender": "ananya.dev@gmail.com",
        "subject": "Fallen tree branch blocking traffic on Church Road",
        "body": "A huge banyan tree branch fell on the road after yesterday's rain and is completely blocking Church Road traffic. Electric cables are also entangled. Please send the municipal clearing squad.",
        "expected": DecisionType.CIVIC_COMPLAINT,
        "type": "civic_obstruction"
    },

    # --- Category: Ambiguous / Citizen Enquiry (Expected: NEEDS_ADMIN_REVIEW) ---
    {
        "id": "AMB-01",
        "sender": "citizen.surya@gmail.com",
        "subject": "Municipal office working hours inquiry",
        "body": "Hello, can someone tell me what are the visiting hours for the property tax office on Saturday? Thank you.",
        "expected": DecisionType.NEEDS_ADMIN_REVIEW,
        "type": "ambiguous"
    },

    # --- Category: Civic Follow-up in Existing Thread (Expected: CIVIC_FOLLOW_UP) ---
    {
        "id": "FOL-01",
        "sender": "citizen.rajesh@gmail.com",
        "subject": "Re: Complaint Acknowledged [JS-2026-00028] - Morampudi Junction",
        "body": "Here are the exact coordinates of the pothole: 17.0005, 81.7800. Also attached photo.",
        "expected": DecisionType.CIVIC_FOLLOW_UP,
        "type": "follow_up",
        "thread_has_complaint": True
    }
]

class TestEmailIntentClassification(unittest.IsolatedAsyncioTestCase):
    """
    Validation test suite for JanSakshi's multi-layered email intent classification.
    Tests precision, recall, specificity, and regression resilience across 34 test cases.
    """

    async def test_full_corpus_classification(self):
        total = len(CORPUS)
        correct = 0
        non_civic_correct = 0
        non_civic_total = 0
        civic_correct = 0
        civic_total = 0
        false_complaints_created = 0

        print(f"\n=======================================================")
        print(f"RUNNING JANSAKSHI EMAIL INTENT CLASSIFICATION TEST SUITE")
        print(f"Total Test Cases: {total}")
        print(f"=======================================================\n")

        for case in CORPUS:
            is_thread = case.get("thread_has_complaint", False)
            result: ClassificationResult = await EmailIntentClassifier.classify(
                subject=case["subject"],
                body_plain=case["body"],
                sender_email=case["sender"],
                thread_has_complaint=is_thread
            )

            is_match = (result.decision == case["expected"])
            if is_match:
                correct += 1

            if case["expected"] == DecisionType.NON_CIVIC:
                non_civic_total += 1
                if result.decision == DecisionType.NON_CIVIC:
                    non_civic_correct += 1
                elif result.decision == DecisionType.CIVIC_COMPLAINT:
                    false_complaints_created += 1

            if case["expected"] == DecisionType.CIVIC_COMPLAINT:
                civic_total += 1
                if result.decision == DecisionType.CIVIC_COMPLAINT:
                    civic_correct += 1

            status_mark = "PASS" if is_match else "FAIL"
            print(f"[{status_mark}] {case['id']} ({case['type']}): Decided={result.decision.value} (Expected={case['expected'].value}) | Conf={result.confidence:.2f} | Layer={result.layer}")

        accuracy = (correct / total) * 100.0
        non_civic_accuracy = (non_civic_correct / non_civic_total) * 100.0 if non_civic_total else 100.0
        civic_recall = (civic_correct / civic_total) * 100.0 if civic_total else 100.0

        print("\n-------------------------------------------------------")
        print(f"RESULTS SUMMARY:")
        print(f"Overall Accuracy: {accuracy:.1f}% ({correct}/{total})")
        print(f"Non-Civic Rejection Rate (Specificity): {non_civic_accuracy:.1f}% ({non_civic_correct}/{non_civic_total})")
        print(f"Civic Complaint Recall: {civic_recall:.1f}% ({civic_correct}/{civic_total})")
        print(f"CRITICAL SAFETY METRIC: False Complaints Created = {false_complaints_created}")
        print(f"-------------------------------------------------------\n")

        # Strict safety assertion: NEVER allow a non-civic email to become a CIVIC_COMPLAINT!
        self.assertEqual(false_complaints_created, 0, "FATAL: Non-civic emails were classified as CIVIC_COMPLAINT!")
        self.assertGreaterEqual(accuracy, 95.0, f"Accuracy below threshold: {accuracy:.1f}%")

if __name__ == "__main__":
    unittest.main()

