"use client";

import React, { useState } from "react";
import { PhoneCall, Copy, Check, MessageSquare, Target, Lightbulb } from "lucide-react";

export default function ColdCallingPlaybook() {
  const [copied, setCopied] = useState(false);

  const scriptText = `Sales Rep: "Hello, is this the owner or manager of [Business Name]?"
Owner: "Yes, speaking. What is this about?"
Sales Rep: "Namaste sir/ma'am. I was looking for services near [Area, e.g., Kudasan / Infocity] on Google. I noticed that while your competitors have their own website where customers view menus and book directly, your Google listing doesn't have an official website attached."
Owner: "Yes, we don't have one right now."
Sales Rep: "We help local businesses in Gandhinagar get an affordable, clean website set up in 48 hours to get direct customer orders without hefty platform commissions. Would it be okay if I sent a 1-minute WhatsApp preview demo of what your website could look like?"`;

  const copyToClipboard = () => {
    navigator.clipboard.writeText(scriptText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-slate-900/80 backdrop-blur-md border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/80 pb-4">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
            <PhoneCall className="w-5 h-5" />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-white tracking-wide">
              Cold Calling & Outreach Playbook
            </h3>
            <p className="text-xs text-slate-400">
              Battle-tested telephone pitch templates tailored for Gandhinagar and local stores
            </p>
          </div>
        </div>

        <button
          onClick={copyToClipboard}
          className="flex items-center gap-1.5 text-xs bg-slate-800 hover:bg-slate-700 text-slate-200 px-3 py-1.5 rounded-lg border border-slate-700 transition-colors self-start sm:self-auto"
        >
          {copied ? (
            <>
              <Check className="w-3.5 h-3.5 text-emerald-400" />
              <span className="text-emerald-400">Copied!</span>
            </>
          ) : (
            <>
              <Copy className="w-3.5 h-3.5 text-slate-400" />
              <span>Copy Full Script</span>
            </>
          )}
        </button>
      </div>

      {/* The Dialogue Flow */}
      <div className="space-y-3 font-sans text-xs">
        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 space-y-1">
          <span className="text-indigo-400 font-semibold uppercase tracking-wider text-[10px]">
            1. Opening & Verification
          </span>
          <p className="text-slate-200">
            <strong className="text-white">You:</strong> &quot;Hello, is this the owner or manager of <span className="text-indigo-300 font-mono">[Business Name]</span>?&quot;
          </p>
          <p className="text-slate-400 italic">
            <strong className="text-slate-300">Owner:</strong> &quot;Yes, speaking. What is this about?&quot;
          </p>
        </div>

        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 space-y-1">
          <span className="text-indigo-400 font-semibold uppercase tracking-wider text-[10px]">
            2. The Hook & The Gap
          </span>
          <p className="text-slate-200">
            <strong className="text-white">You:</strong> &quot;Namaste sir/ma&apos;am. I was looking for services near <span className="text-indigo-300 font-mono">[Kudasan / Infocity / Sector 11]</span> on Google. I noticed that while your competitors have their own website where customers book directly, your Google listing doesn&apos;t have an official website attached.&quot;
          </p>
          <p className="text-slate-400 italic">
            <strong className="text-slate-300">Owner:</strong> &quot;Yes, we don&apos;t have one right now.&quot;
          </p>
        </div>

        <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800/80 space-y-1">
          <span className="text-emerald-400 font-semibold uppercase tracking-wider text-[10px]">
            3. The 48-Hour Low-Friction Close
          </span>
          <p className="text-slate-200">
            <strong className="text-white">You:</strong> &quot;We help local businesses in Gandhinagar get an affordable, clean website set up in 48 hours to get direct customer orders without hefty platform commissions. Would it be okay if I sent a 1-minute WhatsApp preview demo of what your website could look like?&quot;
          </p>
        </div>
      </div>

      {/* Category Pitch Angles Quick Reference */}
      <div className="space-y-2 pt-2">
        <h4 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
          <Lightbulb className="w-3.5 h-3.5 text-amber-400" />
          High-Converting Category Angles
        </h4>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
            <div className="font-semibold text-indigo-300">Auto Garage / Workshop</div>
            <div className="text-slate-400 text-[11px]">
              &quot;Online breakdown assistance and WhatsApp service slot booking&quot;
            </div>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
            <div className="font-semibold text-indigo-300">Cafe / Restaurant</div>
            <div className="text-slate-400 text-[11px]">
              &quot;Save 25-30% commissions on Swiggy/Zomato with a direct online menu&quot;
            </div>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
            <div className="font-semibold text-indigo-300">Clinic / Dentist</div>
            <div className="text-slate-400 text-[11px]">
              &quot;Automated patient slot booking with zero receptionist queueing&quot;
            </div>
          </div>
          <div className="bg-slate-950/60 p-2.5 rounded-lg border border-slate-800">
            <div className="font-semibold text-indigo-300">Hardware / Boutique</div>
            <div className="text-slate-400 text-[11px]">
              &quot;Interactive digital product showcase with direct WhatsApp quotation&quot;
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
