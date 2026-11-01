import csv
import os
import random
import uuid
from datetime import timedelta
from typing import Dict, List, Tuple

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from admins.models import AdminDepartment, AdminInstitution, AdminProfile
from api.models import (
    AttemptEvent,
    EvaluationChangeAuditLog,
    Exam,
    Option,
    Question,
    QuestionAuditLog,
    StudentAnswer,
    StudentAttempt,
    Subject,
    Topic,
)
from faculty.models import FacultyProfile
from students.models import StudentProfile


DEFAULT_PASSWORD = "DevSeed@2026!"

STANDARD_DEPARTMENTS = [
    "Computer Science",
    "Information Technology",
    "Electronics and Communication",
    "Mechanical Engineering",
    "Civil Engineering",
    "Electrical Engineering",
    "Artificial Intelligence and Data Science",
    "Management",
]

FIRST_NAMES = [
    "Aarav", "Aditi", "Akhil", "Ananya", "Aniket", "Ankita", "Arjun", "Bhavya",
    "Chirag", "Deepak", "Divya", "Gaurav", "Harini", "Ishaan", "Kavya", "Madhav",
    "Manish", "Meera", "Neha", "Nikhil", "Pooja", "Pranav", "Priya", "Rahul",
    "Rhea", "Rohan", "Sanjay", "Shreya", "Siddharth", "Sneha", "Tanvi", "Varun",
    "Vikram", "Yash", "Zoya", "Alok", "Devika", "Karthik", "Lavanya", "Naveen",
    "Pallavi", "Rajesh", "Sandhya", "Tarun", "Vidya", "Abhishek", "Geeta", "Mohit"
]

LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Joshi", "Mehta", "Rathore", "Chauhan", "Rajput",
    "Iyer", "Nair", "Murthy", "Rao", "Reddy", "Venkatesh", "Krishnan", "Gowda",
    "Das", "Banerjee", "Mukherjee", "Saikia", "Borah", "Barman", "Roy", "Bose",
    "Mishra", "Tiwari", "Dubey", "Shukla", "Tripathi", "Pandey", "Saxena", "Bhat"
]

FACULTY_DESIGNATIONS = [
    "Assistant Professor",
    "Associate Professor",
    "Professor",
    "Head of Department",
]

