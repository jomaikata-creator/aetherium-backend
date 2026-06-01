"""Email service — Resend API with console fallback for dev."""
import os
import httpx

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@aetherium.dev")
APP_URL = os.getenv("APP_URL", "http://localhost:5175")


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

    # Try Resend API first
    if RESEND_API_KEY:
        try:
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
                print(f"[email] Invite sent to {to_email} via Resend")
                return True
            print(f"[email] Resend error: {r.status_code} {r.text}")
        except Exception as e:
            print(f"[email] Resend failed: {e}")

    # Fallback: log to console
    print(f"\n{'='*60}")
    print(f"[email] INVITE FOR: {to_name} <{to_email}>")
    print(f"[email] Role: {role}")
    print(f"[email] Reset URL: {reset_url}")
    print(f"{'='*60}\n")
    return False
