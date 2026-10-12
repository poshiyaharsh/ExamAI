import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "motion/react";
import {
  Activity,
  ArrowRight,
  Award,
  BarChart3,
  BookOpen,
  Brain,
  Building,
  CheckCircle2,
  ChevronDown,
  Clock,
  Compass,
  Cpu,
  ExternalLink,
  FileCheck,
  FileText,
  GraduationCap,
  HelpCircle,
  Laptop,
  Layers,
  Lock,
  Mail,
  Menu,
  PieChart,
  PlayCircle,
  PlusCircle,
  School,
  Shield,
  ShieldCheck,
  Sparkles,
  TrendingUp,
  UserCheck,
  Users,
  X,
  Zap,
} from "lucide-react";

import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "../components/ui/accordion";
import { useAuth } from "../context/useAuth";
import { DEPARTMENTS } from "../../constants/departments";
import { publicStatsApi, type PublicStatsData } from "../../services/api";
import { formatStat } from "../../utils/formatStat";

function StatCounter({
  value,
  shouldAnimate,
}: {
  value: number;
  shouldAnimate: boolean;
}) {
  const [displayValue, setDisplayValue] = useState<number>(() => {
    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      return value;
    }
    return 0;
  });

  useEffect(() => {
    if (!shouldAnimate) return;

    if (
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches
    ) {
      setDisplayValue(value);
      return;
    }

    if (value <= 0) {
      setDisplayValue(0);
      return;
    }

    let start: number | null = null;
    const duration = 1500;
    let rafId: number;

    const step = (timestamp: number) => {
      if (!start) start = timestamp;
      const elapsed = timestamp - start;
      const progress = Math.min(elapsed / duration, 1);
      const ease = 1 - Math.pow(1 - progress, 3);
      setDisplayValue(Math.floor(ease * value));

      if (progress < 1) {
        rafId = requestAnimationFrame(step);
      } else {
        setDisplayValue(value);
      }
    };

    rafId = requestAnimationFrame(step);
    return () => {
      if (rafId) cancelAnimationFrame(rafId);
    };
  }, [shouldAnimate, value]);

  return <>{formatStat(shouldAnimate ? displayValue : 0)}</>;
}