# Curated domain knowledge banks with questions summing to EXACTLY 50 marks (4*2 + 2*2 + 2*3 + 12 + 20 = 50)
DOMAIN_CURRICULUM = {
    "Computer Science": {
        "code": "CS-301",
        "subject": "Operating Systems & Concurrency",
        "topics": ["Process Synchronization", "Virtual Memory", "CPU Scheduling", "Deadlock Prevention"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which algorithm is provably optimal for CPU scheduling by minimizing average turnaround time?",
                "options": ["First-Come, First-Served (FCFS)", "Round Robin (RR)", "Shortest Job First (SJF)", "Priority Scheduling"],
                "correct": "Shortest Job First (SJF)",
                "explanation": "Shortest Job First (SJF) gives the minimum average waiting time for a given set of processes.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "What synchronization primitive uses atomic test-and-set operations to prevent race conditions?",
                "options": ["Spinlock / Mutex", "Virtual Buffer", "Context Switcher", "Memory MMU"],
                "correct": "Spinlock / Mutex",
                "explanation": "A mutex or spinlock ensures mutual exclusion using underlying hardware atomic instructions.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "Belady's Anomaly occurs in which page replacement algorithm?",
                "options": ["Optimal (OPT)", "Least Recently Used (LRU)", "First-In, First-Out (FIFO)", "Clock Algorithm"],
                "correct": "First-In, First-Out (FIFO)",
                "explanation": "FIFO page replacement can exhibit Belady's Anomaly where allocating more page frames increases page faults.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which condition is NOT required for a deadlock state to occur (Coffman conditions)?",
                "options": ["Mutual Exclusion", "Hold and Wait", "Preemption of Resources", "Circular Wait"],
                "correct": "Preemption of Resources",
                "explanation": "No preemption is the required condition; allowing preemption prevents deadlock.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "A user-level thread context switch requires a trap into kernel space.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "User-level threads are managed entirely in user space by runtime libraries without kernel intervention.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "The Translation Lookaside Buffer (TLB) acts as a hardware cache for virtual-to-physical address mappings.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "The TLB is a fast associative cache inside the MMU that stores recent page table translations.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The memory management technique that eliminates external fragmentation by allocating fixed-size blocks is called ________.",
                "options": [],
                "accepted_answers": ["paging", "Paging", "page allocation"],
                "correct": "paging",
                "explanation": "Paging divides logical memory into fixed pages and physical memory into frames, eliminating external fragmentation.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The system call used in Unix-like kernels to duplicate an existing calling process is ________.",
                "options": [],
                "accepted_answers": ["fork", "fork()", "clone"],
                "correct": "fork()",
                "explanation": "fork() creates an exact duplicate of the parent process with its own address space.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Explain Dijkstra's Banker's Algorithm. Describe the data structures required and how safety is determined.",
                "options": [],
                "correct": "The Banker's Algorithm ensures safe resource allocation by maintaining Available, Max, Allocation, and Need matrices. A state is safe if there exists an execution sequence allowing all processes to finish without deadlock.",
                "rubric": [
                    {"criterion": "Data Structures Defined (Available, Max, Allocation, Need)", "marks": 4.0},
                    {"criterion": "Safety Verification Algorithm Step", "marks": 5.0},
                    {"criterion": "Resource Request Handling & Rollback", "marks": 3.0},
                ],
                "model_answer": "Banker's Algorithm tests for safety by simulating maximum resource allocation: 1. Need = Max - Allocation. 2. Find process P_i such that Need_i <= Work. 3. Work = Work + Allocation_i. If all processes complete, state is safe.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Analyze the Readers-Writers problem with starvation-free priority. Provide pseudocode using semaphores and evaluate concurrency tradeoffs.",
                "options": [],
                "correct": "Readers-writers solution requires a mutex for reader count and a binary semaphore for resource access. Fair solution introduces a turnstile semaphore so writers are not starved by a continuous stream of readers.",
                "rubric": [
                    {"criterion": "Problem Formulation & Race Condition Analysis", "marks": 5.0},
                    {"criterion": "Semaphore-based Starvation-Free Pseudocode", "marks": 8.0},
                    {"criterion": "Correctness Proof & Invariants", "marks": 4.0},
                    {"criterion": "Concurrency vs Throughput Tradeoffs", "marks": 3.0},
                ],
                "model_answer": "Detailed implementation using read_switch, write_switch, and turnstile semaphore to ensure neither readers nor writers experience starvation under high concurrent load.",
            },
        ],
    },
    "Information Technology": {
        "code": "IT-302",
        "subject": "Cloud Computing & Distributed Architecture",
        "topics": ["Microservices", "Consensus Algorithms", "Cloud Security", "CAP Theorem"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "According to Eric Brewer's CAP theorem, what two guarantees can a distributed network choose in the presence of network partitions?",
                "options": ["Consistency or Availability", "Scalability or Durability", "Fault-tolerance or Latency", "Atomicity or Isolation"],
                "correct": "Consistency or Availability",
                "explanation": "When partition tolerance (P) is inevitable in real networks, the system must trade off between Consistency (C) and Availability (A).",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which consensus algorithm is specifically designed to be more understandable than Paxos while maintaining equivalent safety?",
                "options": ["Raft", "Two-Phase Commit (2PC)", "Chubby", "Gossip Protocol"],
                "correct": "Raft",
                "explanation": "Raft decomposes consensus into leader election, log replication, and safety to improve understandability.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which cloud computing deployment model allows dynamic resource autoscaling charged strictly on invocation duration?",
                "options": ["Serverless (FaaS)", "Bare Metal IaaS", "Monolithic PaaS", "Private Cloud SaaS"],
                "correct": "Serverless (FaaS)",
                "explanation": "Function-as-a-Service (FaaS) charges per execution duration and event trigger, scaling to zero when idle.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "What design pattern decouples microservice communications through an asynchronous durable message log?",
                "options": ["Event-Driven Architecture", "Remote Procedure Call (RPC)", "Shared Database Pattern", "Monolithic Facade"],
                "correct": "Event-Driven Architecture",
                "explanation": "Event-driven architecture with brokers like Kafka allows asynchronous, loosely-coupled microservice collaboration.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "In distributed transactions, the Saga pattern relies on compensating transactions rather than distributed locking.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "Sagas split distributed transactions into local transactions, applying compensating actions if a step fails.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "Horizontal scaling refers to adding more CPU and RAM to a single existing virtual machine.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "Adding resources to an existing machine is vertical scaling; horizontal scaling adds more nodes/instances.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The pattern that prevents cascading failures in microservices by failing fast when downstream services become unresponsive is the ________ pattern.",
                "options": [],
                "accepted_answers": ["Circuit Breaker", "circuit breaker", "Circuit-Breaker"],
                "correct": "Circuit Breaker",
                "explanation": "A circuit breaker trips open after a threshold of failures, returning immediate fallback responses.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "In microservices observability, the three core telemetry pillars are metrics, traces, and ________.",
                "options": [],
                "accepted_answers": ["logs", "logging", "Logs"],
                "correct": "logs",
                "explanation": "Observability relies on the three pillars: metrics, distributed traces, and structured logs.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Contrast Two-Phase Commit (2PC) with Raft consensus. Explain why 2PC is considered a blocking protocol.",
                "options": [],
                "correct": "2PC requires all participants to vote and commit synchronously; if the coordinator fails during commit phase, participants remain blocked holding locks. Raft uses quorum consensus and dynamic leader election, remaining non-blocking as long as a majority is alive.",
                "rubric": [
                    {"criterion": "2PC Phase 1 & 2 Execution Mechanics", "marks": 4.0},
                    {"criterion": "Coordinator Failure & Blocking Vulnerability", "marks": 4.0},
                    {"criterion": "Raft Quorum & Non-blocking Safety Comparison", "marks": 4.0},
                ],
                "model_answer": "In 2PC, coordinator failure leaves cohorts in doubt holding shared locks. Raft handles leader crash via randomized election timers and majority log validation.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Design a globally distributed multi-region e-commerce checkout architecture. Address data consistency, idempotency, edge caching, and failover.",
                "options": [],
                "correct": "Architecture uses Route53 latency routing, API Gateway, stateless auth via JWT, DynamoDB Global Tables or Spanner for strong transactional consistency, idempotency keys in Redis, and Kafka for inventory reconciliation.",
                "rubric": [
                    {"criterion": "Multi-Region Topology & Edge Routing", "marks": 5.0},
                    {"criterion": "Data Consistency & Idempotent Payment Flow", "marks": 6.0},
                    {"criterion": "Inventory Reservation & Eventual Reconciliation", "marks": 5.0},
                    {"criterion": "Disaster Recovery & Regional Failover Strategy", "marks": 4.0},
                ],
                "model_answer": "Comprehensive architecture diagram and specification describing active-active multi-region deployment with idempotency headers, token bucket rate limiters, and distributed saga coordination.",
            },
        ],
    },
    "Electronics and Communication": {
        "code": "EC-303",
        "subject": "Digital Signal Processing & Microelectronics",
        "topics": ["Fast Fourier Transform", "Digital Filter Design", "Z-Transforms", "Sampling"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "The Nyquist-Shannon sampling theorem states that the minimum sampling rate must be at least:",
                "options": ["Twice the maximum signal frequency", "Equal to the maximum frequency", "Four times the carrier frequency", "Half the highest frequency component"],
                "correct": "Twice the maximum signal frequency",
                "explanation": "Fs >= 2 * Fmax is necessary to avoid spectral aliasing.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "What is the computational complexity of an N-point Cooley-Tukey Radix-2 FFT algorithm?",
                "options": ["O(N log2 N)", "O(N^2)", "O(N)", "O(log2 N)"],
                "correct": "O(N log2 N)",
                "explanation": "FFT reduces the naive DFT complexity from O(N^2) to O(N log2 N).",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which filter type is inherently stable because all of its poles reside strictly at the origin?",
                "options": ["Finite Impulse Response (FIR)", "Infinite Impulse Response (IIR)", "Butterworth Filter", "Chebyshev Filter"],
                "correct": "Finite Impulse Response (FIR)",
                "explanation": "FIR filters only have zeros in the finite z-plane, making them unconditionally stable.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "What transformation maps the continuous s-plane imaginary axis onto the unit circle of the discrete z-plane without aliasing?",
                "options": ["Bilinear Transformation", "Impulse Invariance Method", "Euler Approximation", "Direct Fourier Mapping"],
                "correct": "Bilinear Transformation",
                "explanation": "The bilinear transform uses a conformal mapping that wraps the entire jw axis onto the discrete unit circle.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "Linear phase response in an FIR filter ensures that all frequency components experience the same constant time delay.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "Linear phase gives constant group delay, preventing signal dispersion and phase distortion.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "The region of convergence (ROC) of a stable discrete-time LTI system's Z-transform must include the unit circle.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "An LTI system is bounded-input bounded-output (BIBO) stable if and only if its ROC includes |z| = 1.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The frequency domain distortion caused by mapping continuous frequencies in bilinear transformation is called frequency ________.",
                "options": [],
                "accepted_answers": ["warping", "Warping"],
                "correct": "warping",
                "explanation": "Frequency warping is the non-linear compression of high analog frequencies into the discrete domain, corrected by pre-warping.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The twiddle factor in radix-2 FFT algorithms is represented mathematically as W_N = e^(-j*2*pi/________).",
                "options": [],
                "accepted_answers": ["N", "n"],
                "correct": "N",
                "explanation": "Twiddle factor W_N = e^(-j 2pi / N) represents roots of unity.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Compare FIR and IIR digital filters across stability, phase linearity, computational complexity, and order.",
                "options": [],
                "correct": "FIR filters provide exact linear phase and unconditional stability, but require higher filter orders. IIR filters achieve sharper transition bands with lower orders, but can become unstable and exhibit non-linear phase distortion.",
                "rubric": [
                    {"criterion": "Stability & Pole-Zero Location", "marks": 3.0},
                    {"criterion": "Phase Linearity & Group Delay", "marks": 3.0},
                    {"criterion": "Hardware Complexity & Order Efficiency", "marks": 3.0},
                    {"criterion": "Quantization & Limit Cycles Sensitivity", "marks": 3.0},
                ],
                "model_answer": "FIR filters have zeros only, guaranteed linear phase with symmetric coefficients. IIR filters require feedback loops, risk limit cycle oscillations under finite word length.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Derive the Decimation-in-Time (DIT) Radix-2 FFT algorithm from the standard DFT definition. Draw the complete 8-point butterfly signal flow graph.",
                "options": [],
                "correct": "DIT decomposes an N-point DFT into two N/2-point DFTs (even and odd indices). By periodicity and symmetry of twiddle factors, computational operations drop from N^2 to (N/2) log2(N) complex multiplications.",
                "rubric": [
                    {"criterion": "Mathematical Derivation (Even/Odd Splitting)", "marks": 6.0},
                    {"criterion": "Twiddle Factor Symmetry & Periodicity Proof", "marks": 4.0},
                    {"criterion": "8-Point Butterfly Diagram & Bit-Reversal Order", "marks": 6.0},
                    {"criterion": "Computational Complexity & Speedup Proof", "marks": 4.0},
                ],
                "model_answer": "Step-by-step mathematical decomposition of X[k] = G[k] + W_N^k H[k], including bit-reversal input sorting table and stage-by-stage butterfly computations.",
            },
        ],
    },
    "Mechanical Engineering": {
        "code": "ME-305",
        "subject": "Thermodynamics & Thermal Power Engineering",
        "topics": ["Carnot Efficiency", "Rankine Cycle", "Heat Exchangers", "Fluid Mechanics"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "The maximum theoretical thermal efficiency of a heat engine operating between temperatures TH and TL is given by:",
                "options": ["1 - (TL / TH)", "(TH - TL) / TL", "1 - (TH / TL)", "TL / (TH + TL)"],
                "correct": "1 - (TL / TH)",
                "explanation": "Carnot efficiency eta = 1 - (TL / TH), where temperatures are expressed in Kelvin.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "In an ideal Rankine cycle with superheat, which component causes the greatest increase in cycle efficiency?",
                "options": ["Boiler superheater / Reheater", "Condenser cooling tower", "Feedwater pump", "Turbine exhaust diffuser"],
                "correct": "Boiler superheater / Reheater",
                "explanation": "Superheating raises the mean temperature of heat addition, increasing thermal efficiency and preventing moisture in turbine blades.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which dimensionless number represents the ratio of inertial forces to viscous forces in fluid flow?",
                "options": ["Reynolds number (Re)", "Prandtl number (Pr)", "Nusselt number (Nu)", "Grashof number (Gr)"],
                "correct": "Reynolds number (Re)",
                "explanation": "Reynolds number Re = rho * v * L / mu governs laminar versus turbulent transition.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "Fourier's law of heat conduction states that heat flux is directly proportional to:",
                "options": ["Negative temperature gradient", "Specific heat capacity", "Square of temperature difference", "Thermal diffusivity"],
                "correct": "Negative temperature gradient",
                "explanation": "q = -k * dT/dx, where the negative sign indicates heat flows from higher to lower temperature.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "Entropy of an isolated system can decrease during a spontaneous irreversible process.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "The Second Law of Thermodynamics dictates that entropy of an isolated system always increases or remains constant (dS >= 0).",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "In counterflow heat exchangers, the log-mean temperature difference (LMTD) is higher than in parallel flow under identical terminal temperatures.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "Counterflow provides the highest effective temperature driving force, resulting in larger LMTD and smaller required surface area.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The thermodynamic property defined as H = U + PV is known as ________.",
                "options": [],
                "accepted_answers": ["enthalpy", "Enthalpy"],
                "correct": "enthalpy",
                "explanation": "Enthalpy represents the total heat content of a system combining internal energy and flow work.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "A process carried out without any heat transfer between the system and surroundings is termed ________.",
                "options": [],
                "accepted_answers": ["adiabatic", "Adiabatic"],
                "correct": "adiabatic",
                "explanation": "An adiabatic process has Q = 0.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Explain the regenerative Rankine cycle. How does bleeding steam for feedwater heaters improve plant heat rate?",
                "options": [],
                "correct": "Regeneration extracts partially expanded steam from intermediate turbine stages to preheat boiler feedwater. This elevates the mean temperature of heat addition in the boiler, reducing fuel consumption and increasing thermal efficiency.",
                "rubric": [
                    {"criterion": "Thermodynamic Principle & T-s Diagram Description", "marks": 4.0},
                    {"criterion": "Feedwater Heater Operation (Open vs Closed)", "marks": 4.0},
                    {"criterion": "Mean Temperature of Heat Addition & Heat Rate Gain", "marks": 4.0},
                ],
                "model_answer": "Regenerative heating reduces irreversibility associated with mixing subcooled liquid with boiling water. Bleeding 15-20% steam improves net thermal efficiency by 4-8%.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Perform a complete thermodynamic analysis of an air-standard Brayton cycle with intercooling, reheat, and regeneration. Formulate equations for net work and thermal efficiency.",
                "options": [],
                "correct": "Brayton cycle uses two-stage compression with intercooler to minimize compression work, two-stage expansion with combustor reheat to maximize turbine work, and a regenerator to exchange turbine exhaust heat with compressor discharge.",
                "rubric": [
                    {"criterion": "System Schematic & State Points Definition", "marks": 5.0},
                    {"criterion": "P-v and T-s Diagrams with Real Losses", "marks": 5.0},
                    {"criterion": "Mathematical Derivation of Net Specific Work", "marks": 5.0},
                    {"criterion": "Regenerator Effectiveness & Thermal Efficiency Optimization", "marks": 5.0},
                ],
                "model_answer": "Complete energy balance formulation showing optimal pressure ratios rp_opt = sqrt(P_max/P_min) for intercooled and reheated stages, maximizing overall cycle efficiency.",
            },
        ],
    },
    "Civil Engineering": {
        "code": "CE-306",
        "subject": "Structural Design & Geotechnical Engineering",
        "topics": ["Limit State Design", "Soil Mechanics", "Concrete Technology", "Shear Strength"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "In Limit State Design of reinforced concrete (IS 456), the partial safety factor for concrete in flexure is:",
                "options": ["1.50", "1.15", "1.20", "2.00"],
                "correct": "1.50",
                "explanation": "Concrete has gamma_m = 1.50, whereas steel reinforcement uses gamma_m = 1.15 due to stricter factory quality control.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "Terzaghi's effective stress principle states that total stress sigma is the sum of effective stress sigma' and:",
                "options": ["Pore water pressure (u)", "Shear resistance (tau)", "Cohesion intercept (c)", "Overburden bulk density"],
                "correct": "Pore water pressure (u)",
                "explanation": "Total stress sigma = sigma' + u, where pore water pressure transmits hydrostatic force without shear resistance.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which test is standard for determining the workability and consistency of fresh concrete in field conditions?",
                "options": ["Slump Cone Test", "Core Cutter Test", "Vee-Bee Consistometer", "Schmidt Rebound Hammer"],
                "correct": "Slump Cone Test",
                "explanation": "The slump test measures the vertical subsidence of fresh concrete under gravity after removing the mold.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "What type of shear failure typically occurs in very loose sand or soft clay soils under shallow foundations?",
                "options": ["Punching Shear Failure", "General Shear Failure", "Local Shear Failure", "Rotational Slip"],
                "correct": "Punching Shear Failure",
                "explanation": "Punching shear is characterized by vertical soil compression under the footing without visible surface bulging.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "Under-reinforced concrete beams fail abruptly in a brittle manner without warning cracks.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "Under-reinforced beams experience tension steel yielding first, providing ductile deflection and visible warning before failure.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "Primary consolidation settlement in saturated clays is governed by the dissipation of excess pore water pressure.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "Consolidation occurs as excess pore water drains over time under sustained vertical load.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The ratio of volume of voids to total volume of a soil mass is termed its ________.",
                "options": [],
                "accepted_answers": ["porosity", "Porosity"],
                "correct": "porosity",
                "explanation": "Porosity n = Vv / V, expressed as a fraction or percentage.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The maximum permissible strain in concrete under axial compression at collapse is ________.",
                "options": [],
                "accepted_answers": ["0.002", "0.0020"],
                "correct": "0.002",
                "explanation": "Under direct axial compression, IS 456 specifies maximum strain of 0.002.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Explain Mohr-Coulomb shear strength criterion for soils. Distinguish between total and effective stress parameters.",
                "options": [],
                "correct": "Mohr-Coulomb failure envelope is tau = c' + sigma' tan(phi'). In effective stress terms, shear strength depends directly on inter-granular contact stress rather than total overburden pressure.",
                "rubric": [
                    {"criterion": "Failure Envelope Formulation (c, phi parameters)", "marks": 4.0},
                    {"criterion": "Effective Stress vs Pore Pressure Influence", "marks": 4.0},
                    {"criterion": "Drained vs Undrained Shear Response", "marks": 4.0},
                ],
                "model_answer": "In consolidated drained tests, cohesive soils exhibit true friction angle phi'. Under undrained conditions, excess pore pressure builds up, reducing available shear resistance.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Design a singly reinforced rectangular concrete beam section for factored moment Mu. Formulate depth of neutral axis, steel area, and shear check.",
                "options": [],
                "correct": "Calculation involves limiting neutral axis xu_max/d, limiting moment capacity Mu_lim = 0.36 fck b d^2 (xu_max/d)(1 - 0.42 xu_max/d), calculating required Ast, and providing vertical stirrups for nominal shear stress tv exceeding concrete shear strength tc.",
                "rubric": [
                    {"criterion": "Stress-Strain Block Parameters & Equilibrium Equations", "marks": 5.0},
                    {"criterion": "Neutral Axis Depth & Balanced Section Capacity", "marks": 5.0},
                    {"criterion": "Tensile Steel Reinforcement Formulation (Ast)", "marks": 5.0},
                    {"criterion": "Shear Stress Verification & Stirrups Design", "marks": 5.0},
                ],
                "model_answer": "Step-by-step mathematical design procedure verifying ductility requirements, minimum steel percentage, and deflection control limits per national structural concrete codes.",
            },
        ],
    },
    "Electrical Engineering": {
        "code": "EE-304",
        "subject": "Power Systems & Control Engineering",
        "topics": ["Transmission Lines", "Power Flow", "Stability Analysis", "Feedback Control"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which bus type in a power flow study has specified active power P and voltage magnitude |V|?",
                "options": ["Generator (PV) Bus", "Load (PQ) Bus", "Slack / Swing Bus", "Infinite Bus"],
                "correct": "Generator (PV) Bus",
                "explanation": "PV buses are generation stations where active power output and terminal voltage magnitude are regulated.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "The Ferranti effect in long transmission lines under light load conditions causes:",
                "options": ["Receiving-end voltage higher than sending-end voltage", "Large inductive reactive losses", "Corona discharge at sending substation", "Frequency drop below nominal rating"],
                "correct": "Receiving-end voltage higher than sending-end voltage",
                "explanation": "Line charging capacitance draws leading current through line inductance, causing voltage rise at the receiving end.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "The Routh-Hurwitz criterion determines system stability by inspecting:",
                "options": ["Sign changes in the first column of the Routh array", "Phase angle margin at unity gain", "Eigenvalues of the state transition matrix", "Damping ratio of complex conjugate zeros"],
                "correct": "Sign changes in the first column of the Routh array",
                "explanation": "The number of sign changes in the first column equals the number of closed-loop poles in the right-half s-plane.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which symmetrical component network has currents flowing only when a neutral ground connection is present?",
                "options": ["Zero-sequence Network", "Positive-sequence Network", "Negative-sequence Network", "Harmonic Sequence Network"],
                "correct": "Zero-sequence Network",
                "explanation": "Zero-sequence currents are in-phase and require a physical ground/neutral return path to flow.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "Adding an integrator (pole at origin) in a control loop increases the system type and reduces steady-state tracking error.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "An integrator provides infinite DC open-loop gain, driving steady-state error to zero for step inputs.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "Equal Area Criterion is applicable to multi-machine transient stability analysis without simplification.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "Equal Area Criterion is strictly applicable to Single Machine Infinite Bus (SMIB) systems or two-machine equivalents.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The maximum power transferable across a lossless transmission line connecting two buses of voltage V1 and V2 with reactance X is P_max = (V1 * V2) / ________.",
                "options": [],
                "accepted_answers": ["X", "x"],
                "correct": "X",
                "explanation": "Active power transfer equation P = (V1*V2/X) * sin(delta), reaching maximum when delta = 90 degrees.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The root locus branches originate at open-loop poles and terminate at open-loop ________.",
                "options": [],
                "accepted_answers": ["zeros", "Zeros"],
                "correct": "zeros",
                "explanation": "Root locus trajectories begin at open-loop poles (K=0) and terminate at finite open-loop zeros or infinity as K approaches infinity.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Derive the swing equation for a synchronous generator connected to a grid. Explain the physical significance of the inertia constant H.",
                "options": [],
                "correct": "The swing equation (2H/omega_s) * d^2(delta)/dt^2 = Pm - Pe governs generator rotor angle dynamics. The inertia constant H represents stored kinetic energy in megajoules per MVA rating at synchronous speed.",
                "rubric": [
                    {"criterion": "Rotor Dynamic Balance & Torque Derivation", "marks": 4.0},
                    {"criterion": "Inertia Constant H Definition & Units", "marks": 4.0},
                    {"criterion": "Damping Term & Electrical Power Angle Formulation", "marks": 4.0},
                ],
                "model_answer": "Rotor mechanical equation J*alpha = Tm - Te converted into per-unit system yields (2H/omega_0)*d^2(delta)/dt^2 = Pm - Pe, essential for transient stability assessment.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Explain the Newton-Raphson power flow method in polar coordinates. Formulate the Jacobian matrix and describe the iterative algorithm.",
                "options": [],
                "correct": "Newton-Raphson solves non-linear power mismatch equations delta_P and delta_Q using Taylor series linearization. The Jacobian consists of submatrices J11 (dP/ddelta), J12 (dP/d|V|), J21 (dQ/ddelta), and J22 (dQ/d|V|). It exhibits quadratic convergence near the solution.",
                "rubric": [
                    {"criterion": "Power Flow Problem Statement & Mismatch Equations", "marks": 5.0},
                    {"criterion": "Jacobian Submatrices Structure & Partial Derivatives", "marks": 6.0},
                    {"criterion": "Step-by-Step Algorithm & Convergence Criterion", "marks": 5.0},
                    {"criterion": "Comparison with Gauss-Seidel Method (Speed & Scalability)", "marks": 4.0},
                ],
                "model_answer": "Complete polar formulation including bus classifications, mismatch vector formulation, Jacobian building algorithms, and LU decomposition solution at each iteration.",
            },
        ],
    },
    "Artificial Intelligence and Data Science": {
        "code": "AI-307",
        "subject": "Deep Learning & Generative AI Systems",
        "topics": ["Transformers", "Backpropagation", "Loss Functions", "Reinforcement Learning"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "What self-attention mechanism scales the dot product by sqrt(d_k) to prevent vanishing gradients in softmax?",
                "options": ["Scaled Dot-Product Attention", "Additive Bahdanau Attention", "Multi-Head Linear Pooling", "Cross-Entropy Alignment"],
                "correct": "Scaled Dot-Product Attention",
                "explanation": "Scaling by 1/sqrt(d_k) keeps the dot product variance constant, avoiding very small gradients in the softmax tails.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which regularization technique randomly drops connections between neural network layers during training?",
                "options": ["Dropout", "Batch Normalization", "Weight Decay (L2)", "Gradient Clipping"],
                "correct": "Dropout",
                "explanation": "Dropout prevents co-adaptation of features by zeroing out activations with probability p during forward propagation.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "What loss function is standard for training multi-class classification neural networks?",
                "options": ["Categorical Cross-Entropy", "Mean Squared Error (MSE)", "Huber Loss", "Hinge Loss"],
                "correct": "Categorical Cross-Entropy",
                "explanation": "Categorical cross-entropy measures divergence between predicted softmax distribution and one-hot ground truth.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which optimizer combines momentum with adaptive learning rates per parameter based on running root-mean-square gradients?",
                "options": ["Adam", "Stochastic Gradient Descent (SGD)", "Adagrad", "Nesterov Accelerated Gradient"],
                "correct": "Adam",
                "explanation": "Adam maintains exponential moving averages of both past gradients (first moment) and squared gradients (second moment).",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "The Vanishing Gradient problem in deep networks is exacerbated by using ReLU activation functions.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "ReLU has a constant derivative of 1 for positive inputs, which largely overcomes the vanishing gradient issue seen in sigmoid/tanh.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "In Transformer architectures, positional encodings are required because self-attention is permutation-invariant.",
                "options": ["True", "False"],
                "correct": "True",
                "explanation": "Without positional encodings, the attention operator cannot distinguish token ordering in a sequence.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "The alignment technique that uses human preference rankings to fine-tune large language models is called RLHF, which stands for Reinforcement Learning from Human ________.",
                "options": [],
                "accepted_answers": ["Feedback", "feedback"],
                "correct": "Feedback",
                "explanation": "RLHF trains a reward model on human preferences and optimizes policy via PPO.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "In autoencoders and latent diffusion models, the information bottleneck where data is compressed is called the ________ space.",
                "options": [],
                "accepted_answers": ["latent", "Latent"],
                "correct": "latent",
                "explanation": "The latent space captures low-dimensional manifold representations of high-dimensional inputs.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Explain Multi-Head Attention in Transformers. Provide the mathematical formulation for Attention(Q, K, V).",
                "options": [],
                "correct": "Attention(Q, K, V) = softmax(Q K^T / sqrt(d_k)) V. Multi-Head Attention projects Queries, Keys, and Values h times with distinct learned linear projections, computes attention in parallel, concatenates outputs, and projects with W_O.",
                "rubric": [
                    {"criterion": "Attention Formula & Scaling Factor Justification", "marks": 4.0},
                    {"criterion": "Multi-Head Linear Projections & Concatenation", "marks": 4.0},
                    {"criterion": "Subspace Representation & Expressivity Benefit", "marks": 4.0},
                ],
                "model_answer": "Multi-head attention allows the model to jointly attend to information from different representation subspaces at different positions, which single-head attention averages out.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Formulate the Backpropagation algorithm for a multi-layer perceptron with cross-entropy loss. Derive weight gradients for hidden-to-output and input-to-hidden layers using the chain rule.",
                "options": [],
                "correct": "Derivation uses the chain rule to propagate error delta_j = dL/dz_j backwards. Output layer delta_k = y_hat_k - y_k for softmax with cross-entropy. Hidden layer delta_j = (sum_k delta_k W_kj) * sigma'(z_j). Weight gradient dL/dW_ij = a_i delta_j.",
                "rubric": [
                    {"criterion": "Forward Pass & Loss Function Definition", "marks": 4.0},
                    {"criterion": "Output Layer Error Derivative (Softmax + Cross-Entropy)", "marks": 6.0},
                    {"criterion": "Hidden Layer Error Propagation & Activation Derivation", "marks": 6.0},
                    {"criterion": "Gradient Descent Weight Update Formulation", "marks": 4.0},
                ],
                "model_answer": "Rigorous vector calculus derivation showing step-by-step application of Jacobian matrices, error propagation deltas, and gradient descent update rules.",
            },
        ],
    },
    "Management": {
        "code": "MG-308",
        "subject": "Corporate Finance & Strategic Management",
        "topics": ["Capital Budgeting", "DCF Valuation", "Porter's Five Forces", "Working Capital"],
        "questions": [
            {
                "order": 1,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which capital budgeting metric reflects the discount rate at which an investment's Net Present Value (NPV) equals zero?",
                "options": ["Internal Rate of Return (IRR)", "Profitability Index", "Payback Period", "Return on Equity (ROE)"],
                "correct": "Internal Rate of Return (IRR)",
                "explanation": "IRR is the break-even discount rate where discounted cash inflows equal initial cash outlay.",
            },
            {
                "order": 2,
                "type": "mcq",
                "marks": 2.0,
                "text": "In Michael Porter's Five Forces framework, which force assesses the ease with which customers can switch to rivals?",
                "options": ["Bargaining Power of Buyers", "Threat of New Entrants", "Bargaining Power of Suppliers", "Barrier to Exit"],
                "correct": "Bargaining Power of Buyers",
                "explanation": "Buyer power is high when customers have low switching costs and access to many alternatives.",
            },
            {
                "order": 3,
                "type": "mcq",
                "marks": 2.0,
                "text": "The Weighted Average Cost of Capital (WACC) incorporates tax shielding because:",
                "options": ["Interest expense on debt is tax-deductible", "Dividends paid on equity are exempt from corporate tax", "Depreciation is a non-cash expense", "Capital gains taxes apply to retained earnings"],
                "correct": "Interest expense on debt is tax-deductible",
                "explanation": "The effective after-tax cost of debt is Kd * (1 - T), reducing WACC.",
            },
            {
                "order": 4,
                "type": "mcq",
                "marks": 2.0,
                "text": "Which financial ratio measures a company's ability to cover short-term liabilities using its most liquid quick assets?",
                "options": ["Quick / Acid-Test Ratio", "Current Ratio", "Debt-to-Equity Ratio", "Inventory Turnover"],
                "correct": "Quick / Acid-Test Ratio",
                "explanation": "Quick Ratio = (Cash + Marketable Securities + Receivables) / Current Liabilities, excluding illiquid inventory.",
            },
            {
                "order": 5,
                "type": "true_false",
                "marks": 2.0,
                "text": "When choosing between mutually exclusive projects with different scales, NPV and IRR always yield identical rankings.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "IRR assumes reinvestment at the IRR itself and ignores project scale, creating conflicts with NPV which is the superior metric.",
            },
            {
                "order": 6,
                "type": "true_false",
                "marks": 2.0,
                "text": "A blue ocean strategy focuses on competing in overcrowded existing market spaces by out-pricing rivals.",
                "options": ["True", "False"],
                "correct": "False",
                "explanation": "Blue ocean strategy seeks to create uncontested market space and render competition irrelevant; competing in existing crowded space is red ocean.",
            },
            {
                "order": 7,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "Net Working Capital is defined as Current Assets minus Current ________.",
                "options": [],
                "accepted_answers": ["Liabilities", "liabilities"],
                "correct": "Liabilities",
                "explanation": "Net Working Capital = Current Assets - Current Liabilities, measuring short-term operating liquidity.",
            },
            {
                "order": 8,
                "type": "fill_blank",
                "marks": 3.0,
                "text": "In portfolio theory, Beta (beta) measures the systematic, non-diversifiable risk of an asset relative to the overall ________.",
                "options": [],
                "accepted_answers": ["market", "Market", "market portfolio"],
                "correct": "market",
                "explanation": "Beta reflects sensitivity to broad market movements that cannot be diversified away.",
            },
            {
                "order": 9,
                "type": "short_answer",
                "marks": 12.0,
                "text": "Explain the Capital Asset Pricing Model (CAPM). State its core formula and define each variable.",
                "options": [],
                "correct": "CAPM formula is E(Ri) = Rf + Beta_i * [E(Rm) - Rf]. It defines the expected return of an asset based on the risk-free rate Rf, asset sensitivity Beta_i, and equity market risk premium [E(Rm) - Rf].",
                "rubric": [
                    {"criterion": "Formula Formulation & Variable Definitions", "marks": 4.0},
                    {"criterion": "Risk-Free Rate & Market Risk Premium Meaning", "marks": 4.0},
                    {"criterion": "Assumptions & Limitations in Corporate Finance", "marks": 4.0},
                ],
                "model_answer": "CAPM establishes linear equilibrium pricing of systematic risk. Key assumptions include frictionless markets, homogeneous expectations, and investor preference for mean-variance efficiency.",
            },
            {
                "order": 10,
                "type": "long_answer",
                "marks": 20.0,
                "text": "Perform a Discounted Cash Flow (DCF) valuation of an enterprise. Detail Free Cash Flow to Firm (FCFF) calculation, terminal value estimation via Gordon Growth Model, and enterprise-to-equity bridge.",
                "options": [],
                "correct": "FCFF = EBIT * (1 - T) + D&A - Capex - Change in NWC. Discounted at WACC. Terminal Value = [FCFF_(n+1)] / (WACC - g). Enterprise Value = PV(discrete FCFF) + PV(Terminal Value). Equity Value = Enterprise Value - Net Debt.",
                "rubric": [
                    {"criterion": "FCFF Derivation from Operating Income", "marks": 5.0},
                    {"criterion": "WACC Cost of Capital Formulation", "marks": 5.0},
                    {"criterion": "Terminal Value & Sustainable Growth Rate (g)", "marks": 5.0},
                    {"criterion": "Enterprise to Equity Bridge (Debt, Cash, Non-operating Assets)", "marks": 5.0},
                ],
                "model_answer": "Comprehensive valuation model showing multi-stage cash flow forecasting, sensitivity table on WACC and terminal growth rates, and share price calculation.",
            },
        ],
    },
}

