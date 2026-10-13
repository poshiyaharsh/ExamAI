# ExamAI Architecture & Deep Design Guide

## 1. System Overview

ExamAI is designed around a multi-tier, multi-tenant architecture where data segregation, mathematical evaluation accuracy, and high concurrency are enforced at the database, application, and caching levels.

```mermaid
flowchart TD
    subgraph Client["Frontend Client (React 18 + Vite)"]
        UI["React SPA (React Router v7)"]
        Axios["Axios Client (api.ts)"]
        Refresh["Auto 401 Refresh Queue"]
        UI --> Axios
        Axios -.->|"On 401 Unauthorized"| Refresh
    end

    subgraph Gateway["Django 6.0 REST Backend"]
        AuthMiddleware["TenantJWTAuthentication"]
        TenantMixin["TenantScopedMixin / Views"]
        CacheLayer["LocMemCache / Redis Layer"]
        DBRetry["db_retry Decorator (Deadlock Guard)"]
        
        Axios -->|"Bearer JWT + institution_id"| AuthMiddleware
        AuthMiddleware --> TenantMixin
        TenantMixin <-->|"Key: tenant_version + institution_id"| CacheLayer
        TenantMixin --> DBRetry
    end

    subgraph Storage["Persistence Layer"]
        MySQL[("MySQL 8.4 LTS InnoDB")]
        SQLite[("SQLite 3 Fallback")]
        DBRetry --> MySQL
        DBRetry -.->|"DB_ENGINE=sqlite"| SQLite
    end
```

---

## 2. Multi-Tenant Isolation Layer

### Tenant Identity in Authentication
1. **User Association**: Every user belongs to an `AdminInstitution` record through their specific profile:
   - **Admin**: `admins_admininstitution.admin_id = user.id`
   - **Faculty**: `faculty_facultyprofile.institution_id`
   - **Student**: `students_studentprofile.institution_id`
2. **JWT Claims**: When tokens are issued via `/api/admin/login/`, `/api/faculty/login/`, or `/api/student/login/`, the user's `institution_id` is embedded in the JWT payload.
3. **Anti-Spoofing Verification**:
   [`TenantJWTAuthentication`](file:///e:/03%20Study/Django/Mini-Project/api/tenant.py) intercepts every incoming request:
   - Verifies the user against `auth_user`.
   - Fetches the active institution from the database.
   - Compares token `institution_id` with database institution `id`. If a mismatch is detected, it immediately throws `AuthenticationFailed('Security violation: token institution mismatch.')`.
   - Checks institution status; if status is `suspended`, rejects with `AuthenticationFailed('Your institution has been suspended.')`.
   - Injects `request.tenant` (`AdminInstitution`) and `request.tenant_id` into the request context.

### Query Scoping
All querysets are filtered explicitly by institution:
```python
# Standard tenant-scoped query pattern
Exam.objects.filter(institution=request.tenant)
Question.objects.filter(institution=request.tenant)
StudentProfile.objects.filter(institution=request.tenant)
```

---

## 3. High-Performance Multi-Tenant Caching

ExamAI uses an in-memory cache architecture with versioned tenant namespaces. Cache keys are strictly namespaced by `institution_id` and a per-tenant version counter:

### Cache Key Syntax
| Type | Cache Key Format | TTL |
| :--- | :--- | :--- |
| **Paper Snapshot** | `paper:v1:t{t_ver}:inst_{inst_id}:fac_{fac_id}:{request_hash}` | 24 Hours (`86400s`) |
| **Candidate Pool** | `pool:v1:t{t_ver}:inst_{inst_id}:dept_{dept}:sub_{sub_id}:top_{topic}:diff_{diff}:type_{type}` | 10 Minutes (`600s`) |
| **Paper List** | `paperlist:v1:t{t_ver}:inst_{inst_id}:fac_{fac_id}:p{page}:{filters}` | 5 Minutes (`300s`) |
| **Paper Detail** | `paperdetail:v1:t{t_ver}:inst_{inst_id}:exam_{exam_id}` | 24 Hours (`86400s`) |

### Instant Tenant Cache Invalidation
When an administrator or faculty member modifies the Question Bank, imports questions, or publishes an exam:
```python
bump_tenant_cache_version(institution_id)
```
This increments the tenant version counter in cache (e.g. `t1` -> `t2`), instantaneously invalidating all cached papers, candidate pools, and lists for that institution with zero race conditions and zero lingering stale data.

---

## 4. Reusable Zero-Duplicate Paper Generation Engine

```mermaid
flowchart TD
    Req["Paper Generation Request (Blueprint)"] --> Hash["Compute Deterministic Request Hash (SHA-256)"]
    Hash --> CacheCheck{"Cache Hit and Valid?"}
    CacheCheck -->|"Yes"| ReturnCache["Return Cached Exam Snapshot (under 200ms)"]
    
    CacheCheck -->|"No"| Pool["Fetch Candidate Question Pool"]
    Pool --> Dedupe["7-Tier Deduplication Pipeline"]
    
    subgraph DedupePipeline["Deduplication Engine (dedupe.py)"]
        D1["Tier 1: Exact Question ID Check"]
        D2["Tier 2: Normalized Text Hash (SHA-256)"]
        D3["Tier 3: Near-Duplicate 3-Shingles and Jaccard Similarity (0.85+)"]
        D4["Tier 4: Same-Concept Topic and Option Overlap (75%+)"]
        D5["Tier 5: Intra-Question Duplicate Options Check"]
        D6["Tier 6: Cross-Paper Repeat Avoidance (Last 30 Days)"]
        D1 --> D2 --> D3 --> D4 --> D5 --> D6
    end
    
    Dedupe --> Balance["Constraint Balancer (Difficulty and Types)"]
    Balance --> Validate["Validation Pipeline (validator.py)"]
    
    subgraph ValidationPipeline["Validation Pipeline"]
        V1["Exact Marks Check (Decimal Precision)"]
        V2["Question Count Match per Section"]
        V3["Difficulty Distribution Tolerance"]
        V4["Negative Marks Guard (0 to marks range)"]
        V5["Estimated Time vs Duration Ratio"]
    end
    
    Validate --> Persist["Transactional Database Save"]
    Persist --> CacheStore["Store in Tenant Cache"]
    CacheStore --> Final["Return Exam Detail and ValidationReport"]
```

---

## 5. Database Entity Relationship (ER) Model

```mermaid
erDiagram
    AdminInstitution ||--o{ AdminDepartment : "contains"
    AdminInstitution ||--o{ AdminProfile : "managed_by"
    AdminInstitution ||--o{ FacultyProfile : "employs"
    AdminInstitution ||--o{ StudentProfile : "enrolls"
    AdminInstitution ||--o{ Subject : "offers"
    AdminInstitution ||--o{ Exam : "administers"
    AdminInstitution ||--o{ Question : "owns"
    
    User ||--o| AdminProfile : "has"
    User ||--o| FacultyProfile : "has"
    User ||--o| StudentProfile : "has"
    
    Subject ||--o{ Topic : "contains"
    Subject ||--o{ Question : "categorizes"
    Topic ||--o{ Question : "groups"
    
    Question ||--o{ Option : "has"
    Question ||--o{ QuestionAuditLog : "audits"
    
    Exam ||--o{ Question : "includes"
    Exam ||--o{ StudentAttempt : "taken_in"
    
    StudentAttempt ||--o{ StudentAnswer : "records"
    Question ||--o{ StudentAnswer : "answers"
```