function StatsStrip({ stats }: { stats: PublicStatsData }) {
  const containerRef = useRef<HTMLElement | null>(null);
  const [inView, setInView] = useState(false);

  useEffect(() => {
    if (inView) return;
    const node = containerRef.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      setInView(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1 }
    );

    observer.observe(node);
    return () => observer.disconnect();
  }, [inView]);

  const statItems = [
    {
      id: "institutes",
      label: "Partner Institutes",
      value: stats.institutes ?? stats.total_institutes ?? 0,
      colorClass: "text-primary",
    },
    {
      id: "students",
      label: "Enrolled Students",
      value: stats.total_students ?? 0,
      colorClass: "text-foreground",
    },
    {
      id: "faculty",
      label: "Faculty Instructors",
      value: stats.total_faculty ?? 0,
      colorClass: "text-primary",
    },
    {
      id: "exams",
      label: "Exams Published",
      value: stats.total_exams ?? 0,
      colorClass: "text-foreground",
    },
    {
      id: "departments",
      label: "Academic Departments",
      value: stats.total_departments ?? 0,
      colorClass: "text-secondary",
    },
  ];

  return (
    <section
      ref={containerRef}
      aria-label="Platform statistics"
      className="border-b border-border bg-card/60 py-8"
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 text-center">
          {statItems.map((item, index) => (
            <div
              key={item.id}
              className={`space-y-1 ${
                index === 4 ? "col-span-2 md:col-span-1" : "col-span-1"
              }`}
            >
              <div
                className={`text-3xl sm:text-4xl font-extrabold ${item.colorClass} tracking-tight`}
              >
                <StatCounter value={item.value} shouldAnimate={inView} />
              </div>
              <div className="text-xs sm:text-sm font-medium text-muted-foreground">
                {item.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

export function Landing() {
  const { session } = useAuth();
  const navigate = useNavigate();

  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [activeSection, setActiveSection] = useState("hero");
  const [stats, setStats] = useState<PublicStatsData | null>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  // Set page title
  useEffect(() => {
    document.title = "ExamAI — Online Examination & Assessment Platform";
  }, []);

  // Fetch real statistics
  useEffect(() => {
    let isMounted = true;
    const fetchStats = async () => {
      try {
        setStatsLoading(true);
        const res = await publicStatsApi.getStats();
        if (isMounted && res.data) {
          setStats(res.data);
        }
      } catch (err) {
        // As per requirements: if stats endpoint fails or is unavailable, keep stats null to hide the strip
        console.warn("Public stats unavailable; hiding stats strip.", err);
        if (isMounted) setStats(null);
      } finally {
        if (isMounted) setStatsLoading(false);
      }
    };
    void fetchStats();
    return () => {
      isMounted = false;
    };
  }, []);

  // Active section scroll spy
  useEffect(() => {
    const handleScroll = () => {
      const sections = ["hero", "features", "how-it-works", "roles", "departments", "preview", "faq"];
      const scrollPosition = window.scrollY + 200;

      for (const sectionId of sections) {
        const el = document.getElementById(sectionId);
        if (el) {
          const top = el.offsetTop;
          const height = el.offsetHeight;
          if (scrollPosition >= top && scrollPosition < top + height) {
            setActiveSection(sectionId);
            break;
          }
        }
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollTo = useCallback((id: string) => {
    setMobileMenuOpen(false);
    const element = document.getElementById(id);
    if (element) {
      element.scrollIntoView({ behavior: "smooth" });
    }
  }, []);

  // Determine dashboard target for logged-in user
  const dashboardPath = session?.role === "admin"
    ? "/admin"
    : session?.role === "faculty"
    ? "/faculty"
    : "/student";

  // Features list
  const features = [
    {
      icon: PlusCircle,
      title: "Easy Exam Creation",
      description: "Faculty can rapidly draft timed exams with custom question types, syllabus integration, and schedule parameters.",
      tag: "Authoring",
    },
    {
      icon: Zap,
      title: "Automatic Scoring",
      description: "Instant score computation for objective questions eliminates manual grading delays and delivers error-free results.",
      tag: "Automation",
    },
    {
      icon: Award,
      title: "Instant Results",
      description: "Students receive transparent scores, percentage benchmarks, and passing statuses the moment an attempt is finalized.",
      tag: "Immediate",
    },
    {
      icon: Building,
      title: "Department-wise Access",
      description: "Strict curriculum scoping ensures students and faculty only access examinations aligned with their department.",
      tag: "Scoping",
    },
    {
      icon: BarChart3,
      title: "Performance Analytics",
      description: "Deep analytics across historical attempts, department benchmarks, class averages, and at-risk student monitoring.",
      tag: "Insights",
    },
    {
      icon: Shield,
      title: "Secure & Role-Based Access",
      description: "Dedicated interfaces and strict permission boundaries for Administrators, Faculty members, and Students.",
      tag: "Security",
    },
  ];

  // How it works steps
  const steps = [
    {
      number: "01",
      icon: UserCheck,
      title: "Register & Profile Setup",
      description: "Create an account and connect to your academic institution as a Student, Faculty member, or Administrator.",
    },
    {
      number: "02",
      icon: Building,
      title: "Join Department",
      description: "Students and faculty are assigned to their respective departments, scoping all subjects and available tests.",
    },
    {
      number: "03",
      icon: PlayCircle,
      title: "Create or Take Exams",
      description: "Faculty schedule examinations; students attempt tests with an auto-saving interface and live timer countdown.",
    },
    {
      number: "04",
      icon: TrendingUp,
      title: "Instant Results & Insights",
      description: "Exams are auto-graded upon submit. Students review performance, and faculty review institutional analytics.",
    },
  ];

  // Role details
  const roles = [
    {
      title: "Student",
      subtitle: "For test takers & learners",
      icon: GraduationCap,
      color: "from-blue-600 to-indigo-600",
      accentBg: "bg-blue-50 text-blue-700 border-blue-200",
      badge: "Learner Portal",
      benefits: [
        "Take scheduled & on-demand department examinations",
        "Distraction-free exam runner with live countdown & auto-save",
        "Instant score calculation with pass/fail evaluation",
        "Personal performance trends & subject strength breakdowns",
      ],
      ctaText: session?.role === "student" ? "Open Student Dashboard" : "Student Login",
      ctaPath: session?.role === "student" ? "/student" : "/login",
    },
    {
      title: "Faculty",
      subtitle: "For educators & instructors",
      icon: Users,
      color: "from-indigo-600 to-purple-600",
      accentBg: "bg-indigo-50 text-indigo-700 border-indigo-200",
      badge: "Faculty Console",
      benefits: [
        "Author comprehensive exams with syllabus and topic tagging",
        "Manage centralized question banks with Bloom's taxonomy",
        "Monitor student attempt progress in real time",
        "Analyze class score distributions and at-risk learners",
      ],
      ctaText: session?.role === "faculty" ? "Open Faculty Dashboard" : "Faculty Login",
      ctaPath: session?.role === "faculty" ? "/faculty" : "/login",
    },
    {
      title: "Administrator",
      subtitle: "For institutional leadership",
      icon: ShieldCheck,
      color: "from-purple-600 to-pink-600",
      accentBg: "bg-purple-50 text-purple-700 border-purple-200",
      badge: "Admin Suite",
      benefits: [
        "Full system oversight of students, faculty, and departments",
        "Cross-department analytics, pass rates, and participation stats",
        "Manage institution profile, codes, and academic settings",
        "Audit log tracking and attention alerts for pending actions",
      ],
      ctaText: session?.role === "admin" ? "Open Admin Dashboard" : "Admin Login",
      ctaPath: session?.role === "admin" ? "/admin" : "/login",
    },
  ];

  // Department icon mapping helper
  const getDepartmentIcon = (name: string) => {
    switch (name) {
      case "Computer Science":
      case "Information Technology":
        return Laptop;
      case "Electronics and Communication":
      case "Electrical Engineering":
        return Cpu;
      case "Mechanical Engineering":
      case "Civil Engineering":
        return Compass;
      case "Business Administration":
      case "Commerce":
        return PieChart;
      default:
        return BookOpen;
    }
  };

  // FAQ items
  const faqs = [
    {
      question: "How do I register for an account on ExamAI?",
      answer: "Click the 'Sign Up' button on the navigation bar or login page. Select whether you are registering as a Student or Faculty member, choose your institution from the dropdown list, provide your details, and create your account instantly.",
    },
    {
      question: "Who can create and publish exams?",
      answer: "Exams can be drafted and published by registered Faculty members for their designated department, as well as institutional Administrators. Students only have permission to attempt published examinations.",
    },
    {
      question: "How are exam scores calculated?",
      answer: "Scores are computed automatically on submission based on each question's assigned marks. The percentage score is calculated using the formula: (Total Marks Obtained / Total Exam Marks) × 100%. The system standard passing threshold is 40%.",
    },
    {
      question: "Can I only see exams from my own department?",
      answer: "Yes! ExamAI enforces strict departmental scoping. Students are enrolled in a specific department and will only see examinations and performance analytics relevant to their academic discipline.",
    },
    {
      question: "Is my exam data and student submission secure?",
      answer: "All endpoints are protected by JSON Web Token (JWT) authentication and role-based access control. Answers are securely saved as you progress, and final submissions are permanently locked and timestamped.",
    },
    {
      question: "Who do I contact if I need help or experience technical difficulties?",
      answer: "You can reach out to our institutional support team via email at support@examai.edu or contact your department administrator directly through your institutional portal.",
    },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col selection:bg-primary/20 selection:text-primary">
      {/* 1. NAVBAR (Sticky & Scroll-Spy) */}
      <header className="sticky top-0 z-50 w-full border-b border-border/80 bg-background/85 backdrop-blur-md transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo & Brand */}
          <Link to="/" className="flex items-center gap-2.5 group">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white shadow-sm group-hover:scale-105 transition-transform">
              <Brain className="w-5 h-5" />
            </div>
            <span className="text-xl font-bold tracking-tight text-foreground">
              Exam<span className="text-primary">AI</span>
            </span>
          </Link>

          {/* Desktop Nav Links */}
          <nav className="hidden md:flex items-center gap-1 lg:gap-2 text-sm font-medium">
            {[
              { id: "hero", label: "Home" },
              { id: "features", label: "Features" },
              { id: "how-it-works", label: "How It Works" },
              { id: "roles", label: "Roles" },
              { id: "departments", label: "Departments" },
              { id: "preview", label: "Preview" },
              { id: "faq", label: "FAQ" },
            ].map((link) => (
              <button
                key={link.id}
                onClick={() => scrollTo(link.id)}
                className={`px-3 py-1.5 rounded-lg transition-colors ${
                  activeSection === link.id
                    ? "text-primary font-semibold bg-primary/5"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted/50"
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>

          {/* Desktop Actions */}
          <div className="hidden md:flex items-center gap-2.5">
            {session ? (
              <Link
                to={dashboardPath}
                className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm shadow-sm hover:opacity-95 transition-all flex items-center gap-1.5"
              >
                <span>Go to Dashboard</span>
                <ArrowRight className="w-4 h-4" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-3.5 py-1.5 rounded-lg border border-border text-foreground hover:bg-muted text-sm font-medium transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  to="/login"
                  className="px-4 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm shadow-sm hover:opacity-95 transition-all"
                >
                  Get Started
                </Link>
              </>
            )}
          </div>

          {/* Mobile Menu Button */}
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="md:hidden p-2 rounded-lg border border-border text-foreground hover:bg-muted"
            aria-label="Toggle Navigation Menu"
          >
            {mobileMenuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>

        {/* Mobile Dropdown Menu */}
        <AnimatePresence>
          {mobileMenuOpen && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="md:hidden border-b border-border bg-background px-4 py-4 space-y-2 shadow-lg"
            >
              {[
                { id: "hero", label: "Home" },
                { id: "features", label: "Features" },
                { id: "how-it-works", label: "How It Works" },
                { id: "roles", label: "Roles" },
                { id: "departments", label: "Departments" },
                { id: "preview", label: "Preview" },
                { id: "faq", label: "FAQ" },
              ].map((link) => (
                <button
                  key={link.id}
                  onClick={() => scrollTo(link.id)}
                  className="w-full text-left px-3 py-2 rounded-lg text-sm font-medium text-foreground hover:bg-muted"
                >
                  {link.label}
                </button>
              ))}

              <div className="pt-3 border-t border-border flex flex-col gap-2">
                {session ? (
                  <Link
                    to={dashboardPath}
                    onClick={() => setMobileMenuOpen(false)}
                    className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm text-center shadow-sm"
                  >
                    Go to Dashboard
                  </Link>
                ) : (
                  <>
                    <Link
                      to="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="w-full py-2 rounded-lg border border-border text-foreground font-medium text-sm text-center hover:bg-muted"
                    >
                      Sign In
                    </Link>
                    <Link
                      to="/login"
                      onClick={() => setMobileMenuOpen(false)}
                      className="w-full py-2.5 rounded-lg bg-gradient-to-r from-primary to-secondary text-white font-medium text-sm text-center shadow-sm"
                    >
                      Get Started
                    </Link>
                  </>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </header>

      <main className="flex-1">
        {/* 2. HERO SECTION */}
        <section
          id="hero"
          className="relative overflow-hidden pt-8 pb-16 md:pt-14 md:pb-24 bg-gradient-to-b from-primary/5 via-accent/30 to-background border-b border-border/40"
        >
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-10 lg:gap-12 items-center">
              {/* Left Column: Copy & CTAs */}
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5 }}
                className="lg:col-span-7 space-y-6 text-center lg:text-left"
              >
                <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-primary/10 border border-primary/20 text-primary text-xs font-semibold">
                  <Sparkles className="w-3.5 h-3.5" />
                  <span>Next-Generation Online Examination Platform</span>
                </div>

                <h1 className="text-3xl sm:text-4xl lg:text-5xl xl:text-6xl font-extrabold tracking-tight text-foreground leading-[1.15]">
                  Conduct and Take Exams Online,{" "}
                  <span className="bg-gradient-to-r from-primary via-secondary to-indigo-600 bg-clip-text text-transparent">
                    Simply & Securely
                  </span>
                </h1>

                <p className="text-base sm:text-lg text-muted-foreground max-w-2xl mx-auto lg:mx-0 leading-relaxed">
                  A unified platform for academic assessments with department-wise scoping, automatic question evaluation, and real-time performance analytics for students, faculty, and administrators.
                </p>

                {/* Primary CTA Buttons */}
                <div className="flex flex-col sm:flex-row items-center justify-center lg:justify-start gap-3 pt-2">
                  {session ? (
                    <Link
                      to={dashboardPath}
                      className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-primary to-secondary text-white font-semibold text-sm shadow-md hover:shadow-lg hover:opacity-95 transition-all flex items-center justify-center gap-2"
                    >
                      <span>Go to Dashboard</span>
                      <ArrowRight className="w-4 h-4" />
                    </Link>
                  ) : (
                    <>
                      <Link
                        to="/login"
                        className="w-full sm:w-auto px-6 py-3 rounded-xl bg-gradient-to-r from-primary to-secondary text-white font-semibold text-sm shadow-md hover:shadow-lg hover:opacity-95 transition-all flex items-center justify-center gap-2"
                      >
                        <span>Get Started Free</span>
                        <ArrowRight className="w-4 h-4" />
                      </Link>
                      <Link
                        to="/login"
                        className="w-full sm:w-auto px-6 py-3 rounded-xl border border-border bg-card hover:bg-muted font-semibold text-sm text-foreground transition-all flex items-center justify-center shadow-2xs"
                      >
                        Sign In to Account
                      </Link>
                    </>
                  )}
                  <button
                    onClick={() => scrollTo("how-it-works")}
                    className="w-full sm:w-auto px-5 py-3 rounded-xl text-muted-foreground hover:text-foreground text-sm font-medium transition-colors"
                  >
                    How It Works
                  </button>
                </div>

                {/* Trust Points */}
                <div className="pt-4 border-t border-border/70 grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs text-muted-foreground">
                  <div className="flex items-center gap-1.5 justify-center lg:justify-start">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Auto-graded</span>
                  </div>
                  <div className="flex items-center gap-1.5 justify-center lg:justify-start">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Department-wise</span>
                  </div>
                  <div className="flex items-center gap-1.5 justify-center lg:justify-start">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Instant results</span>
                  </div>
                  <div className="flex items-center gap-1.5 justify-center lg:justify-start">
                    <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
                    <span>Role-based access</span>
                  </div>
                </div>
              </motion.div>

              {/* Right Column: Modern Visual Mockup */}
              <motion.div
                initial={{ opacity: 0, scale: 0.96 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={{ duration: 0.6, delay: 0.15 }}
                className="lg:col-span-5 relative"
              >
                <div className="relative mx-auto max-w-md lg:max-w-none rounded-2xl border border-border/80 bg-card p-5 sm:p-6 shadow-xl hover:shadow-2xl transition-all duration-300">
                  {/* Mock Window Top Bar */}
                  <div className="flex items-center justify-between border-b border-border pb-3 mb-4">
                    <div className="flex items-center gap-1.5">
                      <div className="w-3 h-3 rounded-full bg-rose-400" />
                      <div className="w-3 h-3 rounded-full bg-amber-400" />
                      <div className="w-3 h-3 rounded-full bg-emerald-400" />
                    </div>
                    <div className="text-[11px] font-mono text-muted-foreground flex items-center gap-1">
                      <Lock className="w-3 h-3 text-emerald-600" />
                      <span>examai.edu/session/live</span>
                    </div>
                  </div>

                  {/* Mock Content Inside Card */}
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div>
                        <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-primary/10 text-primary">
                          Computer Science Midterm
                        </span>
                        <h4 className="font-bold text-sm text-foreground mt-1">
                          Data Structures & Algorithms
                        </h4>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-mono font-bold text-emerald-600 flex items-center gap-1">
                          <Clock className="w-3.5 h-3.5" />
                          <span>42:15 left</span>
                        </div>
                        <span className="text-[10px] text-muted-foreground">Auto-saving</span>
                      </div>
                    </div>

                    {/* Question Mock */}
                    <div className="rounded-xl border border-border bg-muted/30 p-3.5 text-xs space-y-2.5">
                      <div className="flex items-center justify-between text-muted-foreground font-medium">
                        <span>Question 4 of 25</span>
                        <span className="font-semibold text-primary">4 Marks</span>
                      </div>
                      <p className="font-medium text-foreground">
                        Which of the following data structures operates on a First-In-First-Out (FIFO) principle?
                      </p>
                      <div className="space-y-1.5 pt-1">
                        {["A. Stack", "B. Queue", "C. Priority Queue", "D. Binary Tree"].map((opt, i) => (
                          <div
                            key={i}
                            className={`p-2 rounded-lg border text-xs flex items-center justify-between transition-colors ${
                              i === 1
                                ? "bg-primary/10 border-primary text-primary font-semibold"
                                : "bg-card border-border text-foreground hover:bg-muted"
                            }`}
                          >
                            <span>{opt}</span>
                            {i === 1 && <CheckCircle2 className="w-3.5 h-3.5 text-primary" />}
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Bottom Metric Gauge Mock */}
                    <div className="pt-2 grid grid-cols-3 gap-2 text-center text-xs">
                      <div className="p-2 rounded-lg bg-card border border-border">
                        <div className="text-muted-foreground text-[10px]">Answered</div>
                        <div className="font-bold text-foreground mt-0.5">18 / 25</div>
                      </div>
                      <div className="p-2 rounded-lg bg-card border border-border">
                        <div className="text-muted-foreground text-[10px]">Class Avg</div>
                        <div className="font-bold text-emerald-600 mt-0.5">82.4%</div>
                      </div>
                      <div className="p-2 rounded-lg bg-card border border-border">
                        <div className="text-muted-foreground text-[10px]">Pass Rate</div>
                        <div className="font-bold text-indigo-600 mt-0.5">91%</div>
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          </div>
        </section>

        {/* 3. STATS STRIP (Real counts from GET /api/public/stats) */}
        {statsLoading && (
          <section
            aria-label="Loading statistics"
            className="border-b border-border bg-card/60 py-8"
          >
            <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-6 text-center">
                {Array.from({ length: 5 }).map((_, idx) => (
                  <div
                    key={idx}
                    className={`space-y-2 flex flex-col items-center justify-center ${
                      idx === 4 ? "col-span-2 md:col-span-1" : "col-span-1"
                    }`}
                  >
                    <div className="h-9 w-20 bg-muted/60 animate-pulse rounded-md" />
                    <div className="h-4 w-28 bg-muted/40 animate-pulse rounded-md" />
                  </div>
                ))}
              </div>
            </div>
          </section>
        )}

        {!statsLoading && stats && <StatsStrip stats={stats} />}

        {/* 4. FEATURES (Grid of 6 Cards) */}
        <section id="features" className="py-16 sm:py-24 border-b border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                Core Capabilities
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                Everything You Need for Online Testing
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                Engineered specifically for academic rigor, departmental workflows, and fast grading turnaround.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {features.map((feature, i) => (
                <div
                  key={i}
                  className="bg-card rounded-2xl p-6 border border-border shadow-xs hover:shadow-md hover:border-primary/40 transition-all flex flex-col justify-between group"
                >
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-primary/10 to-secondary/15 text-primary flex items-center justify-center group-hover:scale-105 transition-transform">
                        <feature.icon className="w-6 h-6" />
                      </div>
                      <span className="text-[11px] font-semibold px-2 py-0.5 rounded-md bg-muted text-muted-foreground">
                        {feature.tag}
                      </span>
                    </div>

                    <h3 className="text-lg font-bold text-foreground mb-2 group-hover:text-primary transition-colors">
                      {feature.title}
                    </h3>

                    <p className="text-muted-foreground text-xs sm:text-sm leading-relaxed">
                      {feature.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 5. HOW IT WORKS (4 Simple Steps) */}
        <section id="how-it-works" className="py-16 sm:py-24 bg-muted/30 border-b border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-16 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-secondary/10 text-secondary border border-secondary/20">
                Workflow
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                How ExamAI Works
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                A seamless four-step progression from account setup to instant performance feedback.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 relative">
              {steps.map((step, idx) => (
                <div
                  key={step.number}
                  className="bg-card rounded-2xl p-6 border border-border shadow-xs relative flex flex-col justify-between hover:border-primary/40 transition-all"
                >
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <span className="text-2xl font-black text-primary/30 font-mono">
                        {step.number}
                      </span>
                      <div className="w-10 h-10 rounded-lg bg-accent text-primary flex items-center justify-center">
                        <step.icon className="w-5 h-5" />
                      </div>
                    </div>

                    <h3 className="font-bold text-base text-foreground mb-2">
                      {step.title}
                    </h3>

                    <p className="text-muted-foreground text-xs sm:text-sm leading-relaxed">
                      {step.description}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 6. ROLES (Admin, Faculty, Student Cards) */}
        <section id="roles" className="py-16 sm:py-24 border-b border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                Tailored Experiences
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                Built for Every Stakeholder
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                Separate portals customized for students, faculty, and administrators.
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
              {roles.map((r) => (
                <div
                  key={r.title}
                  className="bg-card rounded-2xl p-6 sm:p-7 border border-border shadow-xs hover:shadow-lg hover:border-primary/40 transition-all flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between mb-4">
                      <div className={`w-12 h-12 rounded-xl bg-gradient-to-br ${r.color} text-white flex items-center justify-center shadow-sm`}>
                        <r.icon className="w-6 h-6" />
                      </div>
                      <span className={`text-[11px] font-semibold px-2.5 py-0.5 rounded-full border ${r.accentBg}`}>
                        {r.badge}
                      </span>
                    </div>

                    <h3 className="text-xl font-bold text-foreground">{r.title}</h3>
                    <p className="text-xs text-muted-foreground mb-5">{r.subtitle}</p>

                    <div className="space-y-2.5 mb-6">
                      {r.benefits.map((benefit, i) => (
                        <div key={i} className="flex items-start gap-2 text-xs sm:text-sm text-foreground/90">
                          <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
                          <span>{benefit}</span>
                        </div>
                      ))}
                    </div>
                  </div>

                  <Link
                    to={r.ctaPath}
                    className="w-full py-2.5 rounded-xl border border-border bg-card hover:bg-muted font-semibold text-xs sm:text-sm text-foreground transition-all flex items-center justify-center gap-1.5 shadow-2xs group"
                  >
                    <span>{r.ctaText}</span>
                    <ArrowRight className="w-4 h-4 text-primary group-hover:translate-x-0.5 transition-transform" />
                  </Link>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* 7. DEPARTMENTS (11 Supported Departments) */}
        <section id="departments" className="py-16 sm:py-24 bg-muted/20 border-b border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                Curriculum Scoping
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                Supported Academic Departments
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                ExamAI supports 11 engineering, sciences, and business disciplines with dedicated department channels.
              </p>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 gap-3 sm:gap-4">
              {DEPARTMENTS.map((deptName) => {
                const IconComponent = getDepartmentIcon(deptName);
                return (
                  <div
                    key={deptName}
                    className="bg-card rounded-xl p-4 border border-border hover:border-primary/40 hover:shadow-xs transition-all flex flex-col items-center text-center justify-center gap-2 group"
                  >
                    <div className="w-10 h-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center group-hover:scale-105 transition-transform">
                      <IconComponent className="w-5 h-5" />
                    </div>
                    <span className="text-xs font-semibold text-foreground line-clamp-2">
                      {deptName}
                    </span>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* 8. DASHBOARD PREVIEW */}
        <section id="preview" className="py-16 sm:py-24 border-b border-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-secondary/10 text-secondary border border-secondary/20">
                Interface Preview
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                Intuitive, Data-Driven Dashboards
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                Clean visual metrics that keep students focused on results and faculty on academic progression.
              </p>
            </div>

            {/* Mock Dashboard Layout */}
            <div className="rounded-2xl border border-border bg-card p-4 sm:p-8 shadow-xl max-w-5xl mx-auto space-y-6">
              {/* Header preview */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-border">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-xl bg-primary text-white flex items-center justify-center">
                    <BarChart3 className="w-5 h-5" />
                  </div>
                  <div>
                    <h4 className="font-bold text-base text-foreground">Department Analytics Dashboard</h4>
                    <p className="text-xs text-muted-foreground">Computer Science • Academic Semester 2026</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                    Live Interface
                  </span>
                </div>
              </div>

              {/* 3 Metric Cards */}
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground">Class Average Score</div>
                  <div className="text-2xl font-bold text-foreground mt-1">78.5%</div>
                  <div className="text-[11px] text-emerald-600 font-medium mt-1">Top 15% across university</div>
                </div>
                <div className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground">Exams Passing Rate</div>
                  <div className="text-2xl font-bold text-primary mt-1">92.4%</div>
                  <div className="text-[11px] text-muted-foreground mt-1">Threshold ≥ 40%</div>
                </div>
                <div className="rounded-xl border border-border bg-muted/30 p-4">
                  <div className="text-xs text-muted-foreground">Total Exam Submissions</div>
                  <div className="text-2xl font-bold text-foreground mt-1">248</div>
                  <div className="text-[11px] text-muted-foreground mt-1">Auto-graded on submit</div>
                </div>
              </div>

              {/* Chart & Live Exam Simulation */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
                <div className="rounded-xl border border-border p-4 bg-card space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                    <span>Score Distribution</span>
                    <span className="text-muted-foreground">4 Tiers</span>
                  </div>
                  <div className="space-y-2 pt-2">
                    {[
                      { range: "80 - 100% (Excellent)", pct: 45, color: "bg-emerald-500" },
                      { range: "60 - 80% (Good)", pct: 35, color: "bg-blue-500" },
                      { range: "40 - 60% (Average)", pct: 15, color: "bg-amber-500" },
                      { range: "0 - 40% (Below Pass)", pct: 5, color: "bg-rose-500" },
                    ].map((b, i) => (
                      <div key={i} className="space-y-1">
                        <div className="flex justify-between text-[11px] text-muted-foreground">
                          <span>{b.range}</span>
                          <span className="font-semibold text-foreground">{b.pct}%</span>
                        </div>
                        <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                          <div className={`h-2 rounded-full ${b.color}`} style={{ width: `${b.pct}%` }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-xl border border-border p-4 bg-card space-y-3">
                  <div className="flex items-center justify-between text-xs font-semibold text-foreground">
                    <span>Recent Published Exam</span>
                    <span className="text-xs text-emerald-600 font-semibold">Active</span>
                  </div>
                  <div className="rounded-lg border border-border bg-muted/40 p-3 space-y-2">
                    <h5 className="font-bold text-sm text-foreground">Operating Systems Midterm</h5>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Clock className="w-3.5 h-3.5" /> 60 mins
                      </span>
                      <span>•</span>
                      <span>100 Total Marks</span>
                      <span>•</span>
                      <span>25 Questions</span>
                    </div>
                    <div className="pt-2">
                      <div className="flex justify-between text-[11px] text-muted-foreground mb-1">
                        <span>Submission Progress</span>
                        <span className="font-bold text-foreground">42 / 48 Students</span>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2 overflow-hidden">
                        <div className="h-2 rounded-full bg-primary" style={{ width: "87%" }} />
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* 9. FAQ (Accordion) */}
        <section id="faq" className="py-16 sm:py-24 bg-muted/20 border-b border-border">
          <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="text-center max-w-2xl mx-auto mb-14 space-y-3">
              <span className="text-xs font-semibold px-3 py-1 rounded-full bg-primary/10 text-primary border border-primary/20">
                Common Inquiries
              </span>
              <h2 className="text-3xl sm:text-4xl font-bold text-foreground">
                Frequently Asked Questions
              </h2>
              <p className="text-muted-foreground text-sm sm:text-base">
                Everything you need to know about exam delivery, scoring, and account setup.
              </p>
            </div>

            <div className="bg-card rounded-2xl border border-border p-4 sm:p-6 shadow-xs">
              <Accordion type="single" collapsible className="w-full">
                {faqs.map((faq, i) => (
                  <AccordionItem key={i} value={`item-${i}`} className="border-border">
                    <AccordionTrigger className="text-left font-semibold text-sm sm:text-base text-foreground hover:text-primary">
                      {faq.question}
                    </AccordionTrigger>
                    <AccordionContent className="text-muted-foreground text-xs sm:text-sm leading-relaxed">
                      {faq.answer}
                    </AccordionContent>
                  </AccordionItem>
                ))}
              </Accordion>
            </div>
          </div>
        </section>

        {/* 10. FINAL CALL TO ACTION */}
        <section className="py-16 sm:py-24 relative overflow-hidden bg-gradient-to-r from-primary via-indigo-600 to-secondary text-white">
          <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 text-center space-y-6 relative z-10">
            <h2 className="text-3xl sm:text-4xl lg:text-5xl font-extrabold tracking-tight">
              Ready to Modernize Your Examination Workflow?
            </h2>
            <p className="text-base sm:text-lg text-white/90 max-w-2xl mx-auto leading-relaxed">
              Join educators and students using ExamAI for reliable, automated, and secure testing with department-level analytics.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3 pt-2">
              {session ? (
                <Link
                  to={dashboardPath}
                  className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-white text-primary font-bold text-sm shadow-lg hover:bg-white/95 transition-all flex items-center justify-center gap-2"
                >
                  <span>Go to Your Dashboard</span>
                  <ArrowRight className="w-4 h-4" />
                </Link>
              ) : (
                <>
                  <Link
                    to="/login"
                    className="w-full sm:w-auto px-8 py-3.5 rounded-xl bg-white text-primary font-bold text-sm shadow-lg hover:bg-white/95 transition-all flex items-center justify-center gap-2"
                  >
                    <span>Get Started Free</span>
                    <ArrowRight className="w-4 h-4" />
                  </Link>
                  <Link
                    to="/login"
                    className="w-full sm:w-auto px-8 py-3.5 rounded-xl border-2 border-white/40 text-white font-bold text-sm hover:bg-white/10 transition-all flex items-center justify-center"
                  >
                    Sign In
                  </Link>
                </>
              )}
            </div>
          </div>
        </section>
      </main>

      {/* 11. FOOTER */}
      <footer id="contact" className="border-t border-border bg-card py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-8 mb-10">
            {/* Brand column */}
            <div className="space-y-3">
              <Link to="/" className="flex items-center gap-2.5">
                <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center text-white shadow-sm">
                  <Brain className="w-5 h-5" />
                </div>
                <span className="text-lg font-bold text-foreground">
                  Exam<span className="text-primary">AI</span>
                </span>
              </Link>
              <p className="text-xs text-muted-foreground leading-relaxed">
                A unified, AI-assisted online examination and assessment platform with automatic scoring, department scoping, and performance analytics.
              </p>
            </div>

            {/* Quick Links */}
            <div>
              <h4 className="font-semibold text-xs sm:text-sm text-foreground mb-3">Navigation</h4>
              <ul className="space-y-2 text-xs text-muted-foreground">
                <li>
                  <button onClick={() => scrollTo("hero")} className="hover:text-primary transition-colors">
                    Home
                  </button>
                </li>
                <li>
                  <button onClick={() => scrollTo("features")} className="hover:text-primary transition-colors">
                    Features
                  </button>
                </li>
                <li>
                  <button onClick={() => scrollTo("how-it-works")} className="hover:text-primary transition-colors">
                    How It Works
                  </button>
                </li>
                <li>
                  <button onClick={() => scrollTo("departments")} className="hover:text-primary transition-colors">
                    Departments
                  </button>
                </li>
                <li>
                  <button onClick={() => scrollTo("faq")} className="hover:text-primary transition-colors">
                    FAQ
                  </button>
                </li>
              </ul>
            </div>

            {/* Roles */}
            <div>
              <h4 className="font-semibold text-xs sm:text-sm text-foreground mb-3">Portals</h4>
              <ul className="space-y-2 text-xs text-muted-foreground">
                <li>
                  <Link to="/login" className="hover:text-primary transition-colors">
                    Student Examination Portal
                  </Link>
                </li>
                <li>
                  <Link to="/login" className="hover:text-primary transition-colors">
                    Faculty Assessment Console
                  </Link>
                </li>
                <li>
                  <Link to="/login" className="hover:text-primary transition-colors">
                    Administrator Suite
                  </Link>
                </li>
              </ul>
            </div>

            {/* Contact Support */}
            <div className="space-y-3">
              <h4 className="font-semibold text-xs sm:text-sm text-foreground">Contact & Support</h4>
              <p className="text-xs text-muted-foreground">
                Have questions or need institutional integration support?
              </p>
              <div className="flex items-center gap-2 text-xs font-medium text-foreground">
                <Mail className="w-4 h-4 text-primary" />
                <span>support@examai.edu</span>
              </div>
            </div>
          </div>

          <div className="border-t border-border pt-6 flex flex-col sm:flex-row items-center justify-between gap-3 text-xs text-muted-foreground">
            <p>© {new Date().getFullYear()} ExamAI. All rights reserved.</p>
            <div className="flex items-center gap-4">
              <span>Online Examination System</span>
              <span>•</span>
              <span>Academic Integrity Guaranteed</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
