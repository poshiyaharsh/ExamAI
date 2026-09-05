import { useEffect } from "react";
import { Link } from "react-router-dom";
import { motion } from "motion/react";
import { Brain, FileText, TrendingUp, Users, Clock, CheckCircle, Star } from "lucide-react";
import { ImageWithFallback } from "../components/figma/ImageWithFallback";

export function Landing() {
  useEffect(() => {
    document.title = "Home | ExamAI";
  }, []);

  const features = [
    {
      icon: Brain,
      title: "AI-Powered Generation",
      description: "Automatically generate exam papers using advanced AI algorithms tailored to your syllabus"
    },
    {
      icon: FileText,
      title: "Question Bank Management",
      description: "Organize and manage questions with Bloom's taxonomy and difficulty levels"
    },
    {
      icon: TrendingUp,
      title: "Performance Analytics",
      description: "Track student performance with detailed analytics and AI-driven insights"
    },
    {
      icon: Users,
      title: "Multi-Role Access",
      description: "Separate dashboards for admins, faculty, and students with role-based permissions"
    }
  ];

  const steps = [
    {
      number: "01",
      title: "Upload Syllabus",
      description: "Faculty uploads course syllabus and learning objectives"
    },
    {
      number: "02",
      title: "Generate Paper",
      description: "AI analyzes content and generates balanced exam papers"
    },
    {
      number: "03",
      title: "Review & Publish",
      description: "Review generated papers and publish to students"
    },
    {
      number: "04",
      title: "Analyze Results",
      description: "Get detailed insights on student performance"
    }
  ];

  const testimonials = [
    {
      name: "Dr. Sarah Johnson",
      role: "Professor, Computer Science",
      content: "This platform has revolutionized how we create and manage exams. The AI-generated papers are consistently high quality.",
      rating: 5
    },
    {
      name: "Michael Chen",
      role: "Academic Dean",
      content: "The analytics and insights have helped us improve our curriculum significantly. Highly recommended!",
      rating: 5
    },
    {
      name: "Emily Rodriguez",
      role: "Faculty Coordinator",
      content: "Easy to use, powerful features, and excellent support. It's a game-changer for exam management.",
      rating: 5
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-white to-accent">
      {/* Hero Section */}
      <nav className="border-b bg-white/80 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-6 py-4 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <span className="text-xl font-semibold text-foreground">ExamAI</span>
          </div>
          <Link to="/login">
            <button className="px-6 py-2 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
              Sign In
            </button>
          </Link>
        </div>
      </nav>

      <motion.section 
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.6 }}
        className="max-w-[1280px] mx-auto px-6 py-6 lg:py-8 lg:min-h-[calc(100vh-80px)] flex items-center"
      >
        <div className="grid w-full grid-cols-1 md:grid-cols-[1.15fr_0.85fr] gap-10 lg:gap-16 xl:gap-20 items-center">
          <div className="max-w-2xl self-center">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.2 }}
            >
              <span className="inline-block px-4 py-1 rounded-full bg-accent text-accent-foreground mb-4 lg:mb-6">
                AI-Powered Exam Platform
              </span>
            </motion.div>
            <motion.h1 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3 }}
              className="text-4xl lg:text-5xl font-bold text-foreground mb-4 lg:mb-6 leading-tight max-w-xl"
            >
              Transform Exam Creation with AI
            </motion.h1>
            <motion.p 
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.4 }}
              className="text-lg lg:text-xl text-muted-foreground mb-6 lg:mb-8 max-w-xl leading-relaxed"
            >
              Generate, manage, and analyze exams effortlessly. Our AI-powered platform helps educators create better assessments in minutes.
            </motion.p>
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.5 }}
              className="flex flex-col sm:flex-row gap-4"
            >
              <Link to="/login">
                <button className="px-8 py-3 rounded-lg bg-gradient-to-r from-primary to-secondary text-white hover:opacity-90 transition-opacity">
                  Get Started
                </button>
              </Link>
              <button className="px-8 py-3 rounded-lg border-2 border-primary text-primary hover:bg-accent transition-colors">
                Learn More
              </button>
            </motion.div>
          </div>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.6, type: "spring", stiffness: 120, damping: 18 }}
            whileHover={{ y: -4 }}
            className="relative w-[280px] h-[280px] sm:w-[340px] sm:h-[340px] lg:w-[420px] lg:h-[420px] mx-auto md:justify-self-end md:self-center"
          >
            <div className="flex h-full w-full items-center justify-center rounded-[24px] border border-border bg-white p-5 sm:p-6 lg:p-6 shadow-xl transition-all duration-300 hover:-translate-y-1 hover:shadow-2xl">
              <ImageWithFallback 
                src="https://images.unsplash.com/photo-1749006590639-e749e6b7d84c?crop=entropy&cs=tinysrgb&fit=max&fm=jpg&ixid=M3w3Nzg4Nzd8MHwxfHNlYXJjaHwxfHxhcnRpZmljaWFsJTIwaW50ZWxsaWdlbmNlJTIwdGVjaG5vbG9neSUyMGFic3RyYWN0fGVufDF8fHx8MTc3MjU2MDY5MHww&ixlib=rb-4.1.0&q=80&w=1080&utm_source=figma&utm_medium=referral"
                alt="AI Technology"
                className="max-h-full max-w-full object-contain"
              />
            </div>
          </motion.div>
        </div>
      </motion.section>

      {/* Features Grid */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-bold text-foreground mb-4">Powerful Features</h2>
          <p className="text-xl text-muted-foreground">Everything you need to manage exams efficiently</p>
        </motion.div>

        <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-6">
          {features.map((feature, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className="bg-white rounded-xl p-6 shadow-lg hover:shadow-xl transition-shadow"
            >
              <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-primary to-secondary flex items-center justify-center mb-4">
                <feature.icon className="w-6 h-6 text-white" />
              </div>
              <h3 className="text-xl font-semibold text-foreground mb-2">{feature.title}</h3>
              <p className="text-muted-foreground">{feature.description}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* How It Works */}
      <section className="bg-white py-20">
        <div className="max-w-7xl mx-auto px-6">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <h2 className="text-4xl font-bold text-foreground mb-4">How It Works</h2>
            <p className="text-xl text-muted-foreground">Four simple steps to better exams</p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-8">
            {steps.map((step, index) => (
              <motion.div
                key={index}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ delay: index * 0.1 }}
                className="relative"
              >
                <div className="text-6xl font-bold text-accent mb-4">{step.number}</div>
                <h3 className="text-xl font-semibold text-foreground mb-2">{step.title}</h3>
                <p className="text-muted-foreground">{step.description}</p>
                {index < steps.length - 1 && (
                  <div className="hidden lg:block absolute top-8 left-full w-full h-0.5 bg-accent -z-10" />
                )}
              </motion.div>
            ))}
          </div>
        </div>
      </section>

      {/* Testimonials */}
      <section className="max-w-7xl mx-auto px-6 py-20">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          className="text-center mb-16"
        >
          <h2 className="text-4xl font-bold text-foreground mb-4">What Educators Say</h2>
          <p className="text-xl text-muted-foreground">Trusted by thousands of educators worldwide</p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8">
          {testimonials.map((testimonial, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 20 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ delay: index * 0.1 }}
              className="bg-white rounded-xl p-6 shadow-lg"
            >
              <div className="flex gap-1 mb-4">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="w-5 h-5 fill-primary text-primary" />
                ))}
              </div>
              <p className="text-muted-foreground mb-4">{testimonial.content}</p>
              <div>
                <div className="font-semibold text-foreground">{testimonial.name}</div>
                <div className="text-sm text-muted-foreground">{testimonial.role}</div>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-foreground text-white py-12">
        <div className="max-w-7xl mx-auto px-6">
          <div className="grid md:grid-cols-4 gap-8">
            <div>
              <div className="flex items-center gap-2 mb-4">
                <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-primary to-secondary flex items-center justify-center">
                  <Brain className="w-6 h-6 text-white" />
                </div>
                <span className="text-xl font-semibold">ExamAI</span>
              </div>
              <p className="text-gray-400">AI-powered exam management platform for modern education.</p>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Product</h4>
              <ul className="space-y-2 text-gray-400">
                <li>Features</li>
                <li>Pricing</li>
                <li>Security</li>
                <li>Roadmap</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Company</h4>
              <ul className="space-y-2 text-gray-400">
                <li>About</li>
                <li>Blog</li>
                <li>Careers</li>
                <li>Contact</li>
              </ul>
            </div>
            <div>
              <h4 className="font-semibold mb-4">Legal</h4>
              <ul className="space-y-2 text-gray-400">
                <li>Privacy</li>
                <li>Terms</li>
                <li>Cookie Policy</li>
                <li>Licenses</li>
              </ul>
            </div>
          </div>
          <div className="border-t border-gray-800 mt-12 pt-8 text-center text-gray-400">
            <p>© 2026 ExamAI. All rights reserved.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
