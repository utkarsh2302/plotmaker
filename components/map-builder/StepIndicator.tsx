"use client";

const STEPS = [
  { n: 1, label: "Upload Image" },
  { n: 2, label: "Verify Plots" },
  { n: 3, label: "Excel & Publish" },
];

export default function StepIndicator({ current }: { current: 1 | 2 | 3 }) {
  return (
    <div className="flex items-center gap-0">
      {STEPS.map((step, i) => (
        <div key={step.n} className="flex items-center">
          <div className="flex items-center gap-2">
            <div
              className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold shrink-0"
              style={{
                background:
                  step.n < current
                    ? "#22c55e"
                    : step.n === current
                    ? "#0071e3"
                    : "rgba(0,0,0,0.1)",
                color:
                  step.n <= current ? "#fff" : "rgba(0,0,0,0.35)",
              }}
            >
              {step.n < current ? "✓" : step.n}
            </div>
            <span
              className="text-sm font-medium hidden sm:block"
              style={{
                color:
                  step.n === current
                    ? "#0071e3"
                    : step.n < current
                    ? "#16a34a"
                    : "rgba(0,0,0,0.38)",
              }}
            >
              {step.label}
            </span>
          </div>
          {i < STEPS.length - 1 && (
            <div
              className="w-10 h-px mx-2"
              style={{
                background:
                  step.n < current ? "#22c55e" : "rgba(0,0,0,0.12)",
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
