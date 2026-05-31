"use client";

import { useEffect, useState, useRef } from "react";

interface SceneData {
  title?: string;
  word_count?: number;
  has_formatting?: boolean;
  has_sources?: boolean;
}

export default function DocumentSimulation({ data, progress }: { data?: SceneData; progress?: number }) {
  const [displayText, setDisplayText] = useState("");
  const [showFormatting, setShowFormatting] = useState(false);
  const [showSources, setShowSources] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const sampleTexts = [
    "The rapid advancement of artificial intelligence has transformed numerous industries, from healthcare to finance. Machine learning algorithms now process vast amounts of data, identifying patterns that would be impossible for humans to detect manually. This capability has led to breakthroughs in medical diagnosis, where AI systems can analyze medical images with accuracy comparable to or exceeding that of human experts.\n\nIn the field of natural language processing, large language models have demonstrated remarkable abilities in understanding and generating human-like text. These models, trained on diverse corpora spanning multiple languages and domains, can engage in coherent dialogue, answer questions, and even assist with creative writing tasks.\n\nThe economic implications are equally significant. According to recent studies, AI adoption could contribute up to $15.7 trillion to the global economy by 2030. This growth is driven by productivity gains, improved decision-making, and the creation of new products and services (Smith et al., 2025).",
    "Climate change represents one of the most pressing challenges of our time. Global temperatures have risen by approximately 1.1°C since pre-industrial times, with profound consequences for ecosystems worldwide. The Intergovernmental Panel on Climate Change (IPCC) has documented increasing frequency of extreme weather events, rising sea levels, and biodiversity loss.\n\nHowever, technological innovation offers pathways toward mitigation. Renewable energy sources, particularly solar and wind, have seen dramatic cost reductions over the past decade. In many regions, they now represent the most economical options for new electricity generation. Energy storage technologies continue to improve, addressing the intermittency challenges that have historically limited renewable adoption.\n\nFurthermore, carbon capture and storage (CCS) technologies, while still in relatively early stages of deployment, hold promise for addressing emissions from existing industrial infrastructure. Policy frameworks, including carbon pricing mechanisms and clean energy standards, play a crucial role in accelerating the transition (Johnson & Williams, 2026).",
  ];

  const title = data?.title || "Document";
  const sampleText = sampleTexts[Math.floor(Math.random() * sampleTexts.length)];

  useEffect(() => {
    setDisplayText("");
    setShowFormatting(false);
    setShowSources(false);

    let idx = 0;
    const interval = setInterval(() => {
      if (idx < sampleText.length) {
        setDisplayText(sampleText.slice(0, idx + 1));
        idx++;
      } else {
        clearInterval(interval);
        setShowFormatting(true);
        setTimeout(() => setShowSources(true), 500);
      }
    }, 15);

    return () => clearInterval(interval);
  }, [data?.title]);

  return (
    <div className="w-full h-full flex flex-col items-center justify-start p-4 overflow-hidden">
      {/* Word document frame */}
      <div className="w-full max-w-lg bg-white/5 backdrop-blur-sm border border-white/10 rounded-lg overflow-hidden shadow-2xl">
        {/* Ribbon */}
        <div className="flex items-center gap-1 px-2 py-1 bg-gradient-to-r from-blue-900/30 to-purple-900/30 border-b border-white/10">
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/5 rounded">File</span>
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/5 rounded">Home</span>
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/10 rounded">Insert</span>
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/5 rounded">Design</span>
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/5 rounded">Layout</span>
          <span className="text-[8px] font-mono text-white/50 px-1.5 py-0.5 bg-white/5 rounded">References</span>
          <div className="flex-1" />
          <span className="text-[7px] font-mono text-white/30">{data?.word_count || "—"} words</span>
        </div>

        {/* Toolbar */}
        {showFormatting && (
          <div className="flex items-center gap-1 px-2 py-1 bg-white/5 border-b border-white/5 animate-fadeIn">
            <span className="text-[9px] font-mono text-white/60 px-1 bg-white/5 rounded">Calibri</span>
            <span className="text-[9px] font-mono text-white/60 px-1 bg-white/5 rounded">11</span>
            <div className="w-px h-3 bg-white/10 mx-1" />
            <span className="text-[10px] text-white/50 font-bold">B</span>
            <span className="text-[10px] text-white/50 italic">I</span>
            <span className="text-[10px] text-white/50 underline">U</span>
            <div className="w-px h-3 bg-white/10 mx-1" />
            <span className="text-[9px] text-white/40">≡</span>
            <span className="text-[9px] text-white/40">☰</span>
          </div>
        )}

        {/* Content */}
        <div
          ref={contentRef}
          className="p-4 min-h-[200px] max-h-[300px] overflow-y-auto"
        >
          {displayText && (
            <div className="text-[10px] leading-relaxed text-white/70 whitespace-pre-wrap font-serif">
              {displayText}
              <span className="inline-block w-0.5 h-3 bg-blue-400/60 animate-pulse ml-0.5" />
            </div>
          )}
          {!displayText && (
            <div className="flex items-center justify-center h-[200px]">
              <div className="text-white/20 text-xs font-mono animate-pulse">Generating content...</div>
            </div>
          )}
        </div>

        {/* Footer / Sources */}
        {showSources && (
          <div className="border-t border-white/5 px-4 py-2 animate-fadeIn">
            <div className="text-[7px] font-mono text-white/30 mb-1">REFERENCES</div>
            <div className="text-[7px] font-mono text-white/40 leading-relaxed">
              Smith, J., et al. (2025). AI and Economic Growth. <span className="italic">Journal of Technology Economics</span>, 42(3), 115-132.
            </div>
            <div className="text-[7px] font-mono text-white/40 leading-relaxed">
              Johnson, R., &amp; Williams, T. (2026). Climate Policy and Innovation. <span className="italic">Environmental Science Review</span>, 18(2), 45-67.
            </div>
          </div>
        )}
      </div>

      {/* Progress */}
      <div className="mt-3 w-full max-w-lg">
        <div className="flex justify-between text-[8px] font-mono text-white/30 mb-1">
          <span>Writing...</span>
          <span>{progress || 0}%</span>
        </div>
        <div className="w-full h-0.5 bg-white/5 rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 rounded-full transition-all duration-300"
            style={{ width: `${progress || 0}%` }}
          />
        </div>
      </div>
    </div>
  );
}
