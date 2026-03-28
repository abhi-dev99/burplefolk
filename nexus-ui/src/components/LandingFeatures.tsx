import React, { useRef } from "react";
import { motion, useScroll, useTransform, useSpring } from "framer-motion";
import { Database, BrainCircuit, ShieldCheck, Mail } from "lucide-react";
import clsx from "clsx";

interface NodeProps {
  title: string;
  desc: string;
  icon: React.ReactNode;
  align: "left" | "right";
}

function Node({ title, desc, icon, align }: NodeProps) {
  return (
    <motion.div
      initial={{ opacity: 0, x: align === "left" ? 40 : -40 }}
      whileInView={{ opacity: 1, x: 0 }}
      viewport={{ once: true, margin: "-15%" }}
      transition={{ duration: 1, ease: [0.16, 1, 0.3, 1] }}
      className={clsx(
        "relative flex items-center w-full my-32",
        align === "left" ? "justify-start" : "justify-end"
      )}
    >
      <div
        className={clsx(
          "w-1/2 relative",
          align === "left" ? "pr-12 md:pr-24 text-right" : "pl-12 md:pl-24 text-left"
        )}
      >
        {/* Connection Line to Center Spine */}
        <div
          className={clsx(
            "absolute top-1/2 w-8 md:w-16 h-px bg-black/10 dark:bg-white/10 hidden md:block",
            align === "left" ? "right-6" : "left-6"
          )}
        />

        {/* Node Icon Exactly on Spine */}
        <div
          className={clsx(
            "absolute top-1/2 -translate-y-1/2 w-12 h-12 rounded-full border border-black/10 dark:border-white/10 bg-white/70 dark:bg-[#0b1220]/70 backdrop-blur-xl flex items-center justify-center shadow-sm z-10",
            align === "left" ? "-right-6" : "-left-6"
          )}
        >
          {icon}
        </div>

        <h3 className="text-3xl md:text-5xl font-light tracking-tight text-neutral-900 dark:text-neutral-100 mb-4 md:mb-6 font-inter">
          {title}
        </h3>
        <p
          className={clsx(
            "text-base md:text-xl font-light text-neutral-500 dark:text-neutral-400 leading-relaxed max-w-sm",
            align === "left" ? "ml-auto" : "mr-auto"
          )}
        >
          {desc}
        </p>
      </div>
    </motion.div>
  );
}

