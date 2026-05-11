"""Resume tailoring module — LLM-powered PDF customization per job."""
from .tailor import tailor_resume, refine_resume, get_tailored_content, delete_tailored_resume

__all__ = ["tailor_resume", "refine_resume", "get_tailored_content", "delete_tailored_resume"]
