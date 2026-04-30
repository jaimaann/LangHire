export function getLogLineColor(line: string): string {
  if (line.includes("✅") || line.includes("💾")) return "text-green-400";
  if (line.includes("❌")) return "text-red-400";
  if (line.includes("📍")) return "text-cyan-400 font-semibold mt-2";
  if (line.includes("🎯")) return "text-yellow-300";
  if (line.includes("👍")) return "text-green-300";
  if (line.includes("🧠")) return "text-purple-400";
  if (line.includes("▶️") || line.includes("🖱️")) return "text-gray-500";
  if (line.includes("⚠️")) return "text-amber-400";
  if (line.includes("🤖")) return "text-blue-400";
  return "";
}

export default function LogLine({ line }: { line: string }) {
  return <div className={`leading-relaxed ${getLogLineColor(line)}`}>{line}</div>;
}