export default function LandingFeatures() {
  const containerRef = useRef<HTMLDivElement>(null);

  const { scrollYProgress } = useScroll({
    target: containerRef,
    offset: ["start center", "end end"],
  });

  const smoothProgress = useSpring(scrollYProgress, {
    stiffness: 40,
    damping: 15,
    restDelta: 0.001,
  });

  const torchOpacity = useTransform(smoothProgress, [0.7, 1], [0, 1]);
  const torchScale = useTransform(smoothProgress, [0.7, 1], [0.8, 1]);

  return (
    <section
      ref={containerRef}
      className="relative w-full pb-40 overflow-hidden print-hidden bg-transparent"
    >
      {/* Central Spine System */}
      <div className="absolute left-1/2 top-0 bottom-32 w-px bg-gradient-to-b from-transparent via-black/10 dark:via-white/10 to-transparent -translate-x-1/2" />

      {/* Animated Glowing Traced Spine */}
      <motion.div
        className="absolute left-1/2 top-0 bottom-32 w-[2px] bg-gradient-to-b from-transparent via-[#0059B5] dark:via-[#60A5FA] to-transparent -translate-x-1/2 origin-top shadow-[0_0_15px_rgba(0,89,181,0.5)]"
        style={{ scaleY: smoothProgress }}
      />

      <div className="relative max-w-5xl mx-auto px-6 pt-20">
        <Node
          align="left"
          icon={
            <BrainCircuit className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
          }
          title="Autonomous Intelligence"
          desc="Nexus constantly evaluates incoming schemas with zero manual mapping. Let the engine silently monitor for anomalies while you build."
        />

        <Node
          align="right"
          icon={
            <Database className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
          }
          title="Relational Profiling"
          desc="High-performance distribution metrics. Generates precise histograms for million-row datasets seamlessly."
        />

        <Node
          align="left"
          icon={
            <ShieldCheck className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
          }
          title="Data Guardrails"
          desc="Instantly identify null-heavy fields, PII leaks, and dirty records. Structural profiling that catches bad actors before they hit production."
        />

        <Node
          align="right"
          icon={
            <Mail className="w-5 h-5 text-[#0059B5] dark:text-[#60A5FA]" />
          }
          title="Email Agent Integration"
          desc="Securely link a runtime LLM agent to actively monitor and execute natural language queries against your schema autonomously over email."
        />
      </div>

      {/* The Grok/GitHub Structural Core at the Bottom (Refined, no slop) */}
      <motion.div
        className="relative mt-32 w-full max-w-4xl mx-auto flex flex-col items-center justify-center pt-24"
        style={{ opacity: torchOpacity, scale: torchScale }}
      >
        {/* Soft, deep ambient light instead of an abrupt generic blur */}
        <div className="absolute bottom-0 w-[100vw] h-[50vh] bg-gradient-to-t from-[#0059B5]/10 dark:from-[#60A5FA]/10 via-[#0059B5]/5 to-transparent blur-[120px] rounded-full pointer-events-none -z-10" />

        {/* Structural floor lines */}
        <div className="w-full h-px bg-gradient-to-r from-transparent via-black/10 dark:via-white/10 to-transparent" />
        <div className="absolute w-[40%] h-[2px] bg-gradient-to-r from-transparent via-[#0059B5] dark:via-[#60A5FA] to-transparent shadow-[0_0_20px_rgba(0,89,181,0.8)] mix-blend-screen" />

        <div className="mt-16 text-center relative z-10 flex flex-col items-center">
          <div className="w-3 h-3 rounded-full bg-[#0059B5] dark:bg-[#60A5FA] mb-10 shadow-[0_0_20px_rgba(0,89,181,1)] ring-8 ring-[#0059B5]/20 dark:ring-[#60A5FA]/20" />
          
          <h4 className="text-3xl md:text-5xl font-light tracking-tight text-neutral-900 dark:text-neutral-100 mb-6 font-inter">
            The structural truth of your data.
          </h4>
        </div>
      </motion.div>

      {/* Structural Footer */}
      <footer className="relative z-10 w-full mt-40 border-t border-black/10 dark:border-white/10 pt-24 pb-12 px-6">
        <div className="max-w-5xl mx-auto flex flex-col items-center">
          
          <h2 className="text-2xl md:text-3xl font-light text-neutral-900 dark:text-neutral-100 mb-8 font-inter">
            Ready to analyze your datastore?
          </h2>
          
          <button 
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: 'smooth' })}
            className="px-8 py-4 bg-gradient-to-tr from-[#004289] to-[#0059B5] text-white rounded-2xl font-medium shadow-[0_4px_20px_rgba(0,89,181,0.3)] hover:opacity-90 hover:-translate-y-1 transition-all"
          >
            Start Analyzing Now
          </button>

          <div className="w-full flex flex-col md:flex-row justify-between items-center mt-32 pt-8 border-t border-black/5 dark:border-white/5 text-sm text-neutral-500 font-light space-y-4 md:space-y-0">
            <span>&copy; {new Date().getFullYear()} Nexus Intelligence. All rights reserved.</span>
            <div className="flex space-x-8">
              <a href="#" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Documentation</a>
              <a href="#" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Privacy</a>
              <a href="#" className="hover:text-neutral-900 dark:hover:text-white transition-colors">Terms</a>
            </div>
          </div>
        </div>
      </footer>
    </section>
  );
}
