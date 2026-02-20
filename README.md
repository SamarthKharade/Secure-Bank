# 🏦 SecureBank — Small Bank Application

A full-stack banking application built with Flask and MongoDB featuring a unique 
consent-based admin access control system where administrators must request 
permission from users before accessing their accounts.

## 🌟 Key Highlight
Unlike traditional banking systems where admins have unrestricted access, 
SecureBank requires admins to send an access request to the user. The user 
receives an email notification and must explicitly Grant or Deny the request. 
Access is time-limited to 30 minutes and every action is logged in an audit trail.

## 🚀 Features
- ✅ User Registration & Login with JWT Authentication
- ✅ Deposit, Withdraw & Transfer Money
- ✅ Consent-Based Admin Access Control
- ✅ Email Notifications for every action
- ✅ Fraud Detection using Isolation Forest (ML)
- ✅ Loan Eligibility Prediction using Logistic Regression (ML)
- ✅ Spending Category Analysis (AI-powered)
- ✅ Credit Score Simulation (300-900)
- ✅ Full Audit Trail of every action
- ✅ Admin Dashboard with flagged transactions
- ✅ Account Activate/Deactivate by Admin

## 🛠️ Tech Stack
- **Backend:** Python, Flask
- **Database:** MongoDB Atlas
- **Authentication:** JWT (JSON Web Tokens)
- **Email:** Flask-Mail (Gmail SMTP)
- **Machine Learning:** scikit-learn (Isolation Forest, Logistic Regression)
- **Frontend:** HTML, CSS, Vanilla JavaScript

## 🔐 Security Features
- Password hashing with bcrypt
- Account lockout after 5 failed login attempts
- Rate limiting on all API endpoints
- Time-limited permission tokens (30 min expiry)
- Complete audit logging with IP tracking