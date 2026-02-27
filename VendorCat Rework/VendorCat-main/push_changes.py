#!/usr/bin/env python3
"""
Git push helper script - bypasses terminal pager issues
Stages all changes, commits, and pushes to current branch
"""
import subprocess
import sys
from pathlib import Path

def run_command(cmd, cwd=None, capture=True):
    """Run a command and return output"""
    try:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            shell=True,
            text=True,
            capture_output=capture,
            timeout=60
        )
        if capture:
            return result.returncode, result.stdout, result.stderr
        return result.returncode, "", ""
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except Exception as e:
        return -1, "", str(e)

def main():
    repo_root = Path(__file__).parent
    print("🚀 Git Push Helper Script")
    print(f"📁 Repository: {repo_root}")
    print()
    
    # Get current branch
    code, stdout, stderr = run_command("git rev-parse --abbrev-ref HEAD", cwd=repo_root)
    if code != 0:
        print(f"❌ Failed to get current branch: {stderr}")
        return 1
    
    branch = stdout.strip()
    print(f"🌿 Current branch: {branch}")
    print()
    
    # Get status
    print("📋 Checking status...")
    code, stdout, stderr = run_command("git status --short", cwd=repo_root)
    if code != 0:
        print(f"❌ Failed to get status: {stderr}")
        return 1
    
    lines = stdout.strip().split('\n')
    file_count = len([l for l in lines if l.strip()])
    print(f"   Found {file_count} changed files")
    print()
    
    # Stage all changes
    print("📦 Staging all changes...")
    code, stdout, stderr = run_command("git add -A", cwd=repo_root)
    if code != 0:
        print(f"❌ Failed to stage: {stderr}")
        return 1
    print("   ✓ All files staged")
    print()
    
    # Commit with comprehensive message
    print("💾 Creating commit...")
    commit_message = """feat: Add Help Center with embedded articles and screenshot automation

WHAT:
- Complete Help Center implementation with 30+ workflow articles
- Help feedback and issue reporting system
- Article search and navigation with role-based visibility
- Screenshot automation for documentation maintenance
- Markdown rendering with XSS protection
- Dark mode implementation support
- Various UI improvements (help buttons, better forms)

WHY:
- Reduce onboarding time with contextual in-app help
- Capture user feedback and issues directly in the app
- Maintain screenshot documentation automatically
- Improve UX with dark mode and help links

HOW:
Help Center Backend:
- vendor_help_article, vendor_help_feedback, vendor_help_issue tables
- repository_help.py mixin with article CRUD
- help_validator.py for content quality checks
- Seeded with 33 articles covering all workflows

Help Center Frontend:
- /help routes with search, navigation, article rendering
- Role-based article visibility (viewer/editor/admin)
- Feedback thumbs up/down with comments
- Issue reporting form
- Safe markdown rendering with bleach sanitization

Screenshot Automation:
- tests/e2e/help_screenshots.py using Playwright
- Captures 15+ key pages at 1280x1024
- Saves to static/help/screenshots/
- Can run standalone or in CI/CD
- Documented in SCREENSHOT_MAINTENANCE.md

UI Enhancements:
- Help buttons added to 10+ pages (vendor detail, offering pages, projects)
- Dark mode CSS framework (ready for toggle implementation)
- Port fallback for local development (launch_app.bat)
- Improved form layouts and navigation

IMPACT:
- Self-service help reduces support burden
- Contextual help improves task completion
- Screenshot automation keeps docs in sync
- Foundation for training paths and guided tours
- Dark mode improves accessibility

FILES CHANGED:
- 30+ Help Center files (routes, templates, SQL, validators)
- 10+ template updates (help button additions)
- Schema updates (3 new help tables in Databricks and SQLite)
- Screenshot automation script and documentation
- Dark mode CSS additions
- Launch script improvements

Co-authored-by: GitHub Copilot <noreply@github.com>"""
    
    # Write commit message to temp file to avoid shell escaping issues
    msg_file = repo_root / "temp_commit_msg.txt"
    msg_file.write_text(commit_message, encoding='utf-8')
    
    code, stdout, stderr = run_command(f'git commit -F "{msg_file}"', cwd=repo_root)
    msg_file.unlink()  # Clean up temp file
    
    if code != 0:
        if "nothing to commit" in stdout or "nothing to commit" in stderr:
            print("   ℹ️  No changes to commit (already committed)")
        else:
            print(f"❌ Failed to commit: {stderr}")
            return 1
    else:
        print("   ✓ Commit created")
    print()
    
    # Show commit info
    print("📝 Commit details:")
    code, stdout, stderr = run_command("git log -1 --oneline", cwd=repo_root)
    if code == 0:
        print(f"   {stdout.strip()}")
    print()
    
    # Push to remote
    print(f"🔼 Pushing to origin/{branch}...")
    code, stdout, stderr = run_command(f"git push origin {branch}", cwd=repo_root)
    if code != 0:
        print(f"❌ Failed to push: {stderr}")
        print(f"   stdout: {stdout}")
        return 1
    print("   ✓ Push successful")
    print()
    
    print("✅ All operations completed successfully!")
    print()
    print("Next steps:")
    print(f"   1. View your changes: https://github.com/PrideRock-CoPilot/VendorCat/tree/{branch}")
    print(f"   2. Create PR if needed: https://github.com/PrideRock-CoPilot/VendorCat/compare/{branch}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
