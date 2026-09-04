"use client";

import React, { useState } from "react";
import {
  MapPin,
  Layers,
  Hash,
  Zap,
  Sparkles,
  Loader2,
  X,
  Plus,
  Check,
  Square,
} from "lucide-react";
import { ScanRequest } from "@/lib/api";

interface LeadSearchFormProps {
  onStartScan: (req: ScanRequest) => void;
  onStopScan?: () => void;
  isScanning: boolean;
}

const CATEGORY_PRESETS = [
  "Cafe",
  "Garage",
  "Restaurant",
  "Clinic",
  "Dentist",
  "Pharmacy",
  "Hardware Store",
  "Salon",
  "Boutique",
];

const LOCATION_PRESETS = [
  "Surat, Gujarat",
  "Gandhinagar, Gujarat",
  "Ahmedabad, Gujarat",
  "Vadodara, Gujarat",
];

const LIMIT_PRESETS = [5, 10, 20, 50];

export default function LeadSearchForm({ onStartScan, onStopScan, isScanning }: LeadSearchFormProps) {
  const [location, setLocation] = useState("Surat, Gujarat");
  const [selectedCategories, setSelectedCategories] = useState<string[]>(["Cafe", "Garage"]);
  const [customCategoryInput, setCustomCategoryInput] = useState("");
  const [limit, setLimit] = useState(5);
  const [useMock, setUseMock] = useState(false);

  const toggleCategory = (cat: string) => {
    if (isScanning) return;
    setSelectedCategories((prev) => {
      if (prev.includes(cat)) {
        // Keep at least one category selected
        if (prev.length === 1) return prev;
        return prev.filter((c) => c !== cat);
      } else {
        return [...prev, cat];
      }
    });
  };

  const addCustomCategory = () => {
    const trimmed = customCategoryInput.trim();
    if (!trimmed || isScanning) return;
    if (!selectedCategories.some((c) => c.toLowerCase() === trimmed.toLowerCase())) {
      setSelectedCategories((prev) => [...prev, trimmed]);
    }
    setCustomCategoryInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      e.preventDefault();
      addCustomCategory();
    }
  };

  const removeCategory = (cat: string) => {
    if (isScanning || selectedCategories.length <= 1) return;
    setSelectedCategories((prev) => prev.filter((c) => c !== cat));
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!location.trim() || selectedCategories.length === 0) return;
    onStartScan({
      location: location.trim(),
      categories: selectedCategories,
      limit: Math.max(1, Math.min(100, limit)),
      use_mock: useMock,
    });
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="bg-white/90 backdrop-blur-md border border-slate-200 rounded-2xl p-6 shadow-2xl relative overflow-hidden"
    >
      <div className="absolute top-0 right-0 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none -mr-20 -mt-20" />

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative z-10">
        {/* 1. Target Location Input */}
        <div className="space-y-2 md:col-span-1">
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
            <MapPin className="w-3.5 h-3.5 text-indigo-400" />
            Target Location / Any City
          </label>
          <div className="relative">
            <input
              type="text"
              value={location}
              onChange={(e) => setLocation(e.target.value)}
              disabled={isScanning}
              placeholder="e.g. Surat, Gujarat"
              className="w-full bg-slate-50/80 border border-slate-300 focus:border-indigo-500 rounded-xl px-4 py-3 text-sm text-slate-900 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/20 transition-all disabled:opacity-60"
            />
          </div>
          {/* Location quick chips */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {LOCATION_PRESETS.map((loc) => (
              <button
                key={loc}
                type="button"
                onClick={() => setLocation(loc)}
                disabled={isScanning}
                className={`text-[11px] px-2.5 py-1 rounded-lg border transition-colors ${
                  location === loc
                    ? "bg-indigo-50 text-indigo-700 border-indigo-200"
                    : "bg-slate-100 text-slate-600 border-slate-200 hover:text-slate-900"
                }`}
              >
                {loc.split(",")[0]}
              </button>
            ))}
          </div>
        </div>

        {/* 2. Multi-Category Selector */}
        <div className="space-y-2 md:col-span-1">
          <div className="flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
              <Layers className="w-3.5 h-3.5 text-indigo-400" />
              Target Categories ({selectedCategories.length} selected)
            </label>
          </div>

          {/* Active Selected Tags */}
          <div className="flex flex-wrap gap-1.5 min-h-[38px] p-2 bg-slate-50 border border-slate-300 rounded-xl">
            {selectedCategories.map((cat) => (
              <span
                key={cat}
                className="inline-flex items-center gap-1 bg-indigo-100 text-indigo-800 border border-indigo-200 px-2.5 py-1 rounded-lg text-xs font-medium"
              >
                {cat}
                {selectedCategories.length > 1 && !isScanning && (
                  <button
                    type="button"
                    onClick={() => removeCategory(cat)}
                    className="hover:text-slate-900 transition-colors"
                  >
                    <X className="w-3 h-3" />
                  </button>
                )}
              </span>
            ))}
          </div>

          {/* Add custom tag input */}
          <div className="flex gap-1.5 pt-1">
            <input
              type="text"
              value={customCategoryInput}
              onChange={(e) => setCustomCategoryInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isScanning}
              placeholder="Type custom niche & press Enter..."
              className="flex-1 bg-slate-50 border border-slate-300 focus:border-indigo-500 rounded-lg px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 focus:outline-none"
            />
            <button
              type="button"
              onClick={addCustomCategory}
              disabled={!customCategoryInput.trim() || isScanning}
              className="bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1.5 rounded-lg text-xs border border-slate-200 flex items-center gap-1 disabled:opacity-40"
            >
              <Plus className="w-3 h-3" />
              Add
            </button>
          </div>

          {/* Multi-Select Category Pills */}
          <div className="flex flex-wrap gap-1.5 pt-1">
            {CATEGORY_PRESETS.map((cat) => {
              const isSelected = selectedCategories.includes(cat);
              return (
                <button
                  key={cat}
                  type="button"
                  onClick={() => toggleCategory(cat)}
                  disabled={isScanning}
                  className={`text-[11px] px-2.5 py-1 rounded-lg border transition-all flex items-center gap-1 ${
                    isSelected
                      ? "bg-indigo-600 text-white border-indigo-500 shadow-sm"
                      : "bg-slate-100 text-slate-600 border-slate-200 hover:text-slate-900"
                  }`}
                >
                  {isSelected && <Check className="w-3 h-3" />}
                  {cat}
                </button>
              );
            })}
          </div>
        </div>

        {/* 3. Limit (Cap) & Execution */}
        <div className="space-y-2 md:col-span-1 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <label className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <Hash className="w-3.5 h-3.5 text-indigo-400" />
                Lead Limit (Strict Cap)
              </label>
              <span className="text-[11px] font-mono text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                Target: {limit} leads
              </span>
            </div>

            <div className="flex items-center gap-3 mt-2">
              <input
                type="range"
                min="1"
                max="50"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value))}
                disabled={isScanning}
                className="w-full accent-indigo-500 h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer disabled:opacity-60"
              />
              <input
                type="number"
                min="1"
                max="100"
                value={limit}
                onChange={(e) => setLimit(Math.max(1, Math.min(100, parseInt(e.target.value) || 1)))}
                disabled={isScanning}
                className="w-16 text-center font-mono font-bold bg-slate-50 border border-slate-300 rounded-lg py-1.5 text-sm text-slate-900"
              />
            </div>

            {/* Quick Limit Presets */}
            <div className="flex gap-2 pt-2">
              {LIMIT_PRESETS.map((p) => (
                <button
                  key={p}
                  type="button"
                  onClick={() => setLimit(p)}
                  disabled={isScanning}
                  className={`text-[11px] font-mono px-2 py-0.5 rounded border transition-colors ${
                    limit === p
                      ? "bg-indigo-600 text-white border-indigo-500"
                      : "bg-slate-100 text-slate-600 border-slate-200 hover:text-slate-900"
                  }`}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>

          {/* Action CTA */}
          <div className="pt-4 flex flex-col gap-3">
            {isScanning ? (
              <button
                type="button"
                onClick={onStopScan}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-rose-600 to-rose-500 hover:from-rose-500 hover:to-rose-400 text-white font-semibold py-3.5 px-6 rounded-xl shadow-lg shadow-rose-500/25 transition-all cursor-pointer animate-pulse"
              >
                <Square className="w-4 h-4 fill-current" />
                <span>Stop Scan</span>
              </button>
            ) : (
              <button
                type="submit"
                disabled={selectedCategories.length === 0}
                className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-indigo-500 hover:from-indigo-500 hover:to-indigo-400 text-white font-medium py-3.5 px-6 rounded-xl shadow-lg shadow-indigo-500/25 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <Zap className="w-4 h-4 fill-current" />
                <span>Start Live Scan ({selectedCategories.length} Categories, Cap: {limit})</span>
              </button>
            )}
          </div>
        </div>
      </div>
    </form>
  );
}
