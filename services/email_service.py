"""Email service — SMTP with console fallback for dev."""
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@aetherium.dev")
APP_URL = os.getenv("APP_URL", "http://localhost:5175")

# Keep Resend as optional fallback
RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def _send_email(to_email: str, subject: str, html: str) -> bool:
    """Try SMTP first, then Resend, then console fallback."""
    # 1) SMTP
    if SMTP_HOST and SMTP_USERNAME:
        try:
            msg = MIMEMultipart("alternative")
            msg["From"] = f"Aetherium <{FROM_EMAIL}>"
            msg["To"] = to_email
            msg["Subject"] = subject
            msg.attach(MIMEText(html, "html"))

            with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
                if SMTP_PORT == 587:
                    server.starttls()
                if SMTP_PASSWORD:
                    server.login(SMTP_USERNAME, SMTP_PASSWORD)
                server.sendmail(FROM_EMAIL, [to_email], msg.as_string())

            print(f"[email] Sent to {to_email} via SMTP ({SMTP_HOST})")
            return True
        except Exception as e:
            print(f"[email] SMTP failed: {e}")

    # 2) Resend fallback
    if RESEND_API_KEY:
        try:
            import httpx
            r = httpx.post(
                "https://api.resend.com/emails",
                headers={
                    "Authorization": f"Bearer {RESEND_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "from": f"Aetherium <{FROM_EMAIL}>",
                    "to": [to_email],
                    "subject": subject,
                    "html": html,
                },
                timeout=10,
            )
            if r.status_code == 200:
                print(f"[email] Sent to {to_email} via Resend")
                return True
            print(f"[email] Resend error: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[email] Resend failed: {e}")

    # 3) Console fallback
    print(f"\n{'='*60}")
    print(f"[email] TO: {to_email}")
    print(f"[email] SUBJECT: {subject}")
    print(f"{'='*60}")
    print(html)
    print(f"{'='*60}\n")
    return False


def send_invite_email(to_email: str, to_name: str, reset_token: str, role: str):
    """Send a welcome email with a Set Your Password button."""
    subject = f"Welcome to Aetherium — Set Your Password"
    reset_url = f"{APP_URL}/set-password?token={reset_token}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#08090d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#08090d;padding:40px 0">
<tr><td align="center">
<table width="520" cellpadding="0" cellspacing="0" style="background:#0a0b10;border:1px solid rgba(255,255,255,0.06);border-radius:16px;overflow:hidden">

  <!-- Header -->
  <tr><td style="padding:40px 40px 10px;text-align:center">
    <h1 style="margin:0;color:#fff;font-size:24px;font-weight:700;letter-spacing:-0.02em">Aetherium</h1>
    <p style="margin:8px 0 0;color:rgba(255,255,255,0.4);font-size:13px">Web Design Agency</p>
  </td></tr>

  <!-- Body -->
  <tr><td style="padding:30px 40px">
    <h2 style="margin:0;color:#fff;font-size:18px;font-weight:600">Welcome, {to_name}!</h2>
    <p style="margin:16px 0 0;color:rgba(255,255,255,0.6);font-size:14px;line-height:1.6">
      You've been added to the Aetherium team as a <strong style="color:#60a5fa">{role}</strong>.
      Click the button below to set your password and get started.
    </p>

    <!-- Button -->
    <div style="text-align:center;margin:32px 0">
      <a href="{reset_url}" style="display:inline-block;padding:14px 40px;background:#3b82f6;color:#fff;text-decoration:none;border-radius:10px;font-size:15px;font-weight:600;letter-spacing:0.01em">Set Your Password</a>
    </div>

    <p style="margin:0;color:rgba(255,255,255,0.3);font-size:12px;line-height:1.5">
      This link expires in 48 hours. If you didn't expect this, you can ignore this email.<br><br>
      Or copy this link:<br>
      <span style="color:rgba(255,255,255,0.4)">{reset_url}</span>
    </p>
  </td></tr>

  <!-- Footer -->
  <tr><td style="padding:30px 40px;border-top:1px solid rgba(255,255,255,0.06);text-align:center">
    <p style="margin:0;color:rgba(255,255,255,0.2);font-size:11px">Aetherium Web Studio &copy; 2026</p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return _send_email(to_email, subject, html)


