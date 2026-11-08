from pathlib import Path

def extract_project_intent(repo_root: str, project_name: str) -> str:
    proj_dir = Path(repo_root) / project_name
    readme_candidates = [
        proj_dir / "README.md",
        proj_dir / "readme.md",
        proj_dir / "docs" / "README.md",
    ]
    for r in readme_candidates:
        if r.exists():
            try:
                lines = r.read_text(encoding="utf-8", errors="replace").splitlines()
                # Find first non-header, non-badge paragraph
                para = []
                for line in lines:
                    s = line.strip()
                    if not s or s.startswith("#") or s.startswith("[!") or s.startswith("[![") or s.startswith("```"):
                        if para:
                            break
                        continue
                    para.append(s)
                    if len(para) >= 3:
                        break
                if para:
                    return " ".join(para)[:280]
            except Exception:
                pass
    return f"Modular software project '{project_name}' comprising reusable domain components and utility suites."

print("codbot3:", extract_project_intent("C:/Dev", "codbot3"))
print("brickForge:", extract_project_intent("C:/Dev", "brickForge"))
print("RepoScroller:", extract_project_intent("C:/Dev", "RepoScroller"))
