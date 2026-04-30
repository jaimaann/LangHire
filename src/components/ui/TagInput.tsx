import { Plus, X } from "lucide-react";

interface TagInputProps {
  tags: string[];
  value: string;
  onChange: (value: string) => void;
  onAdd: () => void;
  onRemove: (tag: string) => void;
  placeholder?: string;
  variant?: "default" | "destructive";
}

export default function TagInput({ tags, value, onChange, onAdd, onRemove, placeholder = "Add...", variant = "default" }: TagInputProps) {
  const tagColors = variant === "destructive"
    ? "bg-[#FFF0F0] text-destructive"
    : "bg-secondary text-foreground";

  return (
    <div>
      <div className="flex gap-2 mb-3">
        <input
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), onAdd())}
          placeholder={placeholder}
          className="input-base flex-1"
        />
        <button onClick={onAdd} className="btn-primary !px-3">
          <Plus className="w-4 h-4" />
        </button>
      </div>
      <div className="flex flex-wrap gap-2">
        {tags.map((tag) => (
          <span key={tag} className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-[13px] font-semibold ${tagColors}`}>
            {tag}
            <button onClick={() => onRemove(tag)} className="hover:opacity-60">
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
}
