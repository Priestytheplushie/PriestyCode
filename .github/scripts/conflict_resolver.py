# .github/scripts/conflict_resolver.py

import os
import subprocess
import re
from github import Github #type: ignore

# --- Configuration from Environment Variables ---
GH_TOKEN = os.environ["GH_TOKEN"]
REPO_NAME = os.environ["REPO_NAME"]
PR_NUMBER = int(os.environ["PR_NUMBER"])
BASE_BRANCH = os.environ["BASE_BRANCH"]
HEAD_BRANCH = os.environ["HEAD_BRANCH"]
BOT_USERNAME = os.environ["BOT_USERNAME"]
BOT_REVIEW_TAG = os.environ["BOT_REVIEW_TAG"]

# --- Initialize API Clients ---
g = Github(GH_TOKEN)
repo = g.get_repo(REPO_NAME)
pr = repo.get_pull(PR_NUMBER)

# --- Helper Functions ---
def run_command(command):
    """Runs a shell command and returns its stdout, stderr, and exit code."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    return result.stdout.strip(), result.stderr.strip(), result.returncode

def dismiss_stale_reviews():
    """Find and dismiss any previous 'Changes Requested' reviews from this bot."""
    print("Checking for stale reviews to dismiss...")
    reviews = pr.get_reviews()
    for review in reviews:
        if review.user.login == BOT_USERNAME and review.state == "CHANGES_REQUESTED":
            if BOT_REVIEW_TAG in review.body:
                print(f"Dismissing stale PriestyBot review {review.id}...")
                try:
                    review.dismiss("Conflicts have been updated or resolved.")
                except Exception as e:
                    print(f"Failed to dismiss review {review.id}: {e}")

def parse_conflicts_and_patch_lines(file_path, patch_content):
    """
    Parses a file with git conflict markers and its corresponding patch content
    to return a list of conflicts with their content and their line numbers
    relative to the patch.
    """
    conflicts = []
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            file_lines = f.readlines()
    except Exception as e:
        print(f"Could not read file {file_path}: {e}")
        return []

    patch_lines = patch_content.splitlines()

    in_conflict, is_ours_section = False, True
    current_conflict = {}
    
    # Iterate through the file content to find conflict markers
    # and map them to the patch lines.
    for i, file_line in enumerate(file_lines):
        file_line_number = i + 1

        if file_line.startswith('<<<<<<<'):
            in_conflict = True
            is_ours_section = True
            current_conflict = {
                'start_file_line': file_line_number, 
                'ours': [], 
                'theirs': [], 
                'patch_line_for_ours_content': -1 # New field to store the patch line for the first 'ours' content
            }
            # We will find the patch_line_for_ours_content after parsing the 'ours' block
        elif file_line.startswith('=======') and in_conflict:
            is_ours_section = False
        elif file_line.startswith('>>>>>>>') and in_conflict:
            current_conflict['end_file_line'] = file_line_number
            conflicts.append(current_conflict)
            in_conflict = False
        elif in_conflict:
            if is_ours_section:
                current_conflict['ours'].append(file_line)
                # If this is the first line of 'ours' content, try to find it in the patch
                if len(current_conflict['ours']) == 1:
                    # Search for this exact line in the patch to get its 0-indexed patch line number
                    for p_idx, p_line in enumerate(patch_lines):
                        # Use .strip() for robust comparison, as patch lines might have leading +/-
                        if p_line.strip().lstrip('+-') == file_line.strip():
                            current_conflict['patch_line_for_ours_content'] = p_idx
                            break
            else:
                current_conflict['theirs'].append(file_line)
    
    return conflicts

# --- Main Bot Logic ---
def main():
    try:
        print(f"PriestyBot starting conflict resolution for PR #{PR_NUMBER}...")
        run_command(f'git config user.name "{BOT_USERNAME}"')
        run_command(f'git config user.email "{BOT_USERNAME}@users.noreply.github.com"')
        run_command("git fetch origin")

        dismiss_stale_reviews()

        print(f"Attempting to merge 'origin/{BASE_BRANCH}' into '{HEAD_BRANCH}'...")
        # THIS IS WHERE `merge_stderr` GETS ITS VALUE
        _, merge_stderr, returncode = run_command(f"git merge origin/{BASE_BRANCH} --no-commit --no-ff")

        if returncode == 0:
            print("✅ No merge conflicts found. Aborting test merge and exiting.")
            run_command("git merge --abort")
            print("::set-output name=status::no_conflicts") # Output status for YAML
            return

        print("❌ Merge conflicts detected. Parsing details...")
        stdout, _, _ = run_command("git diff --name-only --diff-filter=U")
        conflicted_files_list = [f for f in stdout.split('\n') if f]

        # Get PR files to access their patches
        pr_files = pr.get_files()
        pr_file_patches = {f.filename: f.patch for f in pr_files}

        all_parsed_conflicts = []
        for file_path in conflicted_files_list:
            patch_content = pr_file_patches.get(file_path)
            if not patch_content:
                print(f"Warning: Could not find patch content for conflicted file {file_path}. Skipping.")
                continue
                
            parsed_conflicts_for_file = parse_conflicts_and_patch_lines(file_path, patch_content)
            for conflict in parsed_conflicts_for_file:
                # Only include conflicts for which we found the patch line for 'ours' content
                if conflict['patch_line_for_ours_content'] != -1:
                    all_parsed_conflicts.append({'file': file_path, **conflict})
                else:
                    print(f"Warning: Could not map conflict in {file_path} to patch lines. Skipping inline comment for this conflict.")

        run_command("git merge --abort")

        if not all_parsed_conflicts:
            print("Merge command failed, but no standard text conflicts were parseable or mappable to diff lines.")
            fallback_body = f"""
{BOT_REVIEW_TAG}
### 🤖 PriestyBot detected a Merge Conflict