# Domain mapping for generic or science departments
DOMAIN_FALLBACK = {
    "Business Administration": "Management",
    "Commerce": "Management",
    "Physics": "Electrical Engineering",
    "Chemistry": "Civil Engineering",
    "Mathematics": "Computer Science",
}


class Command(BaseCommand):
    help = "Populate every remaining institute and every department with realistic fake faculty, students, and exams across all states."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Simulate the seeding process without modifying the database",
        )
        parser.add_argument(
            "--reset-seed",
            action="store_true",
            help="Safely remove ONLY seeded records (is_seed=True or SEED_DEMO_EXAM), leaving all real data intact",
        )
        parser.add_argument(
            "--i-know-this-is-not-prod",
            action="store_true",
            help="Bypass production guard when DEBUG=False",
        )
        parser.add_argument(
            "--dev-password",
            type=str,
            default=DEFAULT_PASSWORD,
            help=f"Shared development password for seeded users (default: {DEFAULT_PASSWORD})",
        )

    def handle(self, *args, **options):
        # 1. Safety Guard
        if not getattr(settings, "DEBUG", False) and not options.get("i_know_this_is_not_prod"):
            raise CommandError(
                "SAFETY GUARD: seed_demo_data cannot run when DEBUG=False without --i-know-this-is-not-prod."
            )

        # 2. Reset Handler
        if options.get("reset_seed"):
            self._handle_reset(options)
            return

        # 3. Main Seeding Execution
        self._handle_seed(options)

    def _handle_reset(self, options):
        self.stdout.write(self.style.WARNING("\n=== RESET SEEDED DEMO DATA ==="))
        with transaction.atomic():
            # Seed exams are those with request_hash='SEED_DEMO_EXAM'
            seed_exams = Exam.objects.filter(request_hash="SEED_DEMO_EXAM")
            exam_count = seed_exams.count()
            seed_exams.delete()

            # Seed user profiles
            seed_stu_users = list(StudentProfile.objects.filter(is_seed=True).values_list("user_id", flat=True))
            seed_fac_users = list(FacultyProfile.objects.filter(is_seed=True).values_list("user_id", flat=True))
            all_users = set(seed_stu_users + seed_fac_users)
            
            # Delete student and faculty users created as seed
            del_users, _ = User.objects.filter(id__in=all_users).delete()

        self.stdout.write(self.style.SUCCESS(
            f"Reset complete. Removed {exam_count} seed exams and {del_users} seed user accounts.\n"
            f"All real accounts, live exams, and submissions remain 100% intact.\n"
        ))

    def _handle_seed(self, options):
        is_dry_run = options.get("dry_run", False)
        dev_password = options.get("dev_password", DEFAULT_PASSWORD)
        rng = random.Random(42)

        self.stdout.write(self.style.NOTICE(
            f"\n=== POPULATING REALISTIC DEMO DATA (ALL INSTITUTES & DEPARTMENTS) ===\n"
            f"Dry Run: {is_dry_run}\n"
            f"Target: All 10 Institutions\n"
        ))

        institutions = AdminInstitution.objects.all().order_by("id")
        self.stdout.write(f"Found {institutions.count()} target institutions.")

        # Ensure credentials file tracking
        cred_file = os.path.join(settings.BASE_DIR, "seed_credentials.csv")
        existing_creds: List[Dict[str, str]] = []
        if os.path.exists(cred_file):
            try:
                with open(cred_file, "r", newline="", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    existing_creds = list(reader)
            except Exception:
                existing_creds = []

        seen_cred_usernames = {row["username"] for row in existing_creds if "username" in row}
        new_creds: List[Dict[str, str]] = []

        total_stats = {
            "institutions_processed": 0,
            "departments_verified": 0,
            "faculty_verified_or_created": 0,
            "students_verified_or_created": 0,
            "exams_created": 0,
            "questions_created": 0,
            "attempts_created": 0,
            "answers_created": 0,
            "audit_logs_created": 0,
            "attempt_events_created": 0,
        }

        for inst in institutions:
            self.stdout.write(self.style.HTTP_INFO(f"\nProcessing Inst ID {inst.id}: {inst.institution_name} ({inst.short_code or 'no-code'})..."))
            total_stats["institutions_processed"] += 1

            # Fix short code if missing
            if not inst.short_code:
                code_map = {
                    2: "gls",
                    3: "gu",
                    4: "ldce",
                    5: "atmiya",
                }
                inst.short_code = code_map.get(inst.id, f"inst{inst.id}")
                if not is_dry_run:
                    inst.save(update_fields=["short_code"])

            # 1. Ensure departments exist
            existing_depts = list(AdminDepartment.objects.filter(institution=inst))
            if not existing_depts:
                # Add standard departments (e.g. for Gujarat Univ and LD College)
                for dept_name in STANDARD_DEPARTMENTS:
                    if not is_dry_run:
                        d, _ = AdminDepartment.objects.get_or_create(institution=inst, department_name=dept_name)
                        existing_depts.append(d)
                self.stdout.write(f"  Created {len(STANDARD_DEPARTMENTS)} standard departments for {inst.institution_name}")

            total_stats["departments_verified"] += len(existing_depts)

            # 2. Iterate each department
            for dept_obj in existing_depts:
                dept_name = dept_obj.department_name
                domain_key = dept_name if dept_name in DOMAIN_CURRICULUM else DOMAIN_FALLBACK.get(dept_name, "Computer Science")
                curriculum = DOMAIN_CURRICULUM[domain_key]

                # A. Ensure Faculty exist for this department (at least 2)
                fac_profiles = list(FacultyProfile.objects.filter(institution=inst, department=dept_name))
                if len(fac_profiles) < 2 and not is_dry_run:
                    needed = 2 - len(fac_profiles)
                    for f_i in range(1, needed + 1):
                        f_first = rng.choice(FIRST_NAMES)
                        f_last = rng.choice(LAST_NAMES)
                        f_user_name = f"{f_first.lower()}.{f_last.lower()}.fac.{inst.short_code}.{dept_obj.id}.{f_i}@example.edu"
                        f_user, u_created = User.objects.get_or_create(
                            username=f_user_name,
                            defaults={"email": f_user_name, "first_name": f_first, "last_name": f_last, "is_active": True}
                        )
                        if u_created:
                            f_user.set_password(dev_password)
                            f_user.save()
                        emp_id = f"F{inst.short_code.upper()[:3]}{dept_obj.id:02d}{f_i:02d}"[:12]
                        fp, _ = FacultyProfile.objects.get_or_create(
                            user=f_user,
                            defaults={
                                "institution": inst,
                                "department": dept_name,
                                "employee_id": emp_id,
                                "designation": rng.choice(FACULTY_DESIGNATIONS),
                                "is_seed": True,
                            }
                        )
                        fac_profiles.append(fp)
                        total_stats["faculty_verified_or_created"] += 1
                        if f_user_name not in seen_cred_usernames:
                            new_creds.append({
                                "institute": inst.institution_name,
                                "role": "faculty",
                                "department": dept_name,
                                "name": f"{f_first} {f_last}",
                                "username": f_user_name,
                                "email": f_user_name,
                                "password": dev_password,
                                "id_number": emp_id,
                            })
                            seen_cred_usernames.add(f_user_name)

                # Pick primary faculty author
                fac_author = fac_profiles[0].user if fac_profiles else inst.admin

                # B. Ensure Students exist for this department (at least 8)
                stu_profiles = list(StudentProfile.objects.filter(institution=inst, department=dept_name))
                if len(stu_profiles) < 8 and not is_dry_run:
                    needed = 8 - len(stu_profiles)
                    for s_i in range(1, needed + 1):
                        s_first = rng.choice(FIRST_NAMES)
                        s_last = rng.choice(LAST_NAMES)
                        s_user_name = f"{s_first.lower()}.{s_last.lower()}.stu.{inst.short_code}.{dept_obj.id}.{s_i}@example.edu"
                        s_user, s_created = User.objects.get_or_create(
                            username=s_user_name,
                            defaults={"email": s_user_name, "first_name": s_first, "last_name": s_last, "is_active": True}
                        )
                        if s_created:
                            s_user.set_password(dev_password)
                            s_user.save()
                        roll_no = f"{inst.short_code.upper()[:4]}-{dept_obj.id:02d}-{s_i:04d}"[:13]
                        sp, _ = StudentProfile.objects.get_or_create(
                            user=s_user,
                            defaults={
                                "institution": inst,
                                "department": dept_name,
                                "student_id": roll_no,
                                "is_seed": True,
                            }
                        )
                        stu_profiles.append(sp)
                        total_stats["students_verified_or_created"] += 1
                        if s_user_name not in seen_cred_usernames:
                            new_creds.append({
                                "institute": inst.institution_name,
                                "role": "student",
                                "department": dept_name,
                                "name": f"{s_first} {s_last}",
                                "username": s_user_name,
                                "email": s_user_name,
                                "password": dev_password,
                                "id_number": roll_no,
                            })
                            seen_cred_usernames.add(s_user_name)

                # C. Subject & Topic
                subj_name = curriculum["subject"]
                subj_code = f"{curriculum['code']}-{inst.short_code.upper()}"
                if not is_dry_run:
                    subject_obj, _ = Subject.objects.get_or_create(
                        institution=inst,
                        department=dept_name,
                        name=subj_name,
                        defaults={"code": subj_code, "created_by": fac_author}
                    )
                    topic_obj, _ = Topic.objects.get_or_create(
                        institution=inst,
                        subject=subject_obj,
                        name=curriculum["topics"][0],
                        defaults={"created_by": fac_author}
                    )
                else:
                    subject_obj = None
                    topic_obj = None

                # D. Create 4 Exams for this Department
                # 1. Past Exam (closed, 14 days ago)
                # 2. Live Exam (published, now)
                # 3. Upcoming Exam (published, +2 days)
                # 4. Draft Exam (draft, +10 days)
                exam_definitions = [
                    {
                        "type": "past",
                        "title": f"{dept_name}: Mid-Term Assessment in {subj_name}",
                        "status": "closed",
                        "starts_at": timezone.now() - timedelta(days=14),
                        "ends_at": timezone.now() - timedelta(days=14, hours=-2),
                        "is_reviewed": True,
                    },
                    {
                        "type": "live",
                        "title": f"{dept_name}: Practical Mid-Semester Session - {subj_name}",
                        "status": "published",
                        "starts_at": timezone.now() - timedelta(minutes=30),
                        "ends_at": timezone.now() + timedelta(minutes=60),
                        "is_reviewed": True,
                    },
                    {
                        "type": "upcoming",
                        "title": f"{dept_name}: Final Comprehensive Examination - {subj_name}",
                        "status": "published",
                        "starts_at": timezone.now() + timedelta(days=2),
                        "ends_at": timezone.now() + timedelta(days=2, hours=3),
                        "is_reviewed": True,
                    },
                    {
                        "type": "draft",
                        "title": f"{dept_name}: Remedial & Advanced Concept Evaluation (Draft)",
                        "status": "draft",
                        "starts_at": timezone.now() + timedelta(days=10),
                        "ends_at": timezone.now() + timedelta(days=10, hours=2),
                        "is_reviewed": False,
                    },
                ]

                for exam_def in exam_definitions:
                    if is_dry_run:
                        total_stats["exams_created"] += 1
                        total_stats["questions_created"] += 10
                        if exam_def["type"] == "past":
                            total_stats["attempts_created"] += 6
                            total_stats["answers_created"] += 60
                            total_stats["audit_logs_created"] += 1
                            total_stats["attempt_events_created"] += 4
                        elif exam_def["type"] == "live":
                            total_stats["attempts_created"] += 2
                            total_stats["answers_created"] += 6
                        continue

                    # Check idempotency: does exam with same title, institution, department exist?
                    exam_obj, created_exam = Exam.objects.get_or_create(
                        institution=inst,
                        department=dept_name,
                        title=exam_def["title"],
                        defaults={
                            "created_by": fac_author,
                            "subject": subj_name,
                            "description": f"Standardized evaluation in {subj_name} covering {', '.join(curriculum['topics'])}.",
                            "duration_minutes": 120 if exam_def["type"] != "live" else 90,
                            "total_marks": 50,
                            "target_total_marks": 50,
                            "marks_shortfall": 0,
                            "topics": curriculum["topics"],
                            "difficulty_distribution": {"easy": 40, "medium": 40, "hard": 20},
                            "question_types": ["mcq", "true_false", "fill_blank", "short_answer", "long_answer"],
                            "status": exam_def["status"],
                            "starts_at": exam_def["starts_at"],
                            "ends_at": exam_def["ends_at"],
                            "is_reviewed": exam_def["is_reviewed"],
                            "is_immutable": exam_def["type"] == "past",
                            "seed": 2026,
                            "request_hash": "SEED_DEMO_EXAM",
                        }
                    )

                    if not created_exam:
                        # Already exists, skip duplicate population
                        continue

                    total_stats["exams_created"] += 1

                    # Populate Questions for this exam
                    created_questions: List[Question] = []
                    for q_spec in curriculum["questions"]:
                        q_obj = Question.objects.create(
                            institution=inst,
                            department=dept_name,
                            subject=subject_obj,
                            topic=topic_obj,
                            topic_text=curriculum["topics"][0],
                            exam=exam_obj,
                            order=q_spec["order"],
                            question_type=q_spec["type"],
                            difficulty="medium" if q_spec["order"] <= 6 else "hard",
                            text=q_spec["text"],
                            explanation=q_spec.get("explanation", ""),
                            marks=q_spec["marks"],
                            negative_marks=0.0,
                            status="active",
                            options=q_spec["options"],
                            correct_answer=q_spec["correct"],
                            accepted_answers=q_spec.get("accepted_answers", []),
                            rubric=q_spec.get("rubric", []),
                            model_answer=q_spec.get("model_answer", ""),
                            created_by=fac_author,
                        )
                        created_questions.append(q_obj)
                        total_stats["questions_created"] += 1

                        # Create Option models for MCQs and T/F
                        if q_spec["options"]:
                            for o_idx, opt_text in enumerate(q_spec["options"]):
                                Option.objects.create(
                                    question=q_obj,
                                    text=opt_text,
                                    is_correct=(opt_text == q_spec["correct"]),
                                    order=o_idx + 1,
                                )

                    # Populate Attempts & Answers based on exam state
                    if exam_def["type"] == "past" and stu_profiles:
                        # 6 student attempts:
                        # Student 0: Top Performer (Grade A+, 47.5/50)
                        # Student 1: High Performer (Grade A, 40.0/50)
                        # Student 2: Average Performer (Grade B, 30.0/50)
                        # Student 3: Average with Override & Audit Record! (31.5/50)
                        # Student 4: Auto-submitted #1, pending subjective grading
                        # Student 5: Auto-submitted #2, pending subjective grading + violation events
                        attempt_configs = [
                            {"stu_idx": 0, "status": "evaluated", "sub_reason": "normal", "score": 47.5, "short_m": 11.5, "long_m": 18.0, "wrong_mcq": 0},
                            {"stu_idx": 1, "status": "evaluated", "sub_reason": "normal", "score": 40.0, "short_m": 10.0, "long_m": 16.0, "wrong_mcq": 1},
                            {"stu_idx": 2, "status": "evaluated", "sub_reason": "normal", "score": 30.0, "short_m": 7.0, "long_m": 13.0, "wrong_mcq": 3},
                            {"stu_idx": 3, "status": "evaluated", "sub_reason": "normal", "score": 31.5, "short_m": 9.5, "long_m": 12.0, "wrong_mcq": 3, "has_override": True},
                            {"stu_idx": 4, "status": "auto_submitted", "sub_reason": "time_expired", "score": 8.0, "pending_sub": True, "wrong_mcq": 4},
                            {"stu_idx": 5, "status": "auto_submitted", "sub_reason": "time_expired", "score": 6.0, "pending_sub": True, "wrong_mcq": 5, "has_events": True},
                        ]

                        for cfg in attempt_configs:
                            s_idx = cfg["stu_idx"] % len(stu_profiles)
                            target_stu = stu_profiles[s_idx].user

                            attempt_obj = StudentAttempt.objects.create(
                                exam=exam_obj,
                                institution=inst,
                                student=target_stu,
                                attempt_number=1,
                                started_at=exam_def["starts_at"] + timedelta(minutes=5),
                                submitted_at=exam_def["starts_at"] + timedelta(minutes=115),
                                expires_at=exam_def["ends_at"],
                                status=cfg["status"],
                                submit_reason=cfg["sub_reason"],
                                max_score=50.0,
                                total_score=cfg["score"],
                                final_total=cfg["score"],
                                auto_total=cfg["score"],
                                review_status="completed" if not cfg.get("pending_sub") else "pending",
                                reviewed_by=fac_author if not cfg.get("pending_sub") else None,
                                finalized_at=exam_def["ends_at"] if not cfg.get("pending_sub") else None,
                            )
                            total_stats["attempts_created"] += 1

                            # Generate Answers for each question
                            for q_idx, q in enumerate(created_questions):
                                is_mcq_tf = q.question_type in ["mcq", "true_false"]
                                is_fill = q.question_type == "fill_blank"
                                is_subjective = q.question_type in ["short_answer", "long_answer"]

                                if is_mcq_tf:
                                    if q_idx < cfg["wrong_mcq"]:
                                        # give incorrect answer
                                        ans_text = q.options[1] if q.options and len(q.options) > 1 else "False"
                                        score_aw = 0.0
                                        is_corr = False
                                    else:
                                        ans_text = str(q.correct_answer)
                                        score_aw = float(q.marks)
                                        is_corr = True
                                elif is_fill:
                                    if q_idx < cfg["wrong_mcq"]:
                                        ans_text = "Standard Solution"
                                        score_aw = 0.0
                                        is_corr = False
                                    else:
                                        ans_text = str(q.correct_answer)
                                        score_aw = float(q.marks)
                                        is_corr = True
                                else:
                                    # Subjective
                                    if cfg.get("pending_sub"):
                                        ans_text = "Student response submitted; pending comprehensive evaluation."
                                        score_aw = 0.0
                                        is_corr = False
                                    elif q.question_type == "short_answer":
                                        ans_text = q.model_answer[:120] if q.model_answer else "Rigorous explanation of underlying principles."
                                        score_aw = cfg["short_m"]
                                        is_corr = True
                                    else:
                                        ans_text = q.model_answer if q.model_answer else "Comprehensive derivation detailing all governing equations and proofs."
                                        score_aw = cfg["long_m"]
                                        is_corr = True

                                sa_obj = StudentAnswer.objects.create(
                                    attempt=attempt_obj,
                                    institution=inst,
                                    question=q,
                                    answer_text=ans_text,
                                    score_awarded=score_aw,
                                    final_marks=score_aw,
                                    is_correct=is_corr,
                                    evaluation_status="evaluated" if not cfg.get("pending_sub") else "pending",
                                    ai_feedback="Detailed automated evaluation: concept comprehension verified against marking rubric." if not cfg.get("pending_sub") else "",
                                    teacher_feedback="Good technical formulation and structure." if not cfg.get("pending_sub") else "",
                                    final_is_correct="CORRECT" if is_corr else "INCORRECT",
                                )
                                total_stats["answers_created"] += 1

                                # Handle Score Override & Audit Log on short answer for student 3
                                if cfg.get("has_override") and q.question_type == "short_answer":
                                    sa_obj.overridden = True
                                    sa_obj.overridden_by = fac_author
                                    sa_obj.overridden_at = timezone.now() - timedelta(days=7)
                                    sa_obj.save(update_fields=["overridden", "overridden_by", "overridden_at"])

                                    EvaluationChangeAuditLog.objects.create(
                                        institution=inst,
                                        attempt=attempt_obj,
                                        question=q,
                                        old_marks=6.0,
                                        new_marks=cfg["short_m"],
                                        old_correctness="PARTIAL",
                                        new_correctness="CORRECT",
                                        reason="Re-evaluation approved: student presented valid mathematical derivation in supplementary working.",
                                        changed_by=fac_author,
                                        ip_address="127.0.0.1",
                                    )
                                    total_stats["audit_logs_created"] += 1

                            # Handle violation AttemptEvents for student 5
                            if cfg.get("has_events"):
                                AttemptEvent.objects.create(
                                    attempt=attempt_obj,
                                    institution=inst,
                                    event_type="fullscreen_exit",
                                    event_id=uuid.uuid4().hex,
                                    metadata={"warning_count": 1, "duration_seconds": 8},
                                    timestamp=exam_def["starts_at"] + timedelta(minutes=45),
                                )
                                AttemptEvent.objects.create(
                                    attempt=attempt_obj,
                                    institution=inst,
                                    event_type="tab_hidden",
                                    event_id=uuid.uuid4().hex,
                                    metadata={"warning_count": 2, "duration_seconds": 14},
                                    timestamp=exam_def["starts_at"] + timedelta(minutes=65),
                                )
                                total_stats["attempt_events_created"] += 2

                    elif exam_def["type"] == "live" and len(stu_profiles) >= 2:
                        # 2 in-progress attempts with partial answers
                        for l_idx in range(2):
                            target_stu = stu_profiles[l_idx].user
                            live_attempt = StudentAttempt.objects.create(
                                exam=exam_obj,
                                institution=inst,
                                student=target_stu,
                                attempt_number=1,
                                started_at=exam_def["starts_at"] + timedelta(minutes=10),
                                expires_at=exam_def["ends_at"],
                                status="in_progress",
                                submit_reason="normal",
                                max_score=50.0,
                                total_score=0.0,
                                review_status="pending",
                            )
                            total_stats["attempts_created"] += 1

                            # Answer first 3 questions
                            for q in created_questions[:3]:
                                StudentAnswer.objects.create(
                                    attempt=live_attempt,
                                    institution=inst,
                                    question=q,
                                    answer_text=q.options[0] if q.options else "In-progress draft response",
                                    score_awarded=0.0,
                                    final_marks=0.0,
                                    is_correct=False,
                                    evaluation_status="pending",
                                )
                                total_stats["answers_created"] += 1

        # 4. Write updated credentials to seed_credentials.csv
        if not is_dry_run and new_creds:
            combined_creds = existing_creds + new_creds
            try:
                with open(cred_file, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=["institute", "role", "department", "name", "username", "email", "password", "id_number"]
                    )
                    writer.writeheader()
                    writer.writerows(combined_creds)
                self.stdout.write(self.style.SUCCESS(f"\nAppended {len(new_creds)} new accounts to {cred_file} (Total: {len(combined_creds)} records)."))
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Failed to update credentials file: {e}"))

        # Summary
        self.stdout.write(self.style.SUCCESS(
            f"\n======================================================\n"
            f"          DEMO SEEDING EXECUTION SUMMARY\n"
            f"======================================================\n"
            f"Institutions Processed:       {total_stats['institutions_processed']}\n"
            f"Departments Verified:         {total_stats['departments_verified']}\n"
            f"Faculty Verified/Created:     {total_stats['faculty_verified_or_created']}\n"
            f"Students Verified/Created:    {total_stats['students_verified_or_created']}\n"
            f"Exams Created:                {total_stats['exams_created']}\n"
            f"Questions Created:            {total_stats['questions_created']}\n"
            f"Student Attempts Created:     {total_stats['attempts_created']}\n"
            f"Student Answers Created:      {total_stats['answers_created']}\n"
            f"Evaluation Audit Logs:        {total_stats['audit_logs_created']}\n"
            f"Attempt Event Logs:           {total_stats['attempt_events_created']}\n"
            f"======================================================\n"
        ))