def send_subscription_email(
    to_email: str,
    client_name: str,
    project_name: str,
    monthly_fee: float,
    checkout_url: str,
):
    """Send a light-themed payment request email for a new subscription."""
    subject = f"Your maintenance subscription for {project_name} is ready"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f2f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f8;padding:48px 16px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">

  <!-- Header accent bar -->
  <tr><td style="height:6px;background:linear-gradient(90deg,#6c5ce7,#a29bfe,#fd79a8)"></td></tr>

  <!-- Logo area -->
  <tr><td style="padding:40px 48px 0;text-align:center">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto">
    <tr>
      <td style="width:44px;height:44px;background:#6c5ce7;border-radius:12px;text-align:center;vertical-align:middle;font-size:20px;font-weight:700;color:#fff;line-height:44px">A</td>
      <td style="padding-left:12px;vertical-align:middle">
        <span style="font-size:20px;font-weight:700;color:#1a1a2e;letter-spacing:-0.3px">Aetherium</span>
        <span style="display:block;font-size:12px;color:#8888a0;font-weight:400;margin-top:-2px">Web Design Studio</span>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:24px 48px 0"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 48px">
    <h2 style="margin:0;color:#1a1a2e;font-size:22px;font-weight:700;letter-spacing:-0.3px">
      Hi {client_name},
    </h2>
    <p style="margin:16px 0 0;color:#555574;font-size:15px;line-height:1.7">
      Your project <strong style="color:#1a1a2e">{project_name}</strong> is complete and we're ready to keep it running smoothly.
      To activate <strong style="color:#1a1a2e">monthly maintenance</strong> — including hosting, updates, and priority support — please complete the secure payment setup below.
    </p>

    <!-- Pricing card -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;background:#f8f9fc;border-radius:14px;border:1px solid #eaecf0">
    <tr><td style="padding:24px 28px">
      <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle">
          <span style="font-size:13px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Monthly Maintenance</span>
          <span style="display:block;font-size:13px;color:#555574;margin-top:4px">{project_name}</span>
        </td>
        <td style="vertical-align:middle;text-align:right">
          <span style="font-size:28px;font-weight:700;color:#1a1a2e;letter-spacing:-0.5px">€{monthly_fee:.2f}</span>
          <span style="font-size:13px;color:#8888a0;display:block">/ month</span>
        </td>
      </tr>
      </table>
    </td></tr>
    </table>

    <!-- Button -->
    <div style="text-align:center;margin:0 0 24px">
      <a href="{checkout_url}" style="display:inline-block;padding:16px 48px;background:#6c5ce7;color:#ffffff;text-decoration:none;border-radius:12px;font-size:16px;font-weight:600;letter-spacing:0.2px;box-shadow:0 4px 14px rgba(108,92,231,0.3)">
        Set Up Payment →
      </a>
    </div>

    <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.6;text-align:center">
      You'll only be charged after setup is complete. You can cancel anytime.
    </p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 48px"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Footer -->
  <tr><td style="padding:24px 48px 36px;text-align:center">
    <p style="margin:0;color:#bbbbcc;font-size:12px;line-height:1.6">
      If the button doesn't work, copy and paste this link into your browser:<br>
      <a href="{checkout_url}" style="color:#6c5ce7;text-decoration:underline;word-break:break-all">{checkout_url}</a>
    </p>
    <p style="margin:16px 0 0;color:#bbbbcc;font-size:11px">
      Aetherium Web Studio &copy; 2026 &middot; All rights reserved.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return _send_email(to_email, subject, html)


