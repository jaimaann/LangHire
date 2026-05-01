import { AlertTriangle, Clock, Globe, X } from "lucide-react";

interface AutomationDialogProps {
  open: boolean;
  title: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export default function AutomationDialog({ open, title, onConfirm, onCancel }: AutomationDialogProps) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40" onClick={onCancel}>
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-lg mx-4 overflow-hidden" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between px-6 pt-6 pb-0">
          <h2 className="text-lg font-bold text-foreground">{title}</h2>
          <button onClick={onCancel} className="p-1.5 rounded-lg hover:bg-secondary transition-colors cursor-pointer">
            <X className="w-5 h-5 text-muted-foreground" />
          </button>
        </div>

        <div className="px-6 py-5 space-y-4">
          <div className="flex gap-3 p-4 bg-amber-50 border border-amber-200 rounded-xl">
            <Clock className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-amber-900">
              <strong className="block mb-1">This may take a while</strong>
              The automation needs time to launch a browser, load pages, and interact with websites.
              Please be patient and <strong>do not close the app</strong> while it's running.
            </div>
          </div>

          <div className="flex gap-3 p-4 bg-blue-50 border border-blue-200 rounded-xl">
            <Globe className="w-5 h-5 text-blue-600 flex-shrink-0 mt-0.5" />
            <div className="text-sm text-blue-900">
              <strong className="block mb-1">First-time login required</strong>
              On the first run, the browser will open LinkedIn and Google login pages.
              You'll need to <strong>log in manually</strong> once — after that, your session cookies
              are saved and future runs will log in automatically.
            </div>
          </div>

          <div className="flex gap-3 p-4 bg-[#F7F7F7] border border-border rounded-xl">
            <AlertTriangle className="w-5 h-5 text-muted-foreground flex-shrink-0 mt-0.5" />
            <div className="text-sm text-foreground">
              <strong className="block mb-1">Keep the browser window open</strong>
              A Chromium window will appear — this is the AI agent working. Don't close it or
              interact with it unless you need to log in.
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 px-6 pb-6">
          <button onClick={onCancel} className="btn-secondary">Cancel</button>
          <button onClick={onConfirm} className="btn-dark">Got it, Start</button>
        </div>
      </div>
    </div>
  );
}