I was unable to merge the base branch `{BASE_BRANCH}` due to a conflict. This can happen with conflicts in binary files or other complex scenarios, or if I couldn't precisely map the conflict to the Pull Request's diff.

Please resolve the conflicts manually using the command line.

<details>
<summary><strong>Raw Git Merge Log</strong></summary>

```
{merge_stderr}
```
</details>
"""
            pr.create_issue_comment(fallback_body.strip())
            print("::set-output name=status::error") # Output status for YAML
            return

        review_comments = []
        for conflict in all_parsed_conflicts:
            # Use the patch_line_for_ours_content as the 'line' for the comment.
            # This points to the first line of the 'ours' content within the diff.
            comment_positioning = {
                "path": conflict['file'],
                "line": conflict['patch_line_for_ours_content'], # This is the 0-indexed line within the diff hunk
                "side": "RIGHT" # Commenting on the head branch's view of the file
            }

            # Ensure suggestions are not empty, as empty suggestions can cause API errors
            ours_suggestion_body = ''.join(conflict['ours'])
            theirs_suggestion_body = ''.join(conflict['theirs'])

            if ours_suggestion_body.strip(): # Only add if there's actual content
                ours_suggestion = f"```suggestion\n{ours_suggestion_body}```"
                review_comments.append({
                    **comment_positioning,
                    "body": f"**Option 1: Keep changes from this PR (`ours`)**\n\n{ours_suggestion}"
                })

            if theirs_suggestion_body.strip(): # Only add if there's actual content
                theirs_suggestion = f"```suggestion\n{theirs_suggestion_body}```"
                review_comments.append({
                    **comment_positioning,
                    "body": f"**Option 2: Accept changes from `{BASE_BRANCH}` (`theirs`)**\n\n{theirs_suggestion}"
                })
        
        # Check if there are any comments to submit after filtering empty suggestions
        if not review_comments:
            print("No valid comments could be generated for the detected conflicts after patch mapping. Posting a general comment instead.")
            fallback_body = f"""
{BOT_REVIEW_TAG}
### 🤖 PriestyBot detected a Merge Conflict

I found **{len(conflicted_files_list)} file(s)** with conflicts, but I couldn't generate specific inline suggestions. This might be due to complex conflict patterns or an inability to precisely map the conflict to the Pull Request's diff.

Please resolve the conflicts manually using the command line.

<details>
<summary><strong>Raw Git Merge Log (for debugging)</strong></summary>

```
{merge_stderr}
```
</details>
"""
            pr.create_issue_comment(fallback_body.strip())
            print("::set-output name=status::error") # Output status for YAML
            return

        summary_body = f"""
{BOT_REVIEW_TAG}
### 🤖 PriestyBot detected a Merge Conflict

I found **{len(all_parsed_conflicts)} conflict(s)** in **{len(conflicted_files_list)} file(s)**.

To resolve, please review the files and click **Commit suggestion** on the version you want to keep. Once all conflicts are resolved, I will automatically dismiss this review.

<details>
<summary><strong>Alternative: Resolve Manually via Command Line</strong></summary>

If you prefer to fix this locally:
1.  Pull the base branch into your feature branch: `git pull origin {BASE_BRANCH}`
2.  Manually edit the files marked with `<<<<<<<` to resolve the conflicts.
3.  Add, commit, and push your changes: `git add .`, `git commit`, `git push`

</details>

<details>
<summary><strong>Raw Git Merge Log (for debugging)</strong></summary>

```
{merge_stderr}
```
</details>
"""

        print("Submitting 'Changes Requested' review with suggestions...")
        pr.create_review(
            body=summary_body.strip(),
            event="REQUEST_CHANGES",
            comments=review_comments
        )
        print("✅ Review submitted successfully.")
        print("::set-output name=status::conflicts_posted") # Output status for YAML

    except Exception as e:
        print(f"An unexpected error occurred in the conflict resolver: {e}")
        print("::set-output name=status::error") # Output status for YAML
        # Optionally, post a general error comment to the PR if the script crashes before creating a review
        try:
            pr.create_issue_comment(f"""
{BOT_REVIEW_TAG}
### ❌ PriestyBot Error

I encountered an unexpected error while trying to process merge conflicts for this PR. My apologies!

Please check the workflow run logs for details. You will need to resolve any conflicts manually.

Error details: `{e}`
""")
        except Exception as comment_e:
            print(f"Failed to post error comment to PR: {comment_e}")


if __name__ == "__main__":
    main()