def send_payment_email(
    to_email: str,
    client_name: str,
    project_name: str,
    amount: float,
    payment_type: str,  # "deposit" or "final"
    checkout_url: str,
):
    """Send a light-themed payment request email with the Stripe checkout link."""
    label = "Deposit Payment" if payment_type == "deposit" else "Final Payment"
    subject = f"{label} for {project_name}"

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f2f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f8;padding:48px 16px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">

  <!-- Header accent bar -->
  <tr><td style="height:6px;background:linear-gradient(90deg,#6c5ce7,#a29bfe,#fd79a8)"></td></tr>

  <!-- Logo area -->
  <tr><td style="padding:40px 48px 0;text-align:center">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto">
    <tr>
      <td style="width:44px;height:44px;background:#6c5ce7;border-radius:12px;text-align:center;vertical-align:middle;font-size:20px;font-weight:700;color:#fff;line-height:44px">A</td>
      <td style="padding-left:12px;vertical-align:middle">
        <span style="font-size:20px;font-weight:700;color:#1a1a2e;letter-spacing:-0.3px">Aetherium</span>
        <span style="display:block;font-size:12px;color:#8888a0;font-weight:400;margin-top:-2px">Web Design Studio</span>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:24px 48px 0"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 48px">
    <h2 style="margin:0;color:#1a1a2e;font-size:22px;font-weight:700;letter-spacing:-0.3px">
      Hi {client_name},
    </h2>
    <p style="margin:16px 0 0;color:#555574;font-size:15px;line-height:1.7">
      Here's the payment link for your project <strong style="color:#1a1a2e">{project_name}</strong>.
      Please complete the secure {label.lower()} below to move forward.
    </p>

    <!-- Pricing card -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;background:#f8f9fc;border-radius:14px;border:1px solid #eaecf0">
    <tr><td style="padding:24px 28px">
      <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle">
          <span style="font-size:13px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">{label}</span>
          <span style="display:block;font-size:13px;color:#555574;margin-top:4px">{project_name}</span>
        </td>
        <td style="vertical-align:middle;text-align:right">
          <span style="font-size:28px;font-weight:700;color:#1a1a2e;letter-spacing:-0.5px">€{amount:.2f}</span>
          <span style="font-size:13px;color:#8888a0;display:block">one-time</span>
        </td>
      </tr>
      </table>
    </td></tr>
    </table>

    <!-- Button -->
    <div style="text-align:center;margin:0 0 24px">
      <a href="{checkout_url}" style="display:inline-block;padding:16px 48px;background:#6c5ce7;color:#ffffff;text-decoration:none;border-radius:12px;font-size:16px;font-weight:600;letter-spacing:0.2px;box-shadow:0 4px 14px rgba(108,92,231,0.3)">
        Pay Securely →
      </a>
    </div>

    <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.6;text-align:center">
      This payment link expires in 24 hours. Your card details are handled securely by Stripe.
    </p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 48px"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Footer -->
  <tr><td style="padding:24px 48px 36px;text-align:center">
    <p style="margin:0;color:#bbbbcc;font-size:12px;line-height:1.6">
      If the button doesn't work, copy and paste this link into your browser:<br>
      <a href="{checkout_url}" style="color:#6c5ce7;text-decoration:underline;word-break:break-all">{checkout_url}</a>
    </p>
    <p style="margin:16px 0 0;color:#bbbbcc;font-size:11px">
      Aetherium Web Studio &copy; 2026 &middot; All rights reserved.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return _send_email(to_email, subject, html)


