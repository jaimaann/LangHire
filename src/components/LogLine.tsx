import { getLogLineColor } from "../lib/logLineColor";

export default function LogLine({ line }: { line: string }) {
  return <div className={`leading-relaxed ${getLogLineColor(line)}`}>{line}</div>;
}
