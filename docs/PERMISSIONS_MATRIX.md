# ExamAI Role & Permissions Matrix

This document provides a comprehensive map of all user roles, resource scopes, and authorization boundaries across the ExamAI platform.

---

## 1. Platform Roles & Tenancy Hierarchy

```
[ Platform Owner / Super Admin ]
       │ Cross-tenant global governance & cloaked console
       ▼
 [ Institute Admin ]  (Scoped strictly to single Institution tenant)
       │ Manages departments, faculty rosters, institute settings
       ├─────────────────────────────────┐
       ▼                                 ▼
   [ Faculty ]                       [ Student ]
(Creates questions, exams,        (Takes exams, views personal
 schedules, grades attempts)       results and feedback)
```

---

## 2. Comprehensive Permissions Matrix

| Platform Resource / Action | Super Admin | Institute Admin | Faculty | Student | Anonymous |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **System Operations** | | | | | |
| Access Cloaked Super Admin Console | **ALLOW** | DENY (404) | DENY (404) | DENY (404) | DENY (404) |
| Trigger Database Backups & Restores | **ALLOW** | DENY | DENY | DENY | DENY |
| Enable/Disable Platform Maintenance | **ALLOW** | DENY | DENY | DENY | DENY |
| Inspect System Error Logs & Metrics | **ALLOW** | DENY | DENY | DENY | DENY |
| Manage Cross-Institute Announcements | **ALLOW** | DENY | DENY | DENY | DENY |
| Process DPDP Data Erasure / Portability | **ALLOW** | DENY | DENY | DENY | DENY |
| **Institutions & Departments** | | | | | |
| Create New Institution Tenant | **ALLOW** | DENY | DENY | DENY | DENY |
| Set Feature Flags & Resource Quotas | **ALLOW** | DENY | DENY | DENY | DENY |
| View Own Institute Settings | **ALLOW** | **ALLOW** | DENY | DENY | DENY |
| Manage Departments in Own Institute | **ALLOW** | **ALLOW** | DENY | DENY | DENY |
| View Other Institutions' Data | **ALLOW** | DENY | DENY | DENY | DENY |
| **User & Account Management** | | | | | |
| Bulk Import Institute Faculty/Students | **ALLOW** | **ALLOW** | DENY | DENY | DENY |
| Suspend / Reactivate User Accounts | **ALLOW** | **ALLOW** (Own) | DENY | DENY | DENY |
| Time-Limited Impersonation | **ALLOW** (Audited) | DENY | DENY | DENY | DENY |
| Reset Super Admin Credentials | **ALLOW** (CLI Only)| DENY | DENY | DENY | DENY |
| **Exam Lifecycle & AI Generation** | | | | | |
| Trigger AI Paper Generation | **ALLOW** | DENY | **ALLOW** | DENY | DENY |
| Edit & Finalize Exam Questions | **ALLOW** | DENY | **ALLOW** (Own) | DENY | DENY |
| Publish Exam to Students | **ALLOW** | **ALLOW** | Policy-governed* | DENY | DENY |
| Schedule Exam Sessions | **ALLOW** | **ALLOW** | **ALLOW** (Assigned) | DENY | DENY |
| Attempt Exam Session | DENY | DENY | DENY | **ALLOW** (Eligible) | DENY |
| View Live Exam Question Feed | **ALLOW** | DENY | DENY | **ALLOW** (In session)| DENY |
| Review / Regrade Submissions | **ALLOW** | DENY | **ALLOW** (Assigned) | DENY | DENY |
| View Student Performance Analytics | **ALLOW** (Global) | **ALLOW** (Institute)| **ALLOW** (Course) | **ALLOW** (Self) | DENY |

*\* Note: Governed per institute by `InstitutePolicy.faculty_can_publish_without_review` (defaults to `True` unless restricted by institute administrator).*

---

## 3. Security Boundaries & Enforcement Layers

1. **Server-Side Enforcement**: All permissions are enforced in Django REST Framework permission classes (`IsSuperAdmin`, `IsInstituteAdmin`, `IsFaculty`, `IsStudent`) and service layers. No frontend flag or client bypass can grant unauthorized access.
2. **Multi-Tenant Isolation**: Queries for Institute Admins and Faculty automatically filter by `institution=request.user.institution`. Any cross-tenant URL probe returns HTTP 404 or HTTP 403.
3. **Impersonation Safety Locks**:
   - Super Admin can never be impersonated.
   - Every impersonated session generates a distinct 15-minute token with claim `is_impersonated: true` and `impersonator_id`.
   - Impersonation requires a mandatory justification reason logged into the immutable audit hash chain.
4. **Cloaked Secret Path Oracle Elimination**: Probing the Super Admin route without correct secret slug and authentication tokens returns an indistinguishable uniform HTTP 404 with no revealing server headers.