def send_invoice_email(
    to_email: str,
    client_name: str,
    project_name: str,
    amount: float,
    currency: str,
    invoice_number: str,
    invoice_date: str,
    invoice_type: str,
    service_description: str,
    stripe_hosted_url: str | None = None,
):
    """Send a light-themed invoice email with the same design as the payment request."""
    type_labels = {"deposit": "Deposit Invoice", "final": "Final Invoice", "monthly": "Monthly Invoice"}
    type_label = type_labels.get(invoice_type, "Invoice")

    subject = f"Invoice {invoice_number} for {project_name}"

    invoice_url_section = ""
    if stripe_hosted_url:
        invoice_url_section = f"""
    <!-- View Invoice button -->
    <div style="text-align:center;margin:0 0 24px">
      <a href="{stripe_hosted_url}" style="display:inline-block;padding:16px 48px;background:#6c5ce7;color:#ffffff;text-decoration:none;border-radius:12px;font-size:16px;font-weight:600;letter-spacing:0.2px;box-shadow:0 4px 14px rgba(108,92,231,0.3)">
        View Invoice &rarr;
      </a>
    </div>"""

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f2f4f8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f2f4f8;padding:48px 16px">
<tr><td align="center">
<table width="560" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.06)">

  <!-- Header accent bar -->
  <tr><td style="height:6px;background:linear-gradient(90deg,#6c5ce7,#a29bfe,#fd79a8)"></td></tr>

  <!-- Logo area -->
  <tr><td style="padding:40px 48px 0;text-align:center">
    <table cellpadding="0" cellspacing="0" style="margin:0 auto">
    <tr>
      <td style="width:44px;height:44px;background:#6c5ce7;border-radius:12px;text-align:center;vertical-align:middle;font-size:20px;font-weight:700;color:#fff;line-height:44px">A</td>
      <td style="padding-left:12px;vertical-align:middle">
        <span style="font-size:20px;font-weight:700;color:#1a1a2e;letter-spacing:-0.3px">Aetherium</span>
        <span style="display:block;font-size:12px;color:#8888a0;font-weight:400;margin-top:-2px">Web Design Studio</span>
      </td>
    </tr>
    </table>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:24px 48px 0"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Body -->
  <tr><td style="padding:32px 48px">
    <h2 style="margin:0;color:#1a1a2e;font-size:22px;font-weight:700;letter-spacing:-0.3px">
      Hi {client_name},
    </h2>
    <p style="margin:16px 0 0;color:#555574;font-size:15px;line-height:1.7">
      Thank you! Your payment for <strong style="color:#1a1a2e">{project_name}</strong> has been received.
      Your invoice is below.
    </p>

    <!-- Invoice card -->
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:28px 0;background:#f8f9fc;border-radius:14px;border:1px solid #eaecf0">
    <tr><td style="padding:24px 28px">

      <!-- Invoice header -->
      <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <span style="font-size:11px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Invoice</span>
          <span style="display:block;font-size:16px;color:#1a1a2e;font-weight:600;margin-top:2px">#{invoice_number}</span>
        </td>
        <td style="text-align:right">
          <span style="font-size:11px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Date</span>
          <span style="display:block;font-size:14px;color:#555574;margin-top:2px">{invoice_date}</span>
        </td>
      </tr>
      </table>

      <div style="height:1px;background:#eaecf0;margin:16px 0"></div>

      <!-- Service -->
      <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td>
          <span style="font-size:11px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Service</span>
          <span style="display:block;font-size:14px;color:#555574;margin-top:2px">{service_description}</span>
          <span style="display:block;font-size:13px;color:#8888a0;margin-top:2px">{project_name}</span>
        </td>
      </tr>
      </table>

      <div style="height:1px;background:#eaecf0;margin:16px 0"></div>

      <!-- Amount + Status -->
      <table width="100%" cellpadding="0" cellspacing="0">
      <tr>
        <td style="vertical-align:middle">
          <span style="font-size:11px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">Amount</span>
          <span style="display:block;font-size:24px;font-weight:700;color:#1a1a2e;letter-spacing:-0.5px;margin-top:4px">&euro;{amount:,.2f} {currency}</span>
        </td>
        <td style="text-align:right;vertical-align:middle">
          <span style="display:inline-block;padding:8px 20px;background:#e8f5e9;border-radius:20px;color:#2e7d32;font-size:12px;font-weight:700;letter-spacing:0.5px;text-transform:uppercase">Paid</span>
        </td>
      </tr>
      </table>

    </td></tr>
    </table>

    <!-- Type label -->
    <div style="text-align:center;margin:0 0 24px">
      <span style="font-size:12px;color:#8888a0;text-transform:uppercase;letter-spacing:0.5px;font-weight:600">{type_label}</span>
    </div>
{invoice_url_section}
    <p style="margin:0;color:#8888a0;font-size:13px;line-height:1.6;text-align:center">
      For any questions, simply reply to this email.
    </p>
  </td></tr>

  <!-- Divider -->
  <tr><td style="padding:0 48px"><div style="height:1px;background:#eaecf0"></div></td></tr>

  <!-- Footer -->
  <tr><td style="padding:24px 48px 36px;text-align:center">
    <p style="margin:0;color:#bbbbcc;font-size:12px;line-height:1.6">
      Aetherium Web Studio &copy; 2026 &middot; All rights reserved.
    </p>
  </td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    return _send_email(to_email, subject, html)
